# Solar Physics Toolkit

> **Note:** This repository is not an out-of-the-box solar toolkit. It provides
> research components that an AI can select and combine according to the data,
> scientific goals, and constraints of a specific task.

[![CI](https://github.com/YUCONG-28/solarphysics/actions/workflows/ci.yml/badge.svg)](https://github.com/YUCONG-28/solarphysics/actions/workflows/ci.yml)

The [`Python`](Python) partition contains the reusable `solar-physics-toolkit`
library for multi-wavelength solar data analysis. It builds on
[Astropy](https://www.astropy.org/) and [SunPy](https://sunpy.org/) while
keeping data paths, event configuration, and workflow orchestration explicit.
The distribution is currently version 0.3.0 and is imported as
`solar_toolkit`.

## Python Library Capabilities

- Parse observation times, discover files, and build reproducible data
  inventories.
- Work with solar maps, coordinates, time series, image sequences, and media.
- Process AIA, HMI, CME, radio, and X-ray/DEM observations through focused
  domain modules.
- Fit reusable numerical models, including two-dimensional Gaussian radio
  sources and associated physical diagnostics.
- Query and download supported public archives through explicit network APIs.

## Install

Install the library from a source checkout:

```bash
python -m pip install -e "./Python"
```

For development and testing:

```bash
python -m pip install -e "./Python[dev]"
```

## Quick Example

The public API can match observations without instrument-specific setup or
local data discovery:

```python
from solar_toolkit.time import extract_time_from_filename, nearest_by_time

files = [
    "aia.lev1_euv_12s.2024-01-10T062925Z.171.image_lev1.fits",
    "aia.lev1_euv_12s.2024-01-10T062937Z.171.image_lev1.fits",
]
observations = [(name, extract_time_from_filename(name)) for name in files]

nearest = nearest_by_time(
    "2024-01-10T06:29:33Z",
    observations,
    key=lambda item: item[1],
    max_diff_seconds=12,
)
print(nearest[0] if nearest else "no match")
```

More deterministic examples are available in
[`Python/examples/public_api`](Python/examples/public_api).

## Package Map

| Namespace | Purpose |
| --- | --- |
| `solar_toolkit.data`, `io`, `time` | Observation inventories, file/FITS helpers, and time selection |
| `solar_toolkit.map`, `coordinates` | Solar-map geometry, metadata, alignment, and coordinate helpers |
| `solar_toolkit.timeseries`, `modeling` | Time-series processing and reusable numerical models |
| `solar_toolkit.aia`, `hmi`, `cme` | Instrument and phenomenon-specific image processing |
| `solar_toolkit.radio`, `xray_dem` | Radio-source analysis and X-ray/DEM calculations |
| `solar_toolkit.net` | Explicit archive queries and downloads |
| `solar_toolkit.visualization` | Plotting, frame processing, and media export helpers |

The package uses lazy domain imports so `import solar_toolkit` remains
lightweight. The public wheel contains no event-specific paths, CLI adapters,
GUI/Web servers, or local workflow configuration.

## Documentation

- [Quickstart](Python/docs/quickstart.md)
- [Package organization](Python/CODE_ORGANIZATION_MANIFEST.md)
- [Python package details](Python/README.md)

The separate [`Paper`](Paper) partition is a static literature-evidence layer.
Its catalog and method notes support research decisions but are not part of
the Python distribution. Catalog retrieval, validation, and publication tools
live under [`tools/literature`](tools/literature).

## Development

Run the public-package checks from the repository root:

```bash
python -m pip check
python -m compileall -q Python/solar_toolkit Python/tests Python/examples/public_api
python -m ruff check Python/solar_toolkit Python/tests Python/examples/public_api
python -m pytest Python/tests
python -m build --wheel --outdir Python/dist Python
```

GitHub Actions runs the same compile, lint, test, dependency, wheel-boundary,
secret-history, and literature-catalog checks in
[Public CI](.github/workflows/ci.yml).

## License and Citation

The Python library is released under the [MIT License](Python/LICENSE).
Citation metadata is provided in [`Python/CITATION.cff`](Python/CITATION.cff).
