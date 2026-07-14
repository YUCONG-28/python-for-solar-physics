"""Compatibility alias for :mod:`solar_toolkit.visualization.media`."""

from __future__ import annotations

import sys

from solar_toolkit.visualization import media as _shared_media
from solar_toolkit.visualization.media import (
    MediaProcessingError,
    normalize_even_size,
    normalize_output_format,
    normalize_recording_source_format,
    probe_video,
    resolve_ffmpeg,
    resolve_ffprobe,
    sanitize_filename,
    save_browser_recording,
    save_browser_recording_stream,
    transcode_recording,
    write_media_from_frames,
    write_media_from_paths,
)

__all__ = [
    "MediaProcessingError",
    "normalize_even_size",
    "normalize_output_format",
    "normalize_recording_source_format",
    "probe_video",
    "resolve_ffmpeg",
    "resolve_ffprobe",
    "sanitize_filename",
    "save_browser_recording",
    "save_browser_recording_stream",
    "transcode_recording",
    "write_media_from_frames",
    "write_media_from_paths",
]

sys.modules[__name__] = _shared_media
