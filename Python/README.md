# Solar Physics Toolkit

[![CI](https://github.com/YUCONG-28/solarphysics/actions/workflows/ci.yml/badge.svg)](https://github.com/YUCONG-28/solarphysics/actions/workflows/ci.yml)

`solar-physics-toolkit` is the reusable scientific-library partition of the
[`solarphysics`](https://github.com/YUCONG-28/solarphysics) repository. The
distribution name remains `solar-physics-toolkit`, the import namespace remains
`solar_toolkit`, and this partition is version 0.3.0.

## Public boundary

The wheel contains reusable base, time, I/O, data, map, time-series, modeling,
AIA, HMI, CME, network, X-ray and radio computation modules. Radio computation
includes the explicit modules:

- `solar_toolkit.radio.reprojection`
- `solar_toolkit.radio.cso_processing`
- `solar_toolkit.radio.physical_diagnostics`

Event configuration, path discovery, CLIs, GUI/Web servers, browser launchers,
static assets and cross-domain orchestration are intentionally not distributed.
They live in the ignored, independent local application repository at
`../Local` and depend on this package in the direction `Local -> solar_toolkit`.
There are no public console scripts in version 0.3.0.

## Install

From the unified repository root:

```powershell
D:\miniforge3\envs\solarphysics_env\python.exe -m pip install -e .\Python
```

Library use always supplies paths and event configuration explicitly:

```python
from solar_toolkit.radio.config import RadioEventConfig
from solar_toolkit.radio.reprojection import nearest_time_index
from datetime import datetime, timedelta

event = RadioEventConfig.from_mapping(
    {"user": {"data": {"multi_band_freqs": [149.0, 164.0]}}}
)
target = datetime.fromisoformat("2025-01-24T04:48:30")
index = nearest_time_index(
    target,
    [target - timedelta(seconds=1), target + timedelta(seconds=2)],
)
```

See [`examples/public_api`](examples/public_api) for source-tree examples.

## Verify

```powershell
$env:PATH="D:\miniforge3\envs\solarphysics_env;D:\miniforge3\envs\solarphysics_env\Library\mingw-w64\bin;D:\miniforge3\envs\solarphysics_env\Library\usr\bin;D:\miniforge3\envs\solarphysics_env\Library\bin;D:\miniforge3\envs\solarphysics_env\Scripts;$env:PATH"
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD="1"
D:\miniforge3\envs\solarphysics_env\python.exe -m pip check
D:\miniforge3\envs\solarphysics_env\python.exe -c "import ssl; ssl.create_default_context(); import sunpy.map; from sunpy.net import Fido"
D:\miniforge3\envs\solarphysics_env\python.exe -m compileall -q solar_toolkit tests examples\public_api
D:\miniforge3\envs\solarphysics_env\python.exe -m ruff check solar_toolkit tests examples\public_api
D:\miniforge3\envs\solarphysics_env\python.exe -m pytest tests
D:\miniforge3\envs\solarphysics_env\python.exe -m build --wheel --no-isolation --outdir dist .
```

## License and citation

This Python partition is covered by [`LICENSE`](LICENSE). The repository root
does not impose that license on the separate Paper evidence layer. Citation
metadata is in [`CITATION.cff`](CITATION.cff).
