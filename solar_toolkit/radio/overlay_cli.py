"""Command-line contract for the AIA/radio/HMI overlay workflow."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from typing import Any

from .config import DEFAULT_CONFIG_NAME, load_aia_radio_overlay_user_config
from .provenance import resolve_provenance_output_dir, write_radio_provenance

__all__ = ["build_parser", "main"]

_BOUNDARY_MESSAGE = (
    "The AIA/radio/HMI overlay runner remains a source-repository compatibility "
    "workflow until real-data parity validation is complete. Use "
    "scripts/radio/run_aia_radio_hmi_overlay.py in a source checkout."
)


def build_parser() -> argparse.ArgumentParser:
    """Build the overlay parser without importing its scientific renderer."""

    parser = argparse.ArgumentParser(
        description="Generate an AIA/radio/HMI overlay.",
        add_help=True,
    )
    parser.add_argument("--config", default=DEFAULT_CONFIG_NAME)
    parser.add_argument(
        "--overlay-section",
        default="aia_radio_hmi",
        help=(
            "EVENT_CONFIG section to run. Defaults to the stable "
            "aia_radio_hmi overlay."
        ),
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: Callable[[dict], Any] | None = None,
) -> int:
    """Run a supplied compatibility runner, or report the parity boundary."""

    args, _unknown = build_parser().parse_known_args(argv)
    if runner is None:
        print(_BOUNDARY_MESSAGE, file=sys.stderr)
        return 2

    user_config = load_aia_radio_overlay_user_config(
        args.config,
        section=args.overlay_section,
    )
    result = runner(user_config)
    output_dir = resolve_provenance_output_dir(user_config)
    if (not isinstance(result, int) or result == 0) and output_dir is not None:
        write_radio_provenance(
            output_dir,
            user_config,
            config_source=args.config,
            cli_overrides=vars(args),
        )
    return result if isinstance(result, int) else 0
