# Public workflow index

Version 0.3.0 has no public scripts or console entry points. Public users import
`solar_toolkit` modules and pass paths/configuration explicitly.

The four local replacement entry points are kept outside the public Git index:

```text
python -m solar_apps.aia.cli
python -m solar_apps.radio.cli
python -m solar_apps.image_viewer.cli
python -m solar_apps.webapp.cli
```

They are listed here only to explain the boundary; their source and tests live
in the independent ignored `Local` repository.
