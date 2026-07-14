"""CSV manifest input and output.

English: Persist simple row dictionaries as CSV and load them as pandas data
frames.

中文：将简单字典记录保存为 CSV，并读取为 pandas 数据表。
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd


def write_manifest(rows: Iterable[dict[str, Any]], path: str | Path) -> Path:
    """Write manifest rows as CSV and return the output path."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(list(rows)).to_csv(output, index=False)
    return output


def read_manifest(path: str | Path) -> pd.DataFrame:
    """Read a CSV manifest into a DataFrame."""

    return pd.read_csv(path)


__all__ = ["read_manifest", "write_manifest"]
