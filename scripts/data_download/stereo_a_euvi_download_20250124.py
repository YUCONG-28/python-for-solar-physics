#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import urllib.request
from pathlib import Path

from sunpy.net import Fido
from sunpy.net import attrs as a

BASE_URL = "https://stereo-ssc.nascom.nasa.gov/data/ins_data"
OUT_DIR = Path(os.getenv("STEREO_EUVI_DATA_DIR", "data/raw/stereo/euvi/20250124"))
START = "2025-01-24 04:00"
END = "2025-01-24 05:00"


def download(url: str, dest: Path) -> str:
    if dest.exists() and dest.stat().st_size > 0:
        return "exists"
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=180) as response, tmp.open("wb") as fh:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            fh.write(chunk)
    tmp.replace(dest)
    return "downloaded"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    result = Fido.search(
        a.Time(START, END),
        a.Instrument("EUVI"),
        a.Source("STEREO_A"),
    )
    table = result[0]
    records = sorted(str(row["fileid"]) for row in table)
    manifest = OUT_DIR / "selected_files.txt"
    manifest.write_text(
        "# STEREO-A SECCHI/EUVI files\n"
        "# time_range=2025-01-24T04:00:00Z/2025-01-24T05:00:00Z\n"
        + "\n".join(records)
        + "\n",
        encoding="utf-8",
    )

    downloaded = 0
    existing = 0
    failed: list[tuple[str, str]] = []
    for index, fileid in enumerate(records, start=1):
        filename = Path(fileid).name
        url = f"{BASE_URL}/{fileid}"
        dest = OUT_DIR / filename
        try:
            status = download(url, dest)
            if status == "downloaded":
                downloaded += 1
            else:
                existing += 1
            print(f"[{index:02d}/{len(records)}] {status}: {filename}", flush=True)
        except Exception as exc:
            failed.append((fileid, str(exc)))
            print(f"[{index:02d}/{len(records)}] failed: {filename}: {exc}", flush=True)

    print(
        f"Done. total={len(records)} downloaded={downloaded} existing={existing} failed={len(failed)}"
    )
    if failed:
        fail_log = OUT_DIR / "download_failed.txt"
        fail_log.write_text(
            "\n".join(f"{fileid}\t{err}" for fileid, err in failed) + "\n",
            encoding="utf-8",
        )
        print(f"failed_log={fail_log}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
