# Project Instructions

These instructions apply to this Python project and its subdirectories.

## Python environment

- Always run Python through the Miniforge `solarphysics_env` environment.
- In a normal activated shell, use this interpreter explicitly for Python commands:

```powershell
D:\miniforge3\envs\solarphysics_env\python.exe
```

- In a non-activated PowerShell session, first prepend the conda environment DLL paths before importing NumPy/SciPy, otherwise MKL-backed NumPy can fail during import:

```powershell
$env:PATH="D:\miniforge3\envs\solarphysics_env;D:\miniforge3\envs\solarphysics_env\Library\mingw-w64\bin;D:\miniforge3\envs\solarphysics_env\Library\usr\bin;D:\miniforge3\envs\solarphysics_env\Library\bin;D:\miniforge3\envs\solarphysics_env\Scripts;$env:PATH"
```

- After that, prefer commands such as:

```powershell
D:\miniforge3\envs\solarphysics_env\python.exe -m pytest
D:\miniforge3\envs\solarphysics_env\python.exe -m pip
D:\miniforge3\envs\solarphysics_env\python.exe script.py
```

- Alternatively, use `conda run` so conda supplies the environment paths:

```powershell
D:\miniforge3\Scripts\conda.exe run -n solarphysics_env python -m pytest
```

- Do not rely on bare `python`, `pip`, or `pytest` unless they have first been verified to resolve to `D:\miniforge3\envs\solarphysics_env`.

## Codex agent behavior

Use these behavioral guidelines when writing, reviewing, or refactoring code in
this repository. Project-specific instructions above take priority if any
guideline conflicts with them.

- Think before coding: state assumptions explicitly, surface tradeoffs, and ask
  for clarification when the task has multiple plausible interpretations.
- Simplicity first: prefer the smallest implementation that solves the stated
  problem, without speculative features or unnecessary abstractions.
- Surgical changes: touch only what the task requires, match the surrounding
  style, and avoid unrelated refactors or formatting churn.
- Goal-driven execution: define concrete success criteria, verify them with the
  appropriate checks, and do not claim completion without fresh evidence.

## Branch completion workflow

- If a branch is created while working on this project, do not silently leave it behind at the end of the task.
- Before finishing, ask the user whether they want to merge the branch into `main` and delete the branch.
- Do not merge into `main` or delete the branch without the user's explicit confirmation.
- If the user confirms, switch to `main`, merge the work branch, then delete the completed local branch.
- If a remote branch was pushed, ask for confirmation before deleting the remote branch too.

## Radio and verification workflow

- Prefer `solar_toolkit.radio` for new reusable radio-processing imports.
- Keep old `scripts.radio.core` import paths working during the migration
  window with compatibility wrappers or aliases rather than symbol copies.
- For radio work, optimize for denoising and clear radio-source visibility on
  AIA imagery, not only for visually prettier Gaussian overlays.
- Keep literature/formula notes mapped to the actual code path and clearly
  separate implemented behavior from future work.
- For focused radio changes, prefer targeted tests first, such as relevant
  `tests\test_radio_*.py` files, then broaden only when shared behavior changed.
- If a broader suite fails, isolate whether the failure is in the changed path
  before treating it as a task blocker.

## Cross-repository and presentation routing

- Use Codex, not a Work deliverable, as the completion surface for code edits,
  tests, compatibility checks, and Git state in this repository.
- When work spans the sibling `Paper` repository, treat Paper as the evidence
  layer and this repository as the implementation layer. Keep proposed methods
  separate from behavior that has actually been implemented and tested.
- Use `academic-paper-director` for manuscript or citation-sensitive text and
  `ppt-style-director` for research-deck style. Create or edit a real `.pptx`
  with `presentation-skill` or `Presentations`, followed by render-based QA.
- Do not expose raw observations, large generated outputs, local paths, or
  private research artifacts through Calendar or Sites. Publish only a
  separately reviewed export after an explicit request.
