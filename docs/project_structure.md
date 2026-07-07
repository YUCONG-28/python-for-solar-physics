# Project Structure

This repository uses a lightweight research-tool layout. The primary workflows
remain runnable scripts, while shared helpers and data-independent tests are kept
separate so the project is easier to maintain and present on GitHub.

```text
python-for-solar-physics/
|-- solar_toolkit/
|   |-- __init__.py
|   |-- aia/
|   |-- cme/
|   |-- data/
|   |-- hmi/
|   |-- io/
|   |-- map/
|   |-- modeling/
|   |-- net/
|   |-- path_config.py
|   |-- radio/
|   |-- solar_analysis_utils.py
|   |-- time/
|   |-- timeseries/
|   |-- visualization/
|   `-- xray_dem/
|-- scripts/
|   |-- aia_hmi/
|   |   |-- core/
|   |   |-- configs/
|   |   |-- docs/
|   |   |-- run_aia_euv_processor.py
|   |   `-- sdo_aia_euv_processor.py
|   |-- radio/
|   |-- data_download/
|   |-- stereo_suvi/
|   |-- xray_dem/
|   |-- lasco_cme/
|   `-- tools/
|-- examples/
|   |-- aia_hmi/
|   |-- configs/
|   |-- images/
|   |-- radio/
|   |-- radio_aia_hmi/
|   `-- videos/
|-- configs/
|   |-- paths.example.yaml
|   |-- aia.example.yaml
|   |-- radio.example.yaml
|   |-- cso.example.yaml
|   `-- overlay.example.yaml
|-- docs/
|   |-- assets/
|   `-- data_download/
|-- legacy/
|   `-- scripts/
|-- archive/                    # ignored local archive area
|-- tests/
|-- outputs/
|-- README.md
|-- requirements.txt
`-- pyproject.toml
```

## Top-Level Directories

- `solar_toolkit/`: installable library layer and package metadata. This
  package contains optional YAML path loading, shared observation-time parsing,
  FITS sorting, local inventory records, map/header helpers, time-series
  helpers, common plotting/coordinate utilities, and science-domain namespaces
  modeled after the Astropy/SunPy package style: `time`, `io`, `data`, `map`,
  `timeseries`, `aia`, `hmi`, `radio`, `xray_dem`, `cme`, `net`, `modeling`,
  and `visualization`.
- `scripts/`: runnable research workflows grouped by instrument or task. These
  scripts are the main command-line interface for local data processing.
- `scripts/data_download/`: event-oriented download/query helpers for
  STEREO-A/EUVI, GOES/SUVI, and Solar Orbiter/EUI.
- `scripts/stereo_suvi/`: STEREO-A/EUVI manifest, overview, ROI movie, and
  GOES/SUVI quadrant plotting workflows.
- `examples/`: local-data examples and historical development workflows. These
  are useful references but usually require observation data that is not tracked
  in Git. Small future examples can be grouped under `examples/images/`,
  `examples/videos/`, and `examples/configs/` when needed.
- `configs/`: configuration templates. Copy `paths.example.yaml` to
  `paths.local.yaml` for machine-specific paths. The module-specific
  `*.example.yaml` files document planned AIA, radio, CSO, and overlay
  parameters for later config consolidation.
- `docs/`: project documentation, including this structure guide,
  `docs/quickstart.md`, and the script index.
- `docs/assets/`: GitHub/README display assets. Put only compressed, documented
  example images or short videos here; do not store raw observation data or bulk
  processing outputs.
- `legacy/`: high-risk historical scripts that may preserve old paper-specific
  parameters or output styles. Keep them visible for review instead of deleting
  them silently.
- `archive/`: ignored local archive area for old copies or manual review
  material. It is intentionally excluded from Git by `.gitignore`.
- `tests/`: lightweight pytest tests that do not depend on FITS, NetCDF, JP2, or
  other local science data.
- `outputs/`: ignored local output tree for generated figures, videos, tables,
  and intermediate data products. Keep durable guidance in `docs/` instead of
  tracking files under `outputs/`.
- `data/products/`: ignored local output tree for generated figures, videos,
  manifests, and other reproducible products. Do not commit it.

## Script Groups

- `scripts/aia_hmi/`: SDO/AIA and SDO/HMI image processing, difference imaging,
  light curves, time-distance analysis, file selection, and magnetic overlays.
  The main AIA EUV processor now uses a radio-style phased structure with
  `run_aia_euv_processor.py`, `core/`, `configs/`, `docs/`, and the historical
  `sdo_aia_euv_processor.py` compatibility entrypoint.
  New reusable AIA logic should go under `solar_toolkit.aia`; HMI-facing
  reusable logic should go under `solar_toolkit.hmi`. The `core/` package is
  now a compatibility namespace for old imports. New command-line entrypoints
  should be small `run_*.py` wrappers. Keep compatibility wrappers when an old
  script path is already used by tests, docs, or local workflows.
- `scripts/radio/`: CSO dynamic spectra, radio source maps, threshold/contour
  center extraction, trajectory playback/export, polarization products,
  multi-frequency source panels, and AIA/radio/HMI overlays. New reusable radio
  code should live under `solar_toolkit.radio`; historical
  `scripts.radio.core.*` modules are compatibility aliases for existing docs,
  tests, and local workflows.
- `scripts/xray_dem/`: GOES SXR, HXR/HXI, Neupert-effect diagnostics, DEM/Tb
  visualization, and combined flare analysis plots. Reusable future helpers
  should be extracted into `solar_toolkit.xray_dem`.
- `scripts/lasco_cme/`: SOHO/LASCO data download, image plotting, and CME
  running-difference workflows. Reusable future helpers should be extracted
  into `solar_toolkit.cme`.
- `scripts/data_download/`: remote data access helpers that create local
  raw-data folders and manifests. These scripts may contact external archives;
  reusable query/download helpers should be extracted into `solar_toolkit.net`.
- `scripts/stereo_suvi/`: products for STEREO-A/EUVI and GOES/SUVI context
  imaging of the 2025-01-24 event.
- `scripts/tools/`: general utilities such as image-sequence video generation
  and Gaussian source fitting. Reusable plotting/media helpers should move
  toward `solar_toolkit.visualization`, while science models should move toward
  `solar_toolkit.modeling`.

## Tests vs Examples

Tests must stay data-independent and fast. Workflows that require local
observation data belong in `scripts/` or `examples/`, not in `tests/`.

Examples may include hard-coded demonstration paths, but reusable scripts should
prefer `solar_toolkit.path_config.load_script_config` or
`apply_config_to_object` so personal paths can live in ignored local YAML files.

## Data and Generated Products

Do not commit raw FITS/JP2/NetCDF data, generated PNG/JPG/TIFF figures, MP4
videos, `.npy` intermediate arrays, Excel/CSV products, zip archives, cache
folders, local archive folders, or local path configs. Keep the repository
focused on reproducible code, documentation, configuration templates, and
data-independent tests.

Root-level images such as `HXR.png`, `SXR.png`, `SXR to HXR.png`, and
`SXR to HXR enhance.png` need manual review before any future move into
`docs/assets/images/`. They may be README assets, paper figures, or historical
outputs, so this cleanup phase leaves the local files in place but removes them
from Git tracking.

## README

`README.md` is the GitHub landing page and is maintained as a bilingual
English/Chinese overview. Detailed public script status lives in
`docs/script_index.md`.
