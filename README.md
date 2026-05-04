# Python for Solar Physics

A research-oriented Python toolkit for multi-wavelength solar event analysis. The repository keeps runnable science workflows in `scripts/`, reusable helpers in `solar_toolkit/`, local-data examples in `examples/`, and lightweight data-independent tests in `tests/`.

GitHub: <https://github.com/YUCONG-28/python-for-solar-physics>

## What It Covers

- SDO/AIA EUV imaging, difference imaging, light curves, and time-distance diagrams
- SDO/HMI magnetic-field context and AIA/HMI overlays
- CSO radio dynamic spectra and radio source maps
- GOES SXR, HXR, ASO-S/HXI, DEM, and combined flare diagnostics
- SOHO/LASCO CME plotting and running-difference workflows

## Install

The project is developed with Miniforge in `solarphysics_env`:

```powershell
conda activate solarphysics_env
D:\miniforge3\envs\solarphysics_env\python.exe -m pip install -e ".[dev]"
```

Core dependencies are declared in `pyproject.toml`. Some workflows need optional extras or local instrument data.

## Repository Layout

```text
solar_toolkit/   Reusable helpers and package metadata
scripts/         Runnable workflows grouped by instrument/task
examples/        Local-data examples and historical development workflows
tests/           Lightweight tests that do not need local observation data
configs/         Path configuration templates
docs/            Project documentation
```

See `docs/project_structure.md` and `docs/script_index.md` for details.

## Local Data Paths

Many scripts need local FITS, NetCDF, JP2, or CSV data. To avoid editing source files, copy the example config and adjust it for your machine:

```powershell
Copy-Item configs\paths.example.yaml configs\paths.local.yaml
```

`configs/paths.local.yaml` is ignored by Git. You can also set:

```powershell
$env:SOLAR_PHYSICS_CONFIG="D:\my_project\solar_paths.yaml"
```

See `docs/path_configuration.md`.

## Quick Commands

```powershell
# AIA batch processing
D:\miniforge3\envs\solarphysics_env\python.exe scripts\aia_hmi\sdo_aia_euv_processor.py

# CSO dynamic spectrum plotting
D:\miniforge3\envs\solarphysics_env\python.exe scripts\radio\cso_radio_spectrogram_plot.py

# Neupert-effect comparison
D:\miniforge3\envs\solarphysics_env\python.exe scripts\xray_dem\neupert_sxr_derivative_hxr_comparison.py
```

## Verification

These checks do not require local observation data:

```powershell
D:\miniforge3\envs\solarphysics_env\python.exe -m compileall -q solar_toolkit scripts tests examples
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD="1"; D:\miniforge3\envs\solarphysics_env\python.exe -m pytest -q tests
D:\miniforge3\envs\solarphysics_env\python.exe -c "from solar_toolkit import solar_analysis_utils; import solar_toolkit; print(solar_toolkit.__version__)"
```

## Contributing

See `CONTRIBUTING.md`. Do not commit large observation data, generated plots, videos, Excel files, caches, or personal path configs.

## Citation

Citation metadata is provided in `CITATION.cff`.

Li, Y. (2025). *Python for Solar Physics: Multi-wavelength Data Processing Toolkit*. Shandong University. <https://github.com/YUCONG-28/python-for-solar-physics>

## License

MIT License. See `LICENSE`.
