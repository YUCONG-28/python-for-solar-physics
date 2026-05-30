# Legacy and Review Files

Last updated: 2026-05-30

This file records files and local artifacts that should not be removed during
automatic cleanup. The project is a research workspace, so outputs, manual
selections, and historical scripts may carry scientific context even when they
look redundant.

## Cleanup Rule

Safe automatic cleanup is limited to reproducible generated artifacts such as
`__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, pytest temporary directories,
and other ignored cache folders.

Do not automatically delete, move, or rename scientific scripts, local data
products, Excel workbooks, manual selections, archive folders, or tool
configuration files unless their role has been reviewed.

## Current Compatibility Entrypoints

| Path | Current role | Cleanup decision |
| --- | --- | --- |
| `scripts/aia_hmi/sdo_aia_euv_processor.py` | Historical AIA EUV command and import path. It now delegates to `scripts/aia_hmi/core/`. | Keep as compatibility wrapper. |
| `scripts/radio/legacy/cso_radio_spectrogram_plot.py` | CSO dynamic-spectrum workflow kept as the current compatibility entrypoint; no `run_*.py` wrapper exists yet. | Keep until a verified wrapper exists. |
| `scripts/radio/legacy/radio_source_map_plot_gaussian_overlay.py` | Radio source-map and Gaussian workflow retained behind `run_radio_source_map.py`. | Keep; scientific behavior is sensitive. |
| `scripts/radio/legacy/sdo_aia_radio_hmi_overlay.py` | AIA/radio/HMI overlay workflow retained behind `run_aia_radio_hmi_overlay.py`. | Keep; FITS/WCS and overlay behavior need verified parity before deeper changes. |

## Historical Scripts Kept for Review

| Path | Current role | Cleanup decision |
| --- | --- | --- |
| `legacy/scripts/aia_hmi/sdo_aia_base_difference.py` | Historical AIA base-difference workflow. | Keep for parameter and output comparison. |
| `legacy/scripts/aia_hmi/sdo_aia_running_difference.py` | Historical AIA running-difference workflow. | Keep for parameter and output comparison. |
| `scripts/aia_hmi/sdo_aia_hmi_overlay.py` | Older AIA/HMI contour overlay script. | Keep until HMI matching and contour defaults are compared against current overlay workflows. |
| `scripts/aia_hmi/sdo_aia_time_distance_diagram.py` | AIA time-distance demonstration workflow. | Keep as legacy-risk example; do not treat as a recommended entrypoint. |
| `examples/radio_aia_hmi/aia_radio_hmi_overlay_demo.py` | Small AIA/radio/HMI demonstration script. | Keep as the current public example. |

## Local Artifacts Requiring Manual Review

These paths are ignored by Git or were previously tracked local products. They
were inspected in the current workspace and were not empty, so they are not
automatic deletion targets.

| Path | Observed role | Cleanup decision |
| --- | --- | --- |
| `AIA.xlsx` | Root-level AIA workbook, likely local research data or an intermediate summary. | Do not delete automatically. |
| `CSO.xlsx` | Root-level CSO workbook, likely local research data or an intermediate summary. | Do not delete automatically. |
| `HXR.png` | Root-level display or historical output image, now ignored and left local. | Keep until confirmed as disposable or moved to `docs/assets/images/`. |
| `SXR.png` | Root-level display or historical output image, now ignored and left local. | Keep until confirmed as disposable or moved to `docs/assets/images/`. |
| `SXR to HXR.png` | Root-level display or historical output image, now ignored and left local. | Keep until confirmed as disposable or moved to `docs/assets/images/`. |
| `SXR to HXR enhance.png` | Root-level display or historical output image, now ignored and left local. | Keep until confirmed as disposable or moved to `docs/assets/images/`. |
| Root `spectrogram_drift_rate_*` JSON/PNG files | Drift-selection products from an interactive radio run, now ignored and left local. | Keep local unless regenerated or explicitly discarded. |
| `archive/` | Ignored local archive area with existing files. | Do not delete automatically. |
| `data dowload/` | Ignored local folder with its own `src/`, `docs/`, `data/`, and requirements; the misspelling suggests a historical local copy, but it is not empty. | Do not delete automatically without user confirmation. |
| `scripts/radio/outputs/` | Ignored radio output tree containing drift-selection JSON and related local products. | Keep as local output unless the user confirms it can be regenerated or discarded. |
| `.automated-tool*` | Ignored automated-tool configuration and convention files. | Keep unless the user wants AI-tool config removed from the workspace. |
| `.vscode/` | Ignored editor configuration. | Keep unless the user wants local editor settings removed. |

## Review Principles

1. Prefer compatibility wrappers over deleting old scientific entrypoints.
2. Move or delete research outputs only after confirming whether they are
   README assets, paper figures, or reproducible scratch products.
3. Keep ignored local data and archive folders out of Git, but do not remove
   non-empty folders without explicit confirmation.
4. Record validation limits honestly: compile/import/mock tests do not prove
   real FITS output equivalence.
