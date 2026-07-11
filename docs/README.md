# Documentation Index

This directory contains both current project guidance and historical refactor
reports. Use the current-guidance documents first; older reports are retained as
audit history and should not be treated as the latest workspace state unless
they explicitly say so.

本目录同时包含当前指南与历史重构报告。决定运行入口或代码边界时，请优先采用“Current
Guidance”中的文件；历史报告只作为审计记录。

## Current Guidance

| Document | Use |
| --- | --- |
| `../README.md` | Public project overview, setup, and recommended entrypoints. |
| `../CODE_ORGANIZATION_MANIFEST.md` | Current whole-repository module boundary and deprecated compatibility policy. |
| `quickstart.md` | Beginner-friendly setup, no-data checks, first imports, path configuration, and safe entrypoint help commands. |
| `README.zh-CN.md` | Chinese project overview, minimal usage notes, data policy, and documentation map. |
| `FUNCTION_MAP.md` | Bilingual public package map, runnable entrypoints, and compatibility policy. |
| `project_structure.md` | Current repository layout, data policy, and AIA/HMI structure notes. |
| `script_index.md` | Current public runnable scripts, compatibility entrypoints, and selected examples. |
| `validation/astropy_sunpy_reorg_parity.md` | Focused AIA and Radio/CSO real-data parity evidence, plus explicit end-to-end exclusions. |
| `MAIN_FILES.md` | Compact list of main workflow files and core module boundaries. |
| `PROJECT_CLEANUP_REPORT.md` | Current cleanup status, validation scope, and remaining review items. |
| `FINAL_CODE_RETENTION_AND_REMOVAL_PLAN.md` | Current retention/removal rules and manual-confirmation boundaries. |
| `LEGACY_AND_REVIEW_FILES.md` | Files and local artifacts that require manual review before removal. |
| `path_configuration.md` | Local path configuration and `configs/paths.local.yaml` guidance. |

## Module-Specific Entrypoint Notes

| Document | Use |
| --- | --- |
| `../scripts/aia_hmi/docs/AIA_ENTRYPOINTS.md` | AIA/HMI recommended entrypoint, compatibility wrapper, and core module map. |
| `../scripts/radio/docs/README.md` | Radio documentation index for current guidance and historical reports. |
| `../scripts/radio/docs/RADIO_ENTRYPOINTS.md` | Radio recommended entrypoints and legacy compatibility notes. |
| `../scripts/radio/docs/RADIO_MIGRATION_NOTES.md` | Radio migration notes and compatibility boundaries. |

## Historical Reports

These files are useful audit records, but some describe earlier states of the
repository. Prefer the current-guidance documents above when deciding what to
run, keep, delete, or stage.

- `PROJECT_OVERVIEW.md`
- `REFACTOR_BASELINE.md`
- `PROJECT_OPTIMIZATION_PLAN.md`
- `CODE_RETENTION_PLAN.md`
- `AIA_REFACTOR_REPORT.md`
- `AIA_WRAPPER_REFACTOR_REPORT.md`
- `RADIO_SOURCE_MAP_REFACTOR_REPORT.md`
- `CSO_REFACTOR_REPORT.md`
- `OVERLAY_REFACTOR_REPORT.md`
- `SHARED_UTILS_REFACTOR_REPORT.md`
- `RADIO_COORDINATE_AUDIT.md`
- `RADIO_FILE_INVENTORY.md`
- `data_download/event_20250124_inventory.md`

## Asset Directories

- `assets/README.md`: policy for README-ready images and videos.
- `assets/images/`: small compressed image assets only.
- `assets/videos/`: small compressed video assets only.

Generated science products, raw observations, FITS/JP2/NetCDF files, bulk
figures, and local spreadsheets should stay out of Git unless explicitly
reviewed and documented.
