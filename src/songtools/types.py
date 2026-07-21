import math
from array import array
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import timedelta

    from songtools.sounds import Sound

Buffer = array[float]
SILENCE = Buffer("f", [0.0])
SAMPLE_RATE = 48000


@dataclass(frozen=True, slots=True)
class Event:
    beat: float
    sound: Sound

    def shifted(self, beats: float) -> Event:
        return Event(self.beat + beats, self.sound)


class KeyRoot(IntEnum):
    C = 0
    Cs = 1
    D = 2
    Ds = 3
    E = 4
    F = 5
    Fs = 6
    G = 7
    Gs = 8
    A = 9
    As = 10
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

    def _wrap(self, steps: int) -> Degree:
        return Degree((self + steps) % len(type(self)))

    def up(self, steps: int) -> Degree:
        return self._wrap(steps)

    def down(self, steps: int) -> Degree:
        return self._wrap(-steps)


Chord = Degree


@runtime_checkable
class Effect(Protocol):
    def apply(self, buffer: Buffer) -> Buffer: ...


@dataclass(frozen=True, slots=True)
class Gain:
    amount: float

    def apply(self, buffer: Buffer) -> Buffer:
        return Buffer("f", (s * self.amount for s in buffer))


@dataclass(frozen=True, slots=True)
class Decay:
    duration: timedelta

    def apply(self, buffer: Buffer) -> Buffer:
        constant = 1.0 / (self.duration.total_seconds() * SAMPLE_RATE)
        return Buffer("f", (s * math.exp(-i * constant) for i, s in enumerate(buffer)))


@dataclass(frozen=True, slots=True)
class LowPass:
    hertz: float

    def apply(self, buffer: Buffer) -> Buffer:
        alpha = 1.0 - math.exp(-math.tau * self.hertz / SAMPLE_RATE)
        state = 0.0
        output = SILENCE * len(buffer)
        for index, sample in enumerate(buffer):
            state += alpha * (sample - state)
            output[index] = state
        return output


@dataclass(frozen=True, slots=True)
class Mix:
    buffers: tuple[Buffer, ...]

    def apply(self, buffer: Buffer) -> Buffer:
        buffers = (buffer, *self.buffers)
        length = min(len(b) for b in buffers)
        return Buffer(
            "f", (sum(b[i] for b in buffers) / len(buffers) for i in range(length))
        )


@dataclass(frozen=True, slots=True)
class ReSample:
    rate: float

    def apply(self, buffer: Buffer) -> Buffer:
        length = max(1, int(len(buffer) / self.rate))
        last = len(buffer) - 1
        output = SILENCE * length
        for i in range(length):
            pos = i * self.rate
            j = int(pos)
            if j < last:
                output[i] = buffer[j] + (buffer[j + 1] - buffer[j]) * (pos - j)
        return output


@dataclass(frozen=True, slots=True)
class Pitch:
    midi: float

    def apply(self, buffer: Buffer) -> Buffer:
        rate = 2 ** ((self.midi - 60) / 12)
        return ReSample(rate=rate).apply(buffer)


@dataclass(frozen=True, slots=True)
class Gate:
    seconds: float

    def apply(self, buffer: Buffer) -> Buffer:
        return buffer[: int(self.seconds * SAMPLE_RATE)]


@dataclass(frozen=True, slots=True)
class Reverse:
    def apply(self, buffer: Buffer) -> Buffer:
        return Buffer("f", reversed(buffer))


@dataclass(frozen=True, slots=True)
class Echo:
    seconds: float

    def apply(self, buffer: Buffer) -> Buffer:
        delay = int(self.seconds * SAMPLE_RATE)
        output = SILENCE * (len(buffer) + delay)
        output[: len(buffer)] = buffer
        for index, sample in enumerate(buffer):
            output[delay + index] += sample / 2
        return output


@dataclass(frozen=True, slots=True)
class Drive:
    amount: float

    def apply(self, buffer: Buffer) -> Buffer:
        norm = math.tanh(self.amount)
        return Buffer("f", (math.tanh(s * self.amount) / norm for s in buffer))


@dataclass(frozen=True, slots=True)
class Humanize:
    velocity: float

    def apply(self, buffer: Buffer) -> Buffer:
        gain = 1.0 + self.velocity * math.tanh(math.sin(sum(buffer)))
        return Buffer("f", (s * gain for s in buffer))
