"""Lazy module dispatch without depending on the CLI presentation layer."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from importlib import import_module
from typing import Any


def requested_top_level_help(argv: Sequence[str]) -> bool:
    """Return whether an adapter should show safe top-level help."""

    return not argv or argv[0] in {"-h", "--help"}


def forward_main(
    module_name: str,
    argv: Sequence[str],
    *,
    program: str | None = None,
) -> int:
    """Load a target lazily and invoke its ``main`` with forwarded arguments."""

    try:
        module = import_module(module_name)
        target: Any = getattr(module, "main")
    except (AttributeError, ImportError) as exc:
        print(
            f"Solar application target {module_name!r} is unavailable: {exc}",
            file=sys.stderr,
        )
        return 2
    original_program = sys.argv[0]
    if program:
        sys.argv[0] = program
    try:
        result = target(list(argv))
        return result if isinstance(result, int) else 0
    finally:
        sys.argv[0] = original_program


__all__ = ["forward_main", "requested_top_level_help"]
