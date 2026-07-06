# Main Files / 主文件索引

This compact index lists the maintainer-facing packages and entrypoints. For
the full boundary map, see `FUNCTION_MAP.md`.

本文档是维护者使用的简明主文件索引。完整功能边界见 `FUNCTION_MAP.md`。

## Public Packages / 公共包

- `solar_toolkit/`: installable library layer.
  - `time/`: shared timestamp parsing, filename time extraction, nearest-time matching, and range filtering.
  - `io/`: local file scanning, natural sorting, FITS data/header reading, and CSV manifest helpers.
  - `data/`: lightweight local observation inventory records without download side effects.
  - `map/`: SunPy Map/FITS-header helper layer for display extent, observation time, ROI crop, and normalization.
  - `timeseries/`: light-curve table time normalization, clipping, smoothing, and derivative helpers.
  - `aia/`: AIA configuration, FITS selection, difference images, mosaics, EUV processing, and lightweight AIA background loading.
  - `hmi/`: HMI-facing facades for FITS renaming, magnetogram plotting, and overlays.
  - `radio/`: radio coordinates, threshold centers, Gaussian fitting, trajectory tables, Newkirk, spectrogram, drift, raw quality, and quicklook helpers.
  - `xray_dem/`: namespace for X-ray, HXI, Neupert, and DEM helpers.
  - `cme/`: namespace for LASCO/CME helpers.
  - `net/`: namespace for archive query and download helpers.
  - `modeling/`: shared Gaussian and density-model boundary.
  - `visualization/`: shared plotting, media-generation, local image sequence viewer, video export, and interactive HTML visualization helpers.
  - `path_config.py`: local YAML path/config loading.
  - `solar_analysis_utils.py`: shared time, FITS ordering, map, memory, and plotting utilities.

## Recommended Entrypoints / 推荐入口

- `scripts/aia_hmi/run_aia_euv_processor.py`
  - Recommended AIA EUV command.
  - Delegates to `solar_toolkit.aia.cli`.
  - Historical `scripts/aia_hmi/sdo_aia_euv_processor.py` remains compatible.
- `scripts/radio/run_radio_burst_pipeline.py`
  - Full radio burst workflow.
  - Uses `solar_toolkit.radio` for reusable helpers and keeps legacy plotting compatibility.
- `scripts/radio/run_radio_source_map.py`
  - Quick radio source-map workflow with Gaussian overlays.
- `scripts/radio/extract_radio_centers.py`
  - Threshold/contour radio-source center extraction to CSV/XLSX.
- `scripts/radio/run_radio_source_app.py`
  - Streamlit trajectory playback frontend that reads existing center tables.
- `scripts/radio/export_radio_source_trajectory.py`
  - Static Plotly HTML export for selected trajectory frames.
- `scripts/radio/run_aia_radio_hmi_overlay.py`
  - AIA/radio/HMI overlay workflow.
- `scripts/radio/run_radio_raw_quality.py`
  - Raw radio FITS quality-diagnostic workflow.
- `scripts/tools/run_image_web_viewer.py`
  - Local Flask/Canvas image sequence viewer for multi-folder playback, ROI review, and composite/separate MP4 export.

## Compatibility Layers / 兼容层

- `scripts/radio/core/`: compatibility wrappers for migrated radio modules.
- `scripts/aia_hmi/core/`: compatibility wrappers for migrated AIA modules.
- `scripts/radio/legacy/`: large historical workflows retained for output reproducibility.
- `legacy/`: archived scripts kept for manual review, not current first-choice entrypoints.

## Script Groups / 脚本分组

- `scripts/aia_hmi/`: AIA/HMI commands and compatibility entrypoints.
- `scripts/radio/`: radio source maps, center extraction, trajectory playback, burst pipeline, raw quality checks, and overlay commands.
- `scripts/xray_dem/`: GOES SXR, HXR/HXI, Neupert, DEM, and multi-panel diagnostic scripts.
- `scripts/lasco_cme/`: SOHO/LASCO download, plotting, and running-difference scripts.
- `scripts/data_download/`: STEREO, GOES/SUVI, and Solar Orbiter/EUI query/download scripts.
- `scripts/stereo_suvi/`: STEREO/EUVI and GOES/SUVI event context products.
- `scripts/tools/`: general utilities such as video generation, image web viewing, and Gaussian fitting wrappers.

## Documentation / 文档

- `docs/FUNCTION_MAP.md`: bilingual package and compatibility map.
- `docs/project_structure.md`: repository layout and data policy.
- `docs/script_index.md`: runnable script index.
- `docs/path_configuration.md`: local path configuration guide.
- `scripts/aia_hmi/docs/AIA_ENTRYPOINTS.md`: AIA entrypoint notes.
- `scripts/radio/docs/RADIO_ENTRYPOINTS.md`: radio entrypoint notes.
- `scripts/radio/docs/RADIO_MIGRATION_NOTES.md`: radio migration and compatibility notes.

## Data Policy / 数据策略

Do not commit raw observations, local path configs, generated bulk products, or
personal archives. Keep tracked content focused on code, tests, public docs,
configuration templates, and reviewed README assets.

不要提交原始观测数据、本地路径配置、批量生成产品或个人归档。Git 中应主要
保留代码、测试、公开文档、配置模板和经过审查的 README 展示资产。
