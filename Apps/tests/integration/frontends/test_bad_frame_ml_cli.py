from __future__ import annotations

import json
from pathlib import Path

from solar_apps.frontends.radio_bad_frame_review.ml_cli import build_parser, main


def test_ml_cli_help_lists_explicit_lifecycle_commands(capsys):
    parser = build_parser()
    help_text = parser.format_help()

    assert "dataset" in help_text
    assert "train" in help_text
    assert "evaluate" in help_text
    assert "publish" in help_text
    assert "models" in help_text
    assert "manually" in help_text


def test_models_command_does_not_train_or_publish(tmp_path: Path, capsys):
    result = main(["--models-root", str(tmp_path / "models"), "models"])

    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["active_model_id"] is None
    assert payload["models"] == {}


def test_powershell_launcher_routes_bad_frame_ml() -> None:
    apps_root = Path(__file__).resolve().parents[3]
    launcher = (apps_root / "run.ps1").read_text(encoding="utf-8")

    assert "-m solar_apps.cli" in launcher
    assert "solarphysics_env_latest" in launcher
