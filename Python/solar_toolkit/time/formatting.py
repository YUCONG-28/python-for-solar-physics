"""Timestamp formatting helpers for displays and filenames."""

from __future__ import annotations

import datetime as dt


def format_time_for_display(value: dt.datetime) -> str:
    """Format a timestamp as ``YYYY-MM-DD HH:MM:SS``."""

    return value.strftime("%Y-%m-%d %H:%M:%S")


def format_time_for_filename(value: dt.datetime) -> str:
    """Format a timestamp as the filesystem-safe ``YYYYMMDD_HHMMSS``."""

    return value.strftime("%Y%m%d_%H%M%S")


__all__ = ["format_time_for_display", "format_time_for_filename"]
