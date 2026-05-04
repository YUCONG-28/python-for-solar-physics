# Project Structure

This repository follows a lightweight research-tool layout rather than a full application layout.

```text
solar_toolkit/   Reusable Python helpers and package metadata
scripts/         Runnable research workflows grouped by instrument/task
examples/        Local-data examples and historical development workflows
tests/           Data-independent pytest tests
configs/         Example configuration files for local paths
docs/            Project documentation
```

## Scripts

- `scripts/aia_hmi/`: SDO/AIA and SDO/HMI imaging, difference imaging, light curves, time-distance analysis, and overlays.
- `scripts/radio/`: CSO spectra, radio source maps, and AIA/radio/HMI overlays.
- `scripts/xray_dem/`: GOES SXR, HXR, ASO-S/HXI, DEM, and combined diagnostics.
- `scripts/lasco_cme/`: SOHO/LASCO downloads, plotting, and running-difference CME images.
- `scripts/tools/`: General-purpose utilities.

## Tests vs Examples

Tests must be lightweight and independent of local observation data. Workflows that require FITS, NetCDF, JP2, CSV, or other local science data belong in `examples/` or `scripts/`, not `tests/`.
