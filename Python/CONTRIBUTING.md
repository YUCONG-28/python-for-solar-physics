# Contributing

Thank you for helping improve this solar-physics toolkit. The repository is organized as a research-tool project: reusable helpers live in `solar_toolkit/`, runnable workflows live in `scripts/`, and lightweight checks live in `tests/`.

## Environment

The project is developed with Miniforge and the `solarphysics_env` environment:

```powershell
conda activate solarphysics_env
python -m pip install -r requirements.txt
D:\miniforge3\envs\solarphysics_env\python.exe -m pip install -e ".[dev]"
```

The `.[dev]` extra is the minimum contributor install for tests and style
checks. Use `.[dev,full]` when validating broader science workflows that need
the optional NetCDF, image, radio, or download helpers.

When running checks from a non-activated PowerShell session, prepend the
Miniforge DLL and script paths before calling the project interpreter:

```powershell
$env:PATH="D:\miniforge3\envs\solarphysics_env;D:\miniforge3\envs\solarphysics_env\Library\mingw-w64\bin;D:\miniforge3\envs\solarphysics_env\Library\usr\bin;D:\miniforge3\envs\solarphysics_env\Library\bin;D:\miniforge3\envs\solarphysics_env\Scripts;$env:PATH"
```

## Before Committing

Run the lightweight checks that do not require local FITS/NetCDF data:

```powershell
D:\miniforge3\envs\solarphysics_env\python.exe -m compileall -q solar_toolkit scripts tests examples
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD="1"; D:\miniforge3\envs\solarphysics_env\python.exe -m pytest -q tests
D:\miniforge3\envs\solarphysics_env\python.exe -m pip install pre-commit
pre-commit run --all-files
```

`pre-commit` runs whitespace, end-of-file, YAML, large-file, Gitleaks, Ruff, and
Black checks, so style, formatting, and obvious data-policy problems are caught
before code reaches shared branches.

## Code Style

- Use Black as the Python formatter.
- Use Ruff for linting, import sorting, and safe automatic fixes.
- Use Pylance in VSCode for type analysis, navigation, and completions.
- Keep autopep8, yapf, flake8, and pylint as manual fallback tools only; do not
  configure them as the default formatter or linter for this project.

## Data and Paths

- Do not commit FITS, NetCDF, generated plots, videos, Excel files, caches, or local data products.
- Copy `configs/paths.example.yaml` to `configs/paths.local.yaml` for personal paths.
- Keep `configs/paths.local.yaml` untracked.

## Script Changes

- Keep scripts runnable from the repository root.
- Prefer adding reusable helpers to `solar_toolkit/` only when multiple scripts need them.
- Examples that require local data belong in `examples/`; tests in `tests/` must be data-independent.
