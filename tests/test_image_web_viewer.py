from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
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
        {"name": "left", "folder": str(left), "files": [left / "frame0.png", left / "frame1.png"]},
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
    groups = [{"name": "source", "folder": str(source), "files": sorted(source.glob("*.png"))}]
    calls: list[dict] = []

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

    monkeypatch.setattr(export_mod, "_write_video_from_paths", fake_writer)

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
    assert len(calls) == 2
    assert calls[0]["fps"] == 7
    assert calls[0]["target_size_tuple"] == (12, 8)
    assert Path(composite["path"]).name == "demo_composite.mp4"


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
        lambda groups, config: {"status": "saved", "path": str(config.output_dir / "demo.mp4")},
    )
    monkeypatch.setattr(
        export_mod,
        "export_separate_videos",
        lambda groups, config: {"status": "saved", "paths": [str(config.output_dir / "single.mp4")]},
    )

    client = create_app(allowed_roots=[tmp_path]).test_client()
    health = client.get("/api/health")
    loaded = client.post("/api/load", json={"folders": [str(folder)], "recursive": False})
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
