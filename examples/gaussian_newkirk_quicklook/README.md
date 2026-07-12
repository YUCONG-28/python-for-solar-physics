# Gaussian/Newkirk Quicklook

This isolated helper regenerates two diagnostic plots from an existing
`radio_gaussian_fit_diagnostics.csv`-compatible file. If `--gaussian-csv` is
not provided, the helper resolves the full-event diagnostics CSV from
`--config`.

- `event_gaussian_newkirk_height_comparison.png`
- `gaussian_center_trajectory.png`

It also writes the intermediate tables used by those plots:

- `radio_gaussian_valid_centers.csv`
- `gaussian_newkirk_height_rows.csv`

## Usage

Run from the repository root with the Miniforge solar physics environment:

```powershell
$env:PATH="D:\miniforge3\envs\solarphysics_env;D:\miniforge3\envs\solarphysics_env\Library\mingw-w64\bin;D:\miniforge3\envs\solarphysics_env\Library\usr\bin;D:\miniforge3\envs\solarphysics_env\Library\bin;D:\miniforge3\envs\solarphysics_env\Scripts;$env:PATH"
D:\miniforge3\envs\solarphysics_env\python.exe examples\gaussian_newkirk_quicklook\quicklook_gaussian_newkirk.py --config radio_20250124_config
```

By default outputs are written to:

```text
examples\gaussian_newkirk_quicklook\quicklook_outputs\
```

Use `--output-dir <path>` to send the generated CSV and PNG files elsewhere.

To test a specific diagnostics CSV, pass it explicitly:

```powershell
D:\miniforge3\envs\solarphysics_env\python.exe examples\gaussian_newkirk_quicklook\quicklook_gaussian_newkirk.py --config radio_20250124_config --gaussian-csv outputs\radio\gaussian_spectrogram_overlay\radio_gaussian_fit_diagnostics.csv
```

The `verification_output\20250503_retune_*` CSV files are small retune
verification samples. They are useful for smoke tests, but they will not
visually match the full-event 2025-01-24 reference figures.

## Test

```powershell
D:\miniforge3\envs\solarphysics_env\python.exe -m pytest -q tests\test_radio_quicklook.py
```

The example CLI is a thin wrapper around `solar_toolkit.radio.quicklook`;
the reusable science and plotting logic is tested from `tests/`.
