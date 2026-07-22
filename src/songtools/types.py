import math
from array import array
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import timedelta

    from songtools.compositions import Sound


class Buffer(array[float]):
    def __hash__(self) -> int:
        return hash((len(self), self.tobytes()))

    def __mul__(self, n: int) -> Buffer:
        result = super().__mul__(n)
        return Buffer(result.typecode, list(result))

    __rmul__ = __mul__


def as_buffer(samples: array[float]) -> Buffer:
    if isinstance(samples, Buffer):
        return samples
    return Buffer(samples.typecode, list(samples))


def make_buffer(samples: Iterable[float]) -> Buffer:
    return cast("Buffer", Buffer("f", list(samples)))


SILENCE = make_buffer([0.0])
SAMPLE_RATE = 48000


@dataclass(frozen=True, slots=True)
class Event:
    beat: float
    sound: Sound


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

    def up(self, steps: int) -> int:
        """Scale steps up. May exceed the octave; Key resolves via divmod."""
        return int(self) + steps

    def down(self, steps: int) -> int:
        """Scale steps down. Negative values resolve to lower octaves."""
        return int(self) - steps


Chord = Degree


@runtime_checkable
class Effect(Protocol):
    def apply(self, buffer: Buffer) -> Buffer: ...


@dataclass(frozen=True, slots=True)
class Gain:
    amount: float

    def apply(self, buffer: Buffer) -> Buffer:
        if self.amount == 1.0:
            return buffer
        amount = self.amount
        return make_buffer(s * amount for s in buffer)


@dataclass(frozen=True, slots=True)
class Decay:
    duration: timedelta

    def apply(self, buffer: Buffer) -> Buffer:
        constant = 1.0 / (self.duration.total_seconds() * SAMPLE_RATE)
        decay = math.exp(-constant)
        gain = 1.0
        output = Buffer("f", bytes(len(buffer) * 4))
        for i, s in enumerate(buffer):
            output[i] = s * gain
            gain *= decay
        return make_buffer(output)


@dataclass(frozen=True, slots=True)
class LowPass:
    hertz: float

    def apply(self, buffer: Buffer) -> Buffer:
        alpha = 1.0 - math.exp(-math.tau * self.hertz / SAMPLE_RATE)
        beta = 1.0 - alpha
        state = 0.0
        output = Buffer("f", bytes(len(buffer) * 4))
        for index, sample in enumerate(buffer):
            state = alpha * sample + beta * state
            output[index] = state
        return make_buffer(output)


@dataclass(frozen=True, slots=True)
class Mix:
    buffers: tuple[Buffer, ...]

    def __init__(self, *buffers: Buffer) -> None:
        if len(buffers) == 1 and isinstance(buffers[0], tuple):
            buffers = buffers[0]
        object.__setattr__(self, "buffers", buffers)

    def apply(self, buffer: Buffer) -> Buffer:
        buffers = (buffer, *self.buffers)
        length = min(len(b) for b in buffers)
        inv = 1.0 / len(buffers)
        buffers = tuple(as_buffer(b) for b in buffers)
        views = [memoryview(b)[:length] for b in buffers]
        return make_buffer(math.fsum(vals) * inv for vals in zip(*views, strict=True))


@dataclass(frozen=True, slots=True)
class ReSample:
    rate: float

    def apply(self, buffer: Buffer) -> Buffer:
        buffer = as_buffer(buffer)
        if self.rate > 1:
            lowpass = LowPass(SAMPLE_RATE / (2 * self.rate))
            for _ in range(4):
                buffer = lowpass.apply(buffer)
        length = max(1, int(len(buffer) / self.rate))
        last = len(buffer) - 1
        rate = self.rate
        output = Buffer("f", bytes(length * 4))
        pos = 0.0
        for i in range(length):
            j = int(pos)
            if j >= last:
                break
            output[i] = buffer[j] + (buffer[j + 1] - buffer[j]) * (pos - j)
            pos += rate
        return make_buffer(output)


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
        return as_buffer(buffer[: int(self.seconds * SAMPLE_RATE)])


@dataclass(frozen=True, slots=True)
class Reverse:
    def apply(self, buffer: Buffer) -> Buffer:
        return make_buffer(reversed(buffer))


@dataclass(frozen=True, slots=True)
class Echo:
    seconds: float

    def apply(self, buffer: Buffer) -> Buffer:
        delay = int(self.seconds * SAMPLE_RATE)
        output = SILENCE * (len(buffer) + delay)
        output[: len(buffer)] = buffer
        tail = make_buffer(s / 2 for s in buffer)
        echoed = output[delay : delay + len(buffer)]
        output[delay : delay + len(buffer)] = make_buffer(
            a + b for a, b in zip(echoed, tail, strict=True)
        )
        return make_buffer(output)


@dataclass(frozen=True, slots=True)
class Drive:
    amount: float

    def apply(self, buffer: Buffer) -> Buffer:
        norm = math.tanh(self.amount)
        return make_buffer(math.tanh(s * self.amount) / norm for s in buffer)


@dataclass(frozen=True, slots=True)
class Humanize:
    velocity: float

    def apply(self, buffer: Buffer) -> Buffer:
        gain = 1.0 + self.velocity * math.tanh(math.sin(math.fsum(buffer)))
        return make_buffer(s * gain for s in buffer)


@dataclass(frozen=True, slots=True)
class HighPass:
    hertz: float

    def apply(self, buffer: Buffer) -> Buffer:
        rc = 1.0 / (math.tau * self.hertz)
        alpha = rc / (rc + 1.0 / SAMPLE_RATE)
        state = 0.0
        previous = 0.0
        output = Buffer("f", bytes(len(buffer) * 4))
        for index, sample in enumerate(buffer):
            state = alpha * (state + sample - previous)
            previous = sample
            output[index] = state
        return make_buffer(output)


@dataclass(frozen=True, slots=True)
class FadeIn:
    seconds: float

    def apply(self, buffer: Buffer) -> Buffer:
        length = min(len(buffer), int(self.seconds * SAMPLE_RATE))
        if length <= 0:
            return buffer
        output = as_buffer(buffer[:])
        for i in range(length):
            output[i] *= i / length
        return output


@dataclass(frozen=True, slots=True)
class FadeOut:
    seconds: float

    def apply(self, buffer: Buffer) -> Buffer:
        length = min(len(buffer), int(self.seconds * SAMPLE_RATE))
        if length <= 0:
            return buffer
        output = as_buffer(buffer[:])
        end = len(buffer)
        for i in range(length):
            output[end - length + i] *= 1.0 - i / length
        return output


@dataclass(frozen=True, slots=True)
class Delay:
    seconds: float
    feedback: float
    mix: float

    def apply(self, buffer: Buffer) -> Buffer:
        delay = int(self.seconds * SAMPLE_RATE)
        if delay <= 0:
            return buffer
        feedback = max(0.0, min(self.feedback, 0.95))
        mix = max(0.0, min(self.mix, 1.0))
        length = len(buffer) + delay
        wet = SILENCE * length
        wet[: len(buffer)] = buffer
        for i in range(delay, length):
            wet[i] += wet[i - delay] * feedback
        return make_buffer(
            (1.0 - mix) * (buffer[i] if i < len(buffer) else 0.0) + mix * wet[i]
            for i in range(length)
        )


@dataclass(frozen=True, slots=True)
class Normalize:
    peak: float

    def apply(self, buffer: Buffer) -> Buffer:
        loudest = max((abs(s) for s in buffer), default=0.0)
        if loudest == 0.0:
            return buffer
        gain = self.peak / loudest
        return make_buffer(s * gain for s in buffer)


@dataclass(frozen=True, slots=True)
class Clip:
    threshold: float

    def apply(self, buffer: Buffer) -> Buffer:
        limit = abs(self.threshold)
        return make_buffer(max(-limit, min(limit, s)) for s in buffer)


@dataclass(frozen=True, slots=True)
class Tremolo:
    hertz: float
    depth: float

    def apply(self, buffer: Buffer) -> Buffer:
        depth = max(0.0, min(self.depth, 1.0))
        step = math.tau * self.hertz / SAMPLE_RATE
        return make_buffer(
            s * (1.0 - depth * (0.5 + 0.5 * math.sin(i * step)))
            for i, s in enumerate(buffer)
        )


@dataclass(frozen=True, slots=True)
class BitCrush:
    bits: int

    def apply(self, buffer: Buffer) -> Buffer:
        steps = (1 << max(1, min(self.bits, 24))) - 1
        return make_buffer(round(s * steps) / steps for s in buffer)
