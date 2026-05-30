# Project Instructions

These instructions apply to this Python project and its subdirectories.

## Python environment

- Always run Python through the Miniforge `solarphysics_env` environment.
- Use this interpreter explicitly for Python commands:

```powershell
D:\miniforge3\envs\solarphysics_env\python.exe
```

- Prefer commands such as:

```powershell
D:\miniforge3\envs\solarphysics_env\python.exe -m pytest
D:\miniforge3\envs\solarphysics_env\python.exe -m pip
D:\miniforge3\envs\solarphysics_env\python.exe script.py
```

- Do not rely on bare `python`, `pip`, or `pytest` unless they have first been verified to resolve to `D:\miniforge3\envs\solarphysics_env`.

## Branch completion workflow

- If a branch is created while working on this project, do not silently leave it behind at the end of the task.
- Before finishing, ask the user whether they want to merge the branch into `main` and delete the branch.
- Do not merge into `main` or delete the branch without the user's explicit confirmation.
- If the user confirms, switch to `main`, merge the work branch, then delete the completed local branch.
- If a remote branch was pushed, ask for confirmation before deleting the remote branch too.
