from __future__ import annotations

import base64
import importlib
import io
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from solar_toolkit.aia.background import AiaBackground
from solar_toolkit.visualization.radio_source_trajectory import aia_colormap_name

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
        "scripts.radio.run_radio_source_app_managed",
    ]:
        module = importlib.import_module(module_name)
        assert hasattr(module, "main")


def test_radio_source_entrypoint_help_commands_run():
    for script in [
        "scripts/radio/extract_radio_centers.py",
        "scripts/radio/export_radio_source_trajectory.py",
        "scripts/radio/run_radio_source_app.py",
        "scripts/radio/run_radio_source_app_managed.py",
    ]:
        result = _run_help(script)
        assert result.returncode == 0, result.stderr
        assert "usage:" in result.stdout.lower()


def test_radio_center_and_app_entrypoint_help_exposes_event_filters():
    center_help = _run_help("scripts/radio/extract_radio_centers.py")
    app_help = _run_help("scripts/radio/run_radio_source_app.py")

    assert center_help.returncode == 0, center_help.stderr
    assert app_help.returncode == 0, app_help.stderr
    for marker in ["--freqs", "--time-start", "--time-end", "--polarizations"]:
        assert marker in center_help.stdout
    for marker in ["--time-start", "--time-end", "--aia-dir", "--frame-mode"]:
        assert marker in app_help.stdout


def test_radio_source_app_help_exposes_frontend_preference_args():
    app_help = _run_help("scripts/radio/run_radio_source_app.py")
    managed_help = _run_help("scripts/radio/run_radio_source_app_managed.py")

    assert app_help.returncode == 0, app_help.stderr
    assert managed_help.returncode == 0, managed_help.stderr
    for marker in [
        "--settings-file",
        "--reset-settings",
        "--theme-mode",
        "--screen-fit",
    ]:
        assert marker in app_help.stdout
    for marker in [
        "--auto-stop",
        "--no-auto-stop",
        "--auto-stop-idle-sec",
        "--browser",
        "--no-browser",
    ]:
        assert marker in managed_help.stdout


def test_radio_source_app_settings_roundtrip_and_cli_override(tmp_path):
    module = importlib.import_module("scripts.radio.run_radio_source_app")
    settings_file = tmp_path / "radio_source_app_settings.json"

    missing = module.load_app_settings(settings_file)
    assert missing["centers"] == "radio_centers.csv"
    assert missing["theme_mode"] == "auto"
    assert missing["screen_fit"] == "auto"
    assert missing["show_debug_tables"] is False
    assert missing["playback_aia_max_pixels"] == 384
    assert missing["playback_min_step_sec"] == 0.25
    assert missing["playback_renderer"] == "preloaded"
    assert missing["plot_layout"] == "overlay"
    assert missing["facet_by"] == "freq_mhz"
    assert missing["video_width"] == 1280
    assert missing["video_height"] == 720
    assert missing["video_fps"] == 6.0
    assert missing["video_output_format"] == "mp4"
    assert missing["video_browser_format"] == "webm"
    assert missing["video_quality"] == "high"
    assert missing["video_output_path"] == ""
    assert missing["video_include_aia"] is True
    assert missing["marker_size"] == 8
    assert missing["frequency_marker_symbols"] == {}
    assert missing["trail_min_opacity"] == 0.25
    assert missing["link_facet_views"] is False

    module.save_app_settings(
        settings_file,
        {
            "centers": "remembered.csv",
            "aia_dir": "remembered_aia",
            "theme_mode": "dark",
            "screen_fit": "portrait",
            "tail_n": 11,
            "playback_aia_max_pixels": 512,
            "playback_min_step_sec": 0.5,
            "plot_layout": "facets",
            "facet_by": "polarization",
            "video_width": 960,
            "video_height": 640,
            "video_fps": 4.0,
            "video_output_format": "gif",
            "video_browser_format": "mp4",
            "video_quality": "low",
            "video_output_path": str(tmp_path / "remembered.webm"),
            "video_include_aia": False,
            "marker_size": 13,
            "frequency_marker_symbols": {"149": "x", "164": "triangle-up"},
            "trail_min_opacity": 0.4,
            "link_facet_views": True,
        },
    )
    stored = module.load_app_settings(settings_file)
    args = module.build_parser().parse_args(
        ["--centers", "explicit.csv", "--theme-mode", "light"]
    )
    resolved = module.resolve_app_settings(args, stored)

    assert resolved["centers"] == "explicit.csv"
    assert resolved["theme_mode"] == "light"
    assert resolved["aia_dir"] == "remembered_aia"
    assert resolved["screen_fit"] == "portrait"
    assert resolved["tail_n"] == 11
    assert resolved["playback_aia_max_pixels"] == 512
    assert resolved["playback_min_step_sec"] == 0.5
    assert resolved["playback_renderer"] == "preloaded"
    assert resolved["plot_layout"] == "facets"
    assert resolved["facet_by"] == "polarization"
    assert resolved["video_width"] == 960
    assert resolved["video_height"] == 640
    assert resolved["video_fps"] == 4.0
    assert resolved["video_output_format"] == "gif"
    assert resolved["video_browser_format"] == "mp4"
    assert resolved["video_quality"] == "low"
    assert resolved["video_output_path"] == str(tmp_path / "remembered.webm")
    assert resolved["video_include_aia"] is False
    assert resolved["marker_size"] == 13
    assert resolved["frequency_marker_symbols"] == {
        "149": "x",
        "164": "triangle-up",
    }
    assert resolved["trail_min_opacity"] == 0.4
    assert resolved["link_facet_views"] is True
    assert (
        module.load_app_settings(settings_file, reset=True)["centers"]
        == "radio_centers.csv"
    )


def test_radio_source_app_coalesces_dense_playback_frame_times():
    module = importlib.import_module("scripts.radio.run_radio_source_app")
    times = [
        "2025-01-24T04:48:45.000",
        "2025-01-24T04:48:45.050",
        "2025-01-24T04:48:45.240",
        "2025-01-24T04:48:45.260",
        "2025-01-24T04:48:45.510",
    ]

    raw = module.coalesce_frame_times(times, min_step_sec=0)
    smooth = module.coalesce_frame_times(times, min_step_sec=0.25)

    assert [item.isoformat() for item in raw] == [
        "2025-01-24T04:48:45",
        "2025-01-24T04:48:45.050000",
        "2025-01-24T04:48:45.240000",
        "2025-01-24T04:48:45.260000",
        "2025-01-24T04:48:45.510000",
    ]
    assert [item.isoformat() for item in smooth] == [
        "2025-01-24T04:48:45",
        "2025-01-24T04:48:45.260000",
        "2025-01-24T04:48:45.510000",
    ]


def test_radio_source_app_uses_low_res_aia_only_during_playback():
    module = importlib.import_module("scripts.radio.run_radio_source_app")

    assert (
        module.resolve_effective_aia_max_pixels(
            max_pixels=1280,
            playback_aia_max_pixels=384,
            playing=True,
        )
        == 384
    )
    assert (
        module.resolve_effective_aia_max_pixels(
            max_pixels=1280,
            playback_aia_max_pixels=384,
            playing=False,
        )
        == 1280
    )


def test_preloaded_payload_deduplicates_aia_backgrounds():
    module = importlib.import_module("scripts.radio.run_radio_source_app")
    centers = pd.DataFrame(
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
                "obs_time": pd.Timestamp("2025-01-24T04:48:45.500"),
                "freq_mhz": 149.0,
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": 11.0,
                "center_y_arcsec": 21.0,
            },
        ]
    )
    aia_table = pd.DataFrame(
        [
            {
                "path": "synthetic_aia.fits",
                "obs_time": pd.Timestamp("2025-01-24T04:48:45.200"),
                "wavelength": "171",
            }
        ]
    )
    background = AiaBackground(
        path="synthetic_aia.fits",
        z=np.array([[0.0, 1.0], [2.0, 3.0]]),
        x_arcsec=np.array([1.0, 2.0]),
        y_arcsec=np.array([3.0, 4.0]),
        label="synthetic",
        obs_time=pd.Timestamp("2025-01-24T04:48:45.200"),
        wavelength="171",
    )
    calls: list[str] = []

    def load_background(path, **_kwargs):
        calls.append(path)
        return background

    payload = module.build_preloaded_playback_payload(
        centers,
        [
            pd.Timestamp("2025-01-24T04:48:45"),
            pd.Timestamp("2025-01-24T04:48:45.500"),
        ],
        frame_mode="all",
        tail_n=5,
        aia_table=aia_table,
        use_aia=True,
        max_aia_dt_sec=10.0,
        playback_aia_max_pixels=384,
        percentile_limits=(1.0, 99.7),
        log_scale=True,
        wcs_mode="header",
        background_loader=load_background,
    )

    assert len(payload["backgrounds"]) == 1
    assert len(calls) == 1
    assert payload["frames"][0]["background"] == payload["frames"][1]["background"]
    assert payload["frames"][1]["groups"][0]["end"] == 2


def test_preloaded_payload_records_facet_metadata_and_tail_indices():
    module = importlib.import_module("scripts.radio.run_radio_source_app")
    centers = pd.DataFrame(
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
                "center_x_arcsec": 11.0,
                "center_y_arcsec": 21.0,
            },
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:45"),
                "freq_mhz": 164.0,
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": -5.0,
                "center_y_arcsec": 17.0,
            },
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:46"),
                "freq_mhz": 164.0,
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": -4.0,
                "center_y_arcsec": 18.0,
            },
        ]
    )

    payload = module.build_preloaded_playback_payload(
        centers,
        [pd.Timestamp("2025-01-24T04:48:46")],
        frame_mode="tail",
        tail_n=1,
        plot_layout="facets",
        facet_by="freq_mhz",
        marker_size=13,
        marker_symbol_by_freq={"149": "x", "164": "triangle-up"},
        trail_min_opacity=0.4,
        link_views=True,
    )

    assert payload["layout"]["plot_layout"] == "facets"
    assert payload["layout"]["facet_by"] == "freq_mhz"
    assert [facet["label"] for facet in payload["layout"]["facets"]] == [
        "149 MHz",
        "164 MHz",
    ]
    assert {trace["facet"] for trace in payload["traces"]} == {0, 1}
    assert all(
        group["end"] - group["start"] == 1 for group in payload["frames"][0]["groups"]
    )
    assert payload["config"]["marker_size"] == 13
    assert payload["config"]["trail_min_opacity"] == 0.4
    assert payload["config"]["link_views"] is True
    assert {
        trace["freq_mhz"]: trace["marker_symbol"] for trace in payload["traces"]
    } == {149.0: "x", 164.0: "triangle-up"}
    assert payload["layout"]["facet_spacing"] == {"x": 0.075, "y": 0.13}


def test_preload_signature_requires_apply_before_rebuild():
    module = importlib.import_module("scripts.radio.run_radio_source_app")
    first = module.build_preload_signature(
        {
            "centers": "centers.csv",
            "time_start": "2025-01-24T04:46:45",
            "tail_n": 5,
            "selected_freqs": [149.0, 164.0],
        }
    )
    first_again = module.build_preload_signature(
        {
            "selected_freqs": [149.0, 164.0],
            "tail_n": 5,
            "time_start": "2025-01-24T04:46:45",
            "centers": "centers.csv",
        }
    )
    changed = module.build_preload_signature(
        {
            "centers": "centers.csv",
            "time_start": "2025-01-24T04:46:45",
            "tail_n": 8,
            "selected_freqs": [149.0, 164.0],
        }
    )

    assert first == first_again
    assert changed != first
    assert (
        module.should_build_preloaded_payload(
            first,
            None,
            apply_clicked=False,
            has_payload=False,
        )
        is True
    )
    assert (
        module.should_build_preloaded_payload(
            changed,
            first,
            apply_clicked=False,
            has_payload=True,
        )
        is False
    )
    assert module.preload_settings_changed(changed, first, has_payload=True) is True
    assert (
        module.should_build_preloaded_payload(
            changed,
            first,
            apply_clicked=True,
            has_payload=True,
        )
        is True
    )


def test_aia_background_to_png_data_uri_preserves_extent():
    module = importlib.import_module("scripts.radio.run_radio_source_app")
    background = AiaBackground(
        path="synthetic_aia.fits",
        z=np.array([[0.0, 1.0], [2.0, 3.0]]),
        x_arcsec=np.array([-5.0, 5.0]),
        y_arcsec=np.array([10.0, 20.0]),
        label="synthetic",
        obs_time=pd.Timestamp("2025-01-24T04:48:45"),
        wavelength="171",
    )

    image = module.aia_background_to_png_image(background)

    assert image["source"].startswith("data:image/png;base64,")
    assert image["x0"] == -5.0
    assert image["x1"] == 5.0
    assert image["y0"] == 10.0
    assert image["y1"] == 20.0


def test_aia_background_png_uses_wavelength_colormap_and_grayscale_fallback():
    module = importlib.import_module("scripts.radio.run_radio_source_app")
    background = AiaBackground(
        path="synthetic_aia.fits",
        z=np.array([[0.0, 0.4], [0.7, 1.0]]),
        x_arcsec=np.array([-5.0, 5.0]),
        y_arcsec=np.array([10.0, 20.0]),
        label="synthetic",
        obs_time=pd.Timestamp("2025-01-24T04:48:45"),
        wavelength="171",
    )
    colored = module.aia_background_to_png_image(background)
    colored_raw = base64.b64decode(colored["source"].split(",", 1)[1])
    colored_image = Image.open(io.BytesIO(colored_raw))
    colored_array = np.asarray(colored_image.convert("RGB"))

    assert aia_colormap_name("94") == "sdoaia94"
    assert aia_colormap_name("171") == "sdoaia171"
    assert colored_image.mode in {"RGB", "RGBA"}
    assert np.any(colored_array[..., 0] != colored_array[..., 1])

    fallback = module.aia_background_to_png_image(
        AiaBackground(
            path="synthetic_aia.fits",
            z=background.z,
            x_arcsec=background.x_arcsec,
            y_arcsec=background.y_arcsec,
            label="synthetic",
            obs_time=background.obs_time,
            wavelength="unknown",
        )
    )
    fallback_raw = base64.b64decode(fallback["source"].split(",", 1)[1])
    fallback_array = np.asarray(Image.open(io.BytesIO(fallback_raw)).convert("RGB"))
    assert np.all(fallback_array[..., 0] == fallback_array[..., 1])
    assert np.all(fallback_array[..., 1] == fallback_array[..., 2])


def test_preloaded_player_html_contains_single_plotly_root_and_payload():
    module = importlib.import_module("scripts.radio.run_radio_source_app")
    payload = {
        "version": 1,
        "frames": [{"time": "2025-01-24T04:48:45", "groups": [], "background": None}],
        "traces": [],
        "backgrounds": {},
        "layout": {
            "height": 500,
            "title": "test",
            "theme_mode": "auto",
            "theme": "light",
            "plot_layout": "overlay",
            "facet_by": "freq_mhz",
            "facets": [],
        },
        "config": {
            "fps": 2.0,
            "draw_lines": True,
            "marker_size": 8,
            "trail_min_opacity": 0.25,
            "link_views": False,
            "recording": {
                "format": "mp4",
                "quality": "high",
                "fps": 30.0,
                "width": 640,
                "height": 480,
                "start_frame": 0,
                "end_frame": 1,
            },
        },
    }

    html = module.build_preloaded_playback_html(
        payload,
        plotly_js="/* plotly */",
        mediabunny_js="window.Mediabunny = {};",
        browser_media_js="window.SolarToolkitMedia = {};",
    )

    assert html.count('id="radio-preloaded-plot"') == 1
    assert "const radioPayload =" in html
    assert "Plotly.newPlot" in html
    assert "Plotly.react" in html
    assert "radio-reset-view" in html
    assert "radio-sync-view" in html
    assert "radio-link-views" in html
    assert 'aria-label="Play or pause smooth playback"' in html
    assert 'title="Reset all plot axes to the initial data range."' in html
    assert 'title="Synchronize all facet plots to the last adjusted view."' in html
    assert 'title="Download the completed browser recording."' in html
    assert "function aspectCorrectRange" in html
    assert "aspectCorrectedAxis" in html
    assert "aspectCorrectRange(axis.x0, axis.x1, axis.y0, axis.y1" in html
    assert "plotly_relayout" in html
    assert "Plotly.relayout" in html
    assert "opacityForPoints" in html
    assert "MediaRecorder" not in html
    assert "captureStream" not in html
    assert "Plotly.toImage" in html
    assert "Radio source time:" in html
    assert "marker_symbol" in html
    assert "symbol: trace.marker_symbol" in html
    assert "prepareRecordingFrames" not in html
    assert "SolarToolkitMedia.createCanvasRecorder" in html
    assert "recordingSession.addFrame(offset / options.fps, 1 / options.fps" in html
    assert 'recordEl.textContent = "Cancel"' in html
    assert 'typeof image.close === "function"' in html
    assert '"start_frame": 0' in html
    assert '"end_frame": 1' in html
    assert '"format": "mp4"' in html
    assert "radio-record" in html
    assert "radio-play" in html


def test_managed_radio_source_app_parser_defaults_and_overrides():
    module = importlib.import_module("scripts.radio.run_radio_source_app_managed")

    default_args = module.build_parser().parse_args([])
    assert default_args.auto_stop is True
    assert default_args.browser is True

    overridden = module.build_parser().parse_args(
        ["--no-auto-stop", "--auto-stop-idle-sec", "15", "--no-browser"]
    )
    assert overridden.auto_stop is False
    assert overridden.auto_stop_idle_sec == 15.0
    assert overridden.browser is False


def test_radio_source_app_visible_copy_is_english():
    source = (REPO_ROOT / "solar_toolkit/radio/source_app.py").read_text(
        encoding="utf-8"
    )

    for expected in [
        "Common Parameters",
        "Image Display",
        "Radio Trajectory",
        "Video Export",
        "Apply & Preload",
        "Export Video",
        "Previous Frame",
        "Motion Summary",
    ]:
        assert expected in source
    for forbidden in [
        "常用参数",
        "图像显示",
        "射电轨迹",
        "视频导出",
        "导出 MP4",
        "上一帧",
        "运动摘要",
    ]:
        assert forbidden not in source
    assert 'st.iframe(html, height=component_height, width="stretch")' in source


def test_radio_source_light_theme_css_covers_streamlit_surfaces():
    module = importlib.import_module("scripts.radio.run_radio_source_app")

    css = module._theme_css(
        app_bg="#ffffff",
        sidebar_bg="#f8fafc",
        text="#111827",
        border="#d1d5db",
        input_bg="#ffffff",
    )

    for marker in [
        '[data-testid="stHeader"]',
        '[data-testid="stSidebar"]',
        '[data-baseweb="input"] input',
        '[data-testid="stTextInput"] input',
        '[data-testid="stButton"] button',
        '[data-testid="stAlert"]',
        ".streamlit-expanderHeader",
        "--radio-theme-input-bg: #ffffff;",
        "background-color: #ffffff",
        "color: #111827",
    ]:
        assert marker in css
