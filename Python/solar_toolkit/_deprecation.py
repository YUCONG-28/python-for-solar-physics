"""Internal helpers for issuing consistent API deprecation warnings."""

from __future__ import annotations

import functools as _functools
import warnings as _warnings
from collections.abc import Callable as _Callable
from typing import Any as _Any
from typing import TypeVar as _TypeVar
from typing import cast as _cast

from .exceptions import SolarToolkitDeprecationWarning as _DeprecationWarning

_CallableT = _TypeVar("_CallableT", bound=_Callable[..., _Any])


def warn_deprecated(
    name: str,
    *,
    since: str,
    alternative: str | None = None,
    removal: str | None = None,
    stacklevel: int = 2,
) -> None:
    """Warn that ``name`` is deprecated using the toolkit warning category."""

    if not name:
        raise ValueError("A deprecated API name is required")
    if not since:
        raise ValueError("A deprecation version is required")

    message = f"{name} is deprecated since solar-physics-toolkit {since}."
    if alternative:
        message += f" Use {alternative} instead."
    if removal:
        message += f" It is scheduled for removal in version {removal}."

    _warnings.warn(
        message,
        category=_DeprecationWarning,
        stacklevel=stacklevel,
    )


def deprecated(
    *,
    since: str,
    alternative: str | None = None,
    removal: str | None = None,
) -> _Callable[[_CallableT], _CallableT]:
    """Decorate a callable so each use emits a consistent warning."""

    def decorator(func: _CallableT) -> _CallableT:
        @_functools.wraps(func)
        def wrapper(*args: _Any, **kwargs: _Any) -> _Any:
            warn_deprecated(
                f"{func.__module__}.{func.__qualname__}",
                since=since,
                alternative=alternative,
                removal=removal,
                stacklevel=3,
            )
            return func(*args, **kwargs)

        return _cast(_CallableT, wrapper)

    return decorator


__all__ = ["deprecated", "warn_deprecated"]
