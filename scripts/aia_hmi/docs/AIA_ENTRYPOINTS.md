# AIA/HMI Entrypoints

This directory now follows the same phased structure used by `scripts/radio`.
The old script path is kept as a compatibility entrypoint, while the reusable
API boundary lives under `solar_toolkit.aia`. The local `core/` package is a
compatibility namespace for historical imports.

## `scripts/aia_hmi/run_aia_euv_processor.py`

Recommended entrypoint for AIA EUV processing.

- Purpose: run the SDO/AIA EUV processor for single-band images, multi-band
  mosaics, test previews, and optional base/running difference products.
- Inputs: AIA FITS folders or files, wavelength selection, ROI, display limits,
  mosaic layout settings, and difference-image settings.
- Outputs: AIA PNG images, mosaics, and optional difference products using the
  existing output directory rules.
- Example:

```powershell
python scripts\aia_hmi\run_aia_euv_processor.py --mode mosaic --waves 94 131 171 193 211 304
```

## `sdo_aia_euv_processor.py`

Compatibility entrypoint for the historical command and import path.

- Purpose: preserve existing commands such as
  `python scripts\aia_hmi\sdo_aia_euv_processor.py ...`.
- Behavior: re-exports `AIAConfig`, `process_aia_fits`, `build_parser`,
  `config_from_args`, and `main` from `solar_toolkit.aia`.
- Note: importing this module is intentionally lightweight; the heavy
  SunPy/Astropy implementation loads only when processing is actually run.

## Public Modules

- `solar_toolkit.aia.config`: AIA and difference defaults plus `AIAConfig`.
- `solar_toolkit.aia.io`: FITS file ordering, wavelength directory discovery, and
  selected-file resolution.
- `solar_toolkit.aia.difference`: lightweight difference-image configuration helpers.
- `solar_toolkit.aia.mosaic`: lightweight mosaic layout and wavelength-slot helpers.
- `solar_toolkit.aia.processor`: lazy runtime dispatcher for the proven implementation.
- `solar_toolkit.aia.cli`: CLI parser, config construction, and command `main()`.

## Compatibility Modules

The historical `scripts.aia_hmi.core.aia_*` modules remain import-compatible
wrappers around `solar_toolkit.aia.*`.

## Compatibility Policy

This refactor does not intentionally change scientific defaults, image
processing, FITS/WCS handling, plotting parameters, output file names, or output
directory rules. The original implementation is retained internally and loaded
by the dispatcher when the workflow runs.
