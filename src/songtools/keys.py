from dataclasses import dataclass
from typing import TYPE_CHECKING

from songtools.types import Degree, Pitch, Quality

if TYPE_CHECKING:
    from songtools.types import Chord, KeyRoot, Scale


@dataclass(frozen=True, slots=True)
class Key:
    root: KeyRoot
    scale: Scale
    quality: Quality

    def _midi(self, degree: int) -> int:
        octv, idx = divmod(degree, len(self.scale.value))
        return 60 + self.root + self.scale.value[idx] + 12 * octv

    def note(self, degree: Degree) -> Pitch:
        return Pitch(self._midi(degree))

    def notes(self, chord: Chord) -> tuple[Pitch, ...]:
        return tuple(Pitch(self._midi(chord + step)) for step in self.quality.value)
