# Solar Physics Toolkit

This repository separates reusable solar-physics software, research evidence,
interactive applications, and private runtime state. The installable library
is `solar-physics-toolkit`; its Python import namespace is `solar_toolkit`.

The toolkit provides focused components for observation discovery, FITS and
map processing, coordinates, time series, radio-source analysis, X-ray/DEM
workflows, visualization, and media export. Scientific choices and local data
locations remain explicit rather than being hidden in package defaults.

## Python library

The [`Python`](Python) partition contains the reusable package. It has no GUI,
Web server, event-specific paths, or application runtime state.

```powershell
$Conda = "<miniforge-root>\Scripts\conda.exe"
& $Conda run -n solarphysics_env_latest python -m pip install -e ".\Python[dev]"
```

```python
from solar_toolkit.time import extract_time_from_filename, nearest_by_time

observations = [
    (name, extract_time_from_filename(name))
    for name in (
        "aia.lev1_euv_12s.2024-01-10T062925Z.171.image_lev1.fits",
        "aia.lev1_euv_12s.2024-01-10T062937Z.171.image_lev1.fits",
    )
]
nearest = nearest_by_time(
    "2024-01-10T06:29:33Z",
    observations,
    key=lambda item: item[1],
    max_diff_seconds=12,
)
print(nearest[0] if nearest else "no match")
```

See the [quickstart](Python/docs/quickstart.md),
[package organization](Python/CODE_ORGANIZATION_MANIFEST.md), and
[Python package reference](Python/README.md).

## Frontend applications

The versioned [`Apps`](Apps) partition contains the Miniforge-launched desktop,
Web, and Streamlit applications. Its nine launchable applications expose ten
interfaces, including the shared Workbench and Radio Workspace server.

From an activated Miniforge Prompt whose current directory is `Python`, launch
the all-in-one radio composite frontend with:

```powershell
# (solarphysics_env_latest) <repo>\Python>
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ..\Apps\run.ps1 frontend radio-composite
```

Installation, commands, theme behavior, state and path memory, scientific
display controls, privacy rules, and troubleshooting are documented in the
[Apps manual](Apps/README.md).

## Research evidence and tools

The [`Paper`](Paper) partition is the static literature-evidence layer.
Catalog retrieval and validation live under
[`tools/literature`](tools/literature). These components are kept separate from
both the Python library and application orchestration.

The complete dependency and data boundary is described in
[Repository architecture](ARCHITECTURE.md).

## Development

Run public-package checks in the primary Miniforge environment:

```powershell
$Conda = "<miniforge-root>\Scripts\conda.exe"
& $Conda run -n solarphysics_env_latest python -m pip check
& $Conda run -n solarphysics_env_latest python -m compileall -q Python/solar_toolkit Python/tests
& $Conda run -n solarphysics_env_latest python -m ruff check Python/solar_toolkit Python/tests
& $Conda run -n solarphysics_env_latest python -m pytest Python/tests
```

## License and citation

The Python library and applications use the MIT License. Bundled third-party
assets retain their own notices. Citation metadata for the reusable library is
provided in [`Python/CITATION.cff`](Python/CITATION.cff).
