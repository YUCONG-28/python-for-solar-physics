#!/usr/bin/env python
"""Query and download Solar Orbiter/EUI FITS files from SOAR."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import requests

START = "2025-01-24 04:00:00"
END = "2025-01-24 05:00:00"
TAP_URL = "http://soar.esac.esa.int/soar-sl-tap/tap/sync"
DATA_URL = "http://soar.esac.esa.int/soar-sl-tap/data"


def query_eui(start: str, end: str) -> list[dict]:
    query = (
        "SELECT h1.instrument,h1.descriptor,h1.level,h1.begin_time,h1.end_time,"
        "h1.data_item_id,h1.filesize,h1.filename,h1.soop_name,"
        "h2.detector,h2.wavelength,h2.dimension_index "
        "FROM v_sc_data_item AS h1 JOIN v_eui_sc_fits AS h2 USING (data_item_oid) "
        "WHERE h1.instrument='EUI' "
        f"AND h1.begin_time>='{start}' "
        f"AND h1.begin_time<='{end}' "
        "AND h1.is_active='True' "
        "ORDER BY h1.begin_time"
    )
    response = requests.get(
        TAP_URL,
        params="REQUEST=doQuery&LANG=ADQL&FORMAT=json&QUERY=" + query,
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    names = [item["name"] for item in payload["metadata"]]
    return [dict(zip(names, row, strict=False)) for row in payload["data"]]


def unique_rows(rows: list[dict]) -> list[dict]:
    seen = {}
    for row in rows:
        seen.setdefault(row["data_item_id"], row)
    return list(seen.values())


def print_summary(rows: list[dict]) -> None:
    unique = unique_rows(rows)
    print(f"metadata rows: {len(rows)}")
    print(f"unique files:  {len(unique)}")
    total_mb = sum((row.get("filesize") or 0) for row in unique) / 1024 / 1024
    print(f"total size:    {total_mb:.2f} MB")
    print()

    groups = defaultdict(list)
    for row in unique:
        key = (
            row["descriptor"],
            row["level"],
            row.get("detector"),
            row.get("wavelength"),
        )
        groups[key].append(row)

    for key, group in sorted(groups.items(), key=lambda item: item[0]):
        size_mb = sum((row.get("filesize") or 0) for row in group) / 1024 / 1024
        first = group[0]["begin_time"]
        last = group[-1]["begin_time"]
        print(f"{key}: n={len(group)} size={size_mb:.2f} MB first={first} last={last}")


def download(rows: list[dict], outdir: Path, descriptor: str | None) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    selected = unique_rows(rows)
    if descriptor:
        selected = [row for row in selected if row["descriptor"] == descriptor]

    for index, row in enumerate(selected, start=1):
        target = outdir / row["filename"]
        if target.exists() and target.stat().st_size > 0:
            print(f"[{index}/{len(selected)}] exists {target}")
            continue

        params = {
            "retrieval_type": "LAST_PRODUCT",
            "product_type": "SCIENCE",
            "data_item_id": row["data_item_id"],
        }
        print(f"[{index}/{len(selected)}] download {row['filename']}")
        with requests.get(
            DATA_URL, params=params, stream=True, timeout=300
        ) as response:
            response.raise_for_status()
            with target.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        handle.write(chunk)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default=START)
    parser.add_argument("--end", default=END)
    parser.add_argument("--outdir", default="data/raw/solo/eui/20250124")
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--descriptor", help="Download only one descriptor.")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    rows = query_eui(args.start, args.end)
    outdir.mkdir(parents=True, exist_ok=True)
    manifest = outdir / "soar_eui_20250124_0400_0500_metadata.json"
    manifest.write_text(json.dumps(rows, indent=2))
    print_summary(rows)
    print(f"saved manifest: {manifest}")

    if args.download:
        download(rows, outdir, args.descriptor)


if __name__ == "__main__":
    main()
