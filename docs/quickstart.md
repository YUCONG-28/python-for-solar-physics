# Quickstart for New Users

This guide is the safest first path through the project. It focuses on commands
that do not require local observation data, then points to the scripts that do
need configured FITS, FTS, JP2, NetCDF, CSV, or image folders.

## 1. Create the Environment

The repository targets Python 3.10+ and is usually developed in the Miniforge
environment named `solarphysics_env`.

```powershell
conda create -n solarphysics_env python=3.11
conda activate solarphysics_env
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e ".[dev,full]"
```

Optional browser and frontend tools use the `app` extra:

```powershell
python -m pip install -e ".[app]"
```

On this Windows workstation, use the explicit project interpreter when running
checks from a non-activated shell:

```powershell
$env:PATH="D:\miniforge3\envs\solarphysics_env;D:\miniforge3\envs\solarphysics_env\Library\mingw-w64\bin;D:\miniforge3\envs\solarphysics_env\Library\usr\bin;D:\miniforge3\envs\solarphysics_env\Library\bin;D:\miniforge3\envs\solarphysics_env\Scripts;$env:PATH"
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
D:\miniforge3\envs\solarphysics_env\python.exe -m compileall -q solar_toolkit scripts tests examples
D:\miniforge3\envs\solarphysics_env\python.exe -m pytest -q tests\test_imports.py tests\test_public_package_boundaries.py tests\test_project_docs_current_paths.py
```

## 2. Try the Library Layer First

These imports are data-independent and safe to run before any local archive is
configured:

```python
from solar_toolkit.time import extract_time_from_filename, nearest_by_time
from solar_toolkit.io import scan_files, scan_fits, read_fits_data_header
from solar_toolkit.map import get_display_extent, normalize_image
from solar_toolkit.timeseries import normalize_time_column, smooth_series
from solar_toolkit.net import download_url, collect_links
from solar_toolkit.cme import extract_lasco_timestamp, running_difference
from solar_toolkit.xray_dem import load_sxr_data, calculate_derivative
```

The package layout follows a lightweight SunPy-style boundary:

- `solar_toolkit.time`, `io`, `data`, `map`, and `timeseries` hold shared
  helpers for local files, timestamps, image metadata, and light-curve tables.
- `solar_toolkit.aia`, `hmi`, `radio`, `xray_dem`, and `cme` hold
  instrument- or domain-specific helpers.
- `solar_toolkit.net`, `modeling`, and `visualization` hold archive access,
  science-model, plotting, browser, and video-export helpers.

## 3. Configure Local Data Only When Needed

Most science workflows need local observation files. Copy the path template and
edit the local copy:

```powershell
Copy-Item configs\paths.example.yaml configs\paths.local.yaml
```

`configs/paths.local.yaml` is ignored by Git. You can also point to an external
YAML file:

```powershell
$env:SOLAR_PHYSICS_CONFIG="D:\my_project\solar_paths.yaml"
```

See `docs/path_configuration.md` for the expected YAML shape.

## 4. Safe Entrypoint Checks

The following commands only show help and should not start a real data run:

```powershell
D:\miniforge3\envs\solarphysics_env\python.exe scripts\aia_hmi\run_aia_euv_processor.py --help
D:\miniforge3\envs\solarphysics_env\python.exe scripts\aia_hmi\sdo_aia_hmi_fits_rename.py --help
D:\miniforge3\envs\solarphysics_env\python.exe scripts\data_download\solo_eui_soar_query_download.py --help
D:\miniforge3\envs\solarphysics_env\python.exe scripts\radio\run_radio_burst_pipeline.py --help
D:\miniforge3\envs\solarphysics_env\python.exe scripts\tools\run_image_web_viewer.py --help
D:\miniforge3\envs\solarphysics_env\python.exe scripts\tools\run_solar_webapp.py --help
```

For the current public script inventory, use `docs/script_index.md`.

## 5. First Real Workflows

Use these only after local data paths are configured:

- AIA EUV products: `scripts/aia_hmi/run_aia_euv_processor.py`
- Full radio burst processing: `scripts/radio/run_radio_burst_pipeline.py`
- Radio-source center extraction: `scripts/radio/extract_radio_centers.py`
- Radio-source trajectory playback: `scripts/radio/run_radio_source_app.py`
- Multi-folder image review and MP4 export:
  `scripts/tools/run_image_web_viewer.py`
- Unified local English web GUI:
  `scripts/tools/run_solar_webapp.py`

Raw observations, generated figures, videos, CSV/XLSX products, and local cache
folders should stay outside Git unless they are explicitly reviewed and moved
under `docs/assets/` as small documentation assets.
