# Project Optimization Plan

Last updated: 2026-05-30

This plan describes the remaining conservative optimization path for the
project. It is scoped to structure, documentation, tests, and safe cleanup. It
does not authorize changes to scientific algorithms, FITS/WCS behavior,
plotting defaults, matching thresholds, output names, or local research
products.

## Current Completed Direction

- Reusable radio helpers now have an installable package boundary under
  `solar_toolkit.radio`. The old `scripts.radio.core.*` module paths remain as
  compatibility aliases for local scripts, tests, and historical docs.
- AIA/HMI now follows a radio-style phased structure with a recommended
  `run_*.py` entrypoint, `core/`, `configs/`, and `docs/`.
- The historical AIA EUV processor path is kept as a compatibility wrapper.
- Current documentation now separates recommended guidance from historical
  reports through `docs/README.md`.
- Cleanup and retention decisions are documented in
  `PROJECT_CLEANUP_REPORT.md`, `FINAL_CODE_RETENTION_AND_REMOVAL_PLAN.md`, and
  `LEGACY_AND_REVIEW_FILES.md`.
- Lightweight tests check current documentation paths, local Markdown links,
  recommended AIA entrypoints, and common mojibake markers.

## High-Priority Next Work

1. Verify AIA/HMI output parity on real FITS data before claiming full
   scientific equivalence of the wrapper/core refactor.
2. Prefer `solar_toolkit.radio.*` for new reusable radio imports; keep legacy
   `scripts.radio.core.*` imports only when testing compatibility or touching
   unmigrated modules.
3. Add a CSO `run_*.py` wrapper only after confirming the current legacy
   spectrogram entrypoint behavior.
4. Keep radio config work separate from this cleanup unless the user explicitly
   asks to include it.
5. Continue documenting non-empty ignored local folders instead of deleting
   them automatically.

## Medium-Priority Next Work

1. Review `scripts/radio/docs/` reports for stale status language and mark
   older reports as historical when needed.
2. Add lightweight tests for any new wrapper introduced around legacy scripts.
3. Improve `docs/script_index.md` coverage for public entrypoints when new
   wrappers are added.
4. Consider moving README-ready root images into `docs/assets/images/` only
   after confirming their source and compression policy.

## Low-Priority Next Work

1. Reduce duplication between old reports after the current documentation set is
   stable.
2. Add small example assets only when they are explicitly reviewed and safe for
   Git.
3. Continue improving comments and docs around legacy code without changing
   scientific defaults.

## Validation Expectations

For safe structural work, keep using:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; D:\miniforge3\envs\solarphysics_env\python.exe -m pytest -q --basetemp outputs\pytest-tmp-codex tests\test_project_docs_current_paths.py tests\test_aia_hmi_radio_style_structure.py tests\test_imports.py tests\test_aia_difference_wrappers.py tests\test_aia_hmi_fits_rename.py
D:\miniforge3\envs\solarphysics_env\python.exe -m ruff check --no-cache scripts\aia_hmi tests\test_aia_hmi_radio_style_structure.py tests\test_project_docs_current_paths.py
D:\miniforge3\envs\solarphysics_env\python.exe -m compileall -q scripts\aia_hmi tests
```

These checks prove import, wrapper, documentation, and syntax consistency. They
do not prove scientific output equivalence on real observations.
