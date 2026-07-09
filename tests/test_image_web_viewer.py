from __future__ import annotations

import importlib.util
import io
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_png(path: Path, color: tuple[int, int, int], size=(8, 6)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)


def test_scan_images_filters_extensions_and_natural_sorts(tmp_path):
    from solar_toolkit.visualization.image_web_viewer.server import scan_images

    _write_png(tmp_path / "frame10.png", (10, 0, 0))
    _write_png(tmp_path / "frame2.png", (2, 0, 0))
    _write_png(tmp_path / "frame1.jpg", (1, 0, 0))
    _write_png(tmp_path / "sub" / "frame0.png", (0, 0, 0))
    (tmp_path / "notes.txt").write_text("ignore", encoding="utf-8")

    root, files = scan_images(tmp_path, recursive=False)
    _recursive_root, recursive_files = scan_images(tmp_path, recursive=True)

    assert root == tmp_path.resolve()
    assert [path.name for path in files] == ["frame1.jpg", "frame2.png", "frame10.png"]
    assert [path.name for path in recursive_files] == [
        "frame0.png",
        "frame1.jpg",
        "frame2.png",
        "frame10.png",
    ]


def test_scan_images_rejects_missing_non_directory_and_disallowed_roots(tmp_path):
    from solar_toolkit.visualization.image_web_viewer.server import scan_images

    allowed = tmp_path / "allowed"
    blocked = tmp_path / "blocked"
    allowed.mkdir()
    blocked.mkdir()
    file_path = allowed / "image.png"
    _write_png(file_path, (1, 2, 3))

    assert scan_images(allowed, allowed_roots=[allowed])[0] == allowed.resolve()
    with pytest.raises(FileNotFoundError):
        scan_images(tmp_path / "missing")
    with pytest.raises(NotADirectoryError):
        scan_images(file_path)
    with pytest.raises(PermissionError):
        scan_images(blocked, allowed_roots=[allowed])


def test_build_composite_frame_handles_roi_and_missing_frames(tmp_path):
    from solar_toolkit.visualization.image_web_viewer.export import (
        build_composite_frame,
    )

    left = tmp_path / "left"
    right = tmp_path / "right"
    _write_png(left / "frame0.png", (255, 0, 0), size=(10, 10))
    _write_png(left / "frame1.png", (0, 255, 0), size=(10, 10))
    _write_png(right / "frame0.png", (0, 0, 255), size=(20, 10))
    groups = [
        {
            "name": "left",
            "folder": str(left),
            "files": [left / "frame0.png", left / "frame1.png"],
        },
        {"name": "right", "folder": str(right), "files": [right / "frame0.png"]},
    ]

    frame = build_composite_frame(
        groups,
        frame_index=1,
        panel_size=(16, 12),
        roi={"x": 0.0, "y": 0.0, "w": 0.5, "h": 1.0},
    )

    assert frame.shape == (12, 32, 3)
    assert np.all(frame[:, :16, 1] >= frame[:, :16, 0])
    assert np.all(frame[:, 16:] == 0)


def test_video_export_invokes_separate_and_composite_writers(tmp_path, monkeypatch):
    from solar_toolkit.visualization.image_web_viewer import export as export_mod

    source = tmp_path / "source"
    _write_png(source / "frame0.png", (1, 2, 3))
    _write_png(source / "frame1.png", (4, 5, 6))
    groups = [
        {"name": "source", "folder": str(source), "files": sorted(source.glob("*.png"))}
    ]
    calls: list[dict] = []
    frame_calls: list[dict] = []

    def fake_writer(paths, output_path, fps, quality, target_size_tuple=None, **kwargs):
        calls.append(
            {
                "paths": [str(path) for path in paths],
                "output_path": str(output_path),
                "fps": fps,
                "quality": quality,
                "target_size_tuple": target_size_tuple,
            }
        )
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(b"fake video")
        return True

    def fake_frame_writer(
        frame_iter,
        output_path,
        fps,
        quality,
        *,
        frame_size,
        output_format,
    ):
        frames = list(frame_iter)
        frame_calls.append(
            {
                "output_path": str(output_path),
                "fps": fps,
                "quality": quality,
                "frame_size": frame_size,
                "output_format": output_format,
                "frame_count": len(frames),
            }
        )
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(b"fake video")
        return True

    monkeypatch.setattr(export_mod, "_write_video_from_paths", fake_writer)
    monkeypatch.setattr(export_mod.media, "write_media_from_frames", fake_frame_writer)

    config = export_mod.ExportConfig(
        output_dir=tmp_path / "videos",
        file_prefix="demo",
        fps=7,
        quality="low",
        target_size=(12, 8),
    )
    separate = export_mod.export_separate_videos(groups, config)
    composite = export_mod.export_composite_video(groups, config)

    assert separate["status"] == "saved"
    assert composite["status"] == "saved"
    assert len(calls) == 1
    assert calls[0]["fps"] == 7
    assert calls[0]["target_size_tuple"] == (12, 8)
    assert frame_calls == [
        {
            "output_path": str(tmp_path / "videos" / "demo_composite.mp4"),
            "fps": 7,
            "quality": "low",
            "frame_size": (12, 8),
            "output_format": "mp4",
            "frame_count": 2,
        }
    ]
    assert Path(composite["path"]).name == "demo_composite.mp4"


def test_video_export_normalizes_format_and_uses_selected_extension(
    tmp_path, monkeypatch
):
    from solar_toolkit.visualization.image_web_viewer import export as export_mod

    source = tmp_path / "source"
    _write_png(source / "frame0.png", (1, 2, 3))
    groups = [
        {"name": "source", "folder": str(source), "files": sorted(source.glob("*.png"))}
    ]
    calls: list[dict] = []
    frame_calls: list[dict] = []

    def fake_writer(paths, output_path, fps, quality, target_size_tuple=None, **kwargs):
        calls.append(
            {
                "output_path": str(output_path),
                "output_format": kwargs["output_format"],
            }
        )
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(b"fake video")
        return True

    def fake_frame_writer(
        frame_iter,
        output_path,
        fps,
        quality,
        *,
        frame_size,
        output_format,
    ):
        list(frame_iter)
        frame_calls.append(
            {
                "output_path": str(output_path),
                "output_format": output_format,
            }
        )
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(b"fake video")
        return True

    monkeypatch.setattr(export_mod, "_write_video_from_paths", fake_writer)
    monkeypatch.setattr(export_mod.media, "write_media_from_frames", fake_frame_writer)

    config = export_mod.ExportConfig(
        output_dir=tmp_path / "videos",
        file_prefix="demo",
        output_format="WEBM",
    )
    separate = export_mod.export_separate_videos(groups, config)
    composite = export_mod.export_composite_video(groups, config)

    assert separate["paths"][0].endswith("_source.webm")
    assert Path(composite["path"]).name == "demo_composite.webm"
    assert [call["output_format"] for call in calls] == ["webm"]
    assert [call["output_format"] for call in frame_calls] == ["webm"]


def test_video_export_defaults_unknown_format_to_mp4(tmp_path, monkeypatch):
    from solar_toolkit.visualization.image_web_viewer import export as export_mod

    source = tmp_path / "source"
    _write_png(source / "frame0.png", (1, 2, 3))
    groups = [
        {"name": "source", "folder": str(source), "files": sorted(source.glob("*.png"))}
    ]

    def fake_writer(paths, output_path, fps, quality, target_size_tuple=None, **kwargs):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(b"fake video")
        return True

    def fake_frame_writer(
        frame_iter,
        output_path,
        fps,
        quality,
        *,
        frame_size,
        output_format,
    ):
        list(frame_iter)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(b"fake video")
        return True

    monkeypatch.setattr(export_mod, "_write_video_from_paths", fake_writer)
    monkeypatch.setattr(export_mod.media, "write_media_from_frames", fake_frame_writer)

    result = export_mod.export_composite_video(
        groups,
        export_mod.ExportConfig(
            output_dir=tmp_path / "videos",
            file_prefix="demo",
            output_format="unknown",
        ),
    )

    assert Path(result["path"]).name == "demo_composite.mp4"


def test_composite_export_streams_generated_frames_without_temp_paths(
    tmp_path, monkeypatch
):
    from solar_toolkit.visualization.image_web_viewer import export as export_mod

    source = tmp_path / "source"
    _write_png(source / "frame0.png", (1, 2, 3), size=(9, 7))
    _write_png(source / "frame1.png", (4, 5, 6), size=(9, 7))
    groups = [
        {"name": "source", "folder": str(source), "files": sorted(source.glob("*.png"))}
    ]
    calls: list[dict] = []

    def fake_path_writer(*args, **kwargs):
        raise AssertionError("composite export should stream frames, not temp paths")

    def fake_frame_writer(
        frame_iter,
        output_path,
        fps,
        quality,
        *,
        frame_size,
        output_format,
    ):
        frames = list(frame_iter)
        calls.append(
            {
                "output_path": Path(output_path),
                "fps": fps,
                "quality": quality,
                "frame_size": frame_size,
                "output_format": output_format,
                "frame_shapes": [frame.shape for frame, _size in frames],
            }
        )
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(b"streamed video")
        return True

    monkeypatch.setattr(export_mod, "_write_video_from_paths", fake_path_writer)
    monkeypatch.setattr(
        export_mod.media, "write_media_from_frames", fake_frame_writer, raising=False
    )

    result = export_mod.export_composite_video(
        groups,
        export_mod.ExportConfig(
            output_dir=tmp_path / "videos",
            file_prefix="demo",
            fps=11,
            quality="high",
            target_size=(12, 8),
            output_format="mp4",
        ),
    )

    assert result["status"] == "saved"
    assert result["frame_count"] == 2
    assert calls == [
        {
            "output_path": tmp_path / "videos" / "demo_composite.mp4",
            "fps": 11,
            "quality": "high",
            "frame_size": (12, 8),
            "output_format": "mp4",
            "frame_shapes": [(8, 12, 3), (8, 12, 3)],
        }
    ]


def test_image_web_viewer_entrypoint_help_does_not_require_flask():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "tools" / "run_image_web_viewer.py"),
            "--help",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()
    assert "--keep-alive-after-close" in result.stdout
    assert "--default-output-format" in result.stdout


def test_image_web_viewer_frontend_exposes_workbench_controls():
    template = (
        REPO_ROOT
        / "solar_toolkit"
        / "visualization"
        / "image_web_viewer"
        / "templates"
        / "index.html"
    ).read_text(encoding="utf-8")
    script = (
        REPO_ROOT
        / "solar_toolkit"
        / "visualization"
        / "image_web_viewer"
        / "static"
        / "main.js"
    ).read_text(encoding="utf-8")

    for marker in [
        'id="sidebar"',
        'id="sidebarToggleBtn"',
        'id="fitLayoutBtn"',
        'id="landscapeLayoutBtn"',
        'id="portraitLayoutBtn"',
        'id="syncViewInput"',
        'id="syncRoiInput"',
        'id="settingsPanel"',
        'id="themeInput"',
        'id="saveSettingsBtn"',
        'id="clearSettingsBtn"',
        'id="stopOnCloseInput"',
        'id="exportSettingsGroup"',
        'id="preloadFrameInput"',
        'id="formatInput"',
        'id="recordBtn"',
        'id="recordStatus"',
        'id="recordingStatusDetail"',
        'id="viewerGrid"',
    ]:
        assert marker in template
    preload_markup = next(
        line for line in template.splitlines() if 'id="preloadFrameInput"' in line
    )
    assert "max=" not in preload_markup
    assert "viewer-slot" in script
    assert "clampView" in script
    assert "layoutMode" in script
    assert "solarToolkit.imageViewer.v1.settings" in script
    assert "requestAnimationFrame" in script
    assert "loadCachedImage" in script
    assert "PRELOAD_SECONDS_AHEAD" in script
    assert "MAX_PRELOAD_CONCURRENCY" in script
    assert "MAX_PRELOAD_AHEAD_FRAMES" not in script
    assert "MAX_CACHE_ENTRIES" not in script
    assert "preloadFrameCount" in script
    assert "normalizePreloadFrameCount" in script
    assert "getPreloadFrameCount" in script
    assert "getDynamicFrameCacheCapacity" in script
    assert "getCachedImageIfReady" in script
    assert "warmFrameWindow" in script
    assert "deferUntilReady" in script
    assert "getSelectedFrameRange" in script
    assert "recordSelectedFrameRange" in script
    assert "captureRangeRecordingFrame" in script
    assert "waitForFrameReady" in script
    assert "Cancel Recording" in script
    assert "Recording canceled." in script
    assert "captureStream(0)" in script
    assert "requestFrame" in script
    assert "requestData" in script
    assert "formatRecordingError" in script
    assert "summarizeSavedPaths" in script
    assert "Preloading frame" in script
    assert "keepCurrentImage" in script
    assert "Missing frame" in script
    assert "Loading..." in script
    assert "/api/client-config" in script
    assert "/api/client-close" in script
    assert "MediaRecorder" in script
    assert "captureStream" in script
    assert "/api/save-recording" in script


@pytest.mark.skipif(
    importlib.util.find_spec("flask") is None,
    reason="Flask is optional; install the app extra to test HTTP routes.",
)
def test_flask_client_lifecycle_routes_schedule_shutdown(tmp_path):
    from solar_toolkit.visualization.image_web_viewer.server import create_app

    shutdown_calls: list[str] = []
    app = create_app(
        allowed_roots=[tmp_path],
        shutdown_callback=lambda: shutdown_calls.append("shutdown"),
        close_grace_seconds=0.01,
    )
    client = app.test_client()

    config = client.get("/api/client-config").get_json()
    heartbeat = client.post("/api/client-heartbeat", json={"client_id": "client-a"})
    closed = client.post(
        "/api/client-close",
        json={"client_id": "client-a", "stop_on_close": True},
    )
    time.sleep(0.05)

    assert config["stop_on_close"] is True
    assert config["heartbeat_interval_ms"] > 0
    assert heartbeat.get_json() == {"ok": True}
    assert closed.get_json()["shutdown_scheduled"] is True
    assert shutdown_calls == ["shutdown"]


@pytest.mark.skipif(
    importlib.util.find_spec("flask") is None,
    reason="Flask is optional; install the app extra to test HTTP routes.",
)
def test_flask_client_lifecycle_can_keep_service_alive(tmp_path):
    from solar_toolkit.visualization.image_web_viewer.server import create_app

    shutdown_calls: list[str] = []
    client = create_app(
        allowed_roots=[tmp_path],
        stop_on_client_close=False,
        shutdown_callback=lambda: shutdown_calls.append("shutdown"),
        close_grace_seconds=0.01,
    ).test_client()

    config = client.get("/api/client-config").get_json()
    closed = client.post(
        "/api/client-close",
        json={"client_id": "client-a", "stop_on_close": True},
    ).get_json()
    time.sleep(0.05)

    assert config["stop_on_close"] is False
    assert closed["shutdown_scheduled"] is False
    assert shutdown_calls == []


@pytest.mark.skipif(
    importlib.util.find_spec("flask") is None,
    reason="Flask is optional; install the app extra to test HTTP routes.",
)
def test_flask_routes_load_images_and_export_video(tmp_path, monkeypatch):
    from solar_toolkit.visualization.image_web_viewer import export as export_mod
    from solar_toolkit.visualization.image_web_viewer.server import create_app

    folder = tmp_path / "images"
    _write_png(folder / "frame0.png", (255, 0, 0))
    monkeypatch.setattr(
        export_mod,
        "export_composite_video",
        lambda groups, config: {
            "status": "saved",
            "path": str(config.output_dir / "demo.mp4"),
        },
    )
    monkeypatch.setattr(
        export_mod,
        "export_separate_videos",
        lambda groups, config: {
            "status": "saved",
            "paths": [str(config.output_dir / "single.mp4")],
        },
    )

    client = create_app(allowed_roots=[tmp_path]).test_client()
    health = client.get("/api/health")
    loaded = client.post(
        "/api/load", json={"folders": [str(folder)], "recursive": False}
    )
    payload = loaded.get_json()
    image = client.get(f"/api/image/{payload['session_id']}/0/0")
    exported = client.post(
        "/api/export-video",
        json={
            "session_id": payload["session_id"],
            "mode": "both",
            "output_dir": str(tmp_path / "videos"),
            "file_prefix": "demo",
            "fps": 5,
        },
    )

    assert health.get_json() == {"ok": True}
    assert payload["ok"] is True
    assert image.status_code == 200
    assert exported.get_json()["ok"] is True


@pytest.mark.skipif(
    importlib.util.find_spec("flask") is None,
    reason="Flask is optional; install the app extra to test HTTP routes.",
)
def test_flask_export_video_passes_selected_format(tmp_path, monkeypatch):
    from solar_toolkit.visualization.image_web_viewer import export as export_mod
    from solar_toolkit.visualization.image_web_viewer.server import create_app

    folder = tmp_path / "images"
    _write_png(folder / "frame0.png", (255, 0, 0))
    seen_configs: list[object] = []

    def fake_composite(groups, config):
        seen_configs.append(config)
        return {"status": "saved", "path": str(config.output_dir / "demo.gif")}

    monkeypatch.setattr(export_mod, "export_composite_video", fake_composite)

    client = create_app(allowed_roots=[tmp_path]).test_client()
    loaded = client.post(
        "/api/load", json={"folders": [str(folder)], "recursive": False}
    )
    payload = loaded.get_json()
    exported = client.post(
        "/api/export-video",
        json={
            "session_id": payload["session_id"],
            "mode": "composite",
            "format": "gif",
            "output_dir": str(tmp_path / "videos"),
            "file_prefix": "demo",
            "fps": 12,
            "quality": "high",
            "start_frame": 1,
            "end_frame": 3,
            "target_width": 640,
            "target_height": 480,
            "use_roi": True,
            "roi": {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4},
        },
    )

    assert exported.get_json()["ok"] is True
    config = seen_configs[0].normalized()
    assert config.output_format == "gif"
    assert config.fps == 12
    assert config.quality == "high"
    assert config.start_frame == 1
    assert config.end_frame == 3
    assert config.target_size == (640, 480)
    assert config.roi == {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4}


@pytest.mark.skipif(
    importlib.util.find_spec("flask") is None,
    reason="Flask is optional; install the app extra to test HTTP routes.",
)
def test_flask_save_recording_saves_webm_directly(tmp_path):
    from solar_toolkit.visualization.image_web_viewer.server import create_app

    client = create_app(allowed_roots=[tmp_path]).test_client()
    response = client.post(
        "/api/save-recording",
        data={
            "recording": (io.BytesIO(b"webm-data"), "recording.webm"),
            "format": "webm",
            "output_dir": str(tmp_path / "videos"),
            "file_prefix": "stage demo",
            "fps": "5",
            "quality": "low",
        },
        content_type="multipart/form-data",
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["format"] == "webm"
    assert Path(payload["path"]).name == "stage_demo_recording.webm"
    assert Path(payload["path"]).read_bytes() == b"webm-data"


@pytest.mark.skipif(
    importlib.util.find_spec("flask") is None,
    reason="Flask is optional; install the app extra to test HTTP routes.",
)
def test_flask_save_recording_transcodes_mp4_and_gif(tmp_path, monkeypatch):
    from solar_toolkit.visualization.image_web_viewer import media
    from solar_toolkit.visualization.image_web_viewer.server import create_app

    transcode_calls: list[dict] = []

    def fake_transcode(
        input_path,
        output_path,
        output_format,
        fps,
        quality,
        recording_size=None,
    ):
        transcode_calls.append(
            {
                "input_suffix": Path(input_path).suffix,
                "output_path": str(output_path),
                "output_format": output_format,
                "fps": fps,
                "quality": quality,
                "recording_size": recording_size,
            }
        )
        Path(output_path).write_bytes(b"converted")
        return True

    monkeypatch.setattr(media, "transcode_recording", fake_transcode)

    client = create_app(allowed_roots=[tmp_path]).test_client()
    for output_format in ["mp4", "gif"]:
        response = client.post(
            "/api/save-recording",
            data={
                "recording": (io.BytesIO(b"webm-data"), "recording.webm"),
                "format": output_format,
                "output_dir": str(tmp_path / "videos"),
                "file_prefix": "stage",
                "fps": "7",
                "quality": "high",
                "recording_width": "641",
                "recording_height": "479",
            },
            content_type="multipart/form-data",
        )
        payload = response.get_json()

        assert response.status_code == 200
        assert payload["ok"] is True
        assert payload["format"] == output_format
        assert Path(payload["path"]).suffix == f".{output_format}"
        assert Path(payload["path"]).read_bytes() == b"converted"

    assert [call["output_format"] for call in transcode_calls] == ["mp4", "gif"]
    assert {call["fps"] for call in transcode_calls} == {7.0}
    assert {call["quality"] for call in transcode_calls} == {"high"}
    assert {call["recording_size"] for call in transcode_calls} == {(641, 479)}


@pytest.mark.skipif(
    importlib.util.find_spec("flask") is None,
    reason="Flask is optional; install the app extra to test HTTP routes.",
)
def test_flask_save_recording_rejects_empty_upload(tmp_path):
    from solar_toolkit.visualization.image_web_viewer.server import create_app

    client = create_app(allowed_roots=[tmp_path]).test_client()
    response = client.post(
        "/api/save-recording",
        data={
            "recording": (io.BytesIO(b""), "recording.webm"),
            "format": "mp4",
            "output_dir": str(tmp_path / "videos"),
            "file_prefix": "stage",
            "fps": "30",
            "quality": "low",
        },
        content_type="multipart/form-data",
    )
    payload = response.get_json()

    assert response.status_code == 400
    assert payload["ok"] is False
    assert "empty" in payload["error"].lower()


def test_recording_transcode_mp4_uses_safe_ffmpeg_filters(tmp_path, monkeypatch):
    from solar_toolkit.visualization.image_web_viewer import media

    commands: list[list[str]] = []

    monkeypatch.setattr(media, "resolve_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(media, "_run_ffmpeg_file", lambda cmd: commands.append(cmd))

    media.transcode_recording(
        tmp_path / "input.webm",
        tmp_path / "output.mp4",
        "mp4",
        fps=30,
        quality="low",
        recording_size=(641, 479),
    )

    command = commands[0]
    filter_index = command.index("-vf") + 1
    filter_expr = command[filter_index]
    assert "fps=30" in filter_expr
    assert "scale=trunc(iw/2)*2:trunc(ih/2)*2" in filter_expr
    assert "format=yuv420p" in filter_expr
    assert "-pix_fmt" in command
    assert "yuv420p" in command


def test_write_media_from_frames_streams_mp4_with_safe_ffmpeg_args(
    tmp_path, monkeypatch
):
    from solar_toolkit.visualization.image_web_viewer import media

    commands: list[list[str]] = []
    consumed_frames: list[tuple[int, int, int]] = []

    def fake_run_ffmpeg_stream(cmd, frame_iter, *, width, height):
        commands.append(cmd)
        consumed_frames.extend(frame.shape for frame, _size in frame_iter)
        assert width == 7
        assert height == 5
        return True

    monkeypatch.setattr(media, "resolve_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(media, "_run_ffmpeg_stream", fake_run_ffmpeg_stream)

    frame = np.zeros((5, 7, 3), dtype=np.uint8)
    ok = media.write_media_from_frames(
        [(frame, (7, 5))],
        tmp_path / "streamed.mp4",
        fps=30,
        quality="high",
        frame_size=(7, 5),
        output_format="mp4",
    )

    assert ok is True
    assert consumed_frames == [(5, 7, 3)]
    command = commands[0]
    assert "-f" in command
    assert "rawvideo" in command
    assert "-pix_fmt" in command
    assert "rgb24" in command
    assert "7x5" in command
    filter_expr = command[command.index("-vf") + 1]
    assert "fps=30" in filter_expr
    assert "scale=trunc(iw/2)*2:trunc(ih/2)*2" in filter_expr
    assert "format=yuv420p" in filter_expr
