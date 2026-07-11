#!/usr/bin/env python3
"""Plot SUVI 2025-01-24 04:48 UT lower-right quadrant images."""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass
from pathlib import Path

import astropy.units as u
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from astropy.coordinates import SkyCoord
from astropy.visualization import AsinhStretch, ImageNormalize, PercentileInterval
from sunpy.map import Map
from sunpy.util.exceptions import SunpyMetadataWarning, SunpyUserWarning

DATA_ROOT = Path(os.getenv("SUVI_DATA_ROOT", "data/raw/suvi"))
OUT_ROOT = Path(os.getenv("SUVI_PRODUCT_DIR", "data/products/suvi"))
DATE_STAMP = "20250124"
TARGET_START = "044800"
SATELLITES = ("goes16", "goes18")
CHANNELS = ("094", "131", "171", "195", "284", "304")


@dataclass(frozen=True)
class SuviSelection:
    satellite: str
    sat_short: str
    channel: str
    path: Path


def find_suvi_files() -> list[SuviSelection]:
    selections: list[SuviSelection] = []
    for satellite in SATELLITES:
        sat_short = f"g{satellite.removeprefix('goes')}"
        for channel in CHANNELS:
            pattern = (
                DATA_ROOT
                / satellite
                / f"ci{channel}"
                / DATE_STAMP
                / f"dr_suvi-l2-ci{channel}_{sat_short}_s{DATE_STAMP}T{TARGET_START}Z*.fits"
            )
            matches = sorted(pattern.parent.glob(pattern.name))
            if len(matches) != 1:
                raise FileNotFoundError(
                    f"Expected exactly one file for {satellite} ci{channel}, found {len(matches)}: {matches}"
                )
            selections.append(SuviSelection(satellite, sat_short, channel, matches[0]))
    return selections


def lower_right_quadrant(suvi_map):
    bottom_left = SkyCoord(
        Tx=0 * u.arcsec,
        Ty=suvi_map.bottom_left_coord.Ty,
        frame=suvi_map.coordinate_frame,
    )
    top_right = SkyCoord(
        Tx=suvi_map.top_right_coord.Tx,
        Ty=0 * u.arcsec,
        frame=suvi_map.coordinate_frame,
    )
    return suvi_map.submap(bottom_left, top_right=top_right)


def make_norm(cropped_map):
    data = cropped_map.data
    finite_positive = data[(data > 0) & (data == data)]
    if finite_positive.size == 0:
        return ImageNormalize(
            data, interval=PercentileInterval(99.7), stretch=AsinhStretch()
        )
    return ImageNormalize(
        finite_positive, interval=PercentileInterval(99.7), stretch=AsinhStretch()
    )


def obs_stamp(suvi_map) -> str:
    return suvi_map.date.strftime("%Y%m%d_%H%M%S")


def title_for(selection: SuviSelection, suvi_map) -> str:
    wave = int(round(suvi_map.wavelength.to_value(u.Angstrom)))
    return f"{selection.sat_short.upper()} SUVI {wave} A | {suvi_map.date.strftime('%Y-%m-%d %H:%M:%S')} UT"


def output_name(selection: SuviSelection, suvi_map) -> str:
    return (
        f"suvi_{selection.sat_short}_ci{selection.channel}_"
        f"{obs_stamp(suvi_map)}_lower_right_quarter.png"
    )


def plot_single(selection: SuviSelection, cropped_map, norm) -> Path:
    fig = plt.figure(figsize=(6.2, 5.6))
    ax = fig.add_subplot(projection=cropped_map)
    im = cropped_map.plot(axes=ax, norm=norm, title=False)
    ax.set_title(title_for(selection, cropped_map), fontsize=11)
    ax.set_xlabel("Helioprojective X (arcsec)")
    ax.set_ylabel("Helioprojective Y (arcsec)")
    ax.coords.grid(color="white", alpha=0.25, linestyle="--", linewidth=0.6)
    cbar = fig.colorbar(im, ax=ax, pad=0.03, fraction=0.05)
    cbar.set_label("Intensity")
    fig.tight_layout()

    out_path = OUT_ROOT / output_name(selection, cropped_map)
    fig.savefig(out_path, dpi=250, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_overview(items: list[tuple[SuviSelection, object, object]]) -> Path:
    fig = plt.figure(figsize=(15.0, 10.0))
    for idx, (selection, cropped_map, norm) in enumerate(items, start=1):
        ax = fig.add_subplot(2, 6, idx, projection=cropped_map)
        cropped_map.plot(axes=ax, norm=norm, title=False, annotate=False)
        ax.set_title(title_for(selection, cropped_map), fontsize=9)
        ax.coords.grid(color="white", alpha=0.22, linestyle="--", linewidth=0.5)
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.tick_params(labelsize=7)
        if idx not in (1, 7):
            ax.coords[1].set_ticklabel_visible(False)
        if idx <= 6:
            ax.coords[0].set_ticklabel_visible(False)

    fig.suptitle("SUVI lower-right quadrant | 2025-01-24 04:48 UT", fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    out_path = (
        OUT_ROOT
        / "suvi_g16_g18_all_channels_20250124_0448_lower_right_quarter_overview.png"
    )
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out_path


def write_selected_files(selections: list[SuviSelection]) -> Path:
    out_path = OUT_ROOT / "selected_files.txt"
    lines = [
        "# SUVI files used for lower-right quadrant plots",
        "# target_start=2025-01-24T04:48:00Z",
        "",
    ]
    for selection in selections:
        lines.append(f"{selection.sat_short} ci{selection.channel}: {selection.path}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def main(argv=None) -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    warnings.filterwarnings("ignore", category=SunpyUserWarning)
    warnings.filterwarnings("ignore", category=SunpyMetadataWarning)

    selections = find_suvi_files()
    if not all(
        f"s{DATE_STAMP}T{TARGET_START}Z" in str(item.path) for item in selections
    ):
        raise RuntimeError(
            "At least one selected FITS file does not match the requested start time."
        )

    plotted_items = []
    single_outputs = []
    for selection in selections:
        full_map = Map(selection.path)
        cropped_map = lower_right_quadrant(full_map)
        norm = make_norm(cropped_map)
        single_outputs.append(plot_single(selection, cropped_map, norm))
        plotted_items.append((selection, cropped_map, norm))

    overview = plot_overview(plotted_items)
    selected_file_log = write_selected_files(selections)

    print(f"single_png={len(single_outputs)}")
    for out_path in single_outputs:
        print(out_path)
    print(f"overview={overview}")
    print(f"selected_files={selected_file_log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
