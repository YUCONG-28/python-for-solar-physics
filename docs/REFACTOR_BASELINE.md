# Refactor Baseline

Date: 2026-05-22

## Scope

Phase 0 safety baseline before merging legacy code. This pass did not move,
delete, rename, stage, commit, or push files. No real FITS processing,
plotting, downloads, GUI, or video generation was run.

Only this baseline document was added.

## Current Git Status

Command:

```powershell
git status --short
```

Result:

```text
?? docs/RADIO_COORDINATE_AUDIT.md
?? solar_toolkit/coordinates.py
?? tests/test_radio_coordinates.py
```

Command:

```powershell
git diff --stat
```

Result:

```text
```

Tracked files currently have no unstaged diff. The repository does have
untracked files listed below.

## Current Untracked Files

```text
docs/RADIO_COORDINATE_AUDIT.md
solar_toolkit/coordinates.py
tests/test_radio_coordinates.py
```

These files were already untracked before this baseline document was created.

## Current Test Results

The default `python` command was not available in the current PowerShell
environment, so the requested fallback interpreter was used:

```powershell
D:\miniforge3\envs\solarphysics_env\python.exe
```

Interpreter and pytest versions:

```text
Python 3.11.15
pytest 9.0.3
```

Command:

```powershell
D:\miniforge3\envs\solarphysics_env\python.exe -m pytest tests
```

Result:

```text
Exit code: 1
No stdout/stderr output was emitted by pytest in this environment.
```

Diagnostic rerun with third-party pytest plugin autoload disabled:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; D:\miniforge3\envs\solarphysics_env\python.exe -m pytest tests -ra
```

Result:

```text
31 passed in 0.13s
```

Interpretation: the project test suite itself passes when isolated from the
ambient pytest plugin environment. The default pytest invocation currently exits
with code 1 without diagnostics, so the default test command is not a stable
green baseline yet.

## Compileall Result

Command:

```powershell
D:\miniforge3\envs\solarphysics_env\python.exe -m compileall solar_toolkit scripts tests
```

Result:

```text
Listing 'solar_toolkit'...
Listing 'scripts'...
Listing 'scripts\\aia_hmi'...
Listing 'scripts\\lasco_cme'...
Listing 'scripts\\radio'...
Listing 'scripts\\tools'...
Listing 'scripts\\xray_dem'...
Listing 'tests'...
```

Exit code: 0. Syntax compilation completed successfully for
`solar_toolkit`, `scripts`, and `tests`.

## Phase 1 Documentation And Configuration Template Check

Observed documentation files:

```text
docs/assets/README.md
docs/LEGACY_AND_REVIEW_FILES.md
docs/MAIN_FILES.md
docs/path_configuration.md
docs/PROJECT_CLEANUP_REPORT.md
docs/PROJECT_OPTIMIZATION_PLAN.md
docs/PROJECT_OVERVIEW.md
docs/project_structure.md
docs/RADIO_COORDINATE_AUDIT.md
docs/script_index.md
```

Observed configuration templates:

```text
configs/aia.example.yaml
configs/cso.example.yaml
configs/overlay.example.yaml
configs/paths.example.yaml
configs/radio.example.yaml
```

Other relevant project configuration files observed:

```text
.github/workflows/ci.yml
.pre-commit-config.yaml
pyproject.toml
requirements.txt
```

Status: first-stage documentation and configuration template artifacts appear
to be present.

## Recommendation For Phase 1

Do not enter Phase 1 as a fully stable baseline until the default pytest
invocation is understood or normalized, because the requested baseline command
`python -m pytest tests` currently exits with code 1 under the fallback
interpreter.

It is reasonable to proceed into Phase 1 only if the team accepts the isolated
test command as the working baseline:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; D:\miniforge3\envs\solarphysics_env\python.exe -m pytest tests
```

Before merging legacy code, also decide whether the existing untracked files
should be included in the refactor baseline, staged separately, or removed from
scope.
