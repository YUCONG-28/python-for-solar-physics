"""Compatibility entrypoint for the packaged image web viewer CLI."""

from __future__ import annotations

from solar_toolkit.visualization.image_web_viewer.cli import (
    build_parser,
    main,
    parse_allowed_roots,
)

__all__ = ["build_parser", "main", "parse_allowed_roots"]


if __name__ == "__main__":
    raise SystemExit(main())
