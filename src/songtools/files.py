import struct
import wave
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from songtools.sounds import Sound
from songtools.types import Buffer

if TYPE_CHECKING:
    from pathlib import Path


class SoundFile(Protocol):
    def parse(self, path: Path) -> Sound: ...


@dataclass(frozen=True, slots=True)
class WavFile:
    @classmethod
    def _unpack(cls, raw: bytes, channel_bytes: int) -> tuple[int, ...]:
        padded = b"".join(
            raw[i : i + channel_bytes].ljust(
                4, b"\xff" if raw[i + channel_bytes - 1] & 128 else b"\x00"
            )
            for i in range(0, len(raw), channel_bytes)
        )
        return struct.unpack(f"<{len(padded) // 4}i", padded)

    @classmethod
    def parse(cls, path: Path) -> Sound:
        with path.open("rb") as f, wave.open(f, "rb") as w:
            channel_bytes = w.getsampwidth()
            channel_count = w.getnchannels()
            raw = w.readframes(w.getnframes())
        bits = channel_bytes * 8
        max_val = 2 ** (bits - 1)
        samples = cls._unpack(raw, channel_bytes)
        if channel_count > 1:
            samples = [
                sum(samples[i : i + channel_count]) / channel_count
                for i in range(0, len(samples), channel_count)
            ]

        return Sound(Buffer("f", (s / max_val for s in samples)))
