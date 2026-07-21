import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from songtools.sounds import Sound
from songtools.transports import mixdown
from songtools.types import Pitch

if TYPE_CHECKING:
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

    def events(self, span: float) -> list[Event]:
        scale = span / self.beats
        events = [
            event.shifted((loop * tune.beats + self.shift) * scale)
            for tune in self.tunes
            for loop in range(self.beats // tune.beats)
            for event in tune.events(scale * tune.beats)
        ]
        return sorted(events, key=lambda event: event.beat)

    def compile(self, beats_per_minute: float) -> Sound:
        buffer = mixdown(self.events(float(self.beats)), self.beats, beats_per_minute)
        return Sound(buffer, Pitch(60))

    def with_effect(self, effect: Effect) -> Layer:
        tunes = tuple(tune.with_effect(effect) for tune in self.tunes)
        return Layer(tunes, self.shift)

    def __add__(self, other: Layer) -> Layer:
        return Layer(self.tunes + other.tunes, self.shift + other.shift)

    def __mul__(self, amount: int) -> Layer:
        repeated = tuple(
            tune.shifted(rep * self.beats)
            for rep in range(amount)
            for tune in self.tunes
        )
        return Layer(repeated, self.shift)

    def __and__(self, other: Tune | Layer) -> Layer:
        if isinstance(other, Layer):
            return Layer(self.tunes + other.tunes, self.shift + other.shift)
        return Layer((*self.tunes, other), self.shift)

    def __matmul__(self, other: Effect) -> Layer:
        return self.with_effect(other)
