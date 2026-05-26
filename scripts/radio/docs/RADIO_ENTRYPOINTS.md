# Radio Entrypoints

This directory now keeps three root-level entrypoints. Run them from
`<PROJECT_ROOT>\Python` with `PYTHONPATH` set to that same directory.
All three entrypoints default to `--config radio_20250124_config`.

## `run_radio_burst_pipeline.py`

Recommended full scientific pipeline.

- Purpose: run Gaussian fitting, dynamic spectrogram support, manual drift-rate
  selection/overlay, Newkirk extrapolation, and summary plots/tables.
- Inputs: radio FITS settings, spectrogram FITS settings, drift-rate settings,
  and output settings inherited from the legacy source-map configuration.
- Outputs: Gaussian diagnostics, valid Gaussian centers, Newkirk extrapolated
  Gaussian heights, drift-rate Newkirk speeds, and diagnostic preview figures.
- Best for: complete burst analysis where fitted radio-source centers and
  drift-rate-derived speeds are both needed.
- Example: `python scripts\radio\run_radio_burst_pipeline.py --config radio_20250124_config`

## `run_radio_source_map.py`

Compatibility entrypoint for radio source maps with Gaussian overlay.

- Purpose: run the multi-frequency radio source-map plotting workflow and draw
  source masks, Gaussian centers, and FWHM ellipses.
- Inputs: radio FITS directories/files, frequency bands, polarization mode,
  display limits, and Gaussian fitting parameters from the archived legacy
  source-map script.
- Outputs: single-band or multi-band source-map images and Gaussian diagnostics
  when enabled.
- Best for: quick visual checks of radio images, source masks, fitted centers,
  FWHM ellipses, and per-band image quality without forcing Newkirk analysis.
- Example: `python scripts\radio\run_radio_source_map.py --config radio_20250124_config`

## `run_aia_radio_hmi_overlay.py`

Compatibility entrypoint for AIA/HMI/radio overlays.

- Purpose: run the archived AIA/HMI/radio overlay workflow with WCS alignment,
  reprojection, magnetic-field contours, and radio overlays.
- Inputs: AIA files, HMI files, radio products, wavelength/band matching
  settings, WCS/reprojection settings, and overlay display options from the
  archived AIA/HMI/radio script.
- Outputs: AIA/HMI/radio overlay images and AIA-radio Gaussian diagnostics when
  enabled.
- Best for: comparing radio source locations against EUV context and HMI
  magnetic structure.
- Example: `python scripts\radio\run_aia_radio_hmi_overlay.py --config radio_20250124_config`

## Output Placement

Newly generated selection JSON, preview PNG, and diagnostics CSV files should be
written under the configured `output_dir` or under `outputs/selections`,
`outputs/previews`, and `outputs/diagnostics` for local scratch runs. They
should not be placed in the `scripts/radio` root.
