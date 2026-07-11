"""Command-line contract for radio source-map generation."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from typing import Any

from .config import DEFAULT_CONFIG_NAME, load_radio_user_config
from .entrypoint_utils import apply_output_overrides, build_common_parser
from .provenance import resolve_provenance_output_dir, write_radio_provenance

__all__ = ["build_parser", "main"]

_BOUNDARY_MESSAGE = (
    "The source-map scientific runner remains a source-repository compatibility "
    "workflow until real-data parity validation is complete. Use "
    "scripts/radio/run_radio_source_map.py in a source checkout."
)


def build_parser():
    """Build the source-map command parser without importing plotting code."""

    return build_common_parser(
        "Run radio source maps with Gaussian overlay.",
        default_config=DEFAULT_CONFIG_NAME,
    )


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

    user_config, newkirk_config = load_radio_user_config(args.config)
    resolved_config = apply_output_overrides(user_config, args)
    result = runner(resolved_config)
    output_dir = resolve_provenance_output_dir(resolved_config)
    if (not isinstance(result, int) or result == 0) and output_dir is not None:
        write_radio_provenance(
            output_dir,
            resolved_config,
            newkirk_config=newkirk_config,
            config_source=args.config,
            cli_overrides=vars(args),
        )
    return result if isinstance(result, int) else 0
