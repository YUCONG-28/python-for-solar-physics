from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pytest
from matplotlib.axes import Axes

from solar_apps.workflows.radio.artifacts import (
    save_figure_artifact,
    sidecar_path_for,
    validate_source_map_artifact,
)
from solar_apps.workflows.radio.source_map_workflow import (
    DEFAULT_CONFIG,
    build_config,
    resolve_spatial_display,
)
from solar_apps.workflows.radio import source_map_workflow
from solar_apps.workflows.radio.spatial_display import SpatialRadioDisplay

matplotlib.use("Agg")


def test_source_map_keeps_single_linear_and_multi_log10_constraints() -> None:
    requested = {
        "display": {
            "radio_cmap": "viridis",
            "transform": "linear",
            "range_mode": "auto",
            "range_scope": "per_band",
            "per_band_percentiles": [90, 99],
        }
    }

    single = build_config({**requested, "mode": "single_band"}, DEFAULT_CONFIG)
    multi = build_config({**requested, "mode": "multi_band"}, DEFAULT_CONFIG)

    assert resolve_spatial_display(single).transform == "linear"
    assert resolve_spatial_display(multi).transform == "log10"
    assert multi["radio_cmap"] == "viridis"
    assert multi["per_band_percentiles"] == [90.0, 99.0]


def test_schema_one_sidecar_accepts_optional_display_and_old_files(
    tmp_path: Path,
) -> None:
    figure, axis = plt.subplots()
    axis.imshow(np.arange(9).reshape(3, 3), extent=[-1, 1, -1, 1])
    target = tmp_path / "map.png"
    display = SpatialRadioDisplay(cmap="plasma", render_profile="preview")
    save_figure_artifact(
        figure,
        target,
        dpi=80,
        radio_axes=[axis],
        panel_metadata=[{"id": "radio-1", "transform": "linear"}],
        mode="single_band",
        polarization="RR",
        source_files=["synthetic.fits"],
        write_sidecar=True,
        display=display.sidecar_payload(),
    )
    plt.close(figure)

    current = validate_source_map_artifact(target)
    assert current["schema_version"] == 1
    assert current["display"]["cmap"] == "plasma"
    assert current["display"]["render_profile"] == "preview"

    sidecar = sidecar_path_for(target)
    legacy = json.loads(sidecar.read_text(encoding="utf-8"))
    legacy.pop("display")
    sidecar.write_text(json.dumps(legacy), encoding="utf-8")
    assert "display" not in validate_source_map_artifact(target)


def test_ui_theme_is_rejected_from_scientific_sidecar(tmp_path: Path) -> None:
    figure, axis = plt.subplots()
    axis.imshow(np.ones((2, 2)), extent=[0, 2, 0, 2])
    with pytest.raises(ValueError, match="UI theme"):
        save_figure_artifact(
            figure,
            tmp_path / "map.png",
            dpi=80,
            radio_axes=[axis],
            panel_metadata=[{"id": "radio-1"}],
            mode="single_band",
            polarization="RR",
            source_files=["synthetic.fits"],
            write_sidecar=True,
            display={"ui_theme": "dark"},
        )
    plt.close(figure)


def test_gaussian_residual_keeps_symmetric_scientific_normalization(
    tmp_path: Path, monkeypatch
) -> None:
    residual = np.array([[-100.0, -2.0], [1.0, 4.0]])
    fit = SimpleNamespace(
        model=np.zeros_like(residual),
        residual_rms=1.0,
        snr=10.0,
        quality_flag="ok",
        image_origin="lower",
    )
    captured: dict[str, object] = {}
    original = Axes.imshow

    def capture(axis, values, **kwargs):
        captured.update(kwargs)
        return original(axis, values, **kwargs)

    monkeypatch.setattr(Axes, "imshow", capture)
    cfg = {
        "fig_size": (3, 2),
        "dpi": 60,
        "title_fontsize": 10,
        "radio_cmap": "viridis",
        "background_bad_color": "magenta",
        "spatial_display": {"transform": "log10", "cmap": "plasma"},
    }
    source_map_workflow._save_gaussian_residual_panel(
        residual,
        fit,
        [-1, 1, -1, 1],
        str(tmp_path / "residual.png"),
        cfg,
    )

    expected = float(np.nanpercentile(np.abs(residual), 99))
    assert captured["cmap"] == "RdBu_r"
    assert captured["vmin"] == pytest.approx(-expected)
    assert captured["vmax"] == pytest.approx(expected)
