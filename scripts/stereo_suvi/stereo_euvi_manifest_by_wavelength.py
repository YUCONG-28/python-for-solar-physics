#!/usr/bin/env python3
"""Create a wavelength manifest and symlink view for STEREO-A EUVI FITS."""

from __future__ import annotations

import csv
import os
from pathlib import Path

from astropy.io import fits

DATA_DIR = Path(os.getenv("STEREO_EUVI_DATA_DIR", "data/raw/stereo/euvi/20250124"))
LINK_ROOT = DATA_DIR / "by_wavelength"
MANIFEST = DATA_DIR / "manifest_by_wavelength.csv"


def read_metadata(path: Path) -> dict[str, str]:
    header = fits.getheader(path)
    wavelength = header.get("WAVELNTH")
    if wavelength is None:
        raise ValueError(f"No WAVELNTH keyword in {path}")
    return {
        "filename": path.name,
        "path": str(path),
        "date_obs": str(header.get("DATE-OBS", "")),
        "wavelength": str(int(round(float(wavelength)))),
        "detector": str(header.get("DETECTOR", "")),
        "observatory": str(header.get("OBSRVTRY", "")),
        "exptime": str(header.get("EXPTIME", "")),
    }


def make_relative_symlink(target: Path, link: Path) -> None:
    if link.is_symlink():
        if link.resolve() == target.resolve():
            return
        link.unlink()
    elif link.exists():
        raise FileExistsError(f"Refusing to replace non-symlink: {link}")
    relative_target = Path("..") / ".." / target.name
    link.symlink_to(relative_target)


def main() -> None:
    fits_files = sorted(DATA_DIR.glob("*.fts"))
    if not fits_files:
        raise FileNotFoundError(f"No .fts files found in {DATA_DIR}")

    rows = [read_metadata(path) for path in fits_files]
    rows.sort(
        key=lambda row: (int(row["wavelength"]), row["date_obs"], row["filename"])
    )

    with MANIFEST.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "filename",
                "date_obs",
                "wavelength",
                "detector",
                "observatory",
                "exptime",
                "path",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    for row in rows:
        wave_dir = LINK_ROOT / row["wavelength"]
        wave_dir.mkdir(parents=True, exist_ok=True)
        target = DATA_DIR / row["filename"]
        link = wave_dir / row["filename"]
        make_relative_symlink(target, link)

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["wavelength"]] = counts.get(row["wavelength"], 0) + 1

    print(f"manifest={MANIFEST}")
    print(f"link_root={LINK_ROOT}")
    print(f"total={len(rows)}")
    for wavelength in sorted(counts, key=int):
        print(f"{wavelength}: {counts[wavelength]}")


if __name__ == "__main__":
    main()
