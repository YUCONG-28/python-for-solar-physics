"""Compatibility launcher for the package-owned GOES SXR light-curve recipe."""

from solar_toolkit.xray_dem.cli import goes_lightcurve_main as main

__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
