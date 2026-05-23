#!/usr/bin/env python3
"""Download GOES-16/18 SUVI L2 composite images for 2025-01-24 04:00-05:00 UT."""

from __future__ import annotations

import html.parser
import os
import re
import sys
import urllib.request
from pathlib import Path

BASE = "https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/goes"
SATELLITES = ("goes16", "goes18")
CHANNELS = ("094", "131", "171", "195", "284", "304")
DATE_PATH = "2025/01/24"
DATE_STAMP = "20250124"
START_MIN = "040000"
START_MAX = "045959"
OUT_ROOT = Path(os.getenv("SUVI_DATA_ROOT", "data/raw/suvi"))


class LinkParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for key, value in attrs:
            if key == "href" and value:
                self.links.append(value)


def list_links(url: str) -> list[str]:
    with urllib.request.urlopen(url, timeout=60) as response:
        text = response.read().decode("utf-8", errors="replace")
    parser = LinkParser()
    parser.feed(text)
    return parser.links


def wanted_file(name: str, satellite: str, channel: str) -> bool:
    sat_num = satellite.removeprefix("goes")
    pattern = (
        rf"^dr_suvi-l2-ci{channel}_g{sat_num}_"
        rf"s{DATE_STAMP}T(\d{{6}})Z_e.*_v[\d-]+\.fits$"
    )
    match = re.match(pattern, name)
    if not match:
        return False
    return START_MIN <= match.group(1) <= START_MAX


def download(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        return False
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as response, tmp.open("wb") as fh:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            fh.write(chunk)
    tmp.replace(dest)
    return True


def main() -> int:
    total = 0
    downloaded = 0
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    for satellite in SATELLITES:
        for channel in CHANNELS:
            url = f"{BASE}/{satellite}/l2/data/suvi-l2-ci{channel}/{DATE_PATH}/"
            out_dir = OUT_ROOT / satellite / f"ci{channel}" / DATE_STAMP
            out_dir.mkdir(parents=True, exist_ok=True)
            links = list_links(url)
            files = sorted(
                link for link in links if wanted_file(link, satellite, channel)
            )
            print(f"{satellite} ci{channel}: {len(files)} files", flush=True)
            for filename in files:
                total += 1
                if download(url + filename, out_dir / filename):
                    downloaded += 1
                    print(f"  downloaded {filename}", flush=True)
    print(f"Done. matched={total}, newly_downloaded={downloaded}, root={OUT_ROOT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
