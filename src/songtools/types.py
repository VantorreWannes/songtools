from array import array
from functools import partial
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

Buffer: Callable[Iterable[float], array] = cast(
    "Callable[Iterable[float], array]", partial(array, "f")
)
