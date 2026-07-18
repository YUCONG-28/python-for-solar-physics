"""Subprocess helpers that preserve the selected Miniforge interpreter."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .environment import inspect_miniforge_runtime

PYTHON_EXECUTABLE_ENV = "SOLAR_APPS_PYTHON_EXECUTABLE"


def selected_python_executable(
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Return the launcher-selected interpreter after Miniforge validation."""

    env = os.environ if environ is None else environ
    requested = env.get(PYTHON_EXECUTABLE_ENV)
    runtime = inspect_miniforge_runtime(requested or sys.executable)
    if requested:
        current = Path(sys.executable).resolve(strict=False)
        if os.path.normcase(str(runtime.executable)) != os.path.normcase(str(current)):
            raise RuntimeError(
                "Selected child interpreter differs from the running application; "
                "restart through Apps/run.ps1."
            )
    return runtime.executable


def miniforge_subprocess_environment(
    base: Mapping[str, str] | None = None,
    *,
    python_executable: str | os.PathLike[str] | None = None,
    inherit_path: bool = True,
) -> dict[str, str]:
    """Build an environment whose DLL and script paths match one interpreter."""

    env = dict(os.environ if base is None else base)
    runtime = inspect_miniforge_runtime(python_executable or sys.executable)
    prefix = runtime.environment_root
    conda_paths = (
        prefix,
        prefix / "Library" / "mingw-w64" / "bin",
        prefix / "Library" / "usr" / "bin",
        prefix / "Library" / "bin",
        prefix / "Scripts",
    )
    existing = env.get("PATH", "")
    env["PATH"] = os.pathsep.join(
        [
            *(str(path) for path in conda_paths),
            *([existing] if inherit_path and existing else []),
        ]
    )
    env.pop("PYTHONPATH", None)
    env[PYTHON_EXECUTABLE_ENV] = str(runtime.executable)
    env["SOLAR_APPS_ENVIRONMENT"] = runtime.environment_name
    env["PYTHONNOUSERSITE"] = "1"
    return env


def python_module_command(module: str, arguments: Sequence[str] = ()) -> list[str]:
    """Build a module command using the current supported interpreter."""

    if not module or module.startswith("-"):
        raise ValueError("A Python module name is required")
    return [str(selected_python_executable()), "-m", module, *map(str, arguments)]


def run_python_module(
    module: str,
    arguments: Sequence[str] = (),
    **kwargs: Any,
) -> subprocess.CompletedProcess[Any]:
    """Run a child module without permitting a different Python runtime."""

    kwargs.setdefault("env", miniforge_subprocess_environment())
    kwargs.setdefault("check", False)
    return subprocess.run(python_module_command(module, arguments), **kwargs)


__all__ = [
    "PYTHON_EXECUTABLE_ENV",
    "miniforge_subprocess_environment",
    "python_module_command",
    "run_python_module",
    "selected_python_executable",
]
