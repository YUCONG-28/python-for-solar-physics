"""Download selected SDO/AIA level-1 EUV FITS files from JSOC.

This event-specific helper fetches 211 A and 304 A records for
2025-01-24 04:00-05:00 UTC and writes a URL manifest beside the downloads.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import Request, urlopen

import drms

OUT = Path.home() / "data" / "aia" / "20250124_2"
BASE = "https://jsoc1.stanford.edu"
SERIES = "aia.lev1_euv_12s"
TIMERANGE = "2025.01.24_04:00:00_UTC/1h"
WAVES = [211, 304]
MAX_WORKERS = 2


def collect_records() -> list[tuple[str, Path]]:
    client = drms.Client()
    records = []
    for wave in WAVES:
        recset = f"{SERIES}[{TIMERANGE}][{wave}]"
        keys, segs = client.query(recset, key="T_REC,WAVELNTH,QUALITY", seg="image")
        for row, seg in zip(
            keys.to_dict("records"), segs["image"].tolist(), strict=False
        ):
            if int(row.get("QUALITY", 0)) != 0:
                print(
                    f"skip quality {row['QUALITY']}: {row['T_REC']} {wave}", flush=True
                )
                continue
            trec = str(row["T_REC"]).replace("-", "").replace(":", "")
            fname = f"aia_lev1_euv_12s_{trec}_{int(row['WAVELNTH'])}.fits"
            records.append((BASE + seg, OUT / fname))
    return records


def download_one(item: tuple[str, Path]) -> tuple[str, str, int | str]:
    url, path = item
    if path.exists() and path.stat().st_size > 1024:
        return ("exists", path.name, path.stat().st_size)

    tmp = path.with_suffix(path.suffix + ".part")
    last_error = ""
    for attempt in range(1, 4):
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=120) as resp, tmp.open("wb") as handle:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
            if tmp.stat().st_size <= 1024:
                raise RuntimeError(f"download too small: {tmp.stat().st_size}")
            tmp.replace(path)
            return ("done", path.name, path.stat().st_size)
        except Exception as exc:
            last_error = repr(exc)
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass
            time.sleep(2 * attempt)
    return ("failed", path.name, last_error)


def main(argv=None) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    records = collect_records()
    manifest = OUT / "manifest_urls.txt"
    manifest.write_text(
        "\n".join(f"{url} {path.name}" for url, path in records) + "\n",
        encoding="utf-8",
    )
    print(f"records: {len(records)}", flush=True)
    print(f"manifest: {manifest}", flush=True)

    seen = set()
    jobs = []
    for url, path in records:
        if path.name not in seen:
            seen.add(path.name)
            jobs.append((url, path))
    print(f"unique files: {len(jobs)}", flush=True)

    start = time.time()
    done = exists = failed = 0
    failures = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(download_one, job) for job in jobs]
        for i, future in enumerate(as_completed(futures), 1):
            status, name, info = future.result()
            if status == "done":
                done += 1
            elif status == "exists":
                exists += 1
            else:
                failed += 1
                failures.append((name, info))

            if i == 1 or i % 10 == 0 or status == "failed":
                elapsed = time.time() - start
                print(
                    f"progress {i}/{len(jobs)} done={done} exists={exists} "
                    f"failed={failed} elapsed={elapsed:.1f}s last={status}:{name}",
                    flush=True,
                )

    if failures:
        failfile = OUT / "failed_downloads.txt"
        failfile.write_text(
            "\n".join(f"{name}\t{err}" for name, err in failures) + "\n",
            encoding="utf-8",
        )
        print(f"failures written: {failfile}", flush=True)

    print(f"finished done={done} exists={exists} failed={failed}", flush=True)
    print(f"files in dir: {sum(1 for path in OUT.glob('*.fits'))}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
