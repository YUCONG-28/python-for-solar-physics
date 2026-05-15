# Project Structure

This repository uses a lightweight research-tool layout. The primary workflows
remain runnable scripts, while shared helpers and data-independent tests are kept
separate so the project is easier to maintain and present on GitHub.

```text
python-for-solar-physics/
├── solar_toolkit/
│   ├── __init__.py
│   ├── path_config.py
│   └── solar_analysis_utils.py
├── scripts/
│   ├── aia_hmi/
│   ├── radio/
│   ├── xray_dem/
│   ├── lasco_cme/
│   └── tools/
├── examples/
│   ├── aia_hmi/
│   ├── radio/
│   └── radio_aia_hmi/
├── configs/
│   └── paths.example.yaml
├── docs/
├── tests/
├── outputs/
├── README.md
├── requirements.txt
└── pyproject.toml
```

## Top-Level Directories

- `solar_toolkit/`: reusable helpers and package metadata. This package contains
  optional YAML path loading, shared observation-time parsing, FITS sorting,
  memory helpers, and common plotting/coordinate utilities.
- `scripts/`: runnable research workflows grouped by instrument or task. These
  scripts are the main interface for local data processing.
- `examples/`: local-data examples and historical development workflows. These
  are useful references but usually require observation data that is not tracked
  in Git.
- `configs/`: configuration templates. Copy `paths.example.yaml` to
  `paths.local.yaml` for machine-specific paths.
- `docs/`: project documentation, including this structure guide and the script
  index.
- `tests/`: lightweight pytest tests that do not depend on FITS, NetCDF, JP2, or
  other local science data.
- `outputs/`: documentation placeholder for generated products. Actual figures,
  videos, and intermediate data products should remain local and ignored.

## Script Groups

- `scripts/aia_hmi/`: SDO/AIA and SDO/HMI image processing, difference imaging,
  light curves, time-distance analysis, file selection, and magnetic overlays.
- `scripts/radio/`: CSO dynamic spectra, radio source maps, polarization
  products, multi-frequency source panels, and AIA/radio/HMI overlays.
- `scripts/xray_dem/`: GOES SXR, HXR/HXI, Neupert-effect diagnostics, DEM/Tb
  visualization, and combined flare analysis plots.
- `scripts/lasco_cme/`: SOHO/LASCO data download, image plotting, and CME
  running-difference workflows.
- `scripts/tools/`: general utilities such as image-sequence video generation
  and Gaussian source fitting.

## Tests vs Examples

Tests must stay data-independent and fast. Workflows that require local
observation data belong in `scripts/` or `examples/`, not in `tests/`.

Examples may include hard-coded demonstration paths, but reusable scripts should
prefer `solar_toolkit.path_config.load_script_config` or
`apply_config_to_object` so personal paths can live in ignored local YAML files.

## Data and Generated Products

Do not commit raw FITS/JP2/NetCDF data, generated PNG/JPG/TIFF figures, MP4
videos, `.npy` intermediate arrays, Excel/CSV products, cache folders, or local
path configs. Keep the repository focused on reproducible code, documentation,
configuration templates, and data-independent tests.
