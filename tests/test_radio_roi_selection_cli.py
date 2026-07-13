"""Focused contracts for the package-owned ROI selection normalizer."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from solar_toolkit.radio import roi_selection_cli


def test_help_path_is_lazy_and_exposes_workspace_arguments():
    script = """
import sys
from solar_toolkit.radio import roi_selection_cli
try:
    roi_selection_cli.main(['--help'])
except SystemExit as exc:
    assert exc.code == 0
else:
    raise AssertionError('--help did not exit')
assert 'numpy' not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "--roi-json-payload" in result.stdout
    assert "--output-dir" in result.stdout


def test_run_normalizes_plotly_box_and_writes_fixed_output_name(tmp_path):
    result = roi_selection_cli.run(
        json.dumps(
            {
                "range": {"x": [1.0, 5.0], "y": [2.0, 8.0]},
                "label": "burst source",
            }
        ),
        tmp_path / "workspace",
    )

    assert result == (tmp_path / "workspace" / "radio_roi_selection.json").resolve()
    saved = json.loads(result.read_text(encoding="utf-8"))
    assert saved["kind"] == "box"
    assert saved["label"] == "burst source"
    assert saved["bounds_arcsec"] == {
        "left": 1.0,
        "bottom": 2.0,
        "right": 5.0,
        "top": 8.0,
    }


def test_run_normalizes_plotly_lasso_with_existing_polygon_semantics(tmp_path):
    result = roi_selection_cli.run(
        {
            "selection": {
                "lassoPoints": {
                    "x": [0.0, 3.0, 1.0],
                    "y": [0.0, 0.0, 2.0],
                }
            }
        },
        tmp_path,
    )

    saved = json.loads(result.read_text(encoding="utf-8"))
    assert saved["kind"] == "polygon"
    assert saved["vertices_arcsec"] == [
        {"x": 0.0, "y": 0.0},
        {"x": 3.0, "y": 0.0},
        {"x": 1.0, "y": 2.0},
    ]


def test_run_accepts_existing_radio_roi_json(tmp_path):
    from solar_toolkit.radio.roi_lightcurve import RadioRoi

    original = RadioRoi.from_box(-4.0, -2.0, 6.0, 8.0, label="saved")
    result = roi_selection_cli.run(original.to_json_dict(), tmp_path)

    assert json.loads(result.read_text(encoding="utf-8")) == original.to_json_dict()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("not-json", "must be valid JSON"),
        ("[]", "must decode to a JSON object"),
        (json.dumps({"points": []}), "must contain Plotly"),
        (
            json.dumps({"lassoPoints": {"x": [0, 1, 2], "y": [0, 1]}}),
            "must have the same length",
        ),
    ],
)
def test_run_reports_clear_payload_errors(tmp_path, payload, message):
    with pytest.raises(ValueError, match=message):
        roi_selection_cli.run(payload, tmp_path)


def test_main_prints_generated_selection_path(tmp_path, monkeypatch, capsys):
    expected = tmp_path / "radio_roi_selection.json"
    observed = {}

    def fake_run(payload, output_dir):
        observed.update(payload=payload, output_dir=output_dir)
        return expected

    monkeypatch.setattr(roi_selection_cli, "run", fake_run)

    result = roi_selection_cli.main(
        [
            "--roi-json-payload",
            '{"range":{"x":[1,2],"y":[3,4]}}',
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert result == 0
    assert observed == {
        "payload": '{"range":{"x":[1,2],"y":[3,4]}}',
        "output_dir": str(tmp_path),
    }
    assert capsys.readouterr().out.strip() == f"Radio ROI selection: {expected}"
