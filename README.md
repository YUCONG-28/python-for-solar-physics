# solarphysics

`solarphysics` is a single repository with two public, reusable partitions and
one local-only application layer:

```text
solarphysics/
|- Python/   reusable solar-physics algorithms and the solar_toolkit package
|- Paper/    curated literature sources, generators, indexes, and method notes
|- Local/    local applications and orchestration (ignored by this repository)
|- 2023/ ... 2026/ and overview/   local observations and working material
```

## Repository boundaries

- `Python/` is the public software library. Its distribution name remains
  `solar-physics-toolkit`, and its import namespace remains `solar_toolkit`.
- `Paper/` is the public evidence layer. Seed data and search configuration are
  inputs; reports and indexes are regenerated and validated by the PowerShell
  workflow.
- `Local/` contains Web/GUI/CLI adapters, event-specific configuration,
  personal paths, and cross-domain orchestration. The outer repository ignores
  the whole directory. `Local/` is maintained as a separate local Git
  repository with no remote and may depend on `solar_toolkit`; public code must
  never depend on `Local/`.
- The year directories (`2023/` through `2026/`), `overview/`, private paper
  documents, and other local workspace material are never tracked by the outer
  repository.

Public CI deliberately validates only `Python/`, `Paper/`, and repository
governance. It does not run, package, or claim to validate `Local/`.

## Install the public Python package

From the repository root, install the reusable package in editable mode:

```powershell
D:\miniforge3\envs\solarphysics_env\python.exe -m pip install -e ".\Python[dev]"
```

The corresponding cross-platform command is:

```bash
python -m pip install -e "./Python[dev]"
```

## Validate the public partitions

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
D:\miniforge3\envs\solarphysics_env\python.exe -m compileall -q .\Python\solar_toolkit .\Python\tests .\Python\examples\public_api
D:\miniforge3\envs\solarphysics_env\python.exe -m ruff check .\Python\solar_toolkit .\Python\tests .\Python\examples\public_api
D:\miniforge3\envs\solarphysics_env\python.exe -m pytest .\Python\tests
D:\miniforge3\envs\solarphysics_env\python.exe -m build .\Python

powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Paper\scripts\paper_daily_recommendation.ps1 -SkipLiveSearch
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Invoke-Pester -Script .\Paper\tests\PaperRecommendation.Tests.ps1"
```

The Paper generator is generate-and-validate only by default. Publishing is a
separate, explicit operation and must remain scoped to approved `Paper/` paths.

## License boundary

There is intentionally no repository-wide `LICENSE`. The MIT license in
[`Python/LICENSE`](Python/LICENSE) applies to the Python software partition
only. It must not be interpreted as automatically licensing Paper content,
local research material, or the ignored `Local/` application layer.
