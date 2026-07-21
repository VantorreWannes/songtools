from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from songtools.types import Buffer, Decay, Effect, Gain, LowPass, ReSample


@dataclass(frozen=True, slots=True)
class Sound:
    buffer: Buffer

    def with_gain(self, gain: Gain) -> Sound:
        buffer = gain.apply(self.buffer)
        return Sound(buffer)

    def with_decay(self, decay: Decay) -> Sound:
        buffer = decay.apply(self.buffer)
        return Sound(buffer)

    def with_lowpass(self, lowpass: LowPass) -> Sound:
        buffer = lowpass.apply(self.buffer)
        return Sound(buffer)

    def with_resample(self, resample: ReSample) -> Sound:
        buffer = resample.apply(self.buffer)
        return Sound(buffer)

    def __matmul__(self, other: Effect) -> Sound:
        """Apply the specified `Effect` to this sound."""
        buffer = other.apply(self.buffer)
        return Sound(buffer)
