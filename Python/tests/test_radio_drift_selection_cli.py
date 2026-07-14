from __future__ import annotations

import json
import subprocess
import sys

import pytest


def test_drift_selection_cli_writes_canonical_json_and_diagnostics(tmp_path):
    from solar_toolkit.radio.drift_rate import load_drift_selection_json
    from solar_toolkit.radio.drift_selection_cli import run

    lines = [
        {
            "label": "drift_001",
            "t_start": "2025-01-24T03:21:00.000",
            "f_start_mhz": 80.0,
            "t_end": "2025-01-24T03:21:10.000",
            "f_end_mhz": 40.0,
            "color": "cyan",
        }
    ]

    json_path, csv_path = run(lines, tmp_path)

    assert json_path.name == "drift_rate_selection.json"
    assert csv_path.name == "drift_rate_diagnostics.csv"
    assert load_drift_selection_json(json_path)[0]["label"] == "drift_001"
    assert "-4.0" in csv_path.read_text(encoding="utf-8")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["source"] == "radio-workspace-same-page-selection"


@pytest.mark.parametrize("payload", ["not-json", "{}", "[]"])
def test_drift_selection_cli_rejects_missing_or_invalid_lines(tmp_path, payload):
    from solar_toolkit.radio.drift_selection_cli import run

    with pytest.raises((TypeError, ValueError)):
        run(payload, tmp_path)


def test_drift_selection_help_does_not_import_numpy():
    code = """
import sys
from solar_toolkit.radio import drift_selection_cli
try:
    drift_selection_cli.main(['--help'])
except SystemExit as exc:
    assert exc.code == 0
assert 'numpy' not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
