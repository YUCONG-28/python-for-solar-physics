"""LASCO/CME file discovery and timestamp parsing.

English: Parse timestamps from LASCO-style file names and scan local image
directories in observation order.

中文：解析 LASCO 风格文件名中的时间戳，并按观测时间扫描本地图像目录。
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

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
    return sorted(files, key=_timestamp_sort_key)


def _timestamp_sort_key(path: Path):
    try:
        return (0, extract_lasco_timestamp(path))
    except ValueError:
        return (1, natural_key(path))


__all__ = ["extract_lasco_timestamp", "scan_lasco_files"]
