# Newkirk Plane-Of-Sky Projection Schematic Report

Date: 2026-05-27

## Added Files

- `scripts/radio/core/radio_io.py`
  - Neutral I/O, datetime, output-path, diagnostic-field, and dataframe helpers.
- `scripts/radio/core/radio_coordinates.py`
  - Neutral arcsec/Rsun conversion, radial-vector validation, residual, extent,
    and pixel/data coordinate helpers.
- `scripts/radio/core/radio_newkirk_spatial.py`
  - Builds the optional Gaussian/Newkirk plane-of-sky projection dataframe.
- `scripts/radio/core/radio_aia171_spatial_plot.py`
  - Plots AIA 171 background, Gaussian centers, FWHM ellipses, Newkirk projected
    positions, residual arrows, type III trajectory, and spike scatter points.
- `tests/test_radio_newkirk_spatial.py`
  - Covers Newkirk radius ordering, radial projection, residuals, NaN handling,
    near-disk-center invalid geometry, unknown source-type fallback, and invalid
    Gaussian-row retention.
- `scripts/radio/docs/PHASE1_IMPORT_AND_TEST_BASELINE_REPORT.md`
- `scripts/radio/docs/PHASE3_CORE_LEGACY_DEPENDENCY_REDUCTION_REPORT.md`

## Modified Files

- `scripts/radio/run_radio_burst_pipeline.py`
  - Keeps the optional Newkirk plane-of-sky projection product behind
    `NEWKIRK_SPATIAL_CONFIG["enable"]`.
- `scripts/radio/configs/__init__.py`
  - Adds `load_newkirk_spatial_config`.
- `scripts/radio/configs/radio_20250124_config.py`
  - Adds `NEWKIRK_SPATIAL_CONFIG`.
- `scripts/radio/core/radio_gaussian_fit.py`
- `scripts/radio/core/radio_spectrogram.py`
- `scripts/radio/core/radio_drift_rate.py`
  - Replace neutral legacy helper imports with `radio_io.py` and
    `radio_coordinates.py`.
- `tests/test_radio_newkirk_extrapolation.py`
- `tests/test_radio_pipeline_modules.py`
  - Update imports for the `scripts.radio.core` package layout.
- `README.md`
- `scripts/radio/docs/RADIO_ENTRYPOINTS.md`

## Added Outputs

When `NEWKIRK_SPATIAL_CONFIG["enable"]` is true, the full pipeline can write
the following illustrative products:

- `gaussian_newkirk_projection_schematic_table.csv`
- `aia171_typeIII_spike_newkirk_projection_schematic.png`

If `aia171_path` is missing or AIA loading fails, the PNG is skipped and the CSV
is still saved.

## Newkirk Density-to-Radius Logic

The physics starts from the plasma-frequency relation to infer electron density
from observing frequency and harmonic choice. The Newkirk density model then
maps density to heliocentric radius using the configured multiplier. Lower
frequencies map to lower densities and therefore larger Newkirk radii.

## Plane-of-Sky Radial Anchoring

Newkirk gives density as a function of heliocentric radius only; it does not
determine a unique 2D position on an AIA image. The spatial diagnostic therefore
uses the observed Gaussian radio center as a plane-of-sky radial anchor. The
Gaussian center direction defines the projected radial direction, and the
Newkirk radius defines the projected model point along that direction.

## Gaussian/Newkirk Projection Schematic

For each Gaussian diagnostic row, the projection table records observed
Gaussian center coordinates in arcsec and Rsun, the Newkirk radius/height, the
projected Newkirk position, and residuals in both Rsun and arcsec. This is an
illustrative plane-of-sky projection only, not a physical 2D reconstruction.
Invalid Gaussian rows remain in the table with `geometry_valid=False` and a
clear `geometry_reason`.

## Tests Run

- Bundled Python compile check:

```powershell
& '<USER_HOME>\.cache\runtime-cache\codex-primary-runtime\dependencies\python\python.exe' -m compileall scripts\radio
```

- Direct test harnesses, used because `pytest` is not installed in the bundled
  runtime:

```powershell
$env:PYTHONPATH='<PROJECT_ROOT>\Python'
& '<USER_HOME>\.cache\runtime-cache\codex-primary-runtime\dependencies\python\python.exe' tests\test_radio_newkirk_extrapolation.py
& '<USER_HOME>\.cache\runtime-cache\codex-primary-runtime\dependencies\python\python.exe' tests\test_radio_newkirk_spatial.py
```

## Remaining Risks

- AIA WCS correctness: the plot uses SunPy loading and FITS header-derived
  solar-X/solar-Y extents, but event-specific WCS parity should be visually
  checked against known AIA/radio overlays.
- Coordinate orientation: no vertical flip is applied; any future WCSAxes
  migration should preserve this explicitly.
- Harmonic choice: spatial output uses `NEWKIRK_SPATIAL_CONFIG["harmonic"]`.
- Newkirk multiplier choice: spatial output uses
  `NEWKIRK_SPATIAL_CONFIG["newkirk_multiplier"]`.
- Source-type classification: explicit `source_type`/`burst_type`/`type`
  columns are preferred; otherwise config windows/ranges are used, and unknown
  rows remain labeled `unknown`.
- Gaussian fit quality thresholds: unchanged from the existing Gaussian
  workflow; low-quality rows remain in the comparison table but are marked
  invalid for geometry.
