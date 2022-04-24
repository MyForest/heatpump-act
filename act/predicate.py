from typing import TypeVar, Callable

T = TypeVar("T")

Predicate = Callable[[T], bool]
