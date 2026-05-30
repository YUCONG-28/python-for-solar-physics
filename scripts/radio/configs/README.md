# Radio Configs

Daily edits should go in `configs/radio_20250124_config.py`. Do not put a new
`USER_CONFIG` block back into `legacy/radio_source_map_plot_gaussian_overlay.py`.

## Common Edits

- `data`: radio FITS paths, frequency list, polarization, frame range.
- `display`: coordinate limits, colormap, per-band percentile settings.
- `gaussian`: source mask thresholds, Gaussian fit controls, FWHM limits, center
  offset limits.
- `spectrogram`: dynamic-spectrum FITS files, time range, frequency range,
  polarization.
- `drift_rate`: interactive selection port, browser behavior, selection reuse,
  diagnostics output names.
- `output`: output directory, plot display/save toggles, DPI.
- `NEWKIRK_CONFIG`: Newkirk multipliers, fundamental/harmonic settings, solar
  radius in arcseconds, and output CSV names.
- `AIA_RADIO_HMI_CONFIG`: AIA/HMI/radio overlay paths, AIA file range, AIA
  wavelength label, HMI matching, WCS/reproject ROI, and overlay output
  settings. Keep this block in the same event config file as `USER_CONFIG`.

## Run Commands

```powershell
cd D:\spike_topping_type_III\Python
conda activate solarphysics_env
$env:PYTHONPATH = "D:\spike_topping_type_III\Python"

python scripts\radio\run_radio_source_map.py --config radio_20250124_config
python scripts\radio\run_radio_burst_pipeline.py --config radio_20250124_config
python scripts\radio\run_aia_radio_hmi_overlay.py --config radio_20250124_config
python scripts\radio\run_aia_radio_hmi_overlay.py --config radio_20250503_config
```

The historical `aia_radio_hmi_20250124_config` module remains importable as a
compatibility shim, but new overlay runs should use the event config module
directly.

If `--config` is omitted, all three entrypoints default to
`radio_20250124_config`.
