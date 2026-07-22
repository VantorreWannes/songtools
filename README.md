# songtools

A Python DSL for composing music from code. Notes carry expression, structure carries time. No magic strings, no duplicate logic or state.

## Install

```bash
uv pip install -e .
```

Requires Python 3.14+ and [sounddevice](https://python-sounddevice.readthedocs.io/) (PortAudio backend).

## Core idea

`Sound` knows timbre, never time. `Tune` owns relative time. `play` / `compile` own absolute time (bpm). Combine them with operators and you get a tiny, composable music language.

## Abstractions

| Name                   | What it is                                                     |
| ---------------------- | -------------------------------------------------------------- |
| `Sound`                | A voice (sample or synth). Knows timbre, never time.           |
| `Key`                  | Harmonic context: root + scale + quality.                      |
| `Tune`                 | Anything arranged in time. Pure data — no methods that mutate. |
| `Layer`                | Parallel voices. Shorter sides loop to LCM.                    |
| `compile()` / `play()` | The transport. Owns bpm and output.                            |

## Operators

| Op               | Meaning                                      |
| ---------------- | -------------------------------------------- |
| `Tune(a, b, c)`  | Slots of 1 beat; nesting subdivides          |
| `Layer(a, b, c)` | Parallel voices; shorter sides loop to LCM   |
| `a + b`          | a, then b (sequence)                         |
| `a * n`          | repeat                                       |
| `x @ y`          | realize: left plays right, in left's context |

`None` is not used — use `REST` for a rest inside a `Tune`.

## Vocabulary

- Notes: `KeyRoot.C`, `KeyRoot.D`, ... (chromatic, 0–11)
- Scales: `Scale.MAJOR`, `Scale.MINOR`, `Scale.DORIAN`
- Qualities: `Quality.TRIAD`, `Quality.SEVENTH`, `Quality.NINTH`, `Quality.SUS2`, `Quality.SUS4`, `Quality.POWER`
- Degrees: `Degree.I`, `Degree.II`, ... `Degree.VII` (also used as chord symbols)

## Effects

Chain on any `Sound` with `@`:

| Effect                    | What it does                       |
| ------------------------- | ---------------------------------- |
| `Gain(amount)`            | Multiply amplitude                 |
| `Decay(duration)`         | Exponential fade (`timedelta`)     |
| `LowPass(hertz)`          | One-pole lowpass filter            |
| `HighPass(hertz)`         | One-pole highpass filter           |
| `Echo(seconds)`           | Single-tap delay at −6 dB          |
| `Delay(seconds, fb, mix)` | Feedback delay with dry/wet blend  |
| `Gate(seconds)`           | Hard cut to length                 |
| `FadeIn(seconds)`         | Linear ramp up from silence        |
| `FadeOut(seconds)`        | Linear ramp down to silence        |
| `Reverse`                 | Reverse the buffer                 |
| `Drive(amount)`           | Tanh saturation                    |
| `Clip(threshold)`         | Hard-limit peaks                   |
| `Normalize(peak)`         | Scale so the loudest sample = peak |
| `Tremolo(hertz, depth)`   | Amplitude modulation               |
| `BitCrush(bits)`          | Reduce bit depth (lo-fi)           |
| `Humanize(velocity)`      | Subtle gain variation              |

## Quick start

### 1. Generate some sounds

```bash
python scripts/sounds.py     # writes pluck.wav, kick.wav, snare.wav, hat.wav
```

### 2. Compose

```python
from datetime import timedelta

from songtools.files import WavFile
from songtools.keys import Key
from songtools.layers import Layer
from songtools.sounds import REST, Sound
from songtools.tunes import Tune
from songtools.types import (
    Decay,
    Degree,
    Echo,
    Gain,
    KeyRoot,
    LowPass,
    Pitch,
    Quality,
    Scale,
)

# --- Load or synthesize sounds ---
pluck = WavFile(Path("pluck.wav")).parse(Pitch(60))
kick  = WavFile(Path("kick.wav")).parse(Pitch(60))
hat   = WavFile(Path("hat.wav")).parse(Pitch(60))

# --- Shape them with effects ---
warm_pluck = pluck @ LowPass(1800) @ Decay(timedelta(milliseconds=900)) @ Gain(0.5)
hard_hat   = hat @ Gain(0.3)

# --- Tune to a key ---
key = Key(KeyRoot.C, Scale.MAJOR, Quality.TRIAD)
melody = Tune(
    warm_pluck @ key @ Degree.I,
    warm_pluck @ key @ Degree.IV,
    warm_pluck @ key @ Degree.V,
    warm_pluck @ key @ Degree.I,
)

# --- Arrange ---
beat = Tune(hard_hat, REST, hard_hat, REST) * 4
bass = Tune(kick, REST, kick, REST) * 4

song = Layer(melody, beat, bass)

# --- Render ---
song.compile(beats_per_minute=120).play()          # play live
WavFile(Path("out.wav")).save(song.compile(beats_per_minute=120))  # or save
```

See `scripts/sounds.py` and `scripts/test.py` for full working examples.

## Rules of thumb

- **Slot = 1 beat.** Want it faster? Nest a `Tune`. Slower? Spread with `REST`. Global speed? bpm.
- **Variations are data.** Write them: `groove * 3 + fill`.
- **Quality falls out of Key × degree.** Never name a chord's quality — it emerges.
- **Transpose a layer:** change one `Key` constant. Drums don't move.
- **`@` chains left-to-right:** `sound @ key @ Degree.I`, then add effects.

## Project layout

```
src/songtools/
  types.py      # Buffer, Pitch, KeyRoot, Scale, Quality, Degree, effects
  sounds.py     # Sound, KeyedSound, REST
  keys.py       # Key (harmonic context)
  tunes.py      # Tune (sequential time)
  layers.py     # Layer (parallel time)
  transports.py # mixdown — the bpm-aware renderer
  files.py      # WavFile — load/save 16-bit mono WAV
scripts/
  sounds.py     # Synthesize pluck, kick, snare, hat
  test.py       # Full song example
```

## License

MIT
