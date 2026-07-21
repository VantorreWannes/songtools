from array import array
from dataclasses import dataclass
from typing import overload

import sounddevice

from songtools.keys import Key
from songtools.types import SAMPLE_RATE, SILENCE, Buffer, Chord, Effect, Mix, Pitch


@dataclass(frozen=True, slots=True)
class Sound:
    buffer: Buffer
    tuned_at: Pitch

    def with_effect(self, effect: Effect) -> Sound:
        return Sound(effect.apply(self.buffer), self.tuned_at)

    def play(self) -> None:
        pcm = array("f", (max(-1.0, min(1.0, s)) for s in self.buffer)).tobytes()
        position = 0

        def callback(outdata: memoryview, frames: int, *_args: object) -> None:
            nonlocal position
            chunk = pcm[position : position + frames * 4]
            outdata[: len(chunk)] = chunk
            if len(chunk) < frames * 4:
                outdata[len(chunk) :] = b"\x00" * (frames * 4 - len(chunk))
                raise sounddevice.CallbackStop
            position += len(chunk)

        with sounddevice.RawOutputStream(
            SAMPLE_RATE, channels=1, dtype="float32", callback=callback
        ):
            sounddevice.sleep(int(len(self.buffer) / SAMPLE_RATE * 1000) + 200)

    def as_key(self, key: Key) -> KeyedSound:
        """Tune this sound to the root note of the given key."""
        shift = 60 + key.root - self.tuned_at.midi
        return KeyedSound(Pitch(60 + shift).apply(self.buffer), key.note(0), key)

    def compile(self) -> Sound:
        """Compile this sound into a `Sound` instance (identity)."""
        return Sound(self.buffer, self.tuned_at)

    @overload
    def __matmul__(self, other: Key) -> KeyedSound: ...
    @overload
    def __matmul__(self, other: Effect) -> Sound: ...
    def __matmul__(self, other: Effect | Key) -> Sound | KeyedSound:
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
        return KeyedSound(effect.apply(self.buffer), self.tuned_at, self.key)

    def as_key(self, key: Key) -> KeyedSound:
        shift = key.root - self.key.root
        return KeyedSound(Pitch(60 + shift).apply(self.buffer), key.note(0), key)

    def as_chord(self, chord: Chord) -> KeyedSound:
        root, *harmony = (pitch.apply(self.buffer) for pitch in self.key.steps(chord))
        mix = Mix(tuple(harmony))
        return KeyedSound(mix.apply(root), self.tuned_at, self.key)

    def __matmul__(self, other: Effect | Key | Chord) -> KeyedSound:
        if isinstance(other, Key):
            return self.as_key(other)
        if isinstance(other, Effect):
            return self.with_effect(other)
        if isinstance(other, Chord):
            return self.as_chord(other)
        raise TypeError(type(other))


class Rest(Sound):
    def __init__(self) -> None:
        super().__init__(SILENCE, Pitch(60))


REST = Rest()
