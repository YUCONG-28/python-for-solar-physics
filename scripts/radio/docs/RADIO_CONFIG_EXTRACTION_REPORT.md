# Radio Config Extraction Report

## What Moved

`USER_CONFIG` was extracted from:

- `scripts/radio/legacy/radio_source_map_plot_gaussian_overlay.py`

and moved to:

- `scripts/radio/configs/radio_20250124_config.py`

The Newkirk settings that were previously nested under `USER_CONFIG["newkirk"]`
were split into:

- `scripts/radio/configs/radio_20250124_config.py::NEWKIRK_CONFIG`

## New Config Files

- `configs/__init__.py`: config module loader and default Newkirk fallback.
- `configs/radio_20250124_config.py`: main user-editable config for the
  2025-01-24 event.
- `configs/radio_20250503_config.py`: template config for a future 2025-05-03
  pass with TODO paths/times.
- `configs/README.md`: user-facing edit and run instructions.
- `configs/example_radio_pipeline_config.py`: compatibility alias to the new
  2025-01-24 config.

## Entrypoint Config Selection

All three root entrypoints accept:

```powershell
--config radio_20250124_config
--config radio_20250503_config
--config scripts.radio.configs.radio_20250124_config
```

If `--config` is omitted, the default is `radio_20250124_config`.

Examples:

```powershell
python scripts\radio\run_radio_source_map.py --config radio_20250124_config
python scripts\radio\run_radio_burst_pipeline.py --config radio_20250124_config
python scripts\radio\run_aia_radio_hmi_overlay.py --config radio_20250124_config
```

## Legacy Default Loading

`legacy/radio_source_map_plot_gaussian_overlay.py` no longer contains the full
editable `USER_CONFIG` block. It now imports the default event config with:

```python
try:
    from scripts.radio.configs.radio_20250124_config import USER_CONFIG
except Exception:
    USER_CONFIG = {}
```

The existing `CONFIG = load_script_config(... build_config(USER_CONFIG,
DEFAULT_CONFIG) ...)` construction remains in place.

## `main(user_config=...)`

`legacy.radio_source_map_plot_gaussian_overlay.main()` now accepts an optional
`user_config` argument. When supplied, it rebuilds the legacy flat config through
the existing `build_config(user_config, DEFAULT_CONFIG)` path, preserving the
old workflow and helper logic.

## Newkirk Config Usage

`run_radio_burst_pipeline.py` now loads:

- `USER_CONFIG` for source-map, Gaussian, spectrogram, and drift-rate settings.
- `NEWKIRK_CONFIG` for Newkirk multipliers, harmonics, solar-radius scale, and
  Newkirk output CSV names.

If a config module omits `NEWKIRK_CONFIG`, `configs.DEFAULT_NEWKIRK_CONFIG` is
used as the fallback.

## User Edit Target

For day-to-day work, edit:

- `scripts/radio/configs/radio_20250124_config.py`

Do not reintroduce a large `USER_CONFIG` block into:

- `scripts/radio/legacy/radio_source_map_plot_gaussian_overlay.py`

## Verification Results

- `python -m compileall scripts\radio` could not run because `python` is not on
  PATH in the current PowerShell environment.
- The equivalent bundled-Python command passed:
  `C:\Users\Lee\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m compileall scripts\radio`.
- Config loader test passed for short config names:
  `load_radio_user_config("radio_20250124_config")` returned `mode=multi_band`
  and `multipliers=[1, 2, 4]`.
- Config loader test passed for fully qualified module names:
  `load_radio_user_config("scripts.radio.configs.radio_20250124_config")`
  returned `mode=multi_band` and `harmonics=[1, 2]`.
- Template config loader test passed for `radio_20250503_config`; it returns the
  copied structure with TODO paths.
- Legacy import/config smoke test was attempted with bundled Python and stopped
  at `ModuleNotFoundError: No module named 'matplotlib'`.

## Remaining Limits

- The available shell environment does not expose the project conda environment
  or a `python` command on PATH; verification used the bundled Codex Python.
- The bundled Python environment lacks scientific runtime dependencies such as
  `matplotlib`, `astropy`, `scipy`, and `tqdm`, so full entrypoint execution and
  dependency-heavy legacy imports cannot complete there.
- `run_aia_radio_hmi_overlay.py` now consumes AIA/HMI/radio overlay config via
  `AIA_RADIO_HMI_CONFIG`. The archived AIA/HMI/radio script still owns its
  dataclass defaults for parameters not yet externalized.
