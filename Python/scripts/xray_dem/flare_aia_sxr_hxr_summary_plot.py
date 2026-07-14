"""Compatibility facade for the package-owned SXR/HXI/AIA summary recipe."""

from solar_toolkit.xray_dem._flare_summary import (
    load_aia_data,
    load_hxi_data,
    load_sxr_data,
    plot_combined_data,
)
from solar_toolkit.xray_dem.cli import flare_summary_main as main

__all__ = [
    "load_aia_data",
    "load_hxi_data",
    "load_sxr_data",
    "main",
    "plot_combined_data",
]


if __name__ == "__main__":
    raise SystemExit(main())
