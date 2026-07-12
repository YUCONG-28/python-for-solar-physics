# Radio Configs

Daily edits should go in `configs/radio_20250124_config.py`. Do not put a new
`USER_CONFIG` block back into `legacy/radio_source_map_plot_gaussian_overlay.py`.

## Common Edits

- `data`: radio FITS paths, frequency list, polarization, frame range.
- `display`: coordinate limits, colormap, per-band percentile settings.
- `gaussian`: source mask thresholds, Gaussian fit controls, FWHM limits, center
  offset limits.
- `spectrogram`: dynamic-spectrum FITS files, time/frequency range,
  polarization, colormap, and event-specific `vmin`/`vmax` color limits.
- `drift_rate`: interactive selection port, browser behavior, selection reuse,
  diagnostics output names.
- `output`: output directory, plot display/save toggles, DPI.
- `OUTPUT_CONFIG`: common output directory, optional analysis subdirectory,
  Gaussian/Newkirk/drift CSV names, drift-selection subdirectory, and summary
  dashboard save toggles.
- `NEWKIRK_CONFIG`: Newkirk multipliers, fundamental/harmonic settings, solar
  radius in arcseconds, and output CSV names.
- `AIA_RADIO_HMI_CONFIG`: AIA/HMI/radio overlay paths, AIA file range, AIA
  wavelength label, HMI matching, explicit `roi_bounds_arcsec`
  left/bottom/right/top limits, and overlay output settings. Keep this block in
  the same event config file as `USER_CONFIG`.

## Run Commands

```powershell
cd <repository-root>
conda activate solarphysics_env
$env:PYTHONPATH = "<repository-root>"

python scripts\radio\run_radio_source_map.py --config radio_20250124_config
python scripts\radio\run_radio_burst_pipeline.py --config radio_20250124_config
python scripts\radio\run_aia_radio_hmi_overlay.py --config radio_20250124_config
python scripts\radio\run_aia_radio_hmi_overlay.py --config radio_20250503_config
```

Use the event config module directly for radio and AIA/radio/HMI runs.

If `--config` is omitted, all three entrypoints default to
`radio_20250124_config`.

For one-off output changes, keep the config file unchanged and pass CLI
overrides instead:

```powershell
python scripts\radio\run_radio_source_map.py --config radio_20250503_config --output-dir D:\tmp\radio --analysis-subdir quick_check --gaussian-csv gaussian_quick.csv
python scripts\radio\run_radio_burst_pipeline.py --config radio_20250503_config --output-dir D:\tmp\radio --analysis-subdir quick_check --valid-centers-csv valid.csv --newkirk-csv heights.csv --drift-speed-csv speeds.csv
```
