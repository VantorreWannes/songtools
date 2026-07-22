import math

from songtools.types import SAMPLE_RATE, SILENCE, Buffer, Event, make_buffer


def mixdown(events: list[Event], beats: int, beats_per_minute: float) -> Buffer:
    frames_per_beat = 60.0 / beats_per_minute * SAMPLE_RATE
    mix = SILENCE * (int(beats * frames_per_beat) + SAMPLE_RATE)
    for event in events:
        start = int(event.beat * frames_per_beat)
        end = min(start + len(event.sound.buffer), len(mix))
        if end <= start:
            continue
        mix[start:end] = make_buffer(
            a + b
            for a, b in zip(
                mix[start:end], event.sound.buffer[: end - start], strict=True
            )
        )
    return make_buffer(math.tanh(x * 0.7) for x in mix)
