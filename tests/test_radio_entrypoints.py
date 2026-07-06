from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_help(script: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / script), "--help"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_radio_source_entrypoint_modules_import_without_streamlit_runtime():
    for module_name in [
        "scripts.radio.extract_radio_centers",
        "scripts.radio.export_radio_source_trajectory",
        "scripts.radio.run_radio_source_app",
    ]:
        module = importlib.import_module(module_name)
        assert hasattr(module, "main")


def test_radio_source_entrypoint_help_commands_run():
    for script in [
        "scripts/radio/extract_radio_centers.py",
        "scripts/radio/export_radio_source_trajectory.py",
        "scripts/radio/run_radio_source_app.py",
    ]:
        result = _run_help(script)
        assert result.returncode == 0, result.stderr
        assert "usage:" in result.stdout.lower()
