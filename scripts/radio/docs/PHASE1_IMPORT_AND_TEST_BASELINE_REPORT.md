# Phase 1 Import and Test Baseline Report

Date: 2026-05-27

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

- `python` and `py` are not available on this workstation PATH.
- Equivalent compile check was run with the bundled Codex Python:

```powershell
& 'C:\Users\Lee\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall scripts\radio
```

Result: `compileall` completed for `scripts/radio`.

Radio pytest baseline could not be executed with the bundled Codex Python
because `pytest` is not installed in that runtime:

```text
C:\Users\Lee\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe: No module named pytest
```

## Scientific Behavior

No Gaussian fitting, source masking, background estimation, WCS/reprojection,
coordinate orientation, spectrogram frequency-axis handling, drift-rate
selection, Newkirk physics, or output field names were changed in this phase.
