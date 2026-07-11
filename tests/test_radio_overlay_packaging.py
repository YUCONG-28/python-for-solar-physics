"""Install-boundary tests for the packaged AIA/radio/HMI overlay."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np


def test_legacy_overlay_path_is_a_true_module_alias():
    canonical = importlib.import_module("solar_toolkit.radio.overlay_workflow")
    legacy = importlib.import_module("scripts.radio.legacy.sdo_aia_radio_hmi_overlay")

    assert legacy is canonical
    assert legacy.Config is canonical.Config
    assert legacy.run_overlay_workflow is canonical.run_overlay_workflow


def test_overlay_cli_executes_without_the_source_scripts_package(tmp_path):
    input_dir = tmp_path / "empty-input"
    output_dir = tmp_path / "products"
    input_dir.mkdir()
    config_path = tmp_path / "overlay.json"
    config_path.write_text(
        json.dumps(
            {
                "aia_radio_hmi": {
                    "paths": {
                        "radio_base_dir": str(input_dir),
                        "aia_base_dir": str(input_dir),
                        "hmi_base_dir": str(input_dir),
                    },
                    "output": {
                        "output_dir": str(output_dir),
                        "save_figure": False,
                    },
                    "runtime": {"debug_mode": False},
                }
            }
        ),
        encoding="utf-8",
    )
    code = f"""
import importlib.abc
import sys

class BlockScripts(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "scripts" or fullname.startswith("scripts."):
            raise ModuleNotFoundError(fullname)
        return None

sys.meta_path.insert(0, BlockScripts())
from solar_toolkit.radio import overlay_workflow

def run_without_observations(user_config):
    return []

overlay_workflow.run_overlay_workflow = run_without_observations
from solar_toolkit.radio.overlay_cli import main
raise SystemExit(main(["--config-file", {str(config_path)!r}]))
"""

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (output_dir / "radio_run_provenance.json").is_file()


def test_overlay_cli_overrides_config_after_section_loading(monkeypatch, tmp_path):
    from solar_toolkit.radio import overlay_cli

    monkeypatch.setattr(
        overlay_cli,
        "load_aia_radio_overlay_user_config",
        lambda _name, *, section: {
            "paths": {"output_dir": "old"},
            "output": {"output_dir": "old"},
            "aia": {"aia_file_start_idx": 10, "aia_file_end_idx": 20},
        },
    )
    observed = {}
    output_dir = tmp_path / "overlay"

    status = overlay_cli.main(
        [
            "--output-dir",
            str(output_dir),
            "--aia-file-start-idx",
            "2",
            "--aia-file-end-idx",
            "3",
        ],
        runner=lambda config: observed.update(config) or [],
    )

    assert status == 0
    assert observed["paths"]["output_dir"] == str(output_dir)
    assert observed["output"]["output_dir"] == str(output_dir)
    assert observed["aia"] == {
        "aia_file_start_idx": 2,
        "aia_file_end_idx": 3,
    }


def test_overlay_spectrogram_uses_packaged_drift_helpers(monkeypatch):
    from solar_toolkit.radio import drift_rate, spectrogram

    calls: list[str] = []
    monkeypatch.setattr(
        drift_rate,
        "get_or_load_drift_rate_results",
        lambda _cache, _cfg: calls.append("load") or [],
    )
    monkeypatch.setattr(
        drift_rate,
        "overlay_drift_rate_results",
        lambda _ax, _results, _cfg: calls.append("overlay"),
    )
    start = datetime(2025, 1, 24, 4, 47)
    times = np.asarray(
        [mdates.date2num(start), mdates.date2num(start + timedelta(seconds=1))]
    )
    cache = spectrogram.SpectrogramCache(
        data=np.ones((2, 2)),
        time_nums=times,
        display_time_nums=(float(times[0]), float(times[-1])),
        time_datetimes=[start, start + timedelta(seconds=1)],
        freq=np.asarray([100.0, 200.0]),
        title="Synthetic spectrum",
        cmap="viridis",
        vmin=None,
        vmax=None,
        cbar_label="intensity",
        source_file="synthetic.fits",
    )

    fig, ax = plt.subplots()
    try:
        spectrogram.overlay_spectrogram_panel(
            ax,
            {"enable_drift_rate_overlay": True},
            current_time=None,
            cache=cache,
        )
    finally:
        plt.close(fig)

    assert calls == ["load", "overlay"]
