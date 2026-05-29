# Phase 1 Import and Test Baseline Report

Date: 2026-05-29

## Scope

Phase 1 fixed stale radio test imports after the refactor that moved reusable
radio modules under `scripts/radio/core/`.

## Files Changed

- `tests/test_radio_newkirk_extrapolation.py`
  - Updated Newkirk imports from `scripts.radio.radio_newkirk_extrapolation` to
    `scripts.radio.core.radio_newkirk_extrapolation`.
- `tests/test_radio_pipeline_modules.py`
  - Updated public API import checks to import `radio_drift_rate`,
    `radio_gaussian_fit`, and `radio_spectrogram` from `scripts.radio.core`.
- `scripts/radio/__init__.py`
  - Added lazy compatibility re-exports for the core radio modules used by
    older `from scripts.radio import ...` callers.

## Backward Compatibility

The entrypoint files remain unchanged in this phase. Lazy re-exports avoid
importing the heavy radio modules until an older caller explicitly requests
them, reducing the chance of circular imports or optional dependency failures
during package import.

## Verification

`python -m pytest` executed under the `solarphysics_env` environment.

An earlier pytest run reported a partial result:

- Most tests completed.
- Several tests in `tests/test_aia_hmi_fits_rename.py` failed during setup.
- The repeated setup failure was:

```text
PermissionError: [WinError 5] Access is denied: 'C:\Users\Lee\AppData\Local\Temp\pytest-of-Lee'
```

That failure occurred while pytest was preparing the `tmp_path` fixture / base
temporary directory.

Temporary directory follow-up:

- `D:\spike_topping_type_III\Python\.pytest_tmp`: not found during cleanup
  check; no removal was needed.
- `D:\spike_topping_type_III\Python\.pytest_tmp_fresh_20260529`: not found
  during cleanup check; no removal was needed.
- `D:\spike_topping_type_III\Python\.pytest_tmp_run`: not found during cleanup
  check; no removal was needed.
- `C:\Users\Lee\AppData\Local\Temp\pytest-of-Lee`: still exists.

A fresh project-local base temp directory was created and write-tested:

```text
D:\spike_topping_type_III\Python\.pytest_tmp_run_final
```

Final pytest rerun command:

```powershell
conda activate solarphysics_env
python -m pytest --basetemp D:\spike_topping_type_III\Python\.pytest_tmp_run_final
```

Final result:

```text
88 passed, 2 warnings in 6.07s
```

Conclusion: the earlier `tests/test_aia_hmi_fits_rename.py` setup errors were
caused by local pytest temporary-directory state/permission issues, not by a
project source-code failure or rename-test logic failure.

## Scientific Behavior

No Gaussian fitting, source masking, background estimation, WCS/reprojection,
coordinate orientation, spectrogram frequency-axis handling, drift-rate
selection, Newkirk physics, or output field names were changed in this phase.
