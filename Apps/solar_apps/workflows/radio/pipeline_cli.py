"""Command-line contract for the full radio burst pipeline."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from .configs import DEFAULT_CONFIG_NAME
from .entrypoint_utils import build_common_parser

__all__ = ["build_parser", "main"]


def build_parser():
    """Build the full-pipeline parser without importing the scientific stack."""

    return build_common_parser(
        "Run the full radio burst Gaussian, drift-rate, and Newkirk-height pipeline.",
        prog="Apps/run.ps1 workflow radio pipeline",
        default_config=DEFAULT_CONFIG_NAME,
        include_pipeline_outputs=True,
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: Callable[[Sequence[str] | None], Any] | None = None,
) -> int:
    """Run the package pipeline or an explicitly supplied compatibility hook."""

    forwarded = None if argv is None else list(argv)
    build_parser().parse_known_args(forwarded)
    if runner is None:
        from .pipeline_workflow import run_pipeline

        runner = run_pipeline

    result = runner(forwarded)
    return result if isinstance(result, int) else 0


if __name__ == "__main__":
    raise SystemExit(main())
