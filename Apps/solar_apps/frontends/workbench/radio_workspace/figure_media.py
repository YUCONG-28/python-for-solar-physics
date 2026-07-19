"""Bounded media validation helpers for Figure Studio persistence."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO

MAX_FIGURE_LAYERS = 32
MAX_FIGURE_DIMENSION = 8192
MAX_FIGURE_PIXELS = 40_000_000
MAX_PNG_BYTES = 25 * 1024 * 1024
MAX_ANIMATION_BYTES = 512 * 1024 * 1024
MAX_ANIMATION_FRAMES = 10_000

_MIME_SUFFIX = {
    "image/png": ".png",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
}


class FigureMediaTooLarge(ValueError):
    """Raised when a Figure Studio upload exceeds its byte limit."""


def canonical_suffix(mime_type: str) -> str:
    """Return the only persisted suffix accepted for a figure MIME type."""

    normalized = str(mime_type).strip().casefold()
    try:
        return _MIME_SUFFIX[normalized]
    except KeyError as exc:
        raise ValueError(f"Unsupported figure MIME type: {mime_type}") from exc


def max_bytes_for_mime(mime_type: str) -> int:
    return (
        MAX_PNG_BYTES if canonical_suffix(mime_type) == ".png" else MAX_ANIMATION_BYTES
    )


def copy_limited_stream(source: BinaryIO, destination: Path, *, limit: int) -> int:
    """Copy one upload without buffering it all and reject bytes beyond ``limit``."""

    total = 0
    with destination.open("xb") as handle:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                raise FigureMediaTooLarge(
                    f"Uploaded figure exceeds the {limit}-byte limit"
                )
            handle.write(chunk)
    if total == 0:
        raise ValueError("Uploaded figure file is empty")
    return total


def validate_media_magic(path: Path, mime_type: str) -> None:
    """Validate a minimal, unambiguous signature before any parser sees the file."""

    normalized = str(mime_type).strip().casefold()
    with path.open("rb") as handle:
        header = handle.read(16)
    if normalized == "image/png":
        valid = header.startswith(b"\x89PNG\r\n\x1a\n")
    elif normalized == "video/mp4":
        valid = len(header) >= 12 and header[4:8] == b"ftyp"
    elif normalized == "video/webm":
        valid = header.startswith(b"\x1a\x45\xdf\xa3")
    else:
        canonical_suffix(normalized)
        valid = False
    if not valid:
        raise ValueError(f"Uploaded bytes do not match {normalized}")


def validate_dimensions(width: int, height: int) -> tuple[int, int]:
    width = int(width)
    height = int(height)
    if width <= 0 or height <= 0:
        raise ValueError("Figure width and height must be positive")
    if width > MAX_FIGURE_DIMENSION or height > MAX_FIGURE_DIMENSION:
        raise ValueError(
            f"Figure dimensions may not exceed {MAX_FIGURE_DIMENSION} pixels"
        )
    if width * height > MAX_FIGURE_PIXELS:
        raise ValueError(f"Figure area may not exceed {MAX_FIGURE_PIXELS} pixels")
    return width, height


def validate_png(path: Path) -> tuple[int, int]:
    """Decode just enough PNG data with Pillow to prove type and dimensions."""

    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:  # pragma: no cover - installation smoke covers this
        raise RuntimeError(
            "Pillow is required for Figure Studio PNG validation"
        ) from exc

    try:
        with Image.open(path) as image:
            if image.format != "PNG":
                raise ValueError("Figure image must decode as PNG")
            _require_single_frame(image)
            width, height = validate_dimensions(*image.size)
            image.verify()
    except UnidentifiedImageError as exc:
        raise ValueError("Figure image is not a valid PNG") from exc
    return width, height


def validate_raster_image(path: Path, mime_type: str) -> tuple[int, int]:
    """Verify a controlled artifact is a supported, non-vector raster image."""

    expected_formats = {
        "image/png": "PNG",
        "image/jpeg": "JPEG",
        "image/webp": "WEBP",
    }
    normalized = str(mime_type).strip().casefold()
    try:
        expected_format = expected_formats[normalized]
    except KeyError as exc:
        raise ValueError(
            "Figure artifact sources must be PNG, JPEG, or WebP raster images"
        ) from exc
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:  # pragma: no cover - installation smoke covers this
        raise RuntimeError(
            "Pillow is required for Figure Studio image validation"
        ) from exc

    try:
        with Image.open(path) as image:
            if image.format != expected_format:
                raise ValueError(
                    f"Artifact bytes do not match declared MIME type {normalized}"
                )
            _require_single_frame(image)
            width, height = validate_dimensions(*image.size)
            image.verify()
    except UnidentifiedImageError as exc:
        raise ValueError("Figure artifact is not a valid raster image") from exc
    return width, height


def _require_single_frame(image: object) -> None:
    """Reject APNG and animated WebP inputs masquerading as static sources."""

    frame_count = int(getattr(image, "n_frames", 1))
    if bool(getattr(image, "is_animated", False)) or frame_count != 1:
        raise ValueError("Figure image sources must be static single-frame images")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def create_thumbnail(source: Path, destination: Path, *, mime_type: str) -> None:
    """Create a safe PNG thumbnail without requiring a video decoder."""

    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:  # pragma: no cover - installation smoke covers this
        raise RuntimeError("Pillow is required for Figure Studio thumbnails") from exc

    if str(mime_type).casefold() == "image/png":
        with Image.open(source) as image:
            image.thumbnail((512, 512))
            image.convert("RGBA").save(destination, format="PNG")
        return

    image = Image.new("RGB", (512, 288), "#101d29")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 491, 267), outline="#61d1ca", width=3)
    draw.text((36, 126), "Figure Studio animation", fill="#eaf2f8")
    image.save(destination, format="PNG")


__all__ = [
    "FigureMediaTooLarge",
    "MAX_ANIMATION_BYTES",
    "MAX_ANIMATION_FRAMES",
    "MAX_FIGURE_DIMENSION",
    "MAX_FIGURE_LAYERS",
    "MAX_FIGURE_PIXELS",
    "MAX_PNG_BYTES",
    "canonical_suffix",
    "copy_limited_stream",
    "create_thumbnail",
    "max_bytes_for_mime",
    "sha256_file",
    "validate_dimensions",
    "validate_media_magic",
    "validate_png",
    "validate_raster_image",
]
