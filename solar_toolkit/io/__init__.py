"""I/O helpers for local observation files and simple manifests.

English: Shared scanning, FITS reading, natural sorting, and manifest helpers
that avoid science-specific defaults.

中文: 本地观测文件扫描、FITS 读取、自然排序和清单读写工具, 不绑定具体科学流程。
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import pandas as pd


def natural_key(value: str | Path) -> list[Any]:
    """Return a natural-sort key, e.g. frame2 before frame10."""

    name = Path(value).name
    return [
        int(part) if part.isdigit() else part.casefold()
        for part in re.split(r"(\d+)", name)
    ]


def scan_files(
    folder: str | Path,
    *,
    suffixes: Sequence[str] | None = None,
    recursive: bool = False,
    min_size_kb: float | None = None,
) -> list[Path]:
    """Scan a folder for files, optionally filtering suffix and size."""

    root = Path(folder).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Path does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Not a folder: {root}")

    normalized_suffixes = None
    if suffixes is not None:
        normalized_suffixes = {suffix.casefold() for suffix in suffixes}
    min_bytes = None if min_size_kb is None else int(float(min_size_kb) * 1024)
    iterator = root.rglob("*") if recursive else root.iterdir()
    files = []
    for path in iterator:
        if not path.is_file():
            continue
        if (
            normalized_suffixes is not None
            and path.suffix.casefold() not in normalized_suffixes
        ):
            continue
        if min_bytes is not None and path.stat().st_size < min_bytes:
            continue
        files.append(path)
    return sorted(files, key=natural_key)


def scan_fits(
    folder: str | Path,
    *,
    recursive: bool = False,
    min_size_kb: float | None = None,
) -> list[Path]:
    """Scan for FITS-like files using common suffixes."""

    return scan_files(
        folder,
        suffixes=(".fits", ".fit", ".fts"),
        recursive=recursive,
        min_size_kb=min_size_kb,
    )


def read_fits_data_header(path: str | Path, *, hdu_index: int = 0):
    """Read FITS data and header from one HDU."""

    from astropy.io import fits

    with fits.open(path) as hdul:
        hdu = hdul[hdu_index]
        return hdu.data, hdu.header.copy()


def write_manifest(rows: Iterable[dict[str, Any]], path: str | Path) -> Path:
    """Write manifest rows as CSV and return the output path."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(list(rows)).to_csv(output, index=False)
    return output


def read_manifest(path: str | Path) -> pd.DataFrame:
    """Read a CSV manifest into a DataFrame."""

    return pd.read_csv(path)


__all__ = [
    "natural_key",
    "read_fits_data_header",
    "read_manifest",
    "scan_files",
    "scan_fits",
    "write_manifest",
]
