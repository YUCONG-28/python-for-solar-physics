"""Compatibility entrypoint for the packaged AIA/radio/HMI overlay CLI."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from solar_toolkit.radio.overlay_cli import build_parser
from solar_toolkit.radio.overlay_cli import main as _package_main

__all__ = ["build_parser", "main"]


def main(
    config_name: str | None = None,
    overlay_section: str | None = None,
    argv: Sequence[str] | None = None,
) -> int:
    """Run the package-owned overlay while preserving the historical script."""

    forwarded = list(sys.argv[1:] if argv is None else argv)
    if config_name is not None:
        forwarded.extend(["--config", config_name])
    if overlay_section is not None:
        forwarded.extend(["--overlay-section", overlay_section])
    return _package_main(forwarded)


if __name__ == "__main__":
    raise SystemExit(main())
