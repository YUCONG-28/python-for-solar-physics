"""Command dispatcher for installable radio-analysis workflows."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from importlib import import_module
from typing import Any

_COMMANDS = {
    "centers": ("solar_toolkit.radio.centers", "main"),
    "overlay": ("solar_toolkit.radio.overlay_cli", "main"),
    "pipeline": ("solar_toolkit.radio.pipeline_cli", "main"),
    "quicklook": ("solar_toolkit.radio.quicklook", "main"),
    "raw-quality": ("solar_toolkit.radio.raw_quality_cli", "main"),
    "roi-lightcurve": ("solar_toolkit.radio.roi_lightcurve_launcher", "main"),
    "source-map": ("solar_toolkit.radio.source_map_cli", "main"),
    "trajectory": ("solar_toolkit.radio.trajectory_cli", "main"),
}

__all__ = ["build_parser", "main"]


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level radio command parser."""

    parser = argparse.ArgumentParser(
        prog="solar-radio",
        description="Run packaged radio-analysis workflows.",
    )
    parser.add_argument("command", nargs="?", choices=sorted(_COMMANDS))
    return parser


def _command_callable(name: str) -> Callable[[list[str] | None], Any]:
    module_name, callable_name = _COMMANDS[name]
    return getattr(import_module(module_name), callable_name)


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch a radio subcommand while preserving its native parser."""

    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        build_parser().print_help()
        return 0
    command = args.pop(0)
    if command not in _COMMANDS:
        build_parser().error(
            f"argument command: invalid choice: {command!r} "
            f"(choose from {', '.join(sorted(_COMMANDS))})"
        )
    original_program = sys.argv[0]
    sys.argv[0] = f"solar-radio {command}"
    try:
        result = _command_callable(command)(args)
    finally:
        sys.argv[0] = original_program
    return result if isinstance(result, int) else 0


if __name__ == "__main__":
    raise SystemExit(main())
