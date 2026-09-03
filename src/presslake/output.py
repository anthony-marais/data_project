"""Sortie CLI : mode silencieux + callback de progression (pipeline)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

ProgressFn = Callable[[int, int | None], None]

_quiet: ContextVar[bool] = ContextVar("presslake_quiet", default=False)
_progress: ContextVar[ProgressFn | None] = ContextVar("presslake_progress", default=None)


def is_quiet() -> bool:
    return _quiet.get()


def info(message: str = "", *, end: str = "\n") -> None:
    """print() ignoré si le pipeline a activé le mode barre."""
    if not _quiet.get():
        print(message, end=end)


def report_progress(current: int, total: int | None) -> None:
    callback = _progress.get()
    if callback is not None:
        callback(current, total)


@contextmanager
def quiet_with_progress(callback: ProgressFn) -> Iterator[None]:
    q = _quiet.set(True)
    p = _progress.set(callback)
    try:
        yield
    finally:
        _progress.reset(p)
        _quiet.reset(q)
