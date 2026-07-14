"""Opt-in CSO drift preview export without an implicit selector server."""

from __future__ import annotations

import datetime as dt
import json

import matplotlib.dates as mdates
import numpy as np

from solar_toolkit.radio import cso_workflow


def _cache() -> cso_workflow.DriftSpectrogramView:
    start = dt.datetime(2025, 5, 3, 7, 15, 10)
    end = dt.datetime(2025, 5, 3, 7, 15, 20)
    return cso_workflow.DriftSpectrogramView(
        data=np.zeros((2, 2), dtype=np.float32),
        time_nums=np.asarray([mdates.date2num(start), mdates.date2num(end)]),
        display_time_nums=(mdates.date2num(start), mdates.date2num(end)),
        freq=np.asarray([100.0, 200.0]),
        title="Synthetic CSO spectrum",
        cmap="jet",
        vmin=None,
        vmax=None,
        cbar_label="Intensity",
        source_file="synthetic.fits",
    )


def test_export_drift_preview_cli_is_opt_in_and_applied():
    assert (
        cso_workflow.PlotConfig.__dataclass_fields__[  # noqa: SLF001
            "export_drift_selection_preview"
        ].default
        is False
    )
    cfg = cso_workflow.PlotConfig()
    cfg.export_drift_selection_preview = False

    default_args = cso_workflow.build_parser().parse_args([])
    cso_workflow._apply_cli_overrides(cfg, default_args)
    assert cfg.export_drift_selection_preview is False

    export_args = cso_workflow.build_parser().parse_args(["--export-drift-preview"])
    cso_workflow._apply_cli_overrides(cfg, export_args)
    assert cfg.export_drift_selection_preview is True


def test_export_preview_suppresses_implicit_selector_server(tmp_path):
    launch_calls = []

    def fail_if_launched(cache, cfg):
        launch_calls.append((cache, cfg))
        raise AssertionError("preview export must not launch the selector server")

    cfg = {
        "enable_drift_rate_overlay": True,
        "drift_rate_mode": "interactive_manual",
        "export_drift_selection_preview": True,
        "drift_rate_selection_json": "missing-selection.json",
        "save_path": str(tmp_path),
        "drift_rate_interactive": {
            "launch_policy": "always",
            "print_usage_hint": False,
        },
    }

    results = cso_workflow.get_or_load_drift_rate_results(
        _cache(), cfg, launch_func=fail_if_launched
    )

    assert results == []
    assert launch_calls == []


def test_preview_renderer_writes_png_and_metadata_without_server(tmp_path):
    cfg = {
        "save_path": str(tmp_path),
        "drift_rate_selection_preview_png": "preview.png",
        "drift_rate_selection_metadata_json": "preview.json",
        "show_plot": False,
        "fig_width": 4.0,
        "fig_height_per": 2.0,
        "dpi": 40,
    }

    preview_path, metadata = cso_workflow.render_spectrogram_selection_preview(
        _cache(), cfg
    )

    assert preview_path == str(tmp_path / "preview.png")
    assert (tmp_path / "preview.png").stat().st_size > 0
    payload = json.loads((tmp_path / "preview.json").read_text(encoding="utf-8"))
    assert payload == metadata
    assert payload["source_file"] == "synthetic.fits"


def test_explicit_selector_still_wins_when_preview_export_is_enabled(tmp_path):
    expected = []
    launch_calls = []

    def explicit_launch(cache, cfg):
        launch_calls.append((cache, cfg))
        return expected

    cfg = {
        "enable_drift_rate_overlay": True,
        "drift_rate_mode": "interactive_manual",
        "export_drift_selection_preview": True,
        "_select_drift_now": True,
        "drift_rate_selection_json": "explicit-selection.json",
        "save_path": str(tmp_path),
        "drift_rate_interactive": {"launch_policy": "always"},
    }

    results = cso_workflow.get_or_load_drift_rate_results(
        _cache(), cfg, launch_func=explicit_launch
    )

    assert results == expected
    assert len(launch_calls) == 1
