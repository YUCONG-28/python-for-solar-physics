# Contributing

Thank you for helping improve this solar-physics toolkit. The repository is organized as a research-tool project: reusable helpers live in `solar_toolkit/`, runnable workflows live in `scripts/`, and lightweight checks live in `tests/`.

## Environment

The project is developed with Miniforge and the `solarphysics_env` environment:

```powershell
conda activate solarphysics_env
D:\miniforge3\envs\solarphysics_env\python.exe -m pip install -e ".[dev]"
```

## Before Committing

Run the lightweight checks that do not require local FITS/NetCDF data:

```powershell
D:\miniforge3\envs\solarphysics_env\python.exe -m compileall -q solar_toolkit scripts tests examples
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD="1"; D:\miniforge3\envs\solarphysics_env\python.exe -m pytest -q tests
pre-commit run --all-files
```

## Data and Paths

- Do not commit FITS, NetCDF, generated plots, videos, Excel files, caches, or local data products.
- Copy `configs/paths.example.yaml` to `configs/paths.local.yaml` for personal paths.
- Keep `configs/paths.local.yaml` untracked.

## Script Changes

- Keep scripts runnable from the repository root.
- Prefer adding reusable helpers to `solar_toolkit/` only when multiple scripts need them.
- Examples that require local data belong in `examples/`; tests in `tests/` must be data-independent.
