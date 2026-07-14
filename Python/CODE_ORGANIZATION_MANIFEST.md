# Python public-package organization

The installable distribution is `solar-physics-toolkit` 0.3.0 and its import
namespace is `solar_toolkit`.

```text
solar_toolkit/
├─ aia/              reusable AIA processing
├─ hmi/              reusable HMI processing
├─ radio/            reusable radio calculations
├─ xray_dem/         HXI/SXR readers and numerical helpers
├─ time/ io/ data/   foundation parsing and explicit I/O
├─ map/ timeseries/  array, map and time-series helpers
├─ modeling/         reusable models
├─ cme/ net/         explicit CME and network helpers
└─ visualization/    shared frames, plotting and media calculations
```

The public package has no event discovery, local path overrides, CLI adapters,
browser/server code, GUI assets or workflow orchestration. Those components are
kept in the ignored independent `../Local` repository under `solar_apps`.

Dependency direction is enforced as:

```text
Local/solar_apps  --->  Python/solar_toolkit
Python/solar_toolkit  -X->  Local, scripts, legacy
```

See `docs/FUNCTION_MAP.md`, `docs/MAIN_FILES.md`, and `docs/script_index.md` for
the maintained public surface.
