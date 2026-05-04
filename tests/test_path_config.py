# -*- coding: utf-8 -*-
"""Tests for optional YAML path configuration loading."""

import shutil
from pathlib import Path

import pytest

from solar_toolkit import path_config

TEST_TMP = Path("tmp/pytest_path_config")


def _fresh_tmp_dir(name: str) -> Path:
    path = TEST_TMP / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def test_load_script_config_returns_defaults_when_no_config(monkeypatch):
    monkeypatch.delenv("SOLAR_PHYSICS_CONFIG", raising=False)
    monkeypatch.setattr(path_config, "_repo_root", lambda: Path("Z:/missing/repo"))

    result = path_config.load_script_config(
        "sdo_aia_euv_processor", {"data_path": "default", "nested": {"a": 1}}
    )

    assert result == {"data_path": "default", "nested": {"a": 1}}


def test_load_script_config_reads_local_yaml(monkeypatch):
    root = _fresh_tmp_dir("local_yaml")
    config_dir = root / "configs"
    config_dir.mkdir()
    (config_dir / "paths.local.yaml").write_text(
        """
scripts:
  demo_script:
    data_path: D:/solar/demo
    nested:
      b: 2
""",
        encoding="utf-8",
    )
    monkeypatch.delenv("SOLAR_PHYSICS_CONFIG", raising=False)
    monkeypatch.setattr(path_config, "_repo_root", lambda: root)

    result = path_config.load_script_config(
        "demo_script", {"data_path": "default", "nested": {"a": 1}}
    )

    assert result == {"data_path": "D:/solar/demo", "nested": {"a": 1, "b": 2}}


def test_load_script_config_uses_environment_path(monkeypatch):
    root = _fresh_tmp_dir("env_yaml")
    config_file = root / "custom_paths.yaml"
    config_file.write_text(
        """
scripts:
  demo_script:
    output_dir: D:/solar/output
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("SOLAR_PHYSICS_CONFIG", str(config_file))

    result = path_config.load_script_config("demo_script", {"output_dir": "default"})

    assert result["output_dir"] == "D:/solar/output"


def test_load_script_config_rejects_non_mapping_section(monkeypatch):
    root = _fresh_tmp_dir("bad_yaml")
    config_file = root / "bad_paths.yaml"
    config_file.write_text("scripts:\n  demo_script: invalid\n", encoding="utf-8")
    monkeypatch.setenv("SOLAR_PHYSICS_CONFIG", str(config_file))

    with pytest.raises(ValueError, match="must be a mapping"):
        path_config.load_script_config("demo_script", {})
