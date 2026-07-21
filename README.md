# Music DSL — Core

**Philosophy:** Notes carry expression, structure carries time.
`play` owns absolute time (bpm). `Tune` owns relative time.
No magic strings, no duplicate logic or state.

## Abstractions (5)

| Name         | What it is                                           |
| ------------ | ---------------------------------------------------- |
| `Sound`      | A voice (sample or synth). Knows timbre, never time. |
| `Key`        | Harmonic context: root + scale.                      |
| `Tune`       | Anything arranged in time. Pure data — no methods.   |
| `play()`     | The transport. Owns bpm and output.                  |
| `Instrument` | Optional namespace grouping Sounds.                  |

## Operators (the whole surface)

| Op          | Meaning                                      |
| ----------- | -------------------------------------------- |
| `Tune(...)` | slots of 1 beat; nesting subdivides          |
| `a + b`     | a, then b                                    |
| `a * n`     | repeat                                       |
| `a & b`     | together — shorter side loops to LCM         |
| `x @ y`     | realize: left plays right, in left's context |

- `None` = rest (inside a `Tune`)

## Vocabulary

- Notes: `C`, `D`, `E`, ...
- `Scales.MAJOR`, `Scales.MINOR`, ...
- `Chords.I`, `Chords.IV`, `Chords.V`, ... — quality emerges from Key × degree
- `Degrees.I`, `Degrees.III`, ... — single tones

## Rules

- Slot = 1 beat. Want it faster? Nest. Slower? Spread with `None`. Global speed? bpm.
- Want a variation? Write it: `groove * 3 + fill`.
- Never name a chord's quality — it falls out of Key × degree.
- Transpose a whole layer: change one `Key` constant. Drums don't move.
- `@` chains left-to-right: `synth @ key @ Chords.IV`.

## Example

```python
hat, kick = Sound("sounds/high_hat.wav"), Sound("sounds/kick.wav")
keys = Sound("sounds/synth_1.wav") @ Key(C, Scales.MAJOR)

beat   = Tune(hat, hat, kick) * 3
chords = Tune(keys @ Chords.I, keys @ Chords.IV, keys @ Chords.V) * 2

song = beat & (Tune(None) * 3 + chords)
play(song, bpm=120)
```
