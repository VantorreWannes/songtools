import math
from array import array
from dataclasses import dataclass
from enum import Enum, IntEnum
from types import SimpleNamespace
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import timedelta

Buffer = array[float]
SILENCE = Buffer("f", [0.0])
SAMPLE_RATE = 48000


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
        constant = 1.0 / (self.duration.seconds * SAMPLE_RATE)
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
        length = max(1, int(len(buffer) / SAMPLE_RATE))
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


class Instrument(SimpleNamespace): ...
