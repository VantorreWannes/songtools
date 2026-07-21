from dataclasses import dataclass
from typing import TYPE_CHECKING

from songtools.layers import Layer

if TYPE_CHECKING:
    from songtools.sounds import Sound
    from songtools.types import Effect


@dataclass(frozen=True, slots=True)
class Tune:
    sounds: tuple[Sound, ...]

    def with_effect(self, effect: Effect) -> Tune:
        sounds = tuple(sound.with_effect(effect) for sound in self.sounds)
        return Tune(sounds)

    def __add__(self, other: Tune) -> Tune:
        """Concatenate two tunes."""
        return Tune(self.sounds + other.sounds)

    def __mul__(self, amount: int) -> Tune:
        """Duplicate a tune `n` times."""
        return Tune(self.sounds * amount)

    def __and__(self, other: Tune) -> Layer:
        """Concatenate two tunes together using the & operator."""
        return Layer((self, other))

    def __matmul__(self, other: Effect) -> Tune:
        """Apply the specified `Effect` to this tune."""
        return self.with_effect(other)
