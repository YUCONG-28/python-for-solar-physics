from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from solar_toolkit.visualization import (
    media,
)
from solar_toolkit.visualization import (
    radio_source_video as video_module,
)
from solar_toolkit.visualization.radio_source_video import (
    VideoExportOptions,
    export_radio_source_video,
    export_radio_source_video_mp4,
)


def _centers() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:45"),
                "freq_mhz": 149.0,
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": 10.0,
                "center_y_arcsec": 20.0,
            },
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:46"),
                "freq_mhz": 149.0,
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": 12.0,
                "center_y_arcsec": 22.0,
            },
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:45"),
                "freq_mhz": 164.0,
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": -8.0,
                "center_y_arcsec": 15.0,
            },
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:46"),
                "freq_mhz": 164.0,
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": -6.0,
                "center_y_arcsec": 17.0,
            },
        ]
    )


def test_export_radio_source_video_mp4_writes_playable_file(tmp_path):
    centers = _centers()
    out = tmp_path / "trajectory.mp4"

    result = export_radio_source_video_mp4(
        centers,
        [
            pd.Timestamp("2025-01-24T04:48:45"),
            pd.Timestamp("2025-01-24T04:48:46"),
        ],
        frame_mode="tail",
        tail_n=1,
        plot_layout="facets",
        facet_by="freq_mhz",
        options=VideoExportOptions(
            out_path=out,
            fps=2.0,
            width=480,
            height=320,
            theme_mode="dark",
            draw_lines=True,
            include_aia=False,
            marker_size=12,
            marker_symbol_by_freq={"149": "x", "164": "triangle-up"},
            trail_min_opacity=0.35,
        ),
    )

    assert result == out.resolve()
    assert result.exists()
    assert result.stat().st_size > 0

    metadata = media.probe_video(
        result,
        expected_size=(480, 320),
        expected_frame_count=2,
    )
    assert metadata["codec"] == "h264"
    assert metadata["frame_count"] == 2
    assert metadata["duration"] == pytest.approx(1.0, abs=0.5)


@pytest.mark.parametrize("output_format", ["mp4", "gif", "webm"])
def test_export_radio_source_video_uses_shared_writer_and_selected_range(
    tmp_path, monkeypatch, output_format
):
    rendered_times: list[pd.Timestamp] = []
    writer_calls: list[dict[str, object]] = []

    def fake_render(_visible, frame_time, **kwargs):
        rendered_times.append(pd.Timestamp(frame_time))
        return np.zeros((kwargs["height"], kwargs["width"], 3), dtype=np.uint8)

    def fake_writer(frame_factory, output_path, fps, quality, **kwargs):
        frames = list(frame_factory())
        writer_calls.append(
            {
                "frames": frames,
                "output_path": Path(output_path),
                "fps": fps,
                "quality": quality,
                **kwargs,
            }
        )
        Path(output_path).write_bytes(b"video")
        return True

    monkeypatch.setattr(video_module, "_render_frame_rgb", fake_render)
    monkeypatch.setattr(media, "write_media_from_frames", fake_writer)
    times = [
        pd.Timestamp("2025-01-24T04:48:45") + pd.Timedelta(seconds=i) for i in range(4)
    ]

    result = export_radio_source_video(
        _centers(),
        times,
        frame_mode="tail",
        tail_n=1,
        plot_layout="overlay",
        facet_by="freq_mhz",
        options=VideoExportOptions(
            out_path=tmp_path / "trajectory.wrong",
            output_format=output_format,
            quality="low",
            fps=29.97,
            width=321,
            height=241,
            include_aia=False,
            start_frame=1,
            end_frame=3,
        ),
    )

    assert result == (tmp_path / f"trajectory.{output_format}").resolve()
    assert rendered_times == times[1:3]
    assert len(writer_calls[0]["frames"]) == 2
    assert writer_calls[0]["fps"] == pytest.approx(29.97)
    assert writer_calls[0]["quality"] == "low"
    assert writer_calls[0]["frame_size"] == (320, 240)
    assert writer_calls[0]["output_format"] == output_format


def test_export_radio_source_video_mp4_wrapper_forces_mp4(tmp_path, monkeypatch):
    captured: dict[str, object] = {}

    def fake_export(*args, **kwargs):
        captured.update(kwargs)
        return tmp_path / "wrapped.mp4"

    monkeypatch.setattr(video_module, "export_radio_source_video", fake_export)
    result = export_radio_source_video_mp4(
        _centers(),
        [pd.Timestamp("2025-01-24T04:48:45")],
        frame_mode="all",
        tail_n=1,
        plot_layout="overlay",
        facet_by="freq_mhz",
        options=VideoExportOptions(
            out_path=tmp_path / "wrapped.webm", output_format="webm"
        ),
    )

    assert result == tmp_path / "wrapped.mp4"
    assert captured["options"].output_format == "mp4"


def test_radio_aia_background_cache_is_bounded_to_eight(tmp_path, monkeypatch):
    paths = [f"aia-{index}.fits" for index in range(9)] + ["aia-0.fits"]
    nearest_calls = iter(paths)
    loaded: list[str] = []

    monkeypatch.setattr(
        video_module,
        "find_nearest_aia",
        lambda *args, **kwargs: SimpleNamespace(
            status="matched", path=next(nearest_calls)
        ),
    )
    monkeypatch.setattr(
        video_module,
        "_render_frame_rgb",
        lambda _visible, _frame_time, **kwargs: np.zeros(
            (kwargs["height"], kwargs["width"], 3), dtype=np.uint8
        ),
    )

    def fake_writer(frame_factory, output_path, *args, **kwargs):
        assert len(list(frame_factory())) == 10
        Path(output_path).write_bytes(b"video")
        return True

    monkeypatch.setattr(media, "write_media_from_frames", fake_writer)
    times = [pd.Timestamp("2025-01-24") + pd.Timedelta(seconds=i) for i in range(10)]
    export_radio_source_video(
        _centers(),
        times,
        frame_mode="all",
        tail_n=1,
        plot_layout="overlay",
        facet_by="freq_mhz",
        options=VideoExportOptions(out_path=tmp_path / "cached.mp4"),
        aia_table=pd.DataFrame({"path": ["placeholder"]}),
        background_loader=lambda path, **kwargs: loaded.append(path) or object(),
    )

    assert loaded.count("aia-0.fits") == 2
    assert len(loaded) == 10


def test_radio_renderer_closes_figure_after_failure(monkeypatch):
    import matplotlib.pyplot as plt

    existing_figures = set(plt.get_fignums())
    monkeypatch.setattr(
        video_module,
        "_draw_axes",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("draw failed")),
    )
    with pytest.raises(RuntimeError, match="draw failed"):
        video_module._render_frame_rgb(
            _centers(),
            pd.Timestamp("2025-01-24T04:48:45"),
            width=320,
            height=240,
            theme_mode="light",
            draw_lines=True,
            marker_size=8,
            marker_symbol_by_freq=None,
            trail_min_opacity=0.25,
            plot_layout="overlay",
            facet_by="freq_mhz",
            facet_values=[],
            axis={"x": (-10.0, 10.0), "y": (-10.0, 10.0)},
            aia_background=None,
        )

    assert set(plt.get_fignums()) == existing_figures
