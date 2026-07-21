import struct
import wave
from array import array
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from songtools.sounds import Sound
from songtools.types import SAMPLE_RATE, Buffer, Pitch

if TYPE_CHECKING:
    from pathlib import Path


class SoundFile(Protocol):
    def load(self) -> Sound: ...

    def save(self, sound: Sound) -> None: ...


@dataclass(frozen=True, slots=True)
class WavFile:
    path: Path

    @classmethod
    def _unpack(cls, raw: bytes, channel_bytes: int) -> tuple[int, ...]:
        padded = b"".join(
            raw[i : i + channel_bytes].ljust(
                4, b"\xff" if raw[i + channel_bytes - 1] & 128 else b"\x00"
            )
            for i in range(0, len(raw), channel_bytes)
        )
        return struct.unpack(f"<{len(padded) // 4}i", padded)

    def parse(self, pitch: Pitch) -> Sound:
        with self.path.open("rb") as f, wave.open(f, "rb") as w:
            channel_bytes = w.getsampwidth()
            channel_count = w.getnchannels()
            raw = w.readframes(w.getnframes())
        bits = channel_bytes * 8
        max_val = 2 ** (bits - 1)
        samples = self._unpack(raw, channel_bytes)
        if channel_count > 1:
            samples = [
                sum(samples[i : i + channel_count]) / channel_count
                for i in range(0, len(samples), channel_count)
            ]

        return Sound(Buffer("f", (s / max_val for s in samples)), pitch)

    def save(self, sound: Sound) -> None:
        pcm16 = array(
            "h",
            (int(max(-1.0, min(1.0, s)) * 32767) for s in sound.buffer),
        ).tobytes()
        with self.path.open("wb") as f, wave.open(f, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SAMPLE_RATE)
            w.writeframes(pcm16)
