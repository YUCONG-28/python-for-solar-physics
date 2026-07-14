"""STEREO-A/EUVI archive search and download workflow."""

from __future__ import annotations

from pathlib import Path

from .downloads import download_url

DEFAULT_BASE_URL = "https://stereo-ssc.nascom.nasa.gov/data/ins_data"


def download_stereo_euvi(
    *,
    start: str,
    end: str,
    output_dir: str | Path,
    base_url: str = DEFAULT_BASE_URL,
) -> int:
    """Search SunPy/Fido for STEREO-A EUVI files and download the selection."""

    from sunpy.net import Fido
    from sunpy.net import attrs as a

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    result = Fido.search(
        a.Time(start, end),
        a.Instrument("EUVI"),
        a.Source("STEREO_A"),
    )
    records = sorted(str(row["fileid"]) for row in result[0])
    manifest = root / "selected_files.txt"
    manifest.write_text(
        "# STEREO-A SECCHI/EUVI files\n"
        f"# time_range={_as_iso_z(start)}/{_as_iso_z(end)}\n"
        + "\n".join(records)
        + "\n",
        encoding="utf-8",
    )

    downloaded = 0
    existing = 0
    failed: list[tuple[str, str]] = []
    for index, file_id in enumerate(records, start=1):
        filename = Path(file_id).name
        url = f"{base_url.rstrip('/')}/{file_id.lstrip('/')}"
        destination = root / filename
        try:
            result = download_url(
                url,
                destination,
                timeout=180,
                chunk_size=1024 * 1024,
                redownload_empty=True,
            )
            status = "downloaded" if result.status == "downloaded" else "exists"
            if status == "downloaded":
                downloaded += 1
            else:
                existing += 1
            print(f"[{index:02d}/{len(records)}] {status}: {filename}", flush=True)
        except Exception as exc:
            failed.append((file_id, str(exc)))
            print(
                f"[{index:02d}/{len(records)}] failed: {filename}: {exc}",
                flush=True,
            )

    print(
        f"Done. total={len(records)} downloaded={downloaded} "
        f"existing={existing} failed={len(failed)}"
    )
    if failed:
        failure_log = root / "download_failed.txt"
        failure_log.write_text(
            "\n".join(f"{file_id}\t{error}" for file_id, error in failed) + "\n",
            encoding="utf-8",
        )
        print(f"failed_log={failure_log}")
        return 1
    return 0


def _as_iso_z(value: str) -> str:
    normalized = value.strip().replace(" ", "T")
    if normalized.endswith("Z"):
        return normalized
    time_part = normalized.partition("T")[2]
    if time_part.count(":") == 1:
        normalized += ":00"
    return normalized + "Z"


__all__ = ["DEFAULT_BASE_URL", "download_stereo_euvi"]
