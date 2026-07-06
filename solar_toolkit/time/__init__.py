"""Time helpers for local solar-observation workflows.

English: Lightweight timestamp parsing, nearest-time matching, and range
filtering shared by AIA, HMI, radio, X-ray, and CME tools.

中文: 面向本地太阳观测流程的轻量时间工具, 用于时间戳解析、最近时间匹配和
时间范围筛选。
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Callable, Iterable, Sequence
from functools import lru_cache
from typing import TypeVar

T = TypeVar("T")


def parse_time(value: str | dt.datetime | dt.date) -> dt.datetime:
    """Parse common solar-workflow time values into naive UTC datetimes."""

    if isinstance(value, dt.datetime):
        parsed = value
    elif isinstance(value, dt.date):
        parsed = dt.datetime.combine(value, dt.time())
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        text = text.replace("T", " ")
        parsed = dt.datetime.fromisoformat(text)

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(dt.timezone.utc).replace(tzinfo=None)
    return parsed


@lru_cache(maxsize=8192)
def extract_time_from_filename(filename: str) -> dt.datetime:
    """Extract a timestamp from common AIA/HMI/radio/CSO-style filenames."""

    patterns = [
        (r"(\d{8}_\d{6})_TAI", "%Y%m%d_%H%M%S"),
        (r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)", "%Y-%m-%dT%H:%M:%SZ"),
        (r"(\d{4}-\d{2}-\d{2}T\d{6}Z)", "%Y-%m-%dT%H%M%SZ"),
        (r"(\d{8})T(\d{6})", "%Y%m%d_%H%M%S"),
        (r"(\d{8})[_-](\d{6})", "%Y%m%d_%H%M%S"),
        (r"(\d{14})", "%Y%m%d%H%M%S"),
        (r"(\d{8})", "%Y%m%d"),
    ]
    for pattern, fmt in patterns:
        match = re.search(pattern, str(filename))
        if not match:
            continue
        token = "_".join(match.groups()) if len(match.groups()) > 1 else match.group(1)
        try:
            return dt.datetime.strptime(token, fmt)
        except ValueError:
            continue
    raise ValueError(f"Could not extract time from filename: {filename}")


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


__all__ = [
    "extract_time_from_filename",
    "filter_by_time_range",
    "nearest_by_time",
    "parse_time",
]
