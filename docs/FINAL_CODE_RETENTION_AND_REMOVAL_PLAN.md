# Final Code Retention And Removal Plan

Last updated: 2026-05-30

This plan records the current retention and removal boundary after the AIA/HMI
radio-style restructuring. It replaces the older Phase 4 snapshot, whose file
lists still referenced paths that have since moved, been archived, or been
deleted.

## Retention Rules

1. Keep public entrypoints and compatibility wrappers until real-data output
   parity has been verified.
2. Keep historical scientific scripts when they may preserve ROI, color-limit,
   contour, timing, FITS/WCS, or output-naming behavior.
3. Remove only reproducible generated artifacts automatically: Python caches,
   lint/test caches, temporary pytest products, and empty scratch directories.
4. Do not delete local scientific products, manual selections, Excel workbooks,
   root display images, ignored archive folders, or tool configuration without
   explicit user confirmation. Generated-looking products may be untracked from
   Git when they remain available as ignored local files.
5. Treat the current radio config changes in the working tree as user work; do
   not fold them into this cleanup plan.

## Current Main Entrypoints

| Area | Keep | Reason |
| --- | --- | --- |
| AIA EUV processing | `scripts/aia_hmi/run_aia_euv_processor.py` | Recommended AIA entrypoint for single-band, mosaic, preview, and difference products. |
| AIA EUV compatibility | `scripts/aia_hmi/sdo_aia_euv_processor.py` | Historical command/import path retained as a lightweight wrapper. |
| Radio burst workflow | `scripts/radio/run_radio_burst_pipeline.py` | Recommended full radio source, Gaussian, drift, and Newkirk workflow. |
| Radio source maps | `scripts/radio/run_radio_source_map.py` | Recommended quick source-map and Gaussian overlay workflow. |
| AIA/radio/HMI overlay | `scripts/radio/run_aia_radio_hmi_overlay.py` | Recommended context overlay workflow. |
| CSO spectrogram compatibility | `scripts/radio/legacy/cso_radio_spectrogram_plot.py` | Current CSO dynamic-spectrum entrypoint until a verified wrapper exists. |
| FITS rename utility | `scripts/aia_hmi/sdo_aia_hmi_fits_rename.py` | Data-preparation utility covered by lightweight tests. |
| Video utility | `scripts/tools/image_sequence_to_video.py` | General non-scientific media utility. |

## Current Core Modules To Keep

| Area | Keep | Reason |
| --- | --- | --- |
| Shared package | `solar_toolkit/` | Shared path, coordinate, CSO, Gaussian, and analysis helpers. |
| AIA/HMI core | `scripts/aia_hmi/core/` | New AIA/HMI config, CLI, I/O, difference, mosaic, and dispatcher boundary. |
| Radio core | `scripts/radio/core/` | Existing extracted Gaussian, spectrogram, drift, Newkirk, coordinate, and plotting helpers. |
| Config templates | `configs/*.example.yaml` | Public examples for future path and workflow configuration. |
| Tests | `tests/` | Lightweight data-independent regression tests. |

## Historical Or Review Files To Keep

| Path | Decision |
| --- | --- |
| `legacy/scripts/aia_hmi/sdo_aia_base_difference.py` | Keep for base-difference default comparison. |
| `legacy/scripts/aia_hmi/sdo_aia_running_difference.py` | Keep for running-difference default comparison. |
| `scripts/aia_hmi/sdo_aia_hmi_overlay.py` | Keep until HMI overlay behavior is compared with current workflows. |
| `scripts/aia_hmi/sdo_aia_time_distance_diagram.py` | Keep as legacy-risk demonstration code. |
| `scripts/radio/legacy/radio_source_map_plot_gaussian_overlay.py` | Keep as compatibility implementation behind the radio source-map wrapper. |
| `scripts/radio/legacy/sdo_aia_radio_hmi_overlay.py` | Keep as compatibility implementation behind the overlay wrapper. |
| `examples/radio_aia_hmi/aia_radio_hmi_overlay_demo.py` | Keep as the public overlay example. |

## Automatic Removal Targets

These may be deleted whenever they appear, because they are reproducible
generated artifacts:

- `__pycache__/`
- `*.pyc`
- `.pytest_cache/`
- pytest temporary directories such as `outputs/pytest-tmp-codex*`
- `.ruff_cache/`
- `.mypy_cache/`
- `pytest-cache-files-*`
- `tmp/` and other empty scratch directories
- empty stray marker files with no path references, such as the removed
  `fit_min_mask_pixels` file

## Manual Confirmation Required

Do not delete the following local files or folders without explicit user
confirmation:

- `AIA.xlsx`
- `CSO.xlsx`
- `HXR.png`
- `SXR.png`
- `SXR to HXR.png`
- `SXR to HXR enhance.png`
- root `spectrogram_drift_rate_*` JSON/PNG products
- `archive/`
- `data dowload/`
- `scripts/radio/outputs/`
- `.automated-tool*`
- `.vscode/`
- any FITS, JP2, NetCDF, CSV, PNG, MP4, JSON selection, or local output that may
  be part of a research run.

## Checks Before Any Future Deletion

Before deleting or moving a scientific file:

1. Search current docs, tests, scripts, examples, and local notes for references
   to the path.
2. Confirm the user no longer runs the path directly.
3. Preserve unique ROI, wavelength, frequency, color-limit, contour, timing,
   WCS, output-name, and output-directory behavior in docs or config.
4. Run lightweight import/compile tests and, for scientific plot paths, compare
   real-data outputs before claiming parity.
5. Stage only reviewed files explicitly; do not use broad staging commands.
