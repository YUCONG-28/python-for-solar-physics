"""ASO-S/HXI light-curve comparison plotting recipe."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from typing import Any

from solar_apps.platform.config import load_script_config

from solar_toolkit.xray_dem.hxi import HXI_ENERGY_CHANNELS, load_hxi_lightcurve

DEFAULT_CONFIG = {
    "file_path": "data/hxi/lightcurve.fits",
}


def run_hxi_sxr_comparison(config: Mapping[str, Any] | None = None) -> None:
    """Plot the four historical HXI channels used by the comparison recipe."""

    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    resolved = (
        dict(config)
        if config is not None
        else load_script_config("asos_hxi_goes_sxr_comparison", DEFAULT_CONFIG)
    )
    lightcurve = load_hxi_lightcurve(resolved["file_path"])
    times = lightcurve["times"]

    plt.figure(figsize=(25, 16))
    axes = plt.gca()
    plt.sca(axes)
    for channel in HXI_ENERGY_CHANNELS:
        plt.semilogy(times, lightcurve["data"][channel], label=f"HXI {channel}")

    plt.ylabel("Counts s⁻¹ detector⁻¹", fontsize=22, labelpad=12)
    plt.legend(loc="upper left", ncol=1, fontsize=18)
    axes.xaxis.set_minor_locator(mdates.MinuteLocator())
    axes.xaxis.grid(True, which="minor", linestyle="--", color="gray", alpha=0.5)
    axes.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    plt.gcf().autofmt_xdate()
    plt.xlabel("time", fontsize=22, labelpad=12)
    plt.title("Soft X-ray Flux & HXI lightcurve", fontsize=22, fontweight="bold")
    plt.show()


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the HXI/SXR comparison recipe."""

    return argparse.ArgumentParser(
        description="Plot the historical ASO-S/HXI and GOES/SXR comparison view."
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the HXI/SXR comparison recipe."""

    build_parser().parse_known_args(argv)
    run_hxi_sxr_comparison()
    return 0


__all__ = [
    "DEFAULT_CONFIG",
    "build_parser",
    "main",
    "run_hxi_sxr_comparison",
]


if __name__ == "__main__":
    raise SystemExit(main())
