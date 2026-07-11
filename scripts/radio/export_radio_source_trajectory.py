"""Compatibility entrypoint for :mod:`solar_toolkit.radio.trajectory_cli`."""

from __future__ import annotations

from solar_toolkit.radio.trajectory_cli import build_parser, main, run_trajectory_export

__all__ = ["build_parser", "main", "run_trajectory_export"]


if __name__ == "__main__":
    raise SystemExit(main())
