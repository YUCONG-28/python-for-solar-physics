"""Time-based selection helpers.

English: Select the nearest observation or filter observations to an inclusive
time range.

中文：选择最接近目标时间的观测，或按闭区间筛选观测。
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Iterable, Sequence
from typing import TypeVar

from .parsing import parse_time

T = TypeVar("T")


def nearest_by_time(
    target_time: str | dt.datetime | dt.date,
    items: Sequence[T],
    *,
    key: Callable[[T], str | dt.datetime | dt.date] | None = None,
    max_diff_seconds: float | None = None,
) -> T | None:
    """Return the item nearest to ``target_time`` or ``None`` past a threshold."""

    if not items:
        return None
    target = parse_time(target_time)
    resolver = key or _default_time_key
    closest = min(
        items,
        key=lambda item: abs((parse_time(resolver(item)) - target).total_seconds()),
    )
    diff_seconds = abs((parse_time(resolver(closest)) - target).total_seconds())
    if max_diff_seconds is not None and diff_seconds > max_diff_seconds:
        return None
    return closest


def filter_by_time_range(
    items: Iterable[T],
    start_time: str | dt.datetime | dt.date,
    end_time: str | dt.datetime | dt.date,
    *,
    key: Callable[[T], str | dt.datetime | dt.date] | None = None,
) -> list[T]:
    """Return items whose resolved time falls within the inclusive range."""

    start = parse_time(start_time)
    end = parse_time(end_time)
    resolver = key or _default_time_key
    return [item for item in items if start <= parse_time(resolver(item)) <= end]


def _default_time_key(item):
    if isinstance(item, tuple) and len(item) >= 2:
        return item[1]
    if isinstance(item, dict):
        for name in ("obs_time", "time", "date_obs", "DATE-OBS"):
            if name in item:
                return item[name]
    return item


__all__ = ["filter_by_time_range", "nearest_by_time"]
