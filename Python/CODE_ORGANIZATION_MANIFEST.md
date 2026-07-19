# Python public-package organization

The installable distribution is `solar-physics-toolkit` 0.3.0 and its import
namespace is `solar_toolkit`.

```text
solar_toolkit/
|-- data/             observation inventories and data manifests
|-- io/               explicit file discovery, FITS, and manifest helpers
|-- time/             filename/time parsing, formatting, and selection
|-- map/              map geometry, metadata, image, and operation helpers
|-- timeseries/       time-series tables and numerical processing
|-- modeling/         reusable mathematical models and fitting primitives
|-- net/              explicit network download and archive clients
|-- visualization/    shared plotting, frame, and media calculations
|-- aia/              reusable AIA processing
|-- hmi/              reusable HMI processing
|-- radio/            reusable radio calculations
|-- xray_dem/         HXI/SXR readers and numerical helpers
`-- cme/              CME file and image-processing helpers
```

This layout follows the same separation used by established astronomy
packages: foundation data structures and I/O stay separate from domain
instrument packages, and application workflows live outside the public library.

The public package has no event discovery, local path overrides, CLI adapters,
browser/server code, GUI assets or workflow orchestration. Those components are
kept in the public `../Apps` source partition under `solar_apps`; their machine
configuration and runtime state live in the ignored `../Local` partition.

Dependency direction is enforced as:

```text
Apps/solar_apps  --->  Python/solar_toolkit
Python/solar_toolkit  -X->  Apps/solar_apps
```

See `docs/FUNCTION_MAP.md`, `docs/MAIN_FILES.md`, and `docs/script_index.md` for
the maintained public surface.
