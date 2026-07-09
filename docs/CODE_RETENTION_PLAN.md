# Code Retention Plan

Last updated: 2026-05-30

This document is the current high-level code-retention plan. It replaces the
older Phase 1 classification notes whose file paths and recommendations no
longer matched the restructured workspace.

For deletion rules and local artifact handling, prefer
`FINAL_CODE_RETENTION_AND_REMOVAL_PLAN.md` and
`LEGACY_AND_REVIEW_FILES.md`.

## Retention Policy

- Keep recommended public entrypoints in `README.md` and `docs/script_index.md`.
- Keep compatibility wrappers when old commands or import paths may still be
  used by local workflows.
- Keep historical scientific scripts until real-data output parity is verified.
- Keep local products and manual selections out of Git, but do not delete them
  automatically.
- Remove only reproducible cache and temporary artifacts without further review.

## Main Code To Keep

| Area | Current main code |
| --- | --- |
| AIA EUV images, mosaics, and differences | `scripts/aia_hmi/run_aia_euv_processor.py` |
| AIA EUV compatibility | `scripts/aia_hmi/sdo_aia_euv_processor.py` |
| Radio burst pipeline | `scripts/radio/run_radio_burst_pipeline.py` |
| Radio source maps | `scripts/radio/run_radio_source_map.py` |
| AIA/radio/HMI overlays | `scripts/radio/run_aia_radio_hmi_overlay.py` |
| CSO spectrograms | `scripts/radio/legacy/cso_radio_spectrogram_plot.py` |
| Gaussian fitting utility | `scripts/tools/gaussian_source_fitting.py` |
| Shared helpers | `solar_toolkit/` |

## Core Module Areas

| Area | Current module boundary |
| --- | --- |
| AIA/HMI | `scripts/aia_hmi/core/` for config, CLI, I/O, difference helpers, mosaic helpers, and runtime dispatch. |
| Radio | `solar_toolkit/radio/` for reusable helpers, with `scripts/radio/core/` retained as deprecated compatibility aliases for historical imports. |
| Shared toolkit | `solar_toolkit/` for reusable package-level helpers. |
| Config templates | `configs/*.example.yaml` for public examples; local path configs stay ignored. |

## Legacy And Compatibility Code

These files are intentionally retained:

- `legacy/scripts/aia_hmi/sdo_aia_base_difference.py`
- `legacy/scripts/aia_hmi/sdo_aia_running_difference.py`
- `scripts/aia_hmi/sdo_aia_hmi_overlay.py`
- `scripts/aia_hmi/sdo_aia_time_distance_diagram.py`
- `scripts/radio/legacy/radio_source_map_plot_gaussian_overlay.py`
- `scripts/radio/legacy/sdo_aia_radio_hmi_overlay.py`
- `examples/radio_aia_hmi/aia_radio_hmi_overlay_demo.py`

They may preserve historical parameters, publication settings, or behavior that
has not yet been compared against the recommended wrappers.

## Not Automatic Cleanup

Do not automatically delete:

- `AIA.xlsx`
- `CSO.xlsx`
- root-level PNG figures
- `archive/`
- `data dowload/`
- `scripts/radio/outputs/`
- `.automated-tool*`
- `.vscode/`
- any FITS, JP2, NetCDF, CSV, JSON selection, PNG, MP4, or local output that may
  belong to a research run.

## Next Retention Work

1. Add real-data output comparison before removing any old scientific workflow.
2. Consider a verified wrapper for the CSO spectrogram entrypoint.
3. Continue moving reusable logic into `core/` modules only when tests cover the
   public behavior.
4. Keep README and `docs/README.md` as the entrypoints for documentation
   navigation.
