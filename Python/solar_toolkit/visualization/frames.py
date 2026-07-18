"""Image-frame decoding and streaming helpers.

This module owns reusable image-sequence preparation for library and Apps
workflows. Optional image backends are imported only when a frame is read or
encoded.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import numpy as np

Frame = tuple[np.ndarray, tuple[int, int]]

__all__ = [
    "Frame",
    "FrameResult",
    "FrameStats",
    "align_even",
    "determine_target_size_for_paths",
    "iter_processed_frames",
    "make_frame_iter_from_paths",
    "normalize_channels",
    "process_single_frame",
    "resize_image",
    "sample_image_sizes",
    "write_video_imageio_stream",
    "write_video_opencv_stream",
]


@dataclass
class FrameStats:
    """Counters collected while decoding an image sequence."""

    valid_count: int = 0
    skipped_count: int = 0
    resized_count: int = 0


@dataclass
class FrameResult:
    """Result of decoding and normalizing one image frame."""

    frame: np.ndarray | None
    original_size: tuple[int, int] | None
    resized: bool = False
    path: str = ""
    error: Exception | None = None


def normalize_channels(image: np.ndarray) -> np.ndarray:
    """Convert grayscale, RGB, RGBA, or numeric image data to RGB uint8."""

    image = np.asarray(image)
    if image.dtype != np.uint8:
        if np.issubdtype(image.dtype, np.floating):
            max_value = float(np.nanmax(image)) if image.size else 0.0
            scale = 255.0 if max_value <= 1.0 else 1.0
            image = np.nan_to_num(image, nan=0.0, posinf=255.0, neginf=0.0)
            image = np.clip(image * scale, 0, 255).astype(np.uint8)
        else:
            image = np.clip(image, 0, 255).astype(np.uint8)

    if image.ndim == 2:
        image = np.repeat(image[..., None], 3, axis=2)
    elif image.ndim == 3:
        channels = image.shape[2]
        if channels == 1:
            image = np.repeat(image, 3, axis=2)
        elif channels == 4:
            alpha = image[:, :, 3:4].astype(np.float32) / 255.0
            rgb = image[:, :, :3].astype(np.float32)
            image = np.clip(rgb * alpha, 0, 255).astype(np.uint8)
        elif channels > 4:
            image = image[:, :, :3]
    else:
        raise ValueError(f"Unsupported image shape: {image.shape}")

    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError(f"Cannot convert image to RGB: {image.shape}")
    return np.ascontiguousarray(image, dtype=np.uint8)


def resize_image(image: np.ndarray, width: int, height: int) -> np.ndarray:
    """Resize an RGB image using Pillow, OpenCV, or deterministic crop/pad."""

    if image.shape[:2] == (height, width):
        return np.ascontiguousarray(image, dtype=np.uint8)

    try:
        from PIL import Image

        resized = Image.fromarray(image).resize((width, height), Image.LANCZOS)
        return np.ascontiguousarray(np.array(resized), dtype=np.uint8)
    except ImportError:
        pass

    try:
        import cv2

        resized = cv2.resize(image, (width, height), interpolation=cv2.INTER_LANCZOS4)
        return np.ascontiguousarray(resized, dtype=np.uint8)
    except ImportError:
        pass

    source_height, source_width = image.shape[:2]
    result = np.zeros((height, width, 3), dtype=np.uint8)
    copy_height = min(source_height, height)
    copy_width = min(source_width, width)
    result[:copy_height, :copy_width] = image[:copy_height, :copy_width]
    return result


def align_even(value: int) -> int:
    """Align a dimension down to the nearest positive codec-safe even value."""

    value = int(value)
    return value if value % 2 == 0 else max(2, value - 1)


def process_single_frame(
    file_path: str, target_size: tuple[int, int] | None = None
) -> FrameResult:
    """Read, normalize, and optionally resize one image frame."""

    try:
        import imageio.v2 as imageio

        image = normalize_channels(imageio.imread(file_path))
        height, width = image.shape[:2]
        resized = False
        if target_size is not None and (width, height) != target_size:
            image = resize_image(image, *target_size)
            resized = True
        return FrameResult(
            np.ascontiguousarray(image, dtype=np.uint8),
            (width, height),
            resized=resized,
            path=file_path,
        )
    except Exception as exc:  # one damaged frame must not abort an export
        return FrameResult(None, None, path=file_path, error=exc)


def iter_processed_frames(
    paths: Sequence[str],
    target_size: tuple[int, int] | None,
    stats: FrameStats | None = None,
    workers: int = 1,
    batch_size: int = 8,
    missing_frame_policy: str = "skip",
    *,
    _processor=None,
) -> Iterator[Frame]:
    """Yield processed frames in input order with bounded parallel prefetch."""

    workers = max(1, int(workers))
    batch_size = max(1, int(batch_size))
    processor = _processor or process_single_frame
    last_frame: np.ndarray | None = None

    def handle(result: FrameResult) -> Frame | None:
        nonlocal last_frame
        if result.frame is None:
            if stats is not None:
                stats.skipped_count += 1
            if missing_frame_policy == "repeat" and target_size is not None:
                if last_frame is None:
                    width, height = target_size
                    last_frame = np.zeros((height, width, 3), dtype=np.uint8)
                return last_frame, target_size
            return None
        if stats is not None:
            stats.valid_count += 1
            stats.resized_count += int(result.resized)
        last_frame = result.frame
        return result.frame, result.original_size or target_size or (0, 0)

    if workers <= 1:
        for path in paths:
            item = handle(processor(path, target_size))
            if item is not None:
                yield item
        return

    with ThreadPoolExecutor(max_workers=workers) as executor:
        for start in range(0, len(paths), batch_size):
            batch = paths[start : start + batch_size]
            for result in executor.map(
                lambda path: processor(path, target_size), batch
            ):
                item = handle(result)
                if item is not None:
                    yield item


def sample_image_sizes(paths: Sequence[str], sample_size: int) -> list[tuple[int, int]]:
    """Read dimensions from a bounded prefix of an image sequence."""

    sizes: list[tuple[int, int]] = []
    for path in paths[:sample_size]:
        result = process_single_frame(path)
        if result.original_size is not None:
            sizes.append(result.original_size)
    return sizes


def determine_target_size_for_paths(
    paths: Sequence[str], requested_size: tuple[int, int] | None = None
) -> tuple[int, int, int, int]:
    """Return target width/height and the sampling statistics used."""

    sample_size = min(30, len(paths))
    sample_sizes = sample_image_sizes(paths, sample_size)
    if not sample_sizes:
        raise RuntimeError("Sampling failed, cannot determine target size")
    if requested_size is not None:
        width, height = map(align_even, requested_size)
        native_count = sample_sizes.count((width, height))
    else:
        (width, height), native_count = Counter(sample_sizes).most_common(1)[0]
        width, height = align_even(width), align_even(height)
    return width, height, sample_size, native_count


def make_frame_iter_from_paths(
    paths: Sequence[str],
    stats: FrameStats,
    size: tuple[int, int],
    workers: int = 1,
    batch_size: int = 8,
    missing_frame_policy: str = "skip",
) -> Iterator[Frame]:
    """Build the ordered frame iterator used by video writers."""

    return iter_processed_frames(
        paths,
        size,
        stats=stats,
        workers=workers,
        batch_size=batch_size,
        missing_frame_policy=missing_frame_policy,
    )


def _imageio_quality(quality: str) -> int:
    return 7 if quality == "high" else 4


def write_video_imageio_stream(
    frame_iter: Iterable[Frame], output_path: str, fps: float, quality: str = "high"
) -> bool:
    """Write MP4 video through imageio one frame at a time."""

    try:
        import imageio.v2 as imageio

        with imageio.get_writer(
            output_path,
            fps=fps,
            codec="libx264",
            pixelformat="yuv420p",
            quality=_imageio_quality(quality),
        ) as writer:
            for frame, _ in frame_iter:
                writer.append_data(frame)
        return True
    except Exception:
        return False


def write_video_opencv_stream(
    frame_iter: Iterable[Frame],
    output_path: str,
    fps: float,
    width: int,
    height: int,
) -> bool:
    """Write MP4 video through OpenCV one frame at a time."""

    try:
        import cv2
    except ImportError:
        return False
    try:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        if not writer.isOpened():
            return False
        try:
            for frame, _ in frame_iter:
                writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        finally:
            writer.release()
        return True
    except Exception:
        return False
