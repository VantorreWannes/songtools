"""Audio buffers, effects, and simple sequencing helpers."""

from __future__ import annotations

import math
import sys
import wave
from array import array
from dataclasses import dataclass
from enum import Enum, IntEnum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import sounddevice

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from datetime import timedelta


SAMPLE_RATE = 44100
C4_FREQ = 261.63


def _zeros(length: int) -> array[float]:
    return array("d", bytes(length * 8))


def _as_doubles(samples: Iterable[float]) -> array[float]:
    return array("d", samples)


@runtime_checkable
class Effect(Protocol):
    def apply(self, buffer: Buffer) -> Buffer: ...


@dataclass(frozen=True, slots=True)
class Buffer:
    """A thin wrapper around a float32 sample array.

    Note: although the dataclass is frozen, the wrapped array is mutable
    (``__setitem__``/``__delitem__`` mutate it in place, returning None).
    """

    array: array[float]

    @classmethod
    def from_data(cls, data: Iterable[float]) -> Buffer:
        return cls(array("f", data))

    def apply_effect(self, effect: Effect) -> Buffer:
        return effect.apply(self)

    def __getitem__(self, key: int | slice) -> float | Buffer:
        if isinstance(key, slice):
            return Buffer(self.array[key])
        return self.array[key]

    def __setitem__(self, key: int, value: float) -> None:
        self.array[key] = value

    def __delitem__(self, key: int | slice) -> None:
        del self.array[key]

    def __iter__(self) -> Iterator[float]:
        return iter(self.array)

    def __len__(self) -> int:
        return len(self.array)

    def __add__(self, other: Buffer) -> Buffer:
        return Buffer.from_data(self.array + other.array)

    def __mul__(self, count: int) -> Buffer:
        if count < 0:
            msg = "count must be non-negative"
            raise ValueError(msg)
        return Buffer.from_data(self.array * count)

    def __repr__(self) -> str:
        return f"Buffer({len(self)} samples)"


class KeyRoot(IntEnum):
    C = 0
    CS = 1
    D = 2
    DS = 3
    E = 4
    F = 5
    FS = 6
    G = 7
    GS = 8
    A = 9
    AS = 10
    B = 11


class Scale(Enum):
    MAJOR = (0, 2, 4, 5, 7, 9, 11)
    MINOR = (0, 2, 3, 5, 7, 8, 10)
    DORIAN = (0, 2, 3, 5, 7, 9, 10)


class Quality(Enum):
    TRIAD = (0, 2, 4)
    SEVENTH = (0, 2, 4, 6)
    NINTH = (0, 2, 4, 6, 8)
    SUS2 = (0, 1, 4)
    SUS4 = (0, 3, 4)
    POWER = (0, 4)


class Degree(IntEnum):
    I = 0  # noqa: E741
    II = 1
    III = 2
    IV = 3
    V = 4
    VI = 5
    VII = 6

    def up(self, steps: int) -> int:
        return int(self) + steps

    def down(self, steps: int) -> int:
        return int(self) - steps


Chord = Degree


@dataclass(frozen=True, slots=True)
class Key:
    root: KeyRoot
    scale: Scale = Scale.MAJOR
    quality: Quality = Quality.TRIAD

    def note(self, degree: Degree) -> Pitch:
        octv, idx = divmod(degree, len(self.scale.value))
        return Pitch(60 + self.root + self.scale.value[idx] + 12 * octv)

    def notes(self, chord: Chord) -> tuple[Pitch, ...]:
        return tuple(self.note(Chord(chord + step)) for step in self.quality.value)


@dataclass(frozen=True, slots=True)
class Gain:
    """Multiplies every sample by ``amount``."""

    amount: float

    def apply(self, buffer: Buffer) -> Buffer:
        if self.amount == 1.0:
            return buffer
        return Buffer.from_data(s * self.amount for s in buffer)


@dataclass(frozen=True, slots=True)
class Decay:
    """Exponential decay envelope with the given time constant."""

    time: timedelta

    def apply(self, buffer: Buffer) -> Buffer:
        seconds = self.time.total_seconds()
        if seconds <= 0:
            msg = "Decay time must be positive"
            raise ValueError(msg)
        decay = math.exp(-1.0 / (seconds * SAMPLE_RATE))
        gain = 1.0
        output = _zeros(len(buffer))
        for i, sample in enumerate(buffer.array):
            output[i] = sample * gain
            gain *= decay
        return Buffer.from_data(output)


@dataclass(frozen=True, slots=True)
class LowPass:
    hertz: float

    def apply(self, buffer: Buffer) -> Buffer:
        if self.hertz <= 0:
            msg = "Cutoff frequency must be positive"
            raise ValueError(msg)
        alpha = 1.0 - math.exp(-math.tau * self.hertz / SAMPLE_RATE)
        beta = 1.0 - alpha
        state = 0.0
        output = _zeros(len(buffer))
        for i, sample in enumerate(buffer.array):
            state = alpha * sample + beta * state
            output[i] = state
        return Buffer.from_data(output)


@dataclass(frozen=True, slots=True)
class Mix:
    buffers: tuple[Buffer, ...]

    def __init__(self, *buffers: Buffer | tuple[Buffer, ...]) -> None:
        if len(buffers) == 1 and isinstance(buffers[0], tuple):
            buffers = buffers[0]
        object.__setattr__(self, "buffers", tuple(buffers))

    def apply(self, buffer: Buffer) -> Buffer:
        arrays = [buffer.array, *(b.array for b in self.buffers)]
        length = min(len(a) for a in arrays)
        gain = 1.0 / len(arrays)
        trimmed = [a[:length] for a in arrays]
        return Buffer.from_data(
            math.fsum(samples) * gain for samples in zip(*trimmed, strict=True)
        )


@dataclass(frozen=True, slots=True)
class ReSample:
    rate: float

    def apply(self, buffer: Buffer) -> Buffer:
        if self.rate <= 0:
            msg = "Resample rate must be positive"
            raise ValueError(msg)
        if len(buffer) == 0:
            return buffer
        source = buffer
        if self.rate > 1:
            # Anti-alias before downsampling (4 cascaded one-pole filters).
            lowpass = LowPass(SAMPLE_RATE / (2 * self.rate))
            for _ in range(4):
                source = lowpass.apply(source)
        samples = source.array
        last = len(samples) - 1
        length = max(1, int(len(samples) / self.rate))
        output = _zeros(length)
        position = 0.0
        for i in range(length):
            j = int(position)
            if j >= last:
                output[i] = samples[last]
            else:
                fraction = position - j
                output[i] = samples[j] + (samples[j + 1] - samples[j]) * fraction
            position += self.rate
        return Buffer.from_data(output)


@dataclass(frozen=True, slots=True)
class Pitch:
    """Sampler-style pitch shift; midi=60 keeps the original pitch."""

    midi: float

    def apply(self, buffer: Buffer) -> Buffer:
        rate = 2 ** ((self.midi - 60) / 12)
        return ReSample(rate).apply(buffer)


@dataclass(frozen=True, slots=True)
class Gate:
    cutoff: timedelta

    def apply(self, buffer: Buffer) -> Buffer:
        stop = max(0, int(self.cutoff.total_seconds() * SAMPLE_RATE))
        return Buffer.from_data(buffer.array[:stop])


@dataclass(frozen=True, slots=True)
class Reverse:
    def apply(self, buffer: Buffer) -> Buffer:
        return Buffer.from_data(buffer.array[::-1])


@dataclass(frozen=True, slots=True)
class Echo:
    duration: timedelta
    decay: float = 0.5

    def apply(self, buffer: Buffer) -> Buffer:
        delay = int(self.duration.total_seconds() * SAMPLE_RATE)
        if delay <= 0:
            return buffer
        dry = _as_doubles(buffer.array)
        output = _zeros(len(buffer) + delay)
        output[: len(dry)] = dry
        for i, sample in enumerate(dry):
            output[delay + i] += sample * self.decay
        return Buffer.from_data(output)


@dataclass(frozen=True, slots=True)
class Drive:
    amount: float

    def apply(self, buffer: Buffer) -> Buffer:
        norm = math.tanh(self.amount)
        if norm == 0.0:
            return buffer
        return Buffer.from_data(math.tanh(s * self.amount) / norm for s in buffer.array)


@dataclass(frozen=True, slots=True)
class Humanize:
    velocity: float

    def apply(self, buffer: Buffer) -> Buffer:
        gain = 1.0 + self.velocity * math.tanh(math.sin(math.fsum(buffer.array)))
        return Buffer.from_data(s * gain for s in buffer)


@dataclass(frozen=True, slots=True)
class HighPass:
    hertz: float

    def apply(self, buffer: Buffer) -> Buffer:
        if self.hertz <= 0:
            msg = "Cutoff frequency must be positive"
            raise ValueError(msg)
        rc = 1.0 / (math.tau * self.hertz)
        alpha = rc / (rc + 1.0 / SAMPLE_RATE)
        state = 0.0
        previous = 0.0
        output = _zeros(len(buffer))
        for i, sample in enumerate(buffer.array):
            state = alpha * (state + sample - previous)
            previous = sample
            output[i] = state
        return Buffer.from_data(output)


@dataclass(frozen=True, slots=True)
class FadeIn:
    duration: timedelta

    def apply(self, buffer: Buffer) -> Buffer:
        length = min(len(buffer), int(self.duration.total_seconds() * SAMPLE_RATE))
        if length <= 0:
            return buffer
        output = _as_doubles(buffer.array)
        step = 1.0 / max(1, length - 1)
        for i in range(length):
            output[i] *= i * step
        return Buffer.from_data(output)


@dataclass(frozen=True, slots=True)
class FadeOut:
    duration: timedelta

    def apply(self, buffer: Buffer) -> Buffer:
        length = min(len(buffer), int(self.duration.total_seconds() * SAMPLE_RATE))
        if length <= 0:
            return buffer
        output = _as_doubles(buffer.array)
        step = 1.0 / max(1, length - 1)
        end = len(output)
        for i in range(length):
            output[end - length + i] *= 1.0 - i * step
        return Buffer.from_data(output)


@dataclass(frozen=True, slots=True)
class Delay:
    time: timedelta
    feedback: float
    mix: float

    def apply(self, buffer: Buffer) -> Buffer:
        delay = int(self.time.total_seconds() * SAMPLE_RATE)
        if delay <= 0:
            return buffer
        feedback = min(max(self.feedback, 0.0), 0.95)
        mix = min(max(self.mix, 0.0), 1.0)
        length = len(buffer) + delay
        wet = _zeros(length)
        wet[: len(buffer)] = _as_doubles(buffer.array)
        for i in range(delay, length):
            wet[i] += wet[i - delay] * feedback
        dry = buffer.array
        dry_len = len(dry)
        return Buffer.from_data(
            (1.0 - mix) * (dry[i] if i < dry_len else 0.0) + mix * wet[i]
            for i in range(length)
        )


@dataclass(frozen=True, slots=True)
class Normalize:
    peak: float

    def apply(self, buffer: Buffer) -> Buffer:
        loudest = max((abs(s) for s in buffer), default=0.0)
        if loudest == 0.0:
            return buffer
        gain = abs(self.peak) / loudest
        return Buffer.from_data(s * gain for s in buffer)


@dataclass(frozen=True, slots=True)
class Clip:
    threshold: float

    def apply(self, buffer: Buffer) -> Buffer:
        limit = abs(self.threshold)
        return Buffer.from_data(max(-limit, min(limit, s)) for s in buffer)


@dataclass(frozen=True, slots=True)
class Tremolo:
    hertz: float
    depth: float

    def apply(self, buffer: Buffer) -> Buffer:
        depth = min(max(self.depth, 0.0), 1.0)
        step = math.tau * self.hertz / SAMPLE_RATE
        return Buffer.from_data(
            s * (1.0 - depth * (0.5 + 0.5 * math.sin(i * step)))
            for i, s in enumerate(buffer.array)
        )


@dataclass(frozen=True, slots=True)
class BitCrush:
    bits: int

    def apply(self, buffer: Buffer) -> Buffer:
        steps = (1 << min(max(self.bits, 1), 24)) - 1
        return Buffer.from_data(round(s * steps) / steps for s in buffer)


class Sound:
    def __init__(
        self,
        samples: Buffer,
        sample_rate: int = SAMPLE_RATE,
        base_frequency: float = C4_FREQ,
        key: Key | None = None,
    ) -> None:
        self.samples = samples
        self.sample_rate = sample_rate
        self.base_frequency = base_frequency
        self.key = key

    @property
    def duration(self) -> float:
        return len(self.samples) / self.sample_rate

    @classmethod
    def silence(cls, sample_count: int, sample_rate: int = SAMPLE_RATE) -> Sound:
        return cls(Buffer.from_data([0.0] * sample_count), sample_rate)

    @classmethod
    def tone(
        cls, frequency: float, sample_count: int, sample_rate: int = SAMPLE_RATE
    ) -> Sound:
        return cls(
            Buffer.from_data(
                math.sin(math.tau * frequency * i / sample_rate)
                for i in range(sample_count)
            ),
            sample_rate,
            base_frequency=frequency,
        )

    @classmethod
    def sequence(
        cls,
        *items: Sound | None,
        bpm: float = 120.0,
        sample_rate: int = SAMPLE_RATE,
    ) -> Sound:
        beat_samples = round(60.0 / bpm * sample_rate)
        rest = cls.silence(beat_samples, sample_rate).samples
        buffer = Buffer.from_data([])

        for item in items:
            if item is None:
                buffer = buffer + rest
            else:
                if item.sample_rate != sample_rate:
                    msg = f"Sample rate mismatch: {item.sample_rate} != {sample_rate}"
                    raise ValueError(msg)

                item_samples = item.samples.array
                if len(item_samples) >= beat_samples:
                    slot_buffer = Buffer.from_data(item_samples[:beat_samples])
                else:
                    padded = _zeros(beat_samples)
                    padded[: len(item_samples)] = _as_doubles(item_samples)
                    slot_buffer = Buffer.from_data(padded)

                buffer = buffer + slot_buffer

        return cls(buffer, sample_rate)

    def _check_compatible(self, other: Sound) -> None:
        if self.sample_rate != other.sample_rate:
            msg = f"Sample rate mismatch: {self.sample_rate} != {other.sample_rate}"
            raise ValueError(msg)

    def __add__(self, other: Sound) -> Sound:
        self._check_compatible(other)
        return Sound(
            self.samples + other.samples,
            self.sample_rate,
            self.base_frequency,
            self.key,
        )

    def __mul__(self, count: int) -> Sound:
        return Sound(
            self.samples * count, self.sample_rate, self.base_frequency, self.key
        )

    def __and__(self, other: Sound) -> Sound:
        self._check_compatible(other)
        return Sound(
            Mix(other.samples).apply(self.samples),
            self.sample_rate,
            self.base_frequency,
            self.key,
        )

    def __matmul__(self, transform: Effect | Key | Degree) -> Sound:
        if isinstance(transform, Effect):
            return Sound(
                transform.apply(self.samples),
                self.sample_rate,
                self.base_frequency,
                self.key,
            )
        if isinstance(transform, Degree):
            return self @ self._pitch_for_degree(transform)

        if isinstance(transform, Key):
            return Sound(self.samples, self.sample_rate, self.base_frequency, transform)
        msg = f"Unsupported transform type: {type(transform).__name__}"
        raise TypeError(msg)

    def _pitch_for_degree(self, degree: Degree) -> Pitch:
        if self.key is None:
            msg = "Pitching by scale degree requires the Sound to have a key"
            raise ValueError(msg)
        scale = getattr(self.key, "scale", Scale.MAJOR)
        offsets = scale.value if isinstance(scale, Scale) else Scale[scale].value
        step = int(degree)
        semitones = offsets[step % 7] + 12 * (step // 7)
        return Pitch(midi=60 + semitones)

    def play(self) -> None:
        sounddevice.play(self.samples.array, samplerate=self.sample_rate)
        sounddevice.wait()


class WavFile:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def read(self) -> Sound:
        with wave.open(str(self.path), "rb") as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            supported_sample_widths = 2
            if sample_width != supported_sample_widths:
                msg = (
                    "Only 16-bit PCM WAV files are supported"
                    f"(got {sample_width * 8}-bit)"
                )
                raise ValueError(msg)
            sample_rate = wf.getframerate()
            raw = wf.readframes(wf.getnframes())
        pcm = array("h")
        pcm.frombytes(raw)
        if sys.byteorder != "little":
            pcm.byteswap()
        if channels > 1:
            pcm = array(
                "h",
                (
                    round(math.fsum(pcm[i : i + channels]) / channels)
                    for i in range(0, len(pcm) - channels + 1, channels)
                ),
            )
        return Sound(
            Buffer.from_data(s / 32768.0 for s in pcm), sample_rate=sample_rate
        )

    def write(self, sound: Sound) -> None:
        pcm = array("h", (int(max(-1.0, min(1.0, s)) * 32767) for s in sound.samples))
        if sys.byteorder != "little":
            pcm.byteswap()
        with wave.open(str(self.path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sound.sample_rate)
            wf.writeframes(pcm.tobytes())
