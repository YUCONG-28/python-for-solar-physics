# Radio Refactor Report

## Moved Files

- `radio_burst_gaussian_newkirk_pipeline.py` -> `run_radio_burst_pipeline.py`
- `radio_gaussian_fit.py` -> `core/radio_gaussian_fit.py`
- `radio_spectrogram.py` -> `core/radio_spectrogram.py`
- `radio_drift_rate.py` -> `core/radio_drift_rate.py`
- `radio_newkirk_extrapolation.py` -> `core/radio_newkirk_extrapolation.py`
- `radio_source_map_plot_gaussian_overlay.py` ->
  `legacy/radio_source_map_plot_gaussian_overlay.py`
- `cso_radio_spectrogram_plot.py` -> `legacy/cso_radio_spectrogram_plot.py`
- `sdo_aia_radio_hmi_overlay.py` -> `legacy/sdo_aia_radio_hmi_overlay.py`

## New Entrypoints

- `run_radio_burst_pipeline.py`: full Gaussian + spectrogram + drift-rate +
  Newkirk pipeline.
- `run_radio_source_map.py`: thin compatibility wrapper for radio source-map
  plotting and Gaussian overlay.
- `run_aia_radio_hmi_overlay.py`: thin compatibility wrapper for AIA/HMI/radio
  overlays.

## Legacy Archive

The following scripts were archived without deleting scientific code:

- `legacy/radio_source_map_plot_gaussian_overlay.py`
- `legacy/cso_radio_spectrogram_plot.py`
- `legacy/sdo_aia_radio_hmi_overlay.py`

## Moved Runtime Artifacts

- `spectrogram_drift_rate_manual_selection.json` ->
  `outputs/selections/spectrogram_drift_rate_manual_selection.json`

No root-level PNG or CSV runtime artifacts were present during this pass.

## Import Changes

- `run_radio_burst_pipeline.py` now imports the source-map workflow from
  `scripts.radio.legacy.radio_source_map_plot_gaussian_overlay`.
- `run_radio_burst_pipeline.py` now imports Gaussian fitting, drift-rate,
  Newkirk, and spectrogram helpers from `scripts.radio.core`.
- `core/radio_gaussian_fit.py`, `core/radio_spectrogram.py`, and
  `core/radio_drift_rate.py` now import shared legacy helpers through
  `..legacy.radio_source_map_plot_gaussian_overlay`.
- Package marker files were added to `radio/`, `radio/core/`, and
  `radio/legacy/` to make imports explicit.

## Recommended Current Entrypoint

Use `python run_radio_burst_pipeline.py` for the complete scientific workflow.
Use `python run_radio_source_map.py` for quick source-map and Gaussian-overlay
checks. Use `python run_aia_radio_hmi_overlay.py` for EUV/HMI/radio context
overlays.

## Still Depending On Legacy

- Full source-map orchestration still lives in
  `legacy/radio_source_map_plot_gaussian_overlay.py`.
- `core.radio_gaussian_fit`, `core.radio_spectrogram`, and
  `core.radio_drift_rate` still rely on small helper functions/constants from
  the legacy source-map script.
- The AIA/HMI/radio overlay path still runs the archived script and has not yet
  been deduplicated against `core.radio_gaussian_fit`.

## Suggested Next Slimming Pass

1. Extract datetime parsing, output path helpers, diagnostics constants, and
   coordinate conversion utilities into `core/radio_io.py`.
2. Switch the three core modules to `core.radio_io` and remove their legacy
   imports.
3. Move `legacy.radio_source_map_plot_gaussian_overlay.main()` orchestration
   into a smaller callable used by `run_radio_source_map.py`.
4. Replace duplicate Gaussian code in the AIA/HMI/radio overlay workflow with
   calls to `core.radio_gaussian_fit`.
5. After output comparisons are reviewed, decide whether old duplicate blocks
   can be removed in a separate commit.

## Verification Notes

- `python` is not available on PATH in the current PowerShell environment, so
  the bundled Codex Python was used for syntax verification.
- `compileall` passed for the repository's `scripts/radio` directory.
- Root-level runtime artifact checks found no selection JSON, preview PNG, or
  diagnostics CSV files left in `scripts/radio`.
- Direct entrypoint smoke runs reached dependency import and then stopped with
  environment errors: `matplotlib` is missing for the radio pipeline/source-map
  workflows, and `astropy` is missing for the AIA/HMI/radio workflow in the
  bundled Python environment.
