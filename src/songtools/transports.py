"""The transport: owns absolute time (bpm)."""

import math

from songtools.types import SAMPLE_RATE, SILENCE, Buffer, Event


def mixdown(events: list[Event], beats: int, beats_per_minute: float) -> Buffer:
    frames_per_beat = 60.0 / beats_per_minute * SAMPLE_RATE
    mix = SILENCE * (int(beats * frames_per_beat) + SAMPLE_RATE)
    for event in events:
        start = int(event.beat * frames_per_beat)
        for index, sample in enumerate(event.sound.buffer):
            if (position := start + index) < len(mix):
                mix[position] += sample
    return Buffer("f", (math.tanh(s) for s in (x * 0.7 for x in mix)))
