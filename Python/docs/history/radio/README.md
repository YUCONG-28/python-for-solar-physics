# Radio Documentation Index

This folder contains the current radio workflow notes plus historical reports
from phased refactors. Use the current guidance first; the reports are retained
as audit records and may describe older intermediate states.

## Current Guidance

| Document | Use |
| --- | --- |
| `RADIO_ENTRYPOINTS.md` | Recommended radio entrypoints, compatibility wrappers, and output placement. |
| `RADIO_MIGRATION_NOTES.md` | Current compatibility layer, remaining legacy dependencies, and safe next steps. |

## Refactor Reports

| Document | Use |
| --- | --- |
| `RADIO_REFACTOR_REPORT.md` | Initial radio-style structure migration summary. |
| `RADIO_CONFIG_EXTRACTION_REPORT.md` | Radio configuration extraction audit. |
| `AIA_CONFIG_EXTRACTION_REPORT.md` | AIA/HMI/radio overlay configuration extraction audit. |
| `PHASE1_IMPORT_AND_TEST_BASELINE_REPORT.md` | Baseline import and test findings from phase 1. |
| `PHASE3_CORE_LEGACY_DEPENDENCY_REDUCTION_REPORT.md` | Later reduction of core-to-legacy helper dependencies. |

## Science Output Notes

| Document | Use |
| --- | --- |
| `DRIFT_SELECTION_AND_HEIGHT_PLOT_OPTIMIZATION_REPORT.md` | Drift selection and height-plot optimization notes. |
| `NEWKIRK_HEIGHT_COMPARISON_REVISION_REPORT.md` | Newkirk height-comparison revision notes. |

Runtime figures, CSV files, local selections, and diagnostics should stay under
configured output directories, not in this documentation folder.
