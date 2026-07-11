"""Explicit, import-safe file downloads.

English: Download a URL into a caller-selected location and report whether the
file was downloaded or skipped.

中文：将 URL 下载到调用者明确指定的位置，并报告文件是新下载还是已跳过。
"""

from __future__ import annotations

import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


@dataclass(frozen=True)
class DownloadResult:
    """Result returned by :func:`download_url`."""

    url: str
    path: Path
    status: str


def download_url(
    url: str,
    destination: str | Path,
    *,
    overwrite: bool = False,
    timeout: float = 30,
    chunk_size: int | None = None,
    atomic: bool = True,
    redownload_empty: bool = False,
) -> DownloadResult:
    """Download ``url`` to ``destination`` with optional atomic streaming."""

    output = Path(destination)
    if (
        output.exists()
        and not overwrite
        and not (redownload_empty and output.stat().st_size == 0)
    ):
        return DownloadResult(url=url, path=output, status="skipped")
    output.parent.mkdir(parents=True, exist_ok=True)
    target = output.with_suffix(output.suffix + ".part") if atomic else output
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            with target.open("wb") as handle:
                _copy_response(response, handle, chunk_size=chunk_size)
        if atomic:
            target.replace(output)
    except Exception:
        if atomic:
            target.unlink(missing_ok=True)
        raise
    return DownloadResult(url=url, path=output, status="downloaded")


def fetch_text(
    url: str,
    *,
    timeout: float = 30,
    encoding: str = "utf-8",
    errors: str = "replace",
) -> str:
    """Fetch a text resource without writing files or mutating local state."""

    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read().decode(encoding, errors=errors)


def _copy_response(response, handle: BinaryIO, *, chunk_size: int | None) -> None:
    if chunk_size is None:
        handle.write(response.read())
        return
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive or None")
    while chunk := response.read(chunk_size):
        handle.write(chunk)


__all__ = ["DownloadResult", "download_url", "fetch_text"]
