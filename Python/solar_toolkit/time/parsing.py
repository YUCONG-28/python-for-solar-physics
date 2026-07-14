"""Timestamp parsing helpers for solar-observation workflows.

English: Parse timestamps supplied directly or embedded in common local file
names without depending on instrument-specific packages.

中文：解析直接提供的时间戳，以及常见本地观测文件名中包含的时间戳。
"""

from __future__ import annotations

import datetime as dt
import re
from functools import lru_cache


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


def parse_isot_time(time_str: str) -> dt.datetime:
    """Parse an ISO-like timestamp accepting ``T`` or a space separator."""

    return dt.datetime.fromisoformat(time_str.replace("T", " "))


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
        (r"(\d{4}-\d{2}-\d{2})", "%Y-%m-%d"),
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


__all__ = ["extract_time_from_filename", "parse_isot_time", "parse_time"]
