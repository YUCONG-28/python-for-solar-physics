"""AIA and ASO-S/HXI image-overlay workflow.

This module owns the historical ``sdo_aia_asos_hxi_overlay.py`` behavior.  The
repository script is retained as a module alias and command-line launcher.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from solar_toolkit.path_config import load_script_config

DEFAULT_CONFIG = {
    "input_dir_AIA": "<DATA_ROOT>/JSOCdata/AIA_304/fits/44/",
    "output_dir": "<DATA_ROOT>/HXI_CLEAN/25_4_24/plot/all_pro/304/",
    "hxi_file_path": "<DATA_ROOT>/HXI_CLEAN/25_4_24/10-20.fits",
    "hxi_file_path_pro": "<DATA_ROOT>/HXI_CLEAN/25_4_24/20-30.fits",
}


def convert_date(date_str):
    """Convert the historical HXI date form to an ISO timestamp."""

    try:
        return datetime.strptime(date_str, "%d-%b-%y %H:%M:%S.%f").strftime(
            "%Y-%m-%dT%H:%M:%S.%f"
        )[:-3]
    except ValueError:
        return date_str


def _prepare_hxi_map(hdu: Any):
    """Build a SunPy map from one HXI image HDU using legacy WCS offsets."""

    import sunpy.map

    header = hdu.header
    print(header)
    header["CUNIT1"] = "arcsec"
    header["CUNIT2"] = "arcsec"
    if "WAVELNTH" in header:
        del header["WAVELNTH"]
    if "DATE_OBS" in header:
        header["DATE_OBS"] = convert_date(header["DATE_OBS"])
    if "DATE-OBS" in header:
        header["DATE-OBS"] = convert_date(header["DATE-OBS"])
    header["crpix1"] = 9 + header["crpix1"]
    header["crpix2"] = 1 + header["crpix2"]
    return sunpy.map.Map(hdu.data, header)


def run_aia_hxi_overlay(config: Mapping[str, Any] | None = None) -> None:
    """Render the historical AIA/HXI contour-overlay image sequence."""

    import astropy.units as u
    import matplotlib.colors as colors
    import matplotlib.pyplot as plt
    import numpy as np
    import sunpy.map
    from astropy.coordinates import SkyCoord
    from astropy.io import fits

    resolved = (
        dict(config)
        if config is not None
        else load_script_config("sdo_aia_asos_hxi_overlay", DEFAULT_CONFIG)
    )
    input_dir_aia = Path(resolved["input_dir_AIA"])
    output_dir = Path(resolved["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    aia_file_paths = [
        path for path in input_dir_aia.iterdir() if path.suffix == ".fits"
    ]
    aia_sequence = sunpy.map.Map(aia_file_paths, sequence=True)

    with (
        fits.open(resolved["hxi_file_path"]) as hdul,
        fits.open(resolved["hxi_file_path_pro"]) as hdul_pro,
    ):
        for index in range(0, min(len(aia_sequence), len(hdul))):
            hxi_map = _prepare_hxi_map(hdul[index])
            hxi_map_pro = _prepare_hxi_map(hdul_pro[index])

            for offset in range(4):
                if index + offset >= len(aia_sequence):
                    continue
                aia_image = aia_sequence[4 * index + offset]
                aia_map = sunpy.map.Map(aia_image)
                roi_bottom_left = SkyCoord(
                    Tx=180 * u.arcsec,
                    Ty=-340 * u.arcsec,
                    frame=aia_map.coordinate_frame,
                )
                roi_top_right = SkyCoord(
                    Tx=520 * u.arcsec,
                    Ty=20 * u.arcsec,
                    frame=aia_map.coordinate_frame,
                )
                aia_submap = aia_map.submap(
                    roi_bottom_left,
                    top_right=roi_top_right,
                )

                figure = plt.figure(figsize=(8, 8))
                axes = figure.add_subplot(projection=aia_submap)
                aia_submap.plot(
                    axes=axes,
                    norm=colors.LogNorm(
                        vmin=1,
                        vmax=0.1 * np.max(aia_submap.data),
                    ),
                )
                aia_submap.draw_grid(axes=axes)

                hxi_map.draw_contours(
                    np.array([0.1]) * hxi_map.data.max(),
                    axes=axes,
                    colors=["green"],
                )
                plt.text(10, 550, "10-20-green", color="white", fontsize=16)
                hxi_map_pro.draw_contours(
                    np.array([0.1]) * hxi_map_pro.data.max(),
                    axes=axes,
                    colors=["red"],
                )
                plt.text(10, 500, "20-30-red", color="white", fontsize=16)

                output_path = (
                    output_dir / f"{aia_file_paths[4 * index + offset].stem}.png"
                )
                plt.savefig(output_path, dpi=200, bbox_inches="tight")
                plt.show()


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the AIA/HXI overlay recipe."""

    return argparse.ArgumentParser(
        description="Overlay ASO-S/HXI contours on SDO/AIA images."
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the AIA/HXI overlay recipe."""

    build_parser().parse_known_args(argv)
    run_aia_hxi_overlay()
    return 0


__all__ = [
    "DEFAULT_CONFIG",
    "build_parser",
    "convert_date",
    "main",
    "run_aia_hxi_overlay",
]


if __name__ == "__main__":
    raise SystemExit(main())
