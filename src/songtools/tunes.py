from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from songtools.layers import Layer
from songtools.sounds import REST
from songtools.transports import export as _export
from songtools.transports import play
from songtools.types import Event

if TYPE_CHECKING:
    from pathlib import Path

    from songtools.sounds import Sound
    from songtools.types import Effect


@dataclass(frozen=True, slots=True)
class Tune:
    sounds: tuple[Sound | Tune, ...]

    @property
    def beats(self) -> int:
        return len(self.sounds)

    def events(self, span: float) -> list[Event]:
        slot_beats = span / len(self.sounds)
        events = []
        for index, slot in enumerate(self.sounds):
            if slot is REST:
                continue
            offset = index * slot_beats
            if isinstance(slot, Tune):
                events.extend(
                    Event(offset + event.beat, event.sound)
                    for event in slot.events(slot_beats)
                )
            else:
                events.append(Event(offset, slot))
        return events

    def compile(self) -> list[Event]:
        return self.events(float(self.beats))

    def shifted(self, beats: float) -> Layer:
        return Layer((self,), beats)

    def play(self, bpm: float) -> None:
        play(self, bpm)

    def export(self, path: Path, bpm: float) -> None:
        _export(self, bpm, path)

    def with_effect(self, effect: Effect) -> Tune:
        return Tune(tuple(slot.with_effect(effect) for slot in self.sounds))

    def __add__(self, other: Tune) -> Tune:
        return Tune(self.sounds + other.sounds)

    def __mul__(self, amount: int) -> Tune:
        return Tune(self.sounds * amount)

    def __and__(self, other: Tune | Layer) -> Layer:
        return Layer((self, other), 0.0)

    def __matmul__(self, other: Effect) -> Tune:
        return self.with_effect(other)
