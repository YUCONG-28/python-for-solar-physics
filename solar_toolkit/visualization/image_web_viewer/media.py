"""Media-format helpers for the local image web viewer."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

SUPPORTED_OUTPUT_FORMATS = {"mp4", "gif", "webm"}
CONDA_FFMPEG = Path(r"D:\miniforge3\envs\solarphysics_env\Library\bin\ffmpeg.exe")


def normalize_output_format(value: str | None) -> str:
    """Normalize a user-facing media format label."""

    output_format = str(value or "mp4").strip().lower().lstrip(".")
    return output_format if output_format in SUPPORTED_OUTPUT_FORMATS else "mp4"


def sanitize_filename(value: str) -> str:
    """Return a filesystem-safe filename stem."""

    text = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value).strip())
    return text.strip("._") or "image_viewer"


def resolve_ffmpeg() -> str | None:
    """Resolve FFmpeg from PATH or the project Miniforge environment."""

    configured = os.getenv("IMAGE_VIEWER_FFMPEG", "").strip()
    if configured:
        configured_path = Path(configured).expanduser()
        if configured_path.exists():
            return str(configured_path)

    discovered = shutil.which("ffmpeg")
    if discovered:
        return discovered

    if CONDA_FFMPEG.exists():
        return str(CONDA_FFMPEG)
    return None


def write_media_from_paths(
    paths: Sequence[str],
    output_path: str | Path,
    fps: int,
    quality: str = "high",
    target_size_tuple: tuple[int, int] | None = None,
    workers: int = 8,
    batch_size: int = 8,
    output_format: str = "mp4",
) -> bool:
    """Write an image sequence to MP4, GIF, or WebM."""

    selected_paths = list(paths)
    if not selected_paths:
        return False

    output_format = normalize_output_format(output_format)
    if output_format == "mp4":
        from scripts.tools.image_sequence_to_video import write_video_from_paths

        return write_video_from_paths(
            selected_paths,
            str(output_path),
            int(fps),
            quality=quality,
            target_size_tuple=target_size_tuple,
            workers=workers,
            batch_size=batch_size,
        )

    from scripts.tools.image_sequence_to_video import (
        FrameStats,
        determine_target_size_for_paths,
        make_frame_iter_from_paths,
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    width, height, _sample_size, _native_count = determine_target_size_for_paths(
        selected_paths,
        requested_size=target_size_tuple,
    )
    stats = FrameStats()
    frame_iter = make_frame_iter_from_paths(
        selected_paths,
        stats,
        (width, height),
        workers=workers,
        batch_size=batch_size,
    )
    ok = write_frames_ffmpeg_stream(
        frame_iter,
        output_path,
        fps=int(fps),
        width=width,
        height=height,
        output_format=output_format,
        quality=quality,
    )
    if ok:
        return True

    if output_format == "gif":
        stats = FrameStats()
        frame_iter = make_frame_iter_from_paths(
            selected_paths,
            stats,
            (width, height),
            workers=workers,
            batch_size=batch_size,
        )
        return write_gif_imageio_stream(frame_iter, output_path, fps=int(fps))

    return False


def write_media_from_frames(
    frame_iter: Iterable[tuple[np.ndarray, tuple[int, int]]],
    output_path: str | Path,
    fps: int,
    quality: str = "high",
    *,
    frame_size: tuple[int, int],
    output_format: str = "mp4",
) -> bool:
    """Write already-rendered RGB frames to MP4, GIF, or WebM."""

    output_format = normalize_output_format(output_format)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    width, height = int(frame_size[0]), int(frame_size[1])
    if width <= 0 or height <= 0:
        return False

    ok = write_frames_ffmpeg_stream(
        frame_iter,
        output_path,
        fps=int(fps),
        width=width,
        height=height,
        output_format=output_format,
        quality=quality,
    )
    if ok:
        return True

    if output_format == "gif":
        return write_gif_imageio_stream(frame_iter, output_path, fps=int(fps))
    return False


def write_frames_ffmpeg_stream(
    frame_iter: Iterable[tuple[np.ndarray, tuple[int, int]]],
    output_path: str | Path,
    *,
    fps: int,
    width: int,
    height: int,
    output_format: str,
    quality: str,
) -> bool:
    """Stream RGB frames into FFmpeg for GIF or WebM output."""

    ffmpeg = resolve_ffmpeg()
    if not ffmpeg:
        return False

    output_format = normalize_output_format(output_format)
    fps = max(1, int(fps))
    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{int(width)}x{int(height)}",
        "-r",
        str(fps),
        "-i",
        "pipe:0",
        "-an",
    ]
    cmd.extend(_ffmpeg_output_args(output_format, quality, fps, ffmpeg=ffmpeg))
    cmd.append(str(output_path))
    return _run_ffmpeg_stream(cmd, frame_iter, width=int(width), height=int(height))


def write_gif_imageio_stream(
    frame_iter: Iterable[tuple[np.ndarray, tuple[int, int]]],
    output_path: str | Path,
    *,
    fps: int,
) -> bool:
    """Fallback GIF writer when FFmpeg is unavailable."""

    import imageio.v2 as imageio

    try:
        with imageio.get_writer(
            str(output_path), mode="I", duration=1 / max(1, fps)
        ) as writer:
            for frame, _original_size in frame_iter:
                writer.append_data(frame)
        return True
    except Exception as exc:
        print(f"[imageio] GIF write failed: {exc}")
        return False


def save_browser_recording(
    recording_file: Any,
    *,
    output_dir: str | Path,
    file_prefix: str,
    output_format: str,
    fps: float,
    quality: str,
    recording_size: tuple[int, int] | None = None,
) -> dict[str, Any]:
    """Save or transcode a WebM browser recording uploaded by the frontend."""

    output_format = normalize_output_format(output_format)
    output_root = Path(output_dir).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    output_path = (
        output_root / f"{sanitize_filename(file_prefix)}_recording.{output_format}"
    )

    if output_format == "webm":
        recording_file.save(output_path)
        _raise_if_empty(output_path)
        return {"status": "saved", "path": str(output_path), "format": output_format}

    with tempfile.NamedTemporaryFile(
        suffix=".webm",
        prefix="image_viewer_recording_",
        dir=output_root,
        delete=False,
    ) as temp_file:
        temp_path = Path(temp_file.name)
    try:
        recording_file.save(temp_path)
        _raise_if_empty(temp_path)
        transcode_recording(
            temp_path,
            output_path,
            output_format,
            fps=max(0.2, float(fps or 5.0)),
            quality=quality,
            recording_size=recording_size,
        )
        _raise_if_empty(output_path)
        return {"status": "saved", "path": str(output_path), "format": output_format}
    finally:
        temp_path.unlink(missing_ok=True)


def transcode_recording(
    input_path: str | Path,
    output_path: str | Path,
    output_format: str,
    fps: float,
    quality: str,
    recording_size: tuple[int, int] | None = None,
) -> bool:
    """Transcode a browser WebM recording to MP4 or GIF."""

    ffmpeg = resolve_ffmpeg()
    if not ffmpeg:
        raise RuntimeError(
            "FFmpeg is required to save browser recordings as MP4 or GIF."
        )

    output_format = normalize_output_format(output_format)
    if output_format == "webm":
        shutil.copyfile(input_path, output_path)
        return True

    fps_int = max(1, int(round(float(fps or 5.0))))
    cmd = [ffmpeg, "-y", "-i", str(input_path), "-an"]
    cmd.extend(
        _ffmpeg_output_args(
            output_format,
            quality,
            fps_int,
            ffmpeg=ffmpeg,
            recording_size=recording_size,
        )
    )
    cmd.append(str(output_path))
    _run_ffmpeg_file(cmd)
    return True


def _ffmpeg_output_args(
    output_format: str,
    quality: str,
    fps: int,
    *,
    ffmpeg: str | None = None,
    recording_size: tuple[int, int] | None = None,
) -> list[str]:
    output_format = normalize_output_format(output_format)
    quality = "high" if quality == "high" else "low"
    if output_format == "webm":
        crf = "28" if quality == "high" else "38"
        encoder = _webm_encoder(ffmpeg) if ffmpeg else "libvpx-vp9"
        return [
            "-c:v",
            encoder,
            "-pix_fmt",
            "yuv420p",
            "-crf",
            crf,
            "-b:v",
            "0",
        ]
    if output_format == "gif":
        return [
            "-vf",
            (
                f"fps={max(1, int(fps))},"
                "split[s0][s1];[s0]palettegen[p];"
                "[s1][p]paletteuse=dither=bayer"
            ),
        ]

    crf = "18" if quality == "high" else "28"
    preset = "slow" if quality == "high" else "fast"
    filter_expr = ",".join(
        [
            f"fps={max(1, int(fps))}",
            "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "format=yuv420p",
        ]
    )
    return [
        "-vf",
        filter_expr,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        preset,
        "-crf",
        crf,
        "-movflags",
        "+faststart",
    ]


def _webm_encoder(ffmpeg: str | None) -> str:
    """Prefer VP9, but use AV1 when this FFmpeg build lacks libvpx."""

    if not ffmpeg:
        return "libvpx-vp9"
    try:
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
    except Exception:
        return "libvpx-vp9"
    encoders = result.stdout or ""
    if "libvpx-vp9" in encoders:
        return "libvpx-vp9"
    if "libaom-av1" in encoders:
        return "libaom-av1"
    return "libvpx-vp9"


def _run_ffmpeg_stream(
    cmd: list[str],
    frame_iter: Iterable[tuple[np.ndarray, tuple[int, int]]],
    *,
    width: int,
    height: int,
) -> bool:
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            shell=False,
        )
    except Exception as exc:
        print(f"[FFmpeg] failed to start: {exc}")
        return False

    stream_error = False
    stderr_text = ""
    try:
        assert proc.stdin is not None
        for frame, _original_size in frame_iter:
            if frame.shape != (height, width, 3):
                raise ValueError(
                    f"Frame shape {frame.shape} does not match {(height, width, 3)}"
                )
            if frame.dtype != np.uint8:
                raise TypeError(f"Frame dtype must be uint8, got {frame.dtype}")
            proc.stdin.write(np.ascontiguousarray(frame).tobytes())
    except (BrokenPipeError, OSError, ValueError, TypeError) as exc:
        stream_error = True
        print(f"[FFmpeg] streaming failed: {exc}")
    finally:
        if proc.stdin is not None:
            try:
                proc.stdin.close()
            except OSError:
                pass
            proc.stdin = None

    if proc.stderr is not None:
        stderr_text = proc.stderr.read().decode("utf-8", errors="replace")
    return_code = proc.wait()
    if return_code == 0 and not stream_error:
        return True

    print(f"[FFmpeg] failed with return code {return_code}")
    if stderr_text:
        print(stderr_text[-1000:])
    return False


def _run_ffmpeg_file(cmd: list[str]) -> None:
    result = subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = _compact_ffmpeg_stderr(result.stderr)
        raise RuntimeError(
            f"FFmpeg failed while saving recording. Diagnostics: {stderr}"
        )


def _compact_ffmpeg_stderr(stderr: str | None) -> str:
    if not stderr:
        return "no FFmpeg stderr"
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    compact = "\n".join(lines[-12:])
    return compact[-1200:] if compact else "no FFmpeg stderr"


def _raise_if_empty(path: Path) -> None:
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"Recording output is empty: {path}")
