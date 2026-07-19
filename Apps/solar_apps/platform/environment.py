"""Validation helpers for the two supported Miniforge environments."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

PRIMARY_ENVIRONMENT = "solarphysics_env_latest"
STANDBY_ENVIRONMENT = "solarphysics_env"
SUPPORTED_ENVIRONMENTS = (PRIMARY_ENVIRONMENT, STANDBY_ENVIRONMENT)


class UnsupportedPythonEnvironment(RuntimeError):
    """Raised when an application would escape the supported Miniforge envs."""


@dataclass(frozen=True, slots=True)
class MiniforgeRuntime:
    executable: Path
    environment_root: Path
    environment_name: str
    miniforge_root: Path


def inspect_miniforge_runtime(
    executable: str | os.PathLike[str] | None = None,
    *,
    miniforge_root: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
    require_exists: bool = True,
) -> MiniforgeRuntime:
    """Validate one interpreter as latest or explicit formal standby."""

    env = os.environ if environ is None else environ
    selected = Path(executable or sys.executable).expanduser().resolve(strict=False)
    if require_exists and not selected.is_file():
        raise UnsupportedPythonEnvironment(f"Python interpreter not found: {selected}")
    environment_root = selected.parent
    environment_name = environment_root.name
    if environment_name not in SUPPORTED_ENVIRONMENTS:
        raise UnsupportedPythonEnvironment(
            "Solar applications require Miniforge environment "
            f"{PRIMARY_ENVIRONMENT!r}, or explicit standby {STANDBY_ENVIRONMENT!r}; "
            f"got {environment_name!r}."
        )
    if environment_root.parent.name.casefold() != "envs":
        raise UnsupportedPythonEnvironment(
            f"Interpreter is not inside a Miniforge envs directory: {selected}"
        )
    installation_root = environment_root.parent.parent.resolve(strict=False)
    trusted_root_value = miniforge_root or env.get("SOLAR_MINIFORGE_ROOT")
    trusted_root = (
        Path(trusted_root_value).expanduser().resolve(strict=False)
        if trusted_root_value
        else None
    )
    if trusted_root is not None and trusted_root != installation_root:
        raise UnsupportedPythonEnvironment(
            "Interpreter environment is not below the explicitly selected Conda root"
        )
    base_metadata = installation_root / "conda-meta"
    if require_exists and not any(
        base_metadata.glob("miniforge_console_shortcut-*.json")
    ):
        raise UnsupportedPythonEnvironment(
            f"Conda installation is not marked as Miniforge: {installation_root}"
        )
    if require_exists and not (environment_root / "conda-meta").is_dir():
        raise UnsupportedPythonEnvironment(
            f"Conda environment metadata is missing: {environment_root}"
        )
    return MiniforgeRuntime(
        executable=selected,
        environment_root=environment_root,
        environment_name=environment_name,
        miniforge_root=installation_root,
    )


__all__ = [
    "MiniforgeRuntime",
    "PRIMARY_ENVIRONMENT",
    "STANDBY_ENVIRONMENT",
    "SUPPORTED_ENVIRONMENTS",
    "UnsupportedPythonEnvironment",
    "inspect_miniforge_runtime",
]
