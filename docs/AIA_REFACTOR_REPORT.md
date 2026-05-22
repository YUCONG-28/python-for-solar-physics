# AIA Refactor Report

Date: 2026-05-22

## Scope

Phase 3A organizes the AIA module around the current main processor without
deleting, moving, or renaming files. No real FITS batch processing or plotting
main workflow was run.

## Main Code

Primary AIA workflow:

- `scripts/aia_hmi/sdo_aia_euv_processor.py`

This file is the recommended README-facing entry point for:

- single AIA plot generation;
- multi-wavelength mosaic generation;
- base difference;
- running difference.

The main processor exposes these through `AIAConfig`, `process_aia_fits()`, and
CLI options such as:

- `--mode single`
- `--mode mosaic`
- `--draw-difference`
- `--difference-method base`
- `--difference-method running`
- `--difference-output-mode single|mosaic|both`

No scientific algorithm in this file was changed in this phase.

## Basic Code

Recommended basic/teaching script:

- `scripts/aia_hmi/sdo_aia_multichannel_panel.py`

Reason:

- It is shorter and easier to read than the main processor.
- It demonstrates the multi-wavelength teaching path: organize FITS files,
  synchronize around a 171 A base channel, estimate percentile display ranges,
  and render a six-panel overview.
- It is not currently the production entry point, but it remains useful as a
  readable example before users move to `sdo_aia_euv_processor.py`.

Keep this file for now. Do not delete it until a replacement minimal example or
README teaching section exists.

## Compatibility Wrappers

The following files are no longer independent algorithm implementations:

- `scripts/aia_hmi/sdo_aia_base_difference.py`
- `scripts/aia_hmi/sdo_aia_running_difference.py`

They are compatibility wrappers that preserve legacy defaults in
`LEGACY_DEFAULTS`, build a processor configuration, and delegate execution to
`scripts/aia_hmi/sdo_aia_euv_processor.py`.

Preserved legacy defaults include:

- base difference: wavelength 131, ROI `(180, 520, -340, 20)`, fixed range
  `[-888, 888]`, `start_idx=99`, `end_idx=200`;
- running difference: wavelength 94, ROI `(600, 1210, -280, 100)`, fixed range
  `[-777, 777]`, `start_idx=150`, `end_idx=450`;
- `use_band_subdirs=False` for both wrappers because the historical scripts
  pointed directly at a single-band FITS folder.

## Coverage By Main Processor

| 功能 | 主处理器覆盖情况 | 当前处理 |
| --- | --- | --- |
| Single AIA plot | Covered by `mode="single"` / `--mode single` | Use `sdo_aia_euv_processor.py` |
| Mosaic | Covered by `mode="mosaic"` / `--mode mosaic` plus mosaic layout options | Use `sdo_aia_euv_processor.py`; keep `sdo_aia_multichannel_panel.py` as teaching code |
| Base difference | Covered by `difference_method="base"` / `--difference-method base` | Legacy script remains wrapper |
| Running difference | Covered by `difference_method="running"` / `--difference-method running` | Legacy script remains wrapper |
| Legacy fixed vmin/vmax | Covered by fixed difference limits | Preserved in wrapper defaults |
| Legacy ROI | Covered by `roi_bounds` / `--roi` | Preserved in wrapper defaults |
| Legacy single-band directory | Covered through programmatic `use_band_subdirs=False` | Preserved in wrapper config |

## Legacy Or Deletion Candidates

No file was deleted in this phase.

Recommended final kept files:

- `scripts/aia_hmi/sdo_aia_euv_processor.py`
- `scripts/aia_hmi/sdo_aia_multichannel_panel.py`
- `scripts/aia_hmi/sdo_aia_base_difference.py`
- `scripts/aia_hmi/sdo_aia_running_difference.py`

Recommended legacy candidates:

- `scripts/aia_hmi/sdo_aia_base_difference.py`
- `scripts/aia_hmi/sdo_aia_running_difference.py`

These are legacy only in the sense that they preserve old entry-point names.
They are already thin wrappers, so moving them to a legacy directory is optional
and should wait until users no longer rely on the old filenames.

Potential deletion candidates requiring human confirmation:

- `scripts/aia_hmi/sdo_aia_base_difference.py`
- `scripts/aia_hmi/sdo_aia_running_difference.py`

Deletion should happen only after all of the following are true:

- README and docs no longer reference the old filenames as runnable entry
  points.
- Any notebooks, shell scripts, paper-reproduction notes, or local workflows
  have been updated to call `sdo_aia_euv_processor.py`.
- The legacy defaults preserved in `LEGACY_DEFAULTS` have been copied to config
  examples or paper-reproduction notes if still needed.
- A real-data comparison confirms that old figure reproduction no longer
  depends on wrapper-specific defaults.

Do not delete `scripts/aia_hmi/sdo_aia_multichannel_panel.py` yet. It remains
the selected basic code.

## Manual Confirmation Before Deletion

Before deleting any AIA wrapper, manually confirm:

- whether the old path is used by collaborators;
- whether the legacy ROI and fixed color limits are needed for paper figures;
- whether exact legacy output naming is needed;
- whether exact legacy output directory behavior is needed;
- whether base cutout-level derotation behavior from the original old script is
  required for pixel-exact figure reproduction;
- whether running first-frame original-image save behavior is still needed.

## Algorithm Impact

No AIA scientific algorithm was changed in this phase. Base difference remains
`current - base`; running difference remains `current - previous`. This phase
only documents the AIA retention decision and confirms the existing wrapper
state.
