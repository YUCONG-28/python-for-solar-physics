from __future__ import annotations

import os
from pathlib import Path

import pytest

from solar_apps.platform.environment import (
    UnsupportedPythonEnvironment,
    inspect_miniforge_runtime,
)
from solar_apps.platform.processes import miniforge_subprocess_environment


def _fake_environment(root: Path, name: str) -> Path:
    marker = root / "conda-meta" / "miniforge_console_shortcut-1.0-test.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("{}", encoding="utf-8")
    environment = root / "envs" / name
    (environment / "conda-meta").mkdir(parents=True)
    python = environment / "python.exe"
    python.touch()
    return python


def _fake_posix_environment(root: Path, name: str) -> Path:
    history = root / "conda-meta" / "history"
    history.parent.mkdir(parents=True, exist_ok=True)
    history.write_text(
        "# cmd: constructor /tmp/Miniforge3 --platform osx-arm64\n",
        encoding="utf-8",
    )
    environment = root / "envs" / name
    (environment / "conda-meta").mkdir(parents=True)
    python = environment / "bin" / "python"
    python.parent.mkdir()
    python.touch()
    return python


def test_primary_and_explicit_standby_are_supported(tmp_path: Path) -> None:
    root = tmp_path / "miniforge3"
    latest = _fake_environment(root, "solarphysics_env_latest")
    standby = _fake_environment(root, "solarphysics_env")
    assert (
        inspect_miniforge_runtime(latest).environment_name == "solarphysics_env_latest"
    )
    assert inspect_miniforge_runtime(standby).environment_name == "solarphysics_env"


def test_posix_bin_interpreter_and_constructor_provenance_are_supported(
    tmp_path: Path,
) -> None:
    root = tmp_path / "miniforge3"
    python = _fake_posix_environment(root, "solarphysics_env_latest")
    runtime = inspect_miniforge_runtime(python)
    assert runtime.executable == python.resolve()
    assert runtime.environment_root == python.parent.parent.resolve()
    assert runtime.miniforge_root == root.resolve()


def test_backup_venv_and_system_interpreters_are_rejected(tmp_path: Path) -> None:
    root = tmp_path / "miniforge3"
    backup = _fake_environment(root, "solarphysics_backup")
    with pytest.raises(UnsupportedPythonEnvironment):
        inspect_miniforge_runtime(backup)
    venv = tmp_path / ".venv" / "python.exe"
    venv.parent.mkdir()
    venv.touch()
    with pytest.raises(UnsupportedPythonEnvironment):
        inspect_miniforge_runtime(venv)


def test_ci_miniforge_marker_allows_a_nonstandard_installation_name(
    tmp_path: Path,
) -> None:
    action_root = tmp_path / "Miniconda3"
    python = _fake_environment(action_root, "solarphysics_env_latest")
    runtime = inspect_miniforge_runtime(
        python,
        miniforge_root=action_root,
        environ={},
    )
    assert runtime.miniforge_root == action_root.resolve()
    assert inspect_miniforge_runtime(python, environ={}).miniforge_root == action_root


def test_conda_without_miniforge_marker_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "Anaconda3"
    environment = root / "envs" / "solarphysics_env_latest"
    (environment / "conda-meta").mkdir(parents=True)
    python = environment / "python.exe"
    python.touch()
    with pytest.raises(UnsupportedPythonEnvironment, match="not marked as Miniforge"):
        inspect_miniforge_runtime(python, miniforge_root=root, environ={})


def test_explicit_root_must_own_the_selected_environment(tmp_path: Path) -> None:
    root = tmp_path / "Miniconda3"
    other = tmp_path / "other"
    python = _fake_environment(root, "solarphysics_env_latest")
    with pytest.raises(UnsupportedPythonEnvironment, match="not below"):
        inspect_miniforge_runtime(python, miniforge_root=other, environ={})


def test_worker_environment_drops_external_python_and_path_injection(
    tmp_path: Path,
) -> None:
    root = tmp_path / "miniforge3"
    python = _fake_environment(root, "solarphysics_env_latest")
    env = miniforge_subprocess_environment(
        {"PATH": "outside-path", "PYTHONPATH": "outside-python"},
        python_executable=python,
        inherit_path=False,
    )
    assert "PYTHONPATH" not in env
    assert "outside-path" not in env["PATH"]
    assert env["PATH"].split(os.pathsep)[0] == str(python.parent.resolve())
