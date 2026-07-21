from dataclasses import dataclass
from typing import overload

from songtools.keys import Key
from songtools.types import Buffer, Chord, Effect, Mix


@dataclass(frozen=True, slots=True)
class Sound:
    buffer: Buffer

    def with_effect(self, effect: Effect) -> Sound:
        return Sound(effect.apply(self.buffer))

    def as_key(self, key: Key) -> KeyedSound:
        return KeyedSound(self.buffer, key)

    @overload
    def __matmul__(self, other: Key) -> KeyedSound: ...
    @overload
    def __matmul__(self, other: Effect) -> Sound: ...

    def __matmul__(self, other: Effect | Key) -> Sound | KeyedSound:
        """Apply the specified `Effect` to this sound."""
        if isinstance(other, Key):
            return self.as_key(other)
        if isinstance(other, Effect):
            return self.with_effect(other)
        message = (
            f"Cannot apply {other} of type {type(other)} to Sound. "
            "Expected an effect or key."
        )
        raise TypeError(message)


@dataclass(frozen=True, slots=True)
class KeyedSound(Sound):
    key: Key

    def with_effect(self, effect: Effect) -> KeyedSound:
        return KeyedSound(effect.apply(self.buffer), self.key)

    def as_key(self, key: Key) -> KeyedSound:
        return KeyedSound(self.buffer, key)

    def as_chord(self, chord: Chord) -> KeyedSound:
        root, *harmony = (pitch.apply(self.buffer) for pitch in self.key.notes(chord))
        mix = Mix(tuple(harmony))
        return KeyedSound(mix.apply(root), self.key)

    def __matmul__(self, other: Effect | Key | Chord) -> KeyedSound:
        """Apply the specified `Effect` to this sound."""
        if isinstance(other, Key):
            return self.as_key(other)
        if isinstance(other, Effect):
            return self.with_effect(other)
        if isinstance(other, Chord):
            return self.as_chord(other)
        raise TypeError(type(other))
