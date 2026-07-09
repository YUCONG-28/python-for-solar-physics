# Project Code Organization Manifest

This manifest records the current whole-repository module boundary after the
Astropy/SunPy-style cleanup. It is a maintained inventory, not a historical
move log. Older file-by-file migration reports remain under `docs/` and
`scripts/radio/docs/`.

中文说明: 本文件记录当前仓库的功能分区和公共边界。历史迁移细节保留在
`docs/` 与 `scripts/radio/docs/` 中；这里以当前状态为准。

## Public Library Boundary

Reusable, data-independent helpers belong under `solar_toolkit/`. New code
should prefer these imports instead of reaching into script internals.

| Package | Current role |
| --- | --- |
| `solar_toolkit.time` | Timestamp parsing, filename time extraction, nearest-time matching, and time-range filtering. |
| `solar_toolkit.io` | Local file scanning, natural sorting, FITS data/header reading, and CSV manifest helpers. |
| `solar_toolkit.data` | Lightweight local observation-file records without download side effects. |
| `solar_toolkit.map` | SunPy Map/FITS-header helpers for extent, observation time, ROI crop, and normalization. |
| `solar_toolkit.timeseries` | Light-curve table time normalization, clipping, smoothing, and derivatives. |
| `solar_toolkit.aia` | AIA configuration, FITS selection, difference products, mosaics, and lazy EUV processing dispatch. |
| `solar_toolkit.hmi` | Lightweight HMI facades for FITS renaming, magnetogram plotting, and AIA/HMI overlay workflows. |
| `solar_toolkit.radio` | Radio coordinates, center extraction, Gaussian fitting, Newkirk, spectrogram, drift, raw-quality, quicklook, and diagnostics. |
| `solar_toolkit.xray_dem` | Reusable GOES/HXR/HXI/DEM helpers extracted from script workflows. |
| `solar_toolkit.cme` | LASCO/CME timestamp, scanning, and running-difference helpers. |
| `solar_toolkit.net` | Archive link collection, filtering, and explicit-location download helpers. |
| `solar_toolkit.modeling` | Shared Gaussian and density-model boundary. |
| `solar_toolkit.visualization` | Shared plotting, trajectory HTML, image viewer, and MP4 export helpers. |
| `solar_toolkit.webapp` | Local English workflow workbench, registry, runner, server, and CLI launcher. |

## Runnable Script Boundary

Runnable workflows stay under `scripts/`, grouped by instrument or task. These
paths are user-facing commands and may keep local path configuration or
script-style behavior.

| Area | Recommended entrypoints |
| --- | --- |
| AIA/HMI | `scripts/aia_hmi/run_aia_euv_processor.py`, `scripts/aia_hmi/sdo_aia_hmi_fits_rename.py` |
| Radio | `scripts/radio/run_radio_burst_pipeline.py`, `scripts/radio/run_radio_source_map.py`, `scripts/radio/extract_radio_centers.py`, `scripts/radio/run_radio_source_app.py`, `scripts/radio/export_radio_source_trajectory.py`, `scripts/radio/run_aia_radio_hmi_overlay.py`, `scripts/radio/run_radio_raw_quality.py` |
| Data download | `scripts/data_download/stereo_a_euvi_download_20250124.py`, `scripts/data_download/goes_suvi_download_20250124.py`, `scripts/data_download/solo_eui_soar_query_download.py` |
| Context imaging | `scripts/stereo_suvi/stereo_euvi_manifest_by_wavelength.py`, `scripts/stereo_suvi/stereo_euvi_0448_overview_plot.py`, `scripts/stereo_suvi/stereo_euvi_roi_movie.py`, `scripts/stereo_suvi/goes_suvi_0448_quadrant_plot.py` |
| X-ray/DEM | `scripts/xray_dem/flare_aia_sxr_hxr_summary_plot.py`, `scripts/xray_dem/neupert_sxr_derivative_hxr_comparison.py`, `scripts/xray_dem/sdo_aia_dem_inversion.py`, `scripts/xray_dem/dem_radio_source_overlay.py` |
| LASCO/CME | `scripts/lasco_cme/soho_lasco_data_download.py`, `scripts/lasco_cme/soho_lasco_image_plot.py`, `scripts/lasco_cme/soho_lasco_running_difference.py` |
| Tools | `scripts/tools/run_image_web_viewer.py`, `scripts/tools/run_solar_webapp.py`, `scripts/tools/image_sequence_to_video.py`, `scripts/tools/gaussian_source_fitting.py` |

## Deprecated Compatibility Boundary

The following paths are retained as deprecated compatibility paths. They are
kept to protect existing local workflows and to support real-data output
comparison before any removal:

- `scripts.radio.core.*`: compatibility aliases for migrated
  `solar_toolkit.radio.*` modules.
- `scripts.aia_hmi.core.*`: compatibility aliases for migrated
  `solar_toolkit.aia.*` modules.
- `scripts/radio/legacy/`: large historical radio and AIA/radio/HMI workflows
  retained behind current run scripts.
- `scripts/aia_hmi/sdo_aia_euv_processor.py`: historical AIA EUV command path
  retained behind `scripts/aia_hmi/run_aia_euv_processor.py`.

This compatibility marking is documentation and test policy only. Runtime code
should not emit deprecation warnings in this pass.

## Data And Artifact Policy

Tracked repository content should stay limited to code, tests, documentation,
configuration templates, and reviewed display assets. Do not commit raw FITS,
FTS, JP2, NetCDF, CDF, HDF5, NumPy arrays, local path configs, bulk generated
figures, MP4/GIF products, large CSV/XLSX outputs, or local archive folders.

Ignored local products such as `archive/`, `data dowload/`,
`scripts/radio/outputs/`, root workbooks, and root display images require
manual review before deletion or movement.

## Verification

Use the project interpreter from `AGENTS.md`:

```powershell
$env:PATH="D:\miniforge3\envs\solarphysics_env;D:\miniforge3\envs\solarphysics_env\Library\mingw-w64\bin;D:\miniforge3\envs\solarphysics_env\Library\usr\bin;D:\miniforge3\envs\solarphysics_env\Library\bin;D:\miniforge3\envs\solarphysics_env\Scripts;$env:PATH"
D:\miniforge3\envs\solarphysics_env\python.exe -m compileall -q solar_toolkit scripts tests examples
D:\miniforge3\envs\solarphysics_env\python.exe -m ruff check solar_toolkit scripts tests examples
D:\miniforge3\envs\solarphysics_env\python.exe -m pytest -q tests
```

These checks verify imports, public boundaries, docs consistency, and
data-independent logic. They do not prove full scientific output equivalence on
real observation data.
