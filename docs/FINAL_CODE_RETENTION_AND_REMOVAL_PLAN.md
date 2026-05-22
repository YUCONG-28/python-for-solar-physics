# Final Code Retention And Removal Plan

Date: 2026-05-22

## Scope

This document records the Phase 4 retention/removal plan and the Phase 4B
actions executed after explicit user confirmation. No staging, commit, or push
was performed in this phase.

Deletion or additional archival actions must wait for the explicit user reply:

```text
确认执行删除/归档
```

## Final Retention List

### AIA

Keep:

- `scripts/aia_hmi/sdo_aia_euv_processor.py`
- `scripts/aia_hmi/sdo_aia_multichannel_panel.py`
- `scripts/aia_hmi/sdo_aia_hmi_overlay.py`
- `scripts/aia_hmi/sdo_aia_hmi_fits_rename.py`
- `scripts/aia_hmi/sdo_aia_lightcurve_extraction.py`
- `scripts/aia_hmi/sdo_aia_lightcurve_plot.py`
- `scripts/aia_hmi/sdo_aia_time_distance_diagram.py`
- `scripts/aia_hmi/sdo_aia_time_file_selector.py`
- `scripts/aia_hmi/sdo_hmi_magnetogram_plot.py`

Archived legacy compatibility wrappers:

- `legacy/scripts/aia_hmi/sdo_aia_base_difference.py`
- `legacy/scripts/aia_hmi/sdo_aia_running_difference.py`

### Radio Source Map

Keep:

- `scripts/radio/radio_source_map_plot_gaussian_overlay.py`
- `scripts/radio/radio_source_map_plot.py`

Protected support/result-like file:

- `scripts/radio/spectrogram_drift_rate_manual_selection.json`

### AIA/Radio/HMI Overlay

Keep:

- `scripts/radio/sdo_aia_radio_hmi_overlay.py`
- `scripts/radio/sdo_aia_radio_hmi_overlay_bgcorrected.py`
- `examples/radio_aia_hmi/aia_radio_hmi_overlay_demo.py`

### CSO Spectrogram

Keep:

- `scripts/radio/cso_radio_spectrogram_plot.py`
- `scripts/radio/cso_spectrogram_class.py`
- `scripts/radio/cso_radio_spectra_gui.py`

### Gaussian Fitting

Keep:

- `solar_toolkit/gaussian.py`
- `scripts/tools/gaussian_source_fitting.py`

### Shared Utilities

Keep:

- `solar_toolkit/__init__.py`
- `solar_toolkit/coordinates.py`
- `solar_toolkit/cso.py`
- `solar_toolkit/path_config.py`
- `solar_toolkit/solar_analysis_utils.py`

### Tools

Keep:

- `scripts/tools/image_sequence_to_video.py`
- `scripts/tools/gaussian_source_fitting.py`

### Examples

Keep as current examples:

- `examples/README.md`
- `examples/aia_hmi/solar_limb_contour_example.py`
- `examples/radio/fits_header_metadata_example.py`
- `examples/radio_aia_hmi/aia_radio_hmi_overlay_demo.py`
- `examples/output/.gitkeep`

Deleted after manual confirmation in Phase 4B:

- `examples/legacy/radio/cso_spectrogram_processing_example.py`
- `examples/legacy/radio_aia_hmi/aia_radio_hmi_overlay_extended_example.py`
- `examples/legacy/radio_aia_hmi/aia_radio_overlay_variant0_example.py`
- `examples/legacy/radio_aia_hmi/aia_radio_overlay_variant1_example.py`

## Final Basic Code List

| Module | Basic script/example | Reason |
| --- | --- | --- |
| AIA | `scripts/aia_hmi/sdo_aia_multichannel_panel.py` | Shorter teaching example for multi-wavelength organization, synchronization, display ranges, and six-panel plotting. |
| Radio source map | `scripts/radio/radio_source_map_plot.py` | Basic source-map reader/plotter without Gaussian, spectrogram panels, drift-rate selection, or frontend logic. |
| AIA/radio/HMI overlay | `examples/radio_aia_hmi/aia_radio_hmi_overlay_demo.py` | Best bridge example for the formal overlay workflow while still showing AIA/radio/HMI behavior. |
| CSO spectrogram | `scripts/radio/cso_spectrogram_class.py` | Basic reusable spectrogram container, reader wrapper, slicing, and simple plotting helper. |
| Gaussian fitting | `scripts/tools/gaussian_source_fitting.py` | Compatibility utility entry point re-exporting shared `solar_toolkit.gaussian` helpers. |

## Legacy Archive List

Archived in `examples/legacy/` during earlier phases and deleted after Phase 4B
manual confirmation:

- `examples/legacy/radio/cso_spectrogram_processing_example.py`
- `examples/legacy/radio_aia_hmi/aia_radio_hmi_overlay_extended_example.py`
- `examples/legacy/radio_aia_hmi/aia_radio_overlay_variant0_example.py`
- `examples/legacy/radio_aia_hmi/aia_radio_overlay_variant1_example.py`

Archived under `legacy/` after Phase 4B manual confirmation:

- `legacy/scripts/aia_hmi/sdo_aia_base_difference.py`
- `legacy/scripts/aia_hmi/sdo_aia_running_difference.py`

Reason: both AIA files are compatibility wrappers. Archiving removes the old
active script entry-point paths while preserving legacy defaults for historical
reference and lightweight tests.

Do not move to legacy automatically:

- `scripts/radio/cso_radio_spectra_gui.py`
- `scripts/radio/sdo_aia_radio_hmi_overlay_bgcorrected.py`
- `scripts/radio/radio_source_map_plot.py`
- `scripts/radio/spectrogram_drift_rate_manual_selection.json`

## Deletion Candidates

Deletion/archival below was executed only after the user explicitly confirmed
the Phase 4 plan.

| File | Covered by main code | Unique function? | Deletion risk | Test coverage | Human confirmation needed |
| --- | --- | --- | --- | --- | --- |
| `legacy/scripts/aia_hmi/sdo_aia_base_difference.py` | `scripts/aia_hmi/sdo_aia_euv_processor.py` with `difference_method="base"` | Legacy entry-point name and preserved defaults only; no independent algorithm remains | Medium. Old scripts/notebooks may call the old active path; legacy ROI/color/output naming may matter for paper reproduction | Wrapper config covered by `tests/test_aia_difference_wrappers.py`; no real-data parity test | Confirmed; archived, not deleted |
| `legacy/scripts/aia_hmi/sdo_aia_running_difference.py` | `scripts/aia_hmi/sdo_aia_euv_processor.py` with `difference_method="running"` | Legacy entry-point name and preserved defaults only; no independent algorithm remains | Medium. Old workflows may call the old active path; first-frame original-image legacy behavior may matter | Wrapper config covered by `tests/test_aia_difference_wrappers.py`; no real-data parity test | Confirmed; archived, not deleted |
| `examples/legacy/radio_aia_hmi/aia_radio_overlay_variant0_example.py` | `scripts/radio/sdo_aia_radio_hmi_overlay.py` plus retained demo | Possible event-specific AIA/radio parameters | Medium. May preserve one-off alignment/ROI/contour defaults | No direct test | Yes |
| `examples/legacy/radio_aia_hmi/aia_radio_overlay_variant1_example.py` | `scripts/radio/sdo_aia_radio_hmi_overlay.py` plus retained demo | Possible event-specific AIA/radio parameters | Medium. May preserve one-off alignment/ROI/contour defaults | No direct test | Yes |
| `examples/legacy/radio_aia_hmi/aia_radio_hmi_overlay_extended_example.py` | `scripts/radio/sdo_aia_radio_hmi_overlay.py` plus retained demo | Yes, may contain exploratory reprojection modes and extended diagnostics | High. Could preserve unreproduced figure settings or experimental reprojection choices | No direct test | Yes |
| `examples/legacy/radio/cso_spectrogram_processing_example.py` | `scripts/radio/cso_radio_spectrogram_plot.py` and `scripts/radio/cso_spectrogram_class.py` | Mostly historical duplicate, but may preserve old plotting defaults | Medium. LL/RR/sum/ratio defaults or publication plots may depend on it | Shared CSO reader covered by `tests/test_cso_utils.py`; example plotting not tested | Yes |

## Cannot Delete List

Do not delete automatically:

- `scripts/radio/sdo_aia_radio_hmi_overlay_bgcorrected.py`
  - Experimental background subtraction and robust/background Gaussian logic.
- `scripts/radio/spectrogram_drift_rate_manual_selection.json`
  - May contain manual drift-rate selections or local result metadata.
- `AIA.xlsx`
  - Possible research table or intermediate result.
- `CSO.xlsx`
  - Possible research table or intermediate result.
- Root PNG files:
  - `HXR.png`
  - `SXR.png`
  - `SXR to HXR.png`
  - `SXR to HXR enhance.png`
- Any real research result file, generated figure, FITS product, spreadsheet,
  manual selection, or local-analysis output unless the user explicitly confirms
  it can be removed.
- `scripts/radio/cso_radio_spectra_gui.py`
  - Optional GUI with interactive and type-II fitting behavior.
- `scripts/radio/radio_source_map_plot.py`
  - Retained basic radio source-map entry point.
- `scripts/aia_hmi/sdo_aia_multichannel_panel.py`
  - Retained AIA basic/teaching code.
- `examples/radio_aia_hmi/aia_radio_hmi_overlay_demo.py`
  - Retained basic overlay example.

## Required Checks Before Deletion Or Archival

Before any deletion or additional move:

1. Search README, docs, notebooks, scripts, and local notes for references to
   the candidate path.
2. Confirm no collaborator still runs the candidate directly.
3. Confirm any unique ROI, color limits, contour levels, time ranges, output
   naming, and local paths have been preserved in docs or config examples.
4. For science plots, compare old and new real-data outputs manually before
   deleting the old reproduction path.
5. Stage changes only after the user explicitly says:

```text
确认执行删除/归档
```

## Phase 4B Execution Status

Executed after explicit user confirmation:

- Archived `scripts/aia_hmi/sdo_aia_base_difference.py` to
  `legacy/scripts/aia_hmi/sdo_aia_base_difference.py`.
- Archived `scripts/aia_hmi/sdo_aia_running_difference.py` to
  `legacy/scripts/aia_hmi/sdo_aia_running_difference.py`.
- Deleted the confirmed duplicate legacy examples:
  - `examples/legacy/radio/cso_spectrogram_processing_example.py`
  - `examples/legacy/radio_aia_hmi/aia_radio_hmi_overlay_extended_example.py`
  - `examples/legacy/radio_aia_hmi/aia_radio_overlay_variant0_example.py`
  - `examples/legacy/radio_aia_hmi/aia_radio_overlay_variant1_example.py`
- Updated `tests/test_aia_difference_wrappers.py` to load archived AIA wrappers
  from `legacy/scripts/aia_hmi/`.

No protected files, real research outputs, GUI files, background-corrected
overlay code, radio source-map basics, CSO main code, or scientific algorithms
were changed by the deletion/archival step.

Post-action checks:

- `python -m pytest tests --basetemp pytest-cache-files-phase4b`: passed,
  45 tests.
- `python -m compileall solar_toolkit scripts tests legacy`: passed.
