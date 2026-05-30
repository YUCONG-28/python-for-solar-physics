# AIA/HMI Entrypoints

This directory now follows the same phased structure used by `scripts/radio`.
The old script path is kept as a compatibility entrypoint, while the reusable
API boundary lives under `core/`.

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
  `config_from_args`, and `main` from `scripts.aia_hmi.core`.
- Note: importing this module is intentionally lightweight; the heavy
  SunPy/Astropy implementation loads only when processing is actually run.

## Core Modules

- `core/aia_config.py`: AIA and difference defaults plus `AIAConfig`.
- `core/aia_io.py`: FITS file ordering, wavelength directory discovery, and
  selected-file resolution.
- `core/aia_difference.py`: lightweight difference-image configuration helpers.
- `core/aia_mosaic.py`: lightweight mosaic layout and wavelength-slot helpers.
- `core/aia_processor.py`: lazy runtime dispatcher for the proven implementation.
- `core/aia_cli.py`: CLI parser, config construction, and command `main()`.

## Compatibility Policy

This refactor does not intentionally change scientific defaults, image
processing, FITS/WCS handling, plotting parameters, output file names, or output
directory rules. The original implementation is retained internally and loaded
by the dispatcher when the workflow runs.
