"""Compatibility entry point for the packaged radio burst pipeline."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from solar_toolkit.radio import pipeline_workflow as _impl
from solar_toolkit.radio.pipeline_cli import main as _package_main

__all__ = ["main"]


def _run_pipeline(argv: Sequence[str] | None = None) -> int:
    """Forward the retained runner hook to the package implementation."""

    return _impl.run_pipeline(argv)


def main(
    config_name: str | None = None,
    argv: Sequence[str] | None = None,
) -> int:
    """Run the package pipeline while preserving the historical signature."""

    forwarded = list(sys.argv[1:] if argv is None else argv)
    if config_name is not None:
        forwarded.extend(["--config", config_name])
    return _package_main(forwarded, runner=_run_pipeline)


def __getattr__(name: str):
    return getattr(_impl, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_impl)))


if __name__ == "__main__":
    raise SystemExit(main())
