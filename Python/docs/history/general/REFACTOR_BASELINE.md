# Refactor Baseline

Original date: 2026-05-22
Current note added: 2026-05-30

This document is a historical Phase 0 baseline from an earlier refactor pass.
It is kept to preserve the validation context of that pass, but it is not the
authoritative current workspace status.

For the current cleanup and retention state, use:

- `docs/PROJECT_CLEANUP_REPORT.md`
- `docs/FINAL_CODE_RETENTION_AND_REMOVAL_PLAN.md`
- `docs/LEGACY_AND_REVIEW_FILES.md`
- `docs/project_structure.md`
- `docs/script_index.md`

## Historical Scope

The original Phase 0 pass was a safety baseline before merging legacy code. It
did not move, delete, rename, stage, commit, or push files. It also did not run
real FITS processing, plotting, downloads, GUI workflows, or video generation.

The baseline recorded that the default `python` command was unavailable in the
PowerShell environment, so the project-specific interpreter was used:

```powershell
D:\miniforge3\envs\solarphysics_env\python.exe
```

## Historical Test Result

The original default pytest invocation was not stable in that environment, but
the isolated command with third-party pytest plugin autoload disabled passed:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; D:\miniforge3\envs\solarphysics_env\python.exe -m pytest tests -ra
```

Recorded result:

```text
31 passed in 0.13s
```

## Historical Compile Result

The original compile baseline used:

```powershell
D:\miniforge3\envs\solarphysics_env\python.exe -m compileall solar_toolkit scripts tests
```

Recorded result: exit code 0.

## Current Use

Use this file only as historical context. It should not be used to decide
whether current files are untracked, safe to delete, or ready to stage. Current
cleanup decisions must be based on the current worktree, the current tests, and
the cleanup/retention documents listed above.
