"""Compatibility facade for the package-owned Neupert comparison recipe."""

from solar_toolkit.xray_dem._neupert_comparison import (
    CustomLogFormatter,
    calculate_derivative,
    get_available_fonts,
    init_plt_settings,
    load_sxr_data,
    plot_derivative,
    plot_flux_comparison,
    smooth_flux_data,
    visualize_results,
)
from solar_toolkit.xray_dem.cli import neupert_comparison_main as main

__all__ = [
    "CustomLogFormatter",
    "calculate_derivative",
    "get_available_fonts",
    "init_plt_settings",
    "load_sxr_data",
    "main",
    "plot_derivative",
    "plot_flux_comparison",
    "smooth_flux_data",
    "visualize_results",
]


if __name__ == "__main__":
    raise SystemExit(main())
