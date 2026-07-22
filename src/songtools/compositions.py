from __future__ import annotations

import math
from array import array
from dataclasses import dataclass
from typing import overload

import sounddevice

from songtools.keys import Key
from songtools.transports import mixdown
from songtools.types import (
    SAMPLE_RATE,
    SILENCE,
    Buffer,
    Chord,
    Effect,
    Event,
    Mix,
    Pitch,
)


class Composition:
    @property
    def beats(self) -> float:
        raise NotImplementedError

    def events(self, span: float) -> list[Event]:
        raise NotImplementedError

    def with_effect(self, effect: Effect) -> Composition:
        raise NotImplementedError

    def compile(self, beats_per_minute: float) -> Sound:
        buffer = mixdown(
            self.events(float(self.beats)), int(self.beats), beats_per_minute
        )
        return Sound(buffer, Pitch(60))

    def shifted(self, beats: float) -> Shifted:
        return Shifted(self, beats)

    def __add__(self, other: Composition) -> Composition:
        if isinstance(self, Tune) and isinstance(other, Tune):
            return Tune(*self.sounds, *other.sounds)
        if isinstance(self, Tune):
            return Tune(*self.sounds, other)
        if isinstance(other, Tune):
            return Tune(self, *other.sounds)
        return Tune(self, other)

    def __mul__(self, amount: int) -> Composition:
        if isinstance(self, Tune):
            return Tune(*(self.sounds * amount))
        return Tune(*(self for _ in range(amount)))

    def __matmul__(self, other: Effect) -> Composition:
        if isinstance(other, Effect):
            return self.with_effect(other)
        return NotImplemented


@dataclass(frozen=True, slots=True)
class Sound(Composition):
    buffer: Buffer
    tuned_at: Pitch

    @property
    def beats(self) -> float:
        return 1.0

    def events(self, span: float) -> list[Event]:
        _ = span
        return [Event(0.0, self)]

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
        shift = 60 + key.root - self.tuned_at.midi
        return KeyedSound(Pitch(60 + shift).apply(self.buffer), key.note(0), key)

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
        mix = Mix(*harmony)
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

    def events(self, span: float) -> list[Event]:
        _ = span
        return []


REST = Rest()


@dataclass(slots=True)
class Shifted(Composition):
    item: Composition
    shift: float

    @property
    def beats(self) -> float:
        return self.item.beats

    def events(self, span: float) -> list[Event]:
        scale = span / self.beats
        return [event.shifted(self.shift * scale) for event in self.item.events(span)]

    def with_effect(self, effect: Effect) -> Shifted:
        return Shifted(self.item.with_effect(effect), self.shift)

    def __mul__(self, amount: int) -> Shifted:
        return Shifted(self.item * amount, self.shift)


@dataclass(slots=True)
class Layer(Composition):
    tunes: tuple[Composition, ...]

    def __init__(self, *tunes: Composition) -> None:
        self.tunes = tuple(tunes)

    @property
    def beats(self) -> float:
        return float(math.lcm(*(int(tune.beats) for tune in self.tunes)))

    def events(self, span: float) -> list[Event]:
        scale = span / self.beats
        events = [
            event.shifted(loop * tune.beats * scale)
            for tune in self.tunes
            for loop in range(int(self.beats // tune.beats))
            for event in tune.events(scale * tune.beats)
        ]
        return sorted(events, key=lambda event: event.beat)

    def with_effect(self, effect: Effect) -> Layer:
        return Layer(*(tune.with_effect(effect) for tune in self.tunes))

    def __mul__(self, amount: int) -> Layer:
        return Layer(*(tune * amount for tune in self.tunes))


@dataclass(slots=True)
class Tune(Composition):
    sounds: tuple[Composition, ...]

    def __init__(self, *sounds: Composition) -> None:
        self.sounds = tuple(sounds)

    @property
    def beats(self) -> float:
        return float(len(self.sounds))

    def events(self, span: float) -> list[Event]:
        slot_beats = span / len(self.sounds)
        return [
            event.shifted(index * slot_beats)
            for index, slot in enumerate(self.sounds)
            for event in slot.events(slot_beats)
        ]

    def every(self, beats: int) -> Tune:
        stretched = [
            slot for sound in self.sounds for slot in (sound, *((REST,) * (beats - 1)))
        ]
        return Tune(*stretched)

    def with_effect(self, effect: Effect) -> Tune:
        return Tune(*(slot.with_effect(effect) for slot in self.sounds))
