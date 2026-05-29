from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd

from scripts.radio.core.radio_drift_products import save_drift_selection_artifacts
from scripts.radio.run_radio_burst_pipeline import _save_drift_selection_products


def test_drift_selection_metadata_contains_selections():
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp)
        result = save_drift_selection_artifacts(
            _spectrogram_data(),
            _time_axis(),
            _frequency_axis(),
            [_selection()],
            output_dir,
            source_file="synthetic.fits",
            config={"preserve_existing": False, "dpi": 80},
        )

        metadata_path = output_dir / "spectrogram_drift_rate_selection_metadata.json"
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))

        assert result["status"] == "saved"
        assert payload["source_file"] == "synthetic.fits"
        assert payload["selections"]
        assert payload["selections"][0]["label"] == "drift_001"
        assert math.isclose(
            payload["selections"][0]["drift_rate_mhz_s"],
            -20.0,
            rel_tol=1e-12,
        )


def test_annotated_preview_can_be_regenerated_from_saved_csv_records():
    with tempfile.TemporaryDirectory() as tmp:
        first_dir = Path(tmp) / "first"
        second_dir = Path(tmp) / "second"
        save_drift_selection_artifacts(
            _spectrogram_data(),
            _time_axis(),
            _frequency_axis(),
            [_selection()],
            first_dir,
            config={"preserve_existing": False, "dpi": 80},
        )

        records = pd.read_csv(
            first_dir / "spectrogram_drift_rate_selection_points.csv"
        ).to_dict("records")
        save_drift_selection_artifacts(
            _spectrogram_data(),
            _time_axis(),
            _frequency_axis(),
            records,
            second_dir,
            config={"preserve_existing": False, "dpi": 80},
        )

        assert (
            second_dir / "spectrogram_drift_rate_selection_preview_annotated.png"
        ).exists()
        assert (second_dir / "cutouts" / "drift_001_zoom.png").exists()


def test_metadata_records_spectrogram_display_parameters():
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp)
        save_drift_selection_artifacts(
            _spectrogram_data(),
            _time_axis(),
            _frequency_axis(),
            [_selection()],
            output_dir,
            config={
                "preserve_existing": False,
                "dpi": 80,
                "cmap": "jet",
                "vmin": 2.5,
                "vmax": 4.5,
                "colorbar_label": r"log$_{10}$ intensity",
            },
        )

        metadata_path = output_dir / "spectrogram_drift_rate_selection_metadata.json"
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))

        assert payload["display"] == {
            "cmap": "jet",
            "vmin": 2.5,
            "vmax": 4.5,
            "colorbar_label": r"log$_{10}$ intensity",
        }


def test_pipeline_forwards_spectrogram_cache_display_parameters():
    captured = {}

    def fake_save_drift_selection_artifacts(*args, **kwargs):
        captured["config"] = kwargs["config"]
        return {"status": "saved"}

    cache = SimpleNamespace(
        data=_spectrogram_data(),
        time_datetimes=list(_time_axis()),
        freq=_frequency_axis(),
        source_file="synthetic.fits",
        cmap="jet",
        vmin=2.5,
        vmax=4.5,
        cbar_label=r"log$_{10}$ intensity",
    )

    with patch(
        "scripts.radio.core.radio_drift_products.save_drift_selection_artifacts",
        fake_save_drift_selection_artifacts,
    ):
        _save_drift_selection_products(
            cache,
            {"enable": True, "output_subdir": "drift_selection"},
            pd.DataFrame([_selection()]),
            Path("analysis"),
        )

    assert captured["config"]["cmap"] == "jet"
    assert captured["config"]["vmin"] == 2.5
    assert captured["config"]["vmax"] == 4.5
    assert captured["config"]["colorbar_label"] == r"log$_{10}$ intensity"


def _spectrogram_data():
    return np.arange(20, dtype=float).reshape(4, 5)


def _time_axis():
    return pd.date_range("2025-01-24T04:48:30", periods=5, freq="1s")


def _frequency_axis():
    return np.asarray([100.0, 120.0, 140.0, 160.0])


def _selection():
    return {
        "label": "drift_001",
        "mode": "manual",
        "t_start": "2025-01-24T04:48:31",
        "t_end": "2025-01-24T04:48:34",
        "f_start_mhz": 160.0,
        "f_end_mhz": 100.0,
        "color": "cyan",
        "quality_flag": "ok",
        "warning": "",
    }


if __name__ == "__main__":
    for name, func in sorted(globals().items()):
        if name.startswith("test_") and callable(func):
            func()
