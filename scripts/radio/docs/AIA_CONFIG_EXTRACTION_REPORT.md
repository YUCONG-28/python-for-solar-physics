# AIA Config Extraction Report

## What Was Extracted

AIA/HMI/radio overlay parameters were extracted from the default values in:

- `scripts/radio/legacy/sdo_aia_radio_hmi_overlay.py::Config`

into the event config:

- `scripts/radio/configs/radio_20250124_config.py`

so the existing default `--config radio_20250124_config` works for the AIA entrypoint.
Later event configs should keep their own `AIA_RADIO_HMI_CONFIG` block in the
same file as `USER_CONFIG`.

## Extracted Parameter Groups

- `paths`: AIA directory, HMI directory, radio base directory, output directory.
- `aia`: AIA wavelength label, AIA file index range, AIA colormap and intensity range.
- `hmi`: HMI overlay toggle, time threshold, smoothing, magnetic contour levels.
- `radio`: selected radio bands, polarization mode, RR/LL directory suffixes, matching thresholds, RA/DEC map toggle.
- `wcs_reproject`: ROI bottom-left/top-right and RA/DEC-map use for WCS/reproject behavior.
- `gaussian`: AIA/radio Gaussian overlay thresholds and diagnostics settings.
- `display`: radio contours, fitted center marker, per-band display colors.
- `output`: save toggle, DPI, output directory.
- `runtime`: debug and auxiliary output toggles.

## Legacy Script Changes

`legacy/sdo_aia_radio_hmi_overlay.py` now has:

- `main(user_config=None)`
- `apply_aia_radio_hmi_user_config(cfg, user_config)`

The existing AIA/HMI/radio matching, WCS/reproject, Gaussian fitting, HMI contour,
and plotting algorithms were not changed. The new helper only maps grouped config
values onto the existing `Config` dataclass before the old workflow runs.

## Entrypoint Changes

`run_aia_radio_hmi_overlay.py` now loads AIA overlay config through:

```python
load_aia_radio_hmi_user_config(args.config)
```

and calls:

```python
legacy_aia.main(user_config=user_config)
```

Supported examples:

```powershell
python scripts\radio\run_aia_radio_hmi_overlay.py --config radio_20250124_config
python scripts\radio\run_aia_radio_hmi_overlay.py --config radio_20250503_config
```

## User Edit Target

For AIA/HMI/radio overlay work, edit the relevant event config:

- `scripts/radio/configs/radio_20250124_config.py`
- `scripts/radio/configs/radio_20250503_config.py`

Common edit locations in the `AIA_RADIO_HMI_CONFIG` block:

- AIA file path: `AIA_RADIO_HMI_CONFIG["paths"]["aia_base_dir"]`
- HMI file path: `AIA_RADIO_HMI_CONFIG["paths"]["hmi_base_dir"]`
- radio file path: `AIA_RADIO_HMI_CONFIG["paths"]["radio_base_dir"]`
- AIA wavelength: `AIA_RADIO_HMI_CONFIG["aia"]["wavelength"]`
- WCS/reproject ROI: `AIA_RADIO_HMI_CONFIG["wcs_reproject"]["roi_bottom_left"]`
  and `AIA_RADIO_HMI_CONFIG["wcs_reproject"]["roi_top_right"]`
- output path: `AIA_RADIO_HMI_CONFIG["output"]["output_dir"]`

## Verification Notes

- `compileall scripts\radio` was run with the bundled Codex Python because
  `python` is not on PATH in the current PowerShell environment.
- AIA config loader checks were run for event config modules such as
  `radio_20250124_config`.
- The requested config loading checks passed: `load_radio_user_config` returned
  `mode=multi_band` and `multipliers=[1, 2, 4]`; `load_aia_radio_hmi_user_config`
  returned a `dict` with `aia.wavelength=171`.
- Full AIA entrypoint execution was not forced in the bundled Python environment
  because it lacks scientific dependencies such as `astropy`, `sunpy`,
  `matplotlib`, `scipy`, and `tqdm`.

## Remaining Limits

- The legacy AIA script still owns the AIA/HMI/radio plotting and alignment
  implementation. This pass only injects external configuration.
- Some Gaussian parameters remain duplicated between radio source-map config and
  AIA overlay config until the AIA workflow is refactored to reuse
  `core.radio_gaussian_fit`.
