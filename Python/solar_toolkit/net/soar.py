"""Solar Orbiter Archive (SOAR) EUI query and download helpers."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

from .downloads import download_url

DEFAULT_TAP_URL = "http://soar.esac.esa.int/soar-sl-tap/tap/sync"
DEFAULT_DATA_URL = "http://soar.esac.esa.int/soar-sl-tap/data"


def query_eui(
    start: str,
    end: str,
    *,
    tap_url: str = DEFAULT_TAP_URL,
    timeout: float = 120,
) -> list[dict]:
    """Query EUI metadata rows from the SOAR TAP service."""

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
    params = urllib.parse.urlencode(
        {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "json", "QUERY": query}
    )
    with urllib.request.urlopen(f"{tap_url}?{params}", timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    names = [item["name"] for item in payload["metadata"]]
    return [dict(zip(names, row, strict=False)) for row in payload["data"]]


def unique_rows(rows: list[dict]) -> list[dict]:
    """Deduplicate metadata joins by SOAR ``data_item_id`` in input order."""

    seen: dict[object, dict] = {}
    for row in rows:
        seen.setdefault(row["data_item_id"], row)
    return list(seen.values())


def print_eui_summary(rows: list[dict]) -> None:
    """Print the selection summary used by the historical script."""

    unique = unique_rows(rows)
    print(f"metadata rows: {len(rows)}")
    print(f"unique files:  {len(unique)}")
    total_mb = sum((row.get("filesize") or 0) for row in unique) / 1024 / 1024
    print(f"total size:    {total_mb:.2f} MB")
    print()

    groups: dict[tuple, list[dict]] = defaultdict(list)
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
        print(
            f"{key}: n={len(group)} size={size_mb:.2f} MB "
            f"first={group[0]['begin_time']} last={group[-1]['begin_time']}"
        )


def download_eui_rows(
    rows: list[dict],
    output_dir: str | Path,
    *,
    descriptor: str | None = None,
    data_url: str = DEFAULT_DATA_URL,
) -> None:
    """Download unique SOAR EUI rows, optionally restricted by descriptor."""

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    selected = unique_rows(rows)
    if descriptor:
        selected = [row for row in selected if row["descriptor"] == descriptor]
    for index, row in enumerate(selected, start=1):
        params = urllib.parse.urlencode(
            {
                "retrieval_type": "LAST_PRODUCT",
                "product_type": "SCIENCE",
                "data_item_id": row["data_item_id"],
            }
        )
        target = root / row["filename"]
        action = (
            "exists" if target.exists() and target.stat().st_size > 0 else "download"
        )
        print(f"[{index}/{len(selected)}] {action} {target}")
        download_url(
            f"{data_url}?{params}",
            target,
            timeout=300,
            chunk_size=1024 * 1024,
            redownload_empty=True,
        )


__all__ = [
    "DEFAULT_DATA_URL",
    "DEFAULT_TAP_URL",
    "download_eui_rows",
    "print_eui_summary",
    "query_eui",
    "unique_rows",
]
