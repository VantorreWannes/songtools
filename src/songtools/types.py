import math
from array import array
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import timedelta

Buffer = array[float]
SILENCE = Buffer("f", [0.0])
SAMPLE_RATE = 48000


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
