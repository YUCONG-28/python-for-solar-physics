"""Compatibility entrypoint for :mod:`solar_toolkit.radio.raw_quality_cli`."""

from __future__ import annotations

from solar_toolkit.radio.raw_quality_cli import (
    DEFAULT_RAW_QUALITY_CONFIG,
    build_parser,
    main,
    run_raw_quality,
)

__all__ = [
    "DEFAULT_RAW_QUALITY_CONFIG",
    "build_parser",
    "main",
    "run_raw_quality",
]


if __name__ == "__main__":
    raise SystemExit(main())
