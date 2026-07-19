"""Explicit JSOC query and download helpers without event defaults or a CLI."""

from __future__ import annotations

import time
from pathlib import Path
from urllib.request import Request, urlopen

__all__ = ["collect_records", "download_one"]


def collect_records(
    *,
    output_dir: str | Path,
    base_url: str,
    series: str,
    timerange: str,
    waves: list[int] | tuple[int, ...],
    client=None,
) -> list[tuple[str, Path]]:
    """Query explicit JSOC record parameters and return download targets."""

    if client is None:
        import drms

        client = drms.Client()
    output = Path(output_dir)
    records: list[tuple[str, Path]] = []
    for wave in waves:
        recset = f"{series}[{timerange}][{wave}]"
        keys, segments = client.query(recset, key="T_REC,WAVELNTH,QUALITY", seg="image")
        for row, segment in zip(
            keys.to_dict("records"), segments["image"].tolist(), strict=False
        ):
            if int(row.get("QUALITY", 0)) != 0:
                continue
            record_time = str(row["T_REC"]).replace("-", "").replace(":", "")
            name = (
                f"{series.replace('.', '_')}_{record_time}_{int(row['WAVELNTH'])}.fits"
            )
            records.append(
                (base_url.rstrip("/") + "/" + segment.lstrip("/"), output / name)
            )
    return records


def download_one(
    item: tuple[str, Path],
    *,
    attempts: int = 3,
    timeout_s: float = 120,
    minimum_size: int = 1024,
) -> tuple[str, str, int | str]:
    """Download one URL atomically to an explicit path."""

    url, path = item
    if path.exists() and path.stat().st_size > minimum_size:
        return "exists", path.name, path.stat().st_size
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    last_error = ""
    for attempt in range(1, attempts + 1):
        try:
            request = Request(url, headers={"User-Agent": "solar-physics-toolkit"})
            with (
                urlopen(request, timeout=timeout_s) as response,
                temporary.open("wb") as handle,
            ):
                while chunk := response.read(1024 * 1024):
                    handle.write(chunk)
            if temporary.stat().st_size <= minimum_size:
                raise RuntimeError(f"download too small: {temporary.stat().st_size}")
            temporary.replace(path)
            return "done", path.name, path.stat().st_size
        except Exception as exc:  # caller receives the final error as data
            last_error = repr(exc)
            temporary.unlink(missing_ok=True)
            if attempt < attempts:
                time.sleep(2 * attempt)
    return "failed", path.name, last_error
