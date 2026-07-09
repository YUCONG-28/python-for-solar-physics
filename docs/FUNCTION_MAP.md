# Function Map

This map records the intended public boundaries after the Astropy/SunPy-style
cleanup. It separates stable library imports from runnable research scripts and
from compatibility paths that are kept for local reproducibility.

Chinese note: API names stay in English. This page is English-first and records
the responsibility boundary for library packages, script entrypoints, and
compatibility paths.

## SunPy-Style Base Layer

The project includes lightweight local-data helpers that mirror the practical
shape of SunPy namespaces without replacing SunPy itself:
`solar_toolkit.time`, `solar_toolkit.io`, `solar_toolkit.data`,
`solar_toolkit.map`, and `solar_toolkit.timeseries`. These packages provide
shared timestamp parsing, file/FITS scanning, local inventory records,
Map/header display helpers, and light-curve table utilities. Science-domain
packages such as `aia`, `hmi`, `radio`, `xray_dem`, and `cme` should use these
building blocks instead of duplicating glue code in scripts.

## Public Library Layer

| Package | Responsibility |
| --- | --- |
| `solar_toolkit.time` | Parse observation times, extract times from filenames, match nearest observations, and filter time ranges. |
| `solar_toolkit.io` | Scan local files, natural-sort paths, read FITS data/header pairs, and write manifest CSV files. |
| `solar_toolkit.data` | Represent local observation-file records and manifests without download side effects. |
| `solar_toolkit.map` | Provide thin SunPy Map/FITS-header helpers for display extent, observation time, ROI crop, and image normalization. |
| `solar_toolkit.timeseries` | Normalize time columns, crop light curves, smooth series, and compute derivatives for GOES/HXI/AIA-style tables. |
| `solar_toolkit.aia` | SDO/AIA configuration, FITS selection, difference-image helpers, mosaics, lazy EUV processing, and lightweight AIA backgrounds. |
| `solar_toolkit.hmi` | HMI-facing helpers and facades for magnetogram, FITS renaming, and AIA/HMI overlay workflows. |
| `solar_toolkit.radio` | Radio coordinates, threshold/contour center extraction, Gaussian fitting, trajectory normalization, Newkirk models, spectrogram overlays, drift products, raw quality checks, and quicklook helpers. |
| `solar_toolkit.xray_dem` | Public boundary for GOES/HXR/HXI/DEM helpers that are being extracted from script workflows. |
| `solar_toolkit.cme` | Public boundary for LASCO/CME file scanning, timestamp parsing, running differences, and plotting helpers. |
| `solar_toolkit.net` | Archive query, link collection, filtering, and download helper boundary. |
| `solar_toolkit.modeling` | Shared science-model boundary for Gaussian and density-model helpers. |
| `solar_toolkit.visualization` | Shared plotting, media generation, image-sequence viewing, video export, and interactive HTML visualization helpers. |

## Runnable Entrypoints

| Entrypoint | Calls Into | Purpose |
| --- | --- | --- |
| `scripts/aia_hmi/run_aia_euv_processor.py` | `solar_toolkit.aia.cli` | Recommended AIA EUV processor entrypoint. |
| `scripts/radio/run_radio_burst_pipeline.py` | `solar_toolkit.radio` plus compatibility workflows | Full radio burst analysis pipeline. |
| `scripts/radio/run_radio_source_map.py` | `scripts.radio.legacy.radio_source_map_plot_gaussian_overlay` | Compatibility source-map runner. |
| `scripts/radio/extract_radio_centers.py` | `solar_toolkit.radio.centers` | Threshold/contour radio-source center extraction to CSV/XLSX. |
| `scripts/radio/run_radio_source_app.py` | `solar_toolkit.radio.trajectory`, `solar_toolkit.aia.background`, `solar_toolkit.visualization.radio_source_trajectory` | Streamlit playback frontend for radio-source trajectories with optional AIA background. |
| `scripts/radio/export_radio_source_trajectory.py` | `solar_toolkit.radio.trajectory`, `solar_toolkit.aia.background`, `solar_toolkit.visualization.radio_source_trajectory` | Static Plotly HTML export for selected trajectory frames. |
| `scripts/radio/run_aia_radio_hmi_overlay.py` | `scripts.radio.legacy.sdo_aia_radio_hmi_overlay` | Compatibility AIA/radio/HMI overlay runner. |
| `scripts/radio/run_radio_raw_quality.py` | `solar_toolkit.radio.raw_quality` | Raw radio FITS quality diagnostics. |
| `scripts/tools/run_image_web_viewer.py` | `solar_toolkit.visualization.image_web_viewer` | Local multi-folder image-sequence browser with synchronized playback, ROI review, and composite/separate MP4 export. |

## Compatibility Policy

- Historical `scripts.radio.core.*` imports remain deprecated compatibility
  aliases of the matching `solar_toolkit.radio.*` modules when the reusable
  implementation has moved.
- Historical `scripts.aia_hmi.core.*` imports remain deprecated compatibility
  aliases of the matching `solar_toolkit.aia.*` modules.
- Large workflows under `scripts/radio/legacy/` are deprecated compatibility
  paths. They stay runnable until output-equivalence checks with real
  observation data justify a separate removal step.
- New reusable code should import from `solar_toolkit.*`. Thin scripts may keep
  user-facing command-line behavior and local path configuration.
