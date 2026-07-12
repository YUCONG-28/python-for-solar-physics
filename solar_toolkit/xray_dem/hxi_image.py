"""ASO-S/HXI FITS image plotting recipe."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from typing import Any

from solar_toolkit.path_config import load_script_config

from .aia_hxi_overlay import convert_date

DEFAULT_CONFIG = {"file_path": ("data/hxi/image_cube.fits")}


def run_hxi_image_plot(config: Mapping[str, Any] | None = None) -> None:
    """Plot the first image plane from the configured HXI FITS cube."""

    import matplotlib.pyplot as plt
    import sunpy.map
    from astropy.io import fits

    resolved = (
        dict(config)
        if config is not None
        else load_script_config("asos_hxi_image_plot", DEFAULT_CONFIG)
    )
    with fits.open(resolved["file_path"]) as hdul:
        for index in range(1):
            header = hdul[index].header
            print(header)
            header["CUNIT1"] = "arcsec"
            header["CUNIT2"] = "arcsec"
            if "WAVELNTH" in header:
                del header["WAVELNTH"]
            if "DATE_OBS" in header:
                header["DATE_OBS"] = convert_date(header["DATE_OBS"])
            if "DATE-OBS" in header:
                header["DATE-OBS"] = convert_date(header["DATE-OBS"])
            hxi_map = sunpy.map.Map(hdul[index].data, header)
            hxi_map.plot()
            plt.text(10, 80, header["ENERGY_H"], color="white")
            plt.show()


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the HXI image recipe."""

    return argparse.ArgumentParser(description="Plot an ASO-S/HXI FITS image.")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the HXI image plotting recipe."""

    build_parser().parse_known_args(argv)
    run_hxi_image_plot()
    return 0


__all__ = [
    "DEFAULT_CONFIG",
    "build_parser",
    "convert_date",
    "main",
    "run_hxi_image_plot",
]


if __name__ == "__main__":
    raise SystemExit(main())
