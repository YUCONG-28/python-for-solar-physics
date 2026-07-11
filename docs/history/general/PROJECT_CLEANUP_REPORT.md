# Project Cleanup Report

Last updated: 2026-05-30

This report summarizes the current cleanup state of the repository. It replaces
the older pre-refactor audit notes whose file lists and cache paths no longer
matched the workspace.

## Cleanup Scope

This cleanup is intentionally conservative:

- Scientific algorithms, FITS/WCS handling, plotting defaults, output naming,
  and local data products are not changed as part of cleanup.
- Legacy scientific entrypoints are kept as wrappers or review files until
  output parity can be verified with real data.
- Ignored local data, archive folders, workbooks, and manually selected results
  are documented but not automatically deleted.
- Regenerable caches and temporary test products are safe cleanup targets.

## Completed Cleanup

- Removed reproducible Python and test artifacts when present:
  `__pycache__/`, `.ruff_cache/`, pytest temporary folders, and old
  `pytest-cache-files-*` style directories.
- Kept non-empty local or research-sensitive ignored paths:
  `archive/`, `data dowload/`, `scripts/radio/outputs/`, `.automated-tool*`,
  `.vscode/`, `AIA.xlsx`, and `CSO.xlsx`.
- Stopped tracking generated-looking root products while leaving local copies in
  place: `HXR.png`, `SXR.png`, `SXR to HXR.png`,
  `SXR to HXR enhance.png`, and the root drift-selection JSON/PNG products.
- Removed the tracked zero-byte `fit_min_mask_pixels` marker file after
  confirming no code or docs referenced it as a path.
- Replaced the large historical AIA script body with a compatibility wrapper
  while retaining the implementation under `scripts/aia_hmi/core/`.
- Added the recommended AIA entrypoint
  `scripts/aia_hmi/run_aia_euv_processor.py`.
- Updated the public documentation set to point at current recommended
  entrypoints and to describe the AIA/HMI radio-style phased structure.

## Current Structure Decisions

| Area | Current decision |
| --- | --- |
| AIA/HMI main processor | Use `scripts/aia_hmi/run_aia_euv_processor.py`; keep `scripts/aia_hmi/sdo_aia_euv_processor.py` as a compatibility wrapper. |
| AIA/HMI reusable code | Place reusable code under `solar_toolkit.aia`; keep `scripts/aia_hmi/core/` as deprecated compatibility aliases for old imports. |
| Radio workflows | Keep existing radio run wrappers, `core/`, `configs/`, `legacy/`, and `docs/` structure. Current radio config changes in the working tree are treated as user work and are not part of this cleanup pass. |
| Historical AIA difference scripts | Keep under `legacy/scripts/aia_hmi/` for parameter and output comparison. |
| Local products | Keep ignored outputs and workbooks local; document them in `docs/LEGACY_AND_REVIEW_FILES.md` rather than deleting them. |

## Current Documentation Set

The current high-signal project documentation is:

- `README.md`: bilingual public overview and recommended entrypoints.
- `docs/project_structure.md`: repository layout, data policy, and AIA/HMI
  structure notes.
- `docs/script_index.md`: public runnable scripts, compatibility entrypoints,
  and selected examples.
- `docs/MAIN_FILES.md`: compact list of core workflows and module boundaries.
- `docs/LEGACY_AND_REVIEW_FILES.md`: files and local artifacts that require
  manual review before removal.
- `scripts/aia_hmi/docs/AIA_ENTRYPOINTS.md`: AIA-specific entrypoint and
  compatibility policy.

## Validation

The cleanup is checked with lightweight, data-independent tests:

- Documentation path and mojibake checks in
  `tests/test_project_docs_current_paths.py`.
- AIA/HMI structure and compatibility checks in
  `tests/test_aia_hmi_radio_style_structure.py`.
- Existing import/wrapper/rename tests for public compatibility.
- `ruff check . --no-cache`.
- `compileall` on `solar_toolkit`, `scripts`, `tests`, and `examples`.
- Targeted pytest with third-party plugin autoload disabled and a workspace
  temporary directory.

Full scientific output equivalence is not claimed by these checks. Real FITS
output comparison remains a separate validation step before deleting legacy
scientific workflows.

## Remaining Review Items

- Decide whether ignored local folders such as `data dowload/` and
  `scripts/radio/outputs/` should be archived outside the repo or kept in place.
- Decide whether the local root-level PNG files should become compressed README
  assets under `docs/assets/images/`.
- Decide whether `AIA.xlsx` and `CSO.xlsx` are local scratch products, research
  inputs, or publishable examples.
- Continue migrating future large scripts using the same wrapper-plus-core
  pattern only after defining tests for their public behavior.
