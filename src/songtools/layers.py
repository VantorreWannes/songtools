from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from songtools.tunes import Tune
    from songtools.types import Effect


@dataclass(frozen=True, slots=True)
class Layer:
    tunes: tuple[Tune, ...]

    def with_effect(self, effect: Effect) -> Layer:
        tunes = tuple(tune.with_effect(effect) for tune in self.tunes)
        return Layer(tunes)

    def __add__(self, other: Layer) -> Layer:
        """Concatenate two layers together using the + operator."""
        return Layer(self.tunes + other.tunes)

    def __mul__(self, amount: int) -> Layer:
        """Duplicate a layer `n` times."""
        return Layer(self.tunes * amount)

    def __and__(self, other: Layer) -> Layer:
        """Combine two layers together using the & operator."""
        return Layer(self.tunes + other.tunes)

    def __matmul__(self, other: Effect) -> Layer:
        """Apply the specified `Effect` to this layer."""
        return self.with_effect(other)
