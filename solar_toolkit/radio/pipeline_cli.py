"""Command-line contract for the full radio burst pipeline."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from typing import Any

from .config import DEFAULT_CONFIG_NAME
from .entrypoint_utils import build_common_parser

__all__ = ["build_parser", "main"]

_BOUNDARY_MESSAGE = (
    "The full pipeline runner remains a source-repository compatibility workflow "
    "until source-map real-data parity validation is complete. Use "
    "scripts/radio/run_radio_burst_pipeline.py in a source checkout."
)


def build_parser():
    """Build the full-pipeline parser without importing the scientific stack."""

    return build_common_parser(
        "Run the full radio burst Gaussian, drift-rate, and Newkirk-height pipeline.",
        default_config=DEFAULT_CONFIG_NAME,
        include_pipeline_outputs=True,
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: Callable[[Sequence[str] | None], Any] | None = None,
) -> int:
    """Run a supplied compatibility runner, or report the parity boundary."""

    forwarded = None if argv is None else list(argv)
    build_parser().parse_known_args(forwarded)
    if runner is None:
        print(_BOUNDARY_MESSAGE, file=sys.stderr)
        return 2

    result = runner(forwarded)
    return result if isinstance(result, int) else 0
