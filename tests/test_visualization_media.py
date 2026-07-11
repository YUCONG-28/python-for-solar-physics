from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from solar_toolkit.visualization import media
from solar_toolkit.visualization.media_assets import read_asset_bytes, read_asset_text


def test_image_viewer_media_import_is_shared_module():
    legacy = importlib.import_module(
        "solar_toolkit.visualization.image_web_viewer.media"
    )

    assert legacy is media


def test_shared_media_normalizes_formats_and_codec_safe_sizes():
    assert media.normalize_output_format(".WEBM") == "webm"
    assert media.normalize_output_format("unknown") == "mp4"
    assert media.normalize_even_size((641, 479)) == (640, 478)
    assert media.normalize_even_size((1, 1)) == (2, 2)


def test_shared_browser_media_assets_are_bundled_with_license():
    mediabunny = read_asset_bytes("mediabunny-1.50.8.cjs")
    helper = read_asset_text("browser_media.js")
    license_text = read_asset_text("mediabunny-MPL-2.0.txt")

    assert len(mediabunny) > 1_000_000
    assert "createCanvasRecorder" in helper
    assert "CanvasSource" in helper
    assert "normalizeQuality" in helper
    assert "output.addVideoTrack(videoSource, {frameRate})" in helper
    assert "framerate: frameRate" in helper
    assert "timestamp" in helper
    assert "duration" in helper
    assert "Mozilla Public License Version 2.0" in license_text


def test_shared_frame_writer_preserves_fractional_fps(tmp_path, monkeypatch):
    commands: list[list[str]] = []
    frame = np.zeros((4, 6, 3), dtype=np.uint8)

    def fake_run(command, frame_iter, *, width, height):
        assert width == 6
        assert height == 4
        assert len(list(frame_iter)) == 2
        commands.append(command)
        Path(command[-1]).write_bytes(b"encoded")
        return True

    monkeypatch.setattr(media, "resolve_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(media, "resolve_ffprobe", lambda: "ffprobe")
    monkeypatch.setattr(media, "_run_ffmpeg_stream", fake_run)
    monkeypatch.setattr(
        media,
        "probe_video",
        lambda *args, **kwargs: {
            "codec": "h264",
            "width": 6,
            "height": 4,
            "frame_count": 2,
            "duration": 2 / 29.97,
        },
    )

    assert media.write_media_from_frames(
        lambda: iter([(frame, (6, 4)), (frame, (6, 4))]),
        tmp_path / "fractional.mp4",
        fps=29.97,
        quality="high",
        frame_size=(6, 4),
        output_format="mp4",
    )
    command = commands[0]
    assert command[command.index("-r") + 1] == "29.97"
    assert "fps=29.97" in command[command.index("-vf") + 1]


def test_probe_video_uses_constant_frame_rate_for_last_frame_duration(
    tmp_path, monkeypatch
):
    path = tmp_path / "short.webm"
    path.write_bytes(b"valid-media-placeholder")
    payload = {
        "streams": [
            {
                "codec_name": "vp9",
                "width": 640,
                "height": 480,
                "nb_read_packets": "3",
                "duration": None,
                "avg_frame_rate": "5/1",
                "r_frame_rate": "5/1",
            }
        ],
        "format": {"duration": "0.400000"},
    }
    monkeypatch.setattr(media, "resolve_ffprobe", lambda: "ffprobe")
    monkeypatch.setattr(
        media.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        ),
    )

    metadata = media.probe_video(path, expected_frame_count=3)

    assert metadata["frame_rate"] == 5.0
    assert metadata["duration"] == 0.6


@pytest.mark.parametrize(
    ("output_format", "expected_codecs"),
    [
        ("mp4", {"h264"}),
        ("webm", {"vp8", "vp9", "av1"}),
        ("gif", {"gif"}),
    ],
)
def test_real_ffmpeg_stream_writes_expected_frame_count(
    tmp_path, output_format, expected_codecs
):
    if not media.resolve_ffmpeg() or not media.resolve_ffprobe():
        pytest.skip("FFmpeg and FFprobe are required")

    def frame_factory():
        for index in range(6):
            frame = np.zeros((48, 64, 3), dtype=np.uint8)
            frame[:, :, index % 3] = 40 + index * 30
            yield frame, (64, 48)

    output_path = tmp_path / f"probe.{output_format}"
    assert media.write_media_from_frames(
        frame_factory,
        output_path,
        fps=30,
        quality="low",
        frame_size=(64, 48),
        output_format=output_format,
    )

    metadata = media.probe_video(
        output_path,
        expected_size=(64, 48),
        expected_frame_count=6,
    )
    assert metadata["codec"] in expected_codecs
    assert metadata["frame_count"] == 6
    assert metadata["duration"] == pytest.approx(6 / 30, abs=1 / 30)


def test_write_media_from_frames_recreates_factory_for_gif_fallback(
    tmp_path, monkeypatch
):
    factory_calls: list[int] = []
    fallback_frames: list[int] = []

    def frame_factory():
        factory_calls.append(len(factory_calls) + 1)
        for value in range(3):
            frame = np.full((4, 6, 3), value, dtype=np.uint8)
            yield frame, (6, 4)

    def fake_ffmpeg(frame_iter, *args, **kwargs):
        next(iter(frame_iter))
        return False

    def fake_gif(frame_iter, output_path, *, fps):
        fallback_frames.extend(int(frame[0, 0, 0]) for frame, _size in frame_iter)
        Path(output_path).write_bytes(b"gif")
        return True

    monkeypatch.setattr(media, "write_frames_ffmpeg_stream", fake_ffmpeg)
    monkeypatch.setattr(media, "write_gif_imageio_stream", fake_gif)

    assert media.write_media_from_frames(
        frame_factory,
        tmp_path / "fallback.gif",
        fps=10,
        quality="low",
        frame_size=(6, 4),
        output_format="gif",
    )
    assert factory_calls == [1, 2]
    assert fallback_frames == [0, 1, 2]


def test_webm_encoder_prefers_svtav1_before_libaom(monkeypatch):
    clear_cache = getattr(media._webm_encoder, "cache_clear", None)
    if clear_cache:
        clear_cache()
    monkeypatch.setattr(
        media.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            0,
            stdout=" V..... libsvtav1\n V..... libaom-av1\n",
            stderr="",
        ),
    )

    assert media._webm_encoder("ffmpeg") == "libsvtav1"


def test_probe_video_rejects_nonempty_invalid_media(tmp_path):
    if not media.resolve_ffprobe():
        pytest.skip("FFprobe is not available")
    path = tmp_path / "invalid.webm"
    path.write_bytes(b"not-a-webm-stream")

    with pytest.raises(RuntimeError, match="decodable video"):
        media.probe_video(path)
