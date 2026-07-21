from dataclasses import dataclass
from typing import TYPE_CHECKING

from songtools.layers import Layer
from songtools.transports import export as _export
from songtools.transports import play
from songtools.types import Event

if TYPE_CHECKING:
    from pathlib import Path

    from songtools.sounds import Sound
    from songtools.types import Effect


@dataclass(frozen=True, slots=True)
class Tune:
    sounds: tuple[Sound, ...]

    @property
    def beats(self) -> int:
        """The number of beats this tune spans; each slot is one beat."""
        return len(self.sounds)

    def compile(self) -> list[Event]:
        """Flatten this tune into events."""
        return [Event(float(beat), sound) for beat, sound in enumerate(self.sounds)]

    def play(self, bpm: float = 120) -> None:
        """Play this tune at `bpm` through the default audio device."""
        play(self, bpm)

    def export(self, path: Path, bpm: float = 120) -> None:
        """Export this tune at `bpm` to a wav file at `path`."""
        _export(self, bpm, path)

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
        """Play two tunes at the same time using the & operator."""
        return Layer((self, other))

    def __matmul__(self, other: Effect) -> Tune:
        """Apply the specified `Effect` to this tune."""
        return self.with_effect(other)
