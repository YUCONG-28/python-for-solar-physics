"""Compatibility launcher for the package-owned Neupert timing recipe."""

from solar_toolkit.xray_dem.cli import neupert_timing_main as main

__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
