# Main Files

This compact index lists the maintainer-facing packages and entrypoints. For the
full boundary map, see `FUNCTION_MAP.md`. For a first-run guide, see
`quickstart.md`.

本页为维护者提供主要包、命令入口和兼容层的简明索引；完整边界见 `FUNCTION_MAP.md`，首次运行
请先阅读 `quickstart.md`。

## Public Packages

- `solar_toolkit/`: installable library layer.
  - `time/`: shared timestamp parsing, filename time extraction, nearest-time matching, and range filtering.
  - `io/`: local file scanning, natural sorting, FITS data/header reading, and CSV manifest helpers.
  - `data/`: lightweight local observation inventory records without download side effects.
  - `map/`: SunPy Map/FITS-header helper layer for display extent, observation time, ROI crop, and normalization.
  - `timeseries/`: light-curve table time normalization, clipping, smoothing, and derivative helpers.
  - `aia/`: AIA configuration, FITS selection, difference images, mosaics, EUV processing, and lightweight AIA background loading.
  - `hmi/`: HMI-facing facades for FITS renaming, magnetogram plotting, and overlays.
  - `radio/`: radio coordinates, threshold centers, Gaussian fitting, trajectory tables, ROI light curves, Newkirk, spectrogram, drift, raw quality, and quicklook helpers.
    - `config.py` and `configs/`: canonical validated loader and installable event configurations; `scripts.radio.configs` keeps aliases.
    - `pipeline_workflow.py`, `source_map_workflow.py`, `overlay_workflow.py`: package-owned complete orchestration.
    - `roi_lightcurve.py`, `roi_lightcurve_app.py`, `roi_lightcurve_launcher.py`: ROI statistics, Streamlit UI, and managed launcher.
    - `roi_selection_cli.py`, `drift_selection_cli.py`, `trajectory_media_cli.py`, `existing_fit_overlay.py`, `existing_fit_overlay_cli.py`: independent structured action services/adapters used by the integrated Radio Workspace; the existing-fit overlay consumes persisted center/Gaussian CSV products and never reruns fitting.
  - `xray_dem/`: X-ray, HXI, Neupert, DEM, image, comparison, and overlay workflow implementations.
  - `cme/`: LASCO/CME helper boundary.
  - `net/`: archive query and download helper boundary.
  - `modeling/`: shared Gaussian and density-model boundary.
  - `visualization/`: shared plotting, media-generation, local image sequence viewer, video export, and interactive HTML visualization helpers.
  - `webapp/`: unified local English web GUI, workflow registry, and job runner.
    - `radio_workspace/contracts.py` and `catalog.py`: versioned module/action/workspace/run/artifact contracts and the eight fused Radio modules.
    - `radio_workspace/store.py`, `runner.py`, and `api.py`: allowed-root persistence, selected-action orchestration, artifacts, cancellation, recovery, and `/api/radio/*`.
    - `radio_workspace/native_previews.py`: same-page ROI, drift, and trajectory Plotly payloads without an external Streamlit service.
    - `templates/radio.html`, `static/radio.css`, and `static/radio.js`: the `/radio` interface and local Plotly/Mediabunny integration.
  - `path_config.py`: local YAML path/config loading.
  - `solar_analysis_utils.py`: compatibility facade for shared time, FITS ordering, map, memory, and plotting utilities.

## Recommended Entrypoints

- `scripts/aia_hmi/run_aia_euv_processor.py`
  - Recommended AIA EUV command.
  - Delegates to `solar_toolkit.aia.cli`.
  - Historical `scripts/aia_hmi/sdo_aia_euv_processor.py` remains compatible.
- `scripts/radio/run_radio_burst_pipeline.py`
  - Thin compatibility command for `solar_toolkit.radio.pipeline_workflow`.
- `scripts/radio/run_radio_source_map.py`
  - Thin compatibility command for `solar_toolkit.radio.source_map_workflow`.
- `scripts/radio/extract_radio_centers.py`
  - Threshold/contour radio-source center extraction to CSV/XLSX.
- `scripts/radio/run_radio_source_app.py`
  - Streamlit trajectory playback frontend that reads existing center tables.
  - Uses the selected Start/End, size, FPS, and quality for deterministic browser MP4/WebM recording and backend MP4/GIF/WebM export.
- `scripts/radio/run_radio_roi_lightcurve_app.py`
  - Streamlit frontend for radio FITS ROI selection, raw statistics, and light-curve export.
  - The installed equivalent is `solar-radio roi-lightcurve`.
- `scripts/radio/export_radio_source_trajectory.py`
  - Static Plotly HTML export for selected trajectory frames.
- `scripts/radio/run_aia_radio_hmi_overlay.py`
  - AIA/radio/HMI overlay workflow.
- `scripts/radio/run_radio_raw_quality.py`
  - Raw radio FITS quality-diagnostic workflow.
- `scripts/tools/run_image_web_viewer.py`
  - Local Flask/Canvas image sequence viewer for multi-folder playback, ROI review, live-stage recording, and composite/separate MP4/GIF/WebM export.
- `solar_toolkit/visualization/media.py`
  - Shared FFmpeg/FFprobe resolution, atomic media writing, validation, cancellation, and frame-factory support used by radio and image-sequence video workflows.
  - Honors `SOLAR_TOOLKIT_FFMPEG` and `SOLAR_TOOLKIT_FFPROBE`, with the older image-viewer environment variable names retained as fallbacks.
- `solar_toolkit/visualization/_media_assets/`
  - Internal canonical package for the bundled Mediabunny recorder, shared browser recorder API, and license files; the old non-private path remains a compatibility alias.
- `scripts/tools/run_solar_webapp.py`
  - Unified local English web GUI for registered public workflows and the modular `/radio` workspace on the same port.
  - Radio module selection and presets only change layout; only a per-action Run or confirmed Run Selected request starts work.

## Compatibility Layers

- `scripts/radio/core/`: deprecated compatibility wrappers for migrated radio modules.
- `scripts/aia_hmi/core/`: deprecated compatibility wrappers for migrated AIA modules.
- `scripts/radio/legacy/`: deprecated module aliases to package-owned workflows.
- `solar_toolkit.gaussian`, `solar_toolkit.coordinates`, and `solar_toolkit.cso`: deprecated root aliases for `solar_toolkit.modeling.gaussian`, `solar_toolkit.map.coordinates`, and `solar_toolkit.radio.cso`.
- `legacy/`: archived scripts kept for manual review, not current first-choice entrypoints.

## Script Groups

- `scripts/aia_hmi/`: AIA/HMI commands and compatibility entrypoints.
- `scripts/radio/`: radio source maps, center extraction, trajectory playback, burst pipeline, raw quality checks, and overlay commands.
- `scripts/xray_dem/`: GOES SXR, HXR/HXI, Neupert, DEM, and multi-panel diagnostic scripts.
- `scripts/lasco_cme/`: SOHO/LASCO download, plotting, and running-difference scripts.
- `scripts/data_download/`: STEREO, GOES/SUVI, and Solar Orbiter/EUI query/download scripts.
- `scripts/stereo_suvi/`: STEREO/EUVI and GOES/SUVI event context products.
- `scripts/tools/`: general utilities such as video generation, image web viewing, and Gaussian fitting wrappers.

## Documentation

- `docs/quickstart.md`: beginner setup, no-data validation, first imports, and safe entrypoint checks.
- `docs/radio_workspace.md`: complete Radio module inventory, selective execution rules, workspace persistence, API, and compatibility map.
- `docs/FUNCTION_MAP.md`: package and compatibility map.
- `CODE_ORGANIZATION_MANIFEST.md`: authoritative repository layout and data policy.
- `docs/script_index.md`: runnable script index.
- `docs/validation/astropy_sunpy_reorg_parity.md`: focused real-data parity record and explicit end-to-end exclusions.
- `docs/path_configuration.md`: local path configuration guide.
- `scripts/aia_hmi/docs/AIA_ENTRYPOINTS.md`: AIA entrypoint notes.
- `docs/history/radio/`: archived Radio entrypoint snapshots and migration reports.

## Data Policy

Do not commit raw observations, local path configs, generated bulk products, or
personal archives. Keep tracked content focused on code, tests, public docs,
configuration templates, and reviewed README assets.
