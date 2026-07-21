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
    tunes: tuple[Tune, ...]

    @property
    def beats(self) -> int:
        return math.lcm(*(tune.beats for tune in self.tunes))

    def compile(self) -> list[Event]:
        events = [
            event.shifted(loop * tune.beats)
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
        return Layer(tunes)

    def __add__(self, other: Layer) -> Layer:
        """Concatenate two layers together using the + operator."""
        return Layer(self.tunes + other.tunes)

    def __mul__(self, amount: int) -> Layer:
        """Duplicate a layer `n` times."""
        return Layer(self.tunes * amount)

    def __and__(self, other: Layer) -> Layer:
        """Combine two layers together using the & operator."""
        return Layer(self.tunes + other.tunes)

    def __matmul__(self, other: Effect) -> Layer:
        """Apply the specified `Effect` to this layer."""
        return self.with_effect(other)
