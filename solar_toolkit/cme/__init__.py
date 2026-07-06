"""CME and coronagraph helper namespace.

English: Reusable LASCO/CME helpers for timestamp parsing, local file scanning,
and simple running-difference products. User-facing scripts remain under
``scripts/lasco_cme``.

中文: LASCO/CME 可复用工具, 包含时间解析、本地文件扫描和 running-difference
基础计算; 面向用户的脚本仍保留在 ``scripts/lasco_cme``。
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import numpy as np

from solar_toolkit.io import natural_key, scan_files


def extract_lasco_timestamp(filename: str | Path) -> dt.datetime:
    """Extract a LASCO-style timestamp from a filename."""

    name = Path(filename).name
    patterns = [
        (r"(\d{8})[_-](\d{6})", "%Y%m%d_%H%M%S"),
        (r"(\d{8})[_-](\d{4})", "%Y%m%d_%H%M"),
        (r"(\d{14})", "%Y%m%d%H%M%S"),
    ]
    for pattern, fmt in patterns:
        match = re.search(pattern, name)
        if not match:
            continue
        token = "_".join(match.groups()) if len(match.groups()) > 1 else match.group(1)
        return dt.datetime.strptime(token, fmt)
    raise ValueError(f"Could not extract LASCO timestamp from filename: {filename}")


def scan_lasco_files(folder: str | Path, *, recursive: bool = False) -> list[Path]:
    """Scan LASCO image files and sort by extracted timestamp when possible."""

    files = scan_files(
        folder,
        suffixes=(".jp2", ".jpg", ".jpeg", ".png", ".fits", ".fts"),
        recursive=recursive,
    )
    return sorted(files, key=lambda path: _timestamp_sort_key(path))


def running_difference(current, previous) -> np.ndarray:
    """Return ``current - previous`` as a float/array preserving NumPy rules."""

    return np.asarray(current) - np.asarray(previous)


def _timestamp_sort_key(path: Path):
    try:
        return (0, extract_lasco_timestamp(path))
    except ValueError:
        return (1, natural_key(path))


__all__ = [
    "extract_lasco_timestamp",
    "running_difference",
    "scan_lasco_files",
]
