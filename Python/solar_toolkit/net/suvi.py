"""GOES/SUVI archive selection and download workflows."""

from __future__ import annotations

import re
import urllib.parse
from collections.abc import Sequence
from pathlib import Path

from .downloads import download_url, fetch_text
from .links import collect_links

DEFAULT_BASE_URL = (
    "https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/goes"
)
DEFAULT_SATELLITES = ("goes16", "goes18")
DEFAULT_CHANNELS = ("094", "131", "171", "195", "284", "304")


def list_remote_links(url: str, *, timeout: float = 60) -> list[str]:
    """Return absolute links from an archive directory listing."""

    return collect_links(fetch_text(url, timeout=timeout), base_url=url)


def is_suvi_file_in_window(
    name: str,
    *,
    satellite: str,
    channel: str,
    date_stamp: str,
    start_hms: str,
    end_hms: str,
) -> bool:
    """Return whether a SUVI filename matches a channel and time window."""

    sat_num = satellite.removeprefix("goes")
    pattern = (
        rf"^dr_suvi-l2-ci{re.escape(channel)}_g{re.escape(sat_num)}_"
        rf"s{re.escape(date_stamp)}T(\d{{6}})Z_e.*_v[\d-]+\.fits$"
    )
    match = re.match(pattern, Path(name).name)
    return bool(match and start_hms <= match.group(1) <= end_hms)


def download_goes_suvi(
    *,
    output_root: str | Path,
    date_path: str,
    date_stamp: str,
    start_hms: str,
    end_hms: str,
    base_url: str = DEFAULT_BASE_URL,
    satellites: Sequence[str] = DEFAULT_SATELLITES,
    channels: Sequence[str] = DEFAULT_CHANNELS,
) -> tuple[int, int]:
    """Download matching GOES/SUVI composites and return matched/new counts."""

    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    matched = 0
    downloaded = 0
    for satellite in satellites:
        for channel in channels:
            directory_url = (
                f"{base_url.rstrip('/')}/{satellite}/l2/data/"
                f"suvi-l2-ci{channel}/{date_path.strip('/')}/"
            )
            output_dir = root / satellite / f"ci{channel}" / date_stamp
            output_dir.mkdir(parents=True, exist_ok=True)
            urls = sorted(
                url
                for url in list_remote_links(directory_url)
                if is_suvi_file_in_window(
                    urllib.parse.urlsplit(url).path,
                    satellite=satellite,
                    channel=channel,
                    date_stamp=date_stamp,
                    start_hms=start_hms,
                    end_hms=end_hms,
                )
            )
            print(f"{satellite} ci{channel}: {len(urls)} files", flush=True)
            for url in urls:
                filename = Path(urllib.parse.urlsplit(url).path).name
                matched += 1
                result = download_url(
                    url,
                    output_dir / filename,
                    timeout=120,
                    chunk_size=1024 * 1024,
                    redownload_empty=True,
                )
                if result.status == "downloaded":
                    downloaded += 1
                    print(f"  downloaded {filename}", flush=True)
    print(f"Done. matched={matched}, newly_downloaded={downloaded}, root={root}")
    return matched, downloaded


__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_CHANNELS",
    "DEFAULT_SATELLITES",
    "download_goes_suvi",
    "is_suvi_file_in_window",
    "list_remote_links",
]
