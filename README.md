# songtools

A Python DSL for composing music from code. Notes carry expression, structure carries time. No magic strings, no duplicate logic or state.

## Install

```bash
uv add songtools
```

Requires Python 3.14+ and [sounddevice](https://python-sounddevice.readthedocs.io/) (PortAudio backend).

## Core idea

The library revolves around the `Sound` object. Use the `@` operator to transform sounds:

- `sound @ Effect`: Applies a DSP effect.
- `sound @ Key`: Applies a harmonic context.
- `sound @ Degree`: Applies a relative pitch shift based on a key.

## Abstractions

| Name      | What it is                                                 |
| --------- | ---------------------------------------------------------- |
| `Sound`   | The primary object. Contains samples and harmonic context. |
| `Buffer`  | Low-level wrapper around a float array for audio data.     |
| `Key`     | Harmonic context: root + scale + quality.                  |
| `WavFile` | Utility for reading/writing 16-bit PCM WAV files.          |

## Operators

| Op              | Meaning                            |
| --------------- | ---------------------------------- |
| `a + b`         | Concatenation (a, then b)          |
| `a * n`         | Repetition (repeat a, n times)     |
| `a & b`         | Mixing (linear sum of buffers)     |
| `a @ transform` | Transform (Effect, Key, or Degree) |

## Vocabulary

- **Notes/Degrees**: `Degree.I` through `Degree.VII`.
- **Scales**: `Scale.MAJOR`, `Scale.MINOR`, `Scale.DORIAN`.
- **Qualities**: `Quality.TRIAD`, `Quality.SEVENTH`, `Quality.NINTH`, `Quality.SUS2`, `Quality.SUS4`, `Quality.POWER`.
- **Roots**: `KeyRoot.C`, `KeyRoot.CS`, etc.

## Effects

Chain effects on any `Sound` using `@`:

| Effect                  | What it does                       |
| ----------------------- | ---------------------------------- |
| `Gain(amount)`          | Multiply amplitude                 |
| `Decay(duration)`       | Exponential envelope (`timedelta`) |
| `LowPass(hertz)`        | One-pole lowpass filter            |
| `HighPass(hertz)`       | One-pole highpass filter           |
| `Echo(duration)`        | Single-tap delay                   |
| `Delay(time, fb, mix)`  | Feedback delay with dry/wet blend  |
| `Gate(duration)`        | Hard cut to length                 |
| `FadeIn(duration)`      | Linear ramp up from silence        |
| `FadeOut(duration)`     | Linear ramp down to silence        |
| `Reverse`               | Reverse the buffer                 |
| `Drive(amount)`         | Tanh saturation                    |
| `Clip(threshold)`       | Hard-limit peaks                   |
| `Normalize(peak)`       | Scale so the loudest sample = peak |
| `Tremolo(hertz, depth)` | Amplitude modulation               |
| `BitCrush(bits)`        | Reduce bit depth (lo-fi)           |
| `Humanize(velocity)`    | Subtle gain variation              |

## Quick start

```python
from datetime import timedelta
from songtools.lib import (
    Sound, Key, KeyRoot, Scale, Quality,
    Degree, Decay, LowPass, WavFile
)

# Create a simple tone
tone = Sound.tone(440.0, 44100)

# Apply transformations and effects
# A C-Major chord sequence with a lowpass filter
melody = (tone @ Key(KeyRoot.C, Scale.MAJOR, Quality.TRIAD) @ Degree.I) @ LowPass(2000)

# Sequence notes
song = Sound.sequence(melody @ Decay(timedelta(seconds=0.5)), tone @ Decay(timedelta(seconds=0.2)), bpm=bpm)

# Play or Save
song.play()
WavFile("output.wav").write(song)
```

## License

MIT
