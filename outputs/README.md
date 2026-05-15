# Generated Outputs

This directory documents the expected place for local generated products, but
large science outputs should not be committed.

Typical local products include:

- AIA, HMI, radio, DEM/Tb, and LASCO PNG figures
- Difference-image sequences
- Overlay figures for event analysis
- MP4 videos made from image sequences
- Temporary CSV, Excel, FITS, NetCDF, or NumPy data products

Use this folder, or a path configured in `configs/paths.local.yaml`, for local
analysis outputs. Keep reproducible scripts and configuration templates in Git,
and keep generated products local.
