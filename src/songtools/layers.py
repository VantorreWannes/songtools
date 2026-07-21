import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from songtools.transports import export, play

if TYPE_CHECKING:
    from pathlib import Path

    from songtools.tunes import Tune
    from songtools.types import Effect, Event


@dataclass(frozen=True, slots=True)
class Layer:
    tunes: tuple[Tune | Layer, ...]
    shift: float

    @property
    def beats(self) -> int:
        return math.lcm(*(tune.beats for tune in self.tunes))

    def shifted(self, beats: float) -> Layer:
        return Layer(self.tunes, self.shift + beats)

    def compile(self) -> list[Event]:
        events = [
            event.shifted(loop * tune.beats + self.shift)
            for tune in self.tunes
            for loop in range(self.beats // tune.beats)
            for event in tune.compile()
        ]
        return sorted(events, key=lambda event: event.beat)

    def play(self, beats_per_minute: float) -> None:
        play(self, beats_per_minute)

    def export(self, path: Path, bpm: float) -> None:
        export(self, bpm, path)

    def with_effect(self, effect: Effect) -> Layer:
        tunes = tuple(tune.with_effect(effect) for tune in self.tunes)
        return Layer(tunes, self.shift)

    def __add__(self, other: Layer) -> Layer:
        """Concatenate two layers together using the + operator."""
        return Layer(self.tunes + other.tunes, self.shift + other.shift)

    def __mul__(self, amount: int) -> Layer:
        """Repeat a layer `n` times, end to end."""
        repeated = tuple(
            tune.shifted(rep * self.beats)
            for rep in range(amount)
            for tune in self.tunes
        )
        return Layer(repeated, self.shift)

    def __and__(self, other: Tune | Layer) -> Layer:
        """Combine two layers together using the & operator."""
        if isinstance(other, Layer):
            return Layer(self.tunes + other.tunes, self.shift + other.shift)
        return Layer((*self.tunes, other), self.shift)

    def __matmul__(self, other: Effect) -> Layer:
        """Apply the specified `Effect` to this layer."""
        return self.with_effect(other)
