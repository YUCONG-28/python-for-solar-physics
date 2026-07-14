"""File-name sorting helpers.

English: Produce deterministic natural-sort keys for local observation files.

中文：为本地观测文件生成稳定的自然排序键。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def natural_key(value: str | Path) -> list[Any]:
    """Return a natural-sort key, e.g. frame2 before frame10."""

    name = Path(value).name
    return [
        int(part) if part.isdigit() else part.casefold()
        for part in re.split(r"(\d+)", name)
    ]


__all__ = ["natural_key"]
