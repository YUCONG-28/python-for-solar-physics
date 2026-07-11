"""
Video Generation from Image Sequences for Solar Data Visualization.

This script converts an image sequence into an MP4 video while keeping memory
usage nearly constant. Frames are decoded, normalized, optionally resized, and
streamed directly into FFmpeg as raw RGB data. If FFmpeg is unavailable, imageio
and OpenCV fallbacks also write frames one by one.
"""

import os
import re
import subprocess
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta

import imageio.v2 as imageio
import numpy as np

from solar_toolkit.path_config import load_script_config

try:
    from PIL import Image as PILImage
except ImportError:  # pragma: no cover - depends on local environment
    PILImage = None

try:
    import cv2
except ImportError:  # pragma: no cover - depends on local environment
    cv2 = None


# ============================================================================
# User configuration
# ============================================================================

PATH_CONFIG = load_script_config(
    "image_sequence_to_video",
    {
        "fps": 10,
        "input_dir": r"<PROJECT_ROOT>\2025\20250503\output\AIA_6band_GaussianRadio_Spectrogram",
        "output_dir": r"<PROJECT_ROOT>\2025\20250503\video",
        "video_name": "AIA_spectrogram_overlay.mp4",
    },
)

fps = PATH_CONFIG["fps"]
input_dir = PATH_CONFIG["input_dir"]
output_dir = PATH_CONFIG["output_dir"]
video_name = PATH_CONFIG["video_name"]
target_suffix = ".png"

# "high": crf=18, preset="slow"; "low": crf=28, preset="fast"
video_quality = "low"

# Frame range is based on sorted index, starting from 1.
start_frame = 1
end_frame = None

# "filename" parses timestamps from filenames; "mtime" uses modification time.
sort_by = "filename"

# None = auto-select the dominant sampled size; or force (width, height).
target_size = None

# Threaded prefetch keeps memory bounded by processing only small ordered batches.
prefetch_workers = 8
prefetch_batch_size = 8


# ============================================================================
# Filename timestamp parsing
# ============================================================================


def _dt(year, month, day, hour=0, minute=0, second=0):
    """Construct datetime, return None if parameters are invalid."""
    try:
        return datetime(
            int(year), int(month), int(day), int(hour), int(minute), int(second)
        )
    except (ValueError, TypeError):
        return None


def _dt_doy(year, doy, hour=0, minute=0, second=0):
    """Construct datetime from year + day-of-year, return None if invalid."""
    try:
        base = datetime(int(year), 1, 1)
        dt = base + timedelta(days=int(doy) - 1)
        return dt.replace(hour=int(hour), minute=int(minute), second=int(second))
    except (ValueError, TypeError):
        return None


_TS_PATTERNS = [
    (
        re.compile(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):?(\d{2}):?(\d{2})"),
        lambda g: _dt(*g[:6]),
    ),
    (
        re.compile(r"(\d{4})(\d{2})(\d{2})[_\-T](\d{2})(\d{2})(\d{2})"),
        lambda g: _dt(*g[:6]),
    ),
    (
        re.compile(r"(\d{4})(\d{3})[_\-T](\d{2})(\d{2})(\d{2})"),
        lambda g: _dt_doy(g[0], g[1], g[2], g[3], g[4]),
    ),
    (re.compile(r"(\d{4})(\d{3})(?!\d)"), lambda g: _dt_doy(g[0], g[1])),
    (re.compile(r"(\d{4})(\d{2})(\d{2})(?!\d)"), lambda g: _dt(g[0], g[1], g[2])),
    (
        re.compile(r"(?<!\d)(\d{2})(\d{2})(\d{2})(?!\d)"),
        lambda g: _dt(1970, 1, 1, g[0], g[1], g[2]),
    ),
]


def parse_timestamp(filename: str):
    """
    Extract timestamp from filename, return datetime; returns None if parsing fails.
    For each pattern, take the first valid match in the filename.
    """
    stem = os.path.splitext(filename)[0]
    for pattern, builder in _TS_PATTERNS:
        for match in pattern.finditer(stem):
            dt = builder(match.groups())
            if dt is not None:
                return dt
    return None


# ============================================================================
# Image preprocessing
# ============================================================================


@dataclass
class FrameStats:
    valid_count: int = 0
    skipped_count: int = 0
    resized_count: int = 0


@dataclass
class FrameResult:
    frame: np.ndarray | None
    original_size: tuple[int, int] | None
    resized: bool = False
    path: str = ""
    error: Exception | None = None


def normalize_channels(img: np.ndarray) -> np.ndarray:
    """Convert grayscale/RGB/RGBA/float images to RGB uint8."""
    if img.dtype != np.uint8:
        if np.issubdtype(img.dtype, np.floating):
            max_value = float(np.nanmax(img)) if img.size else 0.0
            scale = 255.0 if max_value <= 1.0 else 1.0
            img = np.nan_to_num(img, nan=0.0, posinf=255.0, neginf=0.0)
            img = np.clip(img * scale, 0, 255).astype(np.uint8)
        else:
            img = np.clip(img, 0, 255).astype(np.uint8)

    if img.ndim == 2:
        img = np.repeat(img[..., None], 3, axis=2)
    elif img.ndim == 3:
        channels = img.shape[2]
        if channels == 1:
            img = np.repeat(img, 3, axis=2)
        elif channels == 4:
            alpha = img[:, :, 3:4].astype(np.float32) / 255.0
            rgb = img[:, :, :3].astype(np.float32)
            img = np.clip(rgb * alpha, 0, 255).astype(np.uint8)
        elif channels > 4:
            img = img[:, :, :3]
    else:
        raise ValueError(f"Unsupported image shape: {img.shape}")

    if img.ndim != 3 or img.shape[2] != 3:
        raise ValueError(f"Cannot convert image to RGB: {img.shape}")
    return np.ascontiguousarray(img, dtype=np.uint8)


def resize_image(img: np.ndarray, tw: int, th: int) -> np.ndarray:
    """Resize image to (tw, th), using Pillow, then OpenCV, then crop/pad."""
    if img.shape[0] == th and img.shape[1] == tw:
        return np.ascontiguousarray(img, dtype=np.uint8)

    if PILImage is not None:
        resized = PILImage.fromarray(img).resize((tw, th), PILImage.LANCZOS)
        return np.ascontiguousarray(np.array(resized), dtype=np.uint8)

    if cv2 is not None:
        resized = cv2.resize(img, (tw, th), interpolation=cv2.INTER_LANCZOS4)
        return np.ascontiguousarray(resized, dtype=np.uint8)

    h, w = img.shape[:2]
    result = np.zeros((th, tw, 3), dtype=np.uint8)
    cy, cx = min(h, th), min(w, tw)
    result[:cy, :cx] = img[:cy, :cx]
    return result


def align_even(n: int) -> int:
    """Align down to an even value required by yuv420p encoders."""
    return n if n % 2 == 0 else max(2, n - 1)


def process_single_frame(
    file_path: str, target_size_tuple: tuple[int, int] | None = None
) -> FrameResult:
    """Read, normalize, and resize one frame."""
    try:
        img = normalize_channels(imageio.imread(file_path))
        h, w = img.shape[:2]
        resized = False
        if target_size_tuple is not None:
            tw, th = target_size_tuple
            if w != tw or h != th:
                img = resize_image(img, tw, th)
                resized = True
        img = np.ascontiguousarray(img, dtype=np.uint8)
        return FrameResult(img, (w, h), resized=resized, path=file_path)
    except Exception as exc:
        return FrameResult(None, None, path=file_path, error=exc)


def iter_processed_frames(
    paths: Sequence[str],
    target_size_tuple: tuple[int, int] | None,
    stats: FrameStats | None = None,
    workers: int = 1,
    batch_size: int = 8,
    missing_frame_policy: str = "skip",
) -> Iterator[tuple[np.ndarray, tuple[int, int]]]:
    """
    Yield processed RGB uint8 frames in path order without retaining all frames.
    Optional threaded prefetch processes only small ordered batches.
    """
    workers = max(1, int(workers))
    batch_size = max(1, int(batch_size))

    last_frame: np.ndarray | None = None

    def handle_result(result: FrameResult):
        nonlocal last_frame
        if result.frame is None:
            if stats is not None:
                stats.skipped_count += 1
            print(f"  Skipped: {os.path.basename(result.path)}  [{result.error}]")
            if missing_frame_policy == "repeat" and target_size_tuple is not None:
                if last_frame is None:
                    width, height = target_size_tuple
                    last_frame = np.zeros((height, width, 3), dtype=np.uint8)
                return last_frame, target_size_tuple
            return None
        if stats is not None:
            stats.valid_count += 1
            if result.resized:
                stats.resized_count += 1
        last_frame = result.frame
        return result.frame, result.original_size

    if workers <= 1:
        for path in paths:
            item = handle_result(process_single_frame(path, target_size_tuple))
            if item is not None:
                yield item
        return

    with ThreadPoolExecutor(max_workers=workers) as executor:
        for start in range(0, len(paths), batch_size):
            batch = paths[start : start + batch_size]
            for result in executor.map(
                lambda p: process_single_frame(p, target_size_tuple), batch
            ):
                item = handle_result(result)
                if item is not None:
                    yield item


def sample_image_sizes(paths: Sequence[str], sample_size: int) -> list[tuple[int, int]]:
    """Read only image dimensions from a small sample."""
    sample_sizes = []
    for path in paths[:sample_size]:
        try:
            img = normalize_channels(imageio.imread(path))
            sample_sizes.append((img.shape[1], img.shape[0]))
        except Exception as exc:
            print(f"  Sample skipped: {os.path.basename(path)}  [{exc}]")
    return sample_sizes


def determine_target_size_for_paths(
    paths: Sequence[str], requested_size: tuple[int, int] | None = None
) -> tuple[int, int, int, int]:
    """Return target width/height and sample statistics."""
    sample_size = min(30, len(paths))
    sample_sizes = sample_image_sizes(paths, sample_size)
    if not sample_sizes:
        raise RuntimeError("Sampling failed, cannot determine target size")

    if requested_size is not None:
        tw, th = align_even(int(requested_size[0])), align_even(int(requested_size[1]))
        native_count = sample_sizes.count((tw, th))
    else:
        (tw, th), native_count = Counter(sample_sizes).most_common(1)[0]
        tw, th = align_even(tw), align_even(th)
    return tw, th, sample_size, native_count


def determine_target_size(paths: Sequence[str]) -> tuple[int, int, int, int]:
    return determine_target_size_for_paths(paths, target_size)


# ============================================================================
# Video writing
# ============================================================================


def get_quality_params(quality: str) -> tuple[int, str, int]:
    """Return ffmpeg CRF, preset, and imageio quality for a quality label."""
    if quality == "high":
        return 18, "slow", 7
    return 28, "fast", 4


def write_video_ffmpeg_stream(
    frame_iter: Iterable[tuple[np.ndarray, tuple[int, int]]],
    output_path: str,
    fps: int,
    width: int,
    height: int,
    quality: str = "high",
) -> bool:
    """Stream raw RGB frames into FFmpeg via stdin."""
    crf, preset, _ = get_quality_params(quality)
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{width}x{height}",
        "-r",
        str(fps),
        "-i",
        "pipe:0",
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-movflags",
        "+faststart",
        output_path,
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            shell=False,
        )
    except FileNotFoundError:
        print("[FFmpeg] ffmpeg executable was not found in PATH")
        return False
    except Exception as exc:
        print(f"[FFmpeg] failed to start: {exc}")
        return False

    stderr_text = ""
    stream_error = False
    try:
        assert proc.stdin is not None
        for frame, _ in frame_iter:
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


def write_video_imageio_stream(
    frame_iter: Iterable[tuple[np.ndarray, tuple[int, int]]],
    output_path: str,
    fps: int,
    quality: str = "high",
) -> bool:
    """Write video with imageio one frame at a time."""
    _, _, imageio_quality = get_quality_params(quality)
    try:
        with imageio.get_writer(
            output_path,
            fps=fps,
            codec="libx264",
            pixelformat="yuv420p",
            quality=imageio_quality,
        ) as writer:
            for frame, _ in frame_iter:
                writer.append_data(frame)
        return True
    except Exception as exc:
        print(f"[imageio] failed: {exc}")
        return False


def write_video_opencv_stream(
    frame_iter: Iterable[tuple[np.ndarray, tuple[int, int]]],
    output_path: str,
    fps: int,
    width: int,
    height: int,
) -> bool:
    """Write video with OpenCV one frame at a time."""
    if cv2 is None:
        print("[OpenCV] cv2 is not available")
        return False

    try:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        if not writer.isOpened():
            print("[OpenCV] cannot open VideoWriter")
            return False
        try:
            for frame, _ in frame_iter:
                writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        finally:
            writer.release()
        return True
    except Exception as exc:
        print(f"[OpenCV] failed: {exc}")
        return False


# ============================================================================
# Main workflow helpers
# ============================================================================


def scan_image_files(folder: str, suffix: str):
    suffix_lower = suffix.lower()
    with os.scandir(folder) as entries:
        return [
            entry
            for entry in entries
            if entry.is_file() and entry.name.lower().endswith(suffix_lower)
        ]


def sort_entries(entries, method: str):
    if method == "filename":
        parsed, failed = [], []
        for entry in entries:
            ts = parse_timestamp(entry.name)
            (parsed if ts is not None else failed).append((ts, entry))
        parsed.sort(key=lambda item: item[0])
        if failed:
            sample = ", ".join(entry.name for _, entry in failed[:3])
            tail = f" ... total {len(failed)}" if len(failed) > 3 else ""
            print(f"  [WARN] Cannot parse timestamp, appended at end: {sample}{tail}")
        if parsed:
            t0 = parsed[0][0].strftime("%Y-%m-%d %H:%M:%S")
            t1 = parsed[-1][0].strftime("%Y-%m-%d %H:%M:%S")
            print(f"  Time range: {t0} -> {t1}")
        return [entry for _, entry in parsed] + [entry for _, entry in failed]

    if method == "mtime":
        return sorted(entries, key=lambda entry: entry.stat().st_mtime)

    raise ValueError("sort_by must be 'filename' or 'mtime'")


def select_frame_range(entries):
    total = len(entries)
    start = max(1, min(int(start_frame), total))
    end = total if end_frame is None else max(start, min(int(end_frame), total))
    return entries[start - 1 : end], start, end


def make_frame_iter_from_paths(
    paths: Sequence[str],
    stats: FrameStats,
    size: tuple[int, int],
    workers: int = 1,
    batch_size: int = 8,
    missing_frame_policy: str = "skip",
):
    return iter_processed_frames(
        paths,
        size,
        stats=stats,
        workers=workers,
        batch_size=batch_size,
        missing_frame_policy=missing_frame_policy,
    )


def make_frame_iter(paths: Sequence[str], stats: FrameStats, size: tuple[int, int]):
    return make_frame_iter_from_paths(
        paths,
        stats,
        size,
        workers=prefetch_workers,
        batch_size=prefetch_batch_size,
    )


def write_video_from_paths(
    paths: Sequence[str],
    output_path: str,
    fps: int,
    quality: str = "high",
    target_size_tuple: tuple[int, int] | None = None,
    workers: int = 8,
    batch_size: int = 8,
) -> bool:
    selected_paths = list(paths)
    if not selected_paths:
        print("No frames selected")
        return False
    if quality not in ("high", "low"):
        print(f"[WARN] Invalid video quality '{quality}', using 'high'")
        quality = "high"
    output_folder = os.path.dirname(output_path)
    if output_folder:
        os.makedirs(output_folder, exist_ok=True)

    tw, th, _sample_size, _native_count = determine_target_size_for_paths(
        selected_paths, requested_size=target_size_tuple
    )
    stats = FrameStats()
    frame_iter = make_frame_iter_from_paths(
        selected_paths,
        stats,
        (tw, th),
        workers=workers,
        batch_size=batch_size,
    )
    ok = write_video_ffmpeg_stream(frame_iter, output_path, fps, tw, th, quality)
    if ok:
        return True

    print("[INFO] Falling back to imageio streaming writer")
    stats = FrameStats()
    frame_iter = make_frame_iter_from_paths(
        selected_paths,
        stats,
        (tw, th),
        workers=workers,
        batch_size=batch_size,
    )
    ok = write_video_imageio_stream(frame_iter, output_path, fps, quality)
    if ok:
        return True

    print("[INFO] Falling back to OpenCV streaming writer")
    stats = FrameStats()
    frame_iter = make_frame_iter_from_paths(
        selected_paths,
        stats,
        (tw, th),
        workers=workers,
        batch_size=batch_size,
    )
    return write_video_opencv_stream(frame_iter, output_path, fps, tw, th)


def main():
    global video_quality

    if not os.path.isdir(input_dir):
        raise FileNotFoundError(f"Input folder does not exist: {input_dir}")
    os.makedirs(output_dir, exist_ok=True)

    if video_quality not in ("high", "low"):
        print(f"[WARN] Invalid video_quality '{video_quality}', using 'high'")
        video_quality = "high"

    all_entries = scan_image_files(input_dir, target_suffix)
    if not all_entries:
        print(f"No {target_suffix} files found: {input_dir}")
        return

    sorted_entries = sort_entries(all_entries, sort_by)
    selected_entries, range_start, range_end = select_frame_range(sorted_entries)
    selected_paths = [entry.path for entry in selected_entries]
    if not selected_paths:
        print("No frames selected")
        return

    tw, th, sample_size, native_count = determine_target_size(selected_paths)
    output_path = os.path.join(output_dir, video_name)
    crf, preset, _ = get_quality_params(video_quality)

    print("Video generation settings")
    print(f"  Scanned files: {len(all_entries)}")
    print(f"  Frames selected: {len(selected_paths)} ({range_start} ~ {range_end})")
    print(f"  Sorting method: {sort_by}")
    print(f"  Sampled frames: {sample_size}")
    print(f"  Target size: {tw}x{th} ({native_count} sampled frames native)")
    print(f"  Quality: {video_quality} (crf={crf}, preset={preset})")
    print("  Streaming FFmpeg: yes")
    print(f"  Prefetch workers: {prefetch_workers}, batch size: {prefetch_batch_size}")

    stats = FrameStats()
    frame_iter = make_frame_iter(selected_paths, stats, (tw, th))
    ok = write_video_ffmpeg_stream(frame_iter, output_path, fps, tw, th, video_quality)
    backend = "FFmpeg raw stream"

    if not ok:
        print("[INFO] Falling back to imageio streaming writer")
        stats = FrameStats()
        frame_iter = make_frame_iter(selected_paths, stats, (tw, th))
        ok = write_video_imageio_stream(frame_iter, output_path, fps, video_quality)
        backend = "imageio stream"

    if not ok:
        print("[INFO] Falling back to OpenCV streaming writer")
        stats = FrameStats()
        frame_iter = make_frame_iter(selected_paths, stats, (tw, th))
        ok = write_video_opencv_stream(frame_iter, output_path, fps, tw, th)
        backend = "OpenCV stream"

    if not ok:
        print("[ERROR] All video writers failed")
        print("        Install FFmpeg and make sure it is available in PATH.")
        return

    print("Video generation completed")
    print(f"  Backend: {backend}")
    print(f"  Successful frames: {stats.valid_count}")
    print(f"  Skipped frames: {stats.skipped_count}")
    print(f"  Resized frames: {stats.resized_count}")
    print(f"  Output: {output_path}")


if __name__ == "__main__":
    main()
