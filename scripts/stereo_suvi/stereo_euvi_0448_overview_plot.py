#!/usr/bin/env python3
"""Plot STEREO-A EUVI images nearest 2025-01-24 04:48:30-04:49:00 UT."""

from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path

import astropy.units as u
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from astropy.visualization import AsinhStretch, ImageNormalize, PercentileInterval
from sunpy.map import Map

DATA_DIR = Path(os.getenv("STEREO_EUVI_DATA_DIR", "data/raw/stereo/euvi/20250124"))
MANIFEST = DATA_DIR / "manifest_by_wavelength.csv"
OUT_DIR = Path(os.getenv("STEREO_EUVI_PRODUCT_DIR", "data/products/stereo_euvi"))
TARGET = datetime.fromisoformat("2025-01-24T04:48:45")
WAVELENGTHS = ("171", "195", "284", "304")


def load_manifest() -> list[dict[str, str]]:
    with MANIFEST.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def nearest_file(rows: list[dict[str, str]], wavelength: str) -> Path:
    candidates = [row for row in rows if row["wavelength"] == wavelength]
    if not candidates:
        raise FileNotFoundError(f"No EUVI files found for {wavelength} A")
    best = min(
        candidates,
        key=lambda row: abs(
            (datetime.fromisoformat(row["date_obs"]) - TARGET).total_seconds()
        ),
    )
    return Path(best["path"])


def normalized_map(path: Path):
    euvi_map = Map(path)
    exptime = getattr(euvi_map, "exposure_time", None)
    if exptime is not None and exptime.to_value(u.s) > 0:
        euvi_map = euvi_map / exptime.to_value(u.s)
        euvi_map.meta["bunit"] = "DN/s"
    return euvi_map


def make_norm(euvi_map):
    data = np.asarray(euvi_map.data, dtype=float)
    valid = data[np.isfinite(data) & (data > 0)]
    if valid.size == 0:
        valid = data[np.isfinite(data)]
    return ImageNormalize(
        valid, interval=PercentileInterval(99.7), stretch=AsinhStretch()
    )


def title_for(euvi_map) -> str:
    wave = int(round(euvi_map.wavelength.to_value(u.Angstrom)))
    return f"STEREO-A EUVI {wave} A | {euvi_map.date.strftime('%Y-%m-%d %H:%M:%S')} UT"


def out_name(euvi_map) -> str:
    wave = int(round(euvi_map.wavelength.to_value(u.Angstrom)))
    return f"stereo_a_euvi_{wave}_{euvi_map.date.strftime('%Y%m%d_%H%M%S')}.png"


def plot_single(euvi_map, norm) -> Path:
    fig = plt.figure(figsize=(6.3, 6.0))
    ax = fig.add_subplot(projection=euvi_map)
    im = euvi_map.plot(axes=ax, norm=norm, title=False)
    ax.set_title(title_for(euvi_map), fontsize=11)
    ax.set_xlabel("Helioprojective X (arcsec)")
    ax.set_ylabel("Helioprojective Y (arcsec)")
    ax.coords.grid(color="white", alpha=0.22, linestyle="--", linewidth=0.6)
    cbar = fig.colorbar(im, ax=ax, pad=0.03, fraction=0.045)
    cbar.set_label(euvi_map.meta.get("bunit", "Intensity"))
    fig.tight_layout()
    out = OUT_DIR / out_name(euvi_map)
    fig.savefig(out, dpi=230, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_overview(items) -> Path:
    fig = plt.figure(figsize=(11.5, 10.5))
    for idx, (euvi_map, norm) in enumerate(items, start=1):
        ax = fig.add_subplot(2, 2, idx, projection=euvi_map)
        euvi_map.plot(axes=ax, norm=norm, title=False)
        ax.set_title(title_for(euvi_map), fontsize=10)
        ax.coords.grid(color="white", alpha=0.22, linestyle="--", linewidth=0.5)
        ax.set_xlabel("")
        ax.set_ylabel("")
    fig.suptitle("STEREO-A EUVI nearest 2025-01-24 04:48:30-04:49:00 UT", fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out = OUT_DIR / "stereo_a_euvi_044830_044900_all_wavelengths_overview.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_manifest()
    paths = [nearest_file(rows, wavelength) for wavelength in WAVELENGTHS]
    items = []
    single_outputs = []
    selection_lines = []
    for path in paths:
        euvi_map = normalized_map(path)
        norm = make_norm(euvi_map)
        single_outputs.append(plot_single(euvi_map, norm))
        items.append((euvi_map, norm))
        selection_lines.append(
            f"{int(round(euvi_map.wavelength.to_value(u.Angstrom)))} A,"
            f"{euvi_map.date.isot},{path}"
        )
    overview = plot_overview(items)
    selected = OUT_DIR / "selected_euvi_044830_044900.txt"
    selected.write_text(
        "wavelength,date_obs,path\n" + "\n".join(selection_lines) + "\n",
        encoding="utf-8",
    )

    print(f"single_png={len(single_outputs)}")
    for out in single_outputs:
        print(out)
    print(f"overview={overview}")
    print(f"selected={selected}")


if __name__ == "__main__":
    main()
