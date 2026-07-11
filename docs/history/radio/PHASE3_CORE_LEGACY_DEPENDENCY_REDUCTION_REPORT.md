# Phase 3 Core-Legacy Dependency Reduction Report

Date: 2026-05-27

## Scope

Phase 3 reduced reverse dependencies from `scripts/radio/core/` back into the
large legacy source-map script. Only neutral helpers were moved into new core
utility modules. No scientific algorithms were intentionally changed.

## Removed Legacy Imports

- `scripts/radio/core/radio_gaussian_fit.py`
  - Removed import of `scripts.radio.legacy.radio_source_map_plot_gaussian_overlay`
    for type aliases, Gaussian diagnostic fields, output-subdirectory naming,
    pixel/data coordinate conversion, roundtrip error calculation, and 2D index
    unraveling.
- `scripts/radio/core/radio_spectrogram.py`
  - Removed import of the legacy source-map script for datetime parsing and
    numeric/time index-range helpers.
- `scripts/radio/core/radio_drift_rate.py`
  - Removed import of the legacy source-map script for datetime parsing,
    drift-output path resolution, and drift diagnostic field names.

## New Helper Locations

- `scripts/radio/core/radio_io.py`
  - Path normalization, output directory creation, JSON/CSV helpers, safe
    dataframe column access, skipped-row/reason helpers, datetime parsing,
    index-range helpers, output-subdirectory selection, drift-output path
    resolution, diagnostic field constants, and radio array type aliases.
- `scripts/radio/core/radio_coordinates.py`
  - Arcsec/Rsun conversion, radial unit-vector validation, plot extent/origin
    validation, residual calculation, pixel/data coordinate conversion,
    roundtrip error calculation, and 2D index unraveling.

## Unchanged Scientific Behaviors

- Gaussian model formulas were not changed.
- Gaussian source mask selection was not changed.
- Background estimation and background-fit behavior were not changed.
- Gaussian quality thresholds and output field names were not changed.
- Spectrogram rebinned-plane behavior and frequency-axis handling were not
  changed.
- Drift-rate interactive selection behavior and saved filenames were not
  changed.
- AIA/HMI/radio WCS/reprojection behavior was not changed.

## Remaining Legacy Dependencies

- `run_radio_burst_pipeline.py` still calls
  `legacy.radio_source_map_plot_gaussian_overlay.main()` for the full
  source-map/Gaussian workflow.
- `run_radio_source_map.py` remains a compatibility wrapper around the legacy
  source-map workflow.
- `run_aia_radio_hmi_overlay.py` remains a compatibility wrapper around the
  legacy AIA/HMI/radio overlay workflow.
- The legacy scripts remain available and were not deleted or renamed.

## Verification

`compileall scripts/radio` was run with the bundled Codex Python because
`python` is not available on PATH in this environment.
