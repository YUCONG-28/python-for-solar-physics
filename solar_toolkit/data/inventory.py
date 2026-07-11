"""Local observation-file inventory models.

English: Represent local observation files and convert entries into a tabular
inventory without archive queries or downloads.

中文：表示本地观测文件并生成表格清单，不执行归档查询或下载。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class ObservationFile:
    """One local observation file entry."""

    path: Path
    instrument: str | None = None
    wavelength: str | None = None
    obs_time: str | None = None

    def as_row(self) -> dict[str, str | None]:
        row = asdict(self)
        row["path"] = str(self.path)
        return row


def build_inventory(entries: list[ObservationFile]) -> pd.DataFrame:
    """Build a DataFrame inventory from observation entries."""

    return pd.DataFrame([entry.as_row() for entry in entries])


__all__ = ["ObservationFile", "build_inventory"]
