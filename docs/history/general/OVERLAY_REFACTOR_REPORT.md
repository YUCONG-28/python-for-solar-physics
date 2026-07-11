# AIA/Radio/HMI Overlay Refactor Report

Date: 2026-05-22

## Scope

Phase 3C organizes the AIA/radio/HMI overlay module around the formal main
script and keeps one basic example in the normal examples folder. No files were
deleted. No real FITS plotting workflow was run.

## Main Code

Formal main code:

- `scripts/radio/sdo_aia_radio_hmi_overlay.py`

This remains the recommended production entry point for AIA/radio/HMI overlay
figures. It owns the formal time matching, radio contour extraction, Gaussian
radio reprojection, AIA context handling, optional HMI contour overlay, and
output workflow.

## Experimental Code Not Modified

Do not modify automatically:

- `scripts/radio/sdo_aia_radio_hmi_overlay_bgcorrected.py`

Reason: this file contains experimental background subtraction and robust
Gaussian/background fitting behavior. It may encode important scientific
assumptions and should stay separate until the background-correction science is
reviewed.

This phase did not modify that file.

## Basic Example

Selected basic example:

- `examples/radio_aia_hmi/aia_radio_hmi_overlay_demo.py`

Reason:

- It is shorter than the extended example.
- It still demonstrates the AIA/radio/HMI workflow, unlike the variant0/variant1
  files, which are older AIA/radio-only style variants.
- It is a better teaching bridge to the formal main script than the extended
  example, which contains more exploratory helpers and broader workflow logic.

## Legacy Examples

Moved to:

- `examples/legacy/radio_aia_hmi/aia_radio_hmi_overlay_extended_example.py`
- `examples/legacy/radio_aia_hmi/aia_radio_overlay_variant0_example.py`
- `examples/legacy/radio_aia_hmi/aia_radio_overlay_variant1_example.py`

Rationale:

- `aia_radio_hmi_overlay_extended_example.py` overlaps heavily with the formal
  main overlay workflow and includes extra exploratory reprojection modes.
- `aia_radio_overlay_variant0_example.py` and
  `aia_radio_overlay_variant1_example.py` are short historical AIA/radio
  variants, but they do not cover the full AIA/radio/HMI target workflow.
- Keeping them in `examples/legacy/radio_aia_hmi/` preserves old parameter and
  reproduction value without presenting them as current first-choice examples.

## Deletion Candidates

No example was deleted in this phase.

Future deletion candidates requiring human confirmation:

- `examples/legacy/radio_aia_hmi/aia_radio_overlay_variant0_example.py`
- `examples/legacy/radio_aia_hmi/aia_radio_overlay_variant1_example.py`

Possible later deletion candidate, but higher review burden:

- `examples/legacy/radio_aia_hmi/aia_radio_hmi_overlay_extended_example.py`

The extended example may preserve experimental reprojection and paper-figure
settings, so it should be reviewed more carefully before deletion.

## Manual Confirmation Before Deletion

Before deleting any legacy overlay example, confirm:

- whether README, docs, notebooks, or local scripts reference the old path;
- whether a paper or presentation figure depends on exact ROI, contour, color,
  beam, or reprojection defaults from the example;
- whether variant0/variant1 encode event-specific AIA/radio alignment choices;
- whether the extended example contains a still-useful reprojection mode not
  covered by `sdo_aia_radio_hmi_overlay.py`;
- whether collaborators still run the example directly.

## Algorithm Impact

This phase did not change AIA/radio/HMI coordinate overlay logic, WCS behavior,
reprojection behavior, contour behavior, Gaussian fitting behavior, or HMI
overlay behavior. It only reorganized examples and documented the retention
decision.
