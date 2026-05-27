from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.radio.core.radio_drift_products import save_drift_selection_artifacts


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
