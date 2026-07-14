# Public function map

| Area | Public modules | Responsibility |
| --- | --- | --- |
| Foundation | `solar_toolkit.time`, `io`, `data`, `map`, `timeseries` | Parsing, discovery, explicit I/O, coordinate-neutral array/table helpers |
| Modeling | `solar_toolkit.modeling`, `gaussian` | Reusable numerical models and fitting |
| AIA/HMI | `solar_toolkit.aia`, `hmi` | FITS selection, normalization, differences, mosaics and magnetogram calculations |
| CME/network | `solar_toolkit.cme`, `net` | Explicit file processing, queries and downloads |
| X-ray | `solar_toolkit.xray_dem.hxi`, `processing`, `sxr` | Reusable readers and numerical processing |
| Radio core | `solar_toolkit.radio` | FITS metadata, Gaussian fitting, spectra, ROI statistics, trajectories and diagnostics |
| Radio split modules | `radio.reprojection`, `radio.cso_processing`, `radio.physical_diagnostics` | Reprojection, CSO array processing and pure physical diagnostics |

Application servers, event recipes, CLIs and workflow orchestration are owned by
the local `solar_apps` namespace and must depend on this public layer, never the
reverse.
