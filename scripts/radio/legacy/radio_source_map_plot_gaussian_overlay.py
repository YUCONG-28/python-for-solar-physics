"""Compatibility wrapper for the packaged radio source-map workflow."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from solar_toolkit.radio import source_map_workflow as _impl
from solar_toolkit.radio.config import DEFAULT_CONFIG_NAME, load_radio_user_config

__all__ = list(_impl.__all__)

DEFAULT_CONFIG = _impl.DEFAULT_CONFIG
build_config = _impl.build_config


def _run_source_map_workflow(
    *,
    user_config: dict | None = None,
    argv: Sequence[str] | None = None,
):
    """Forward the historical workflow to the installable implementation."""

    resolved = user_config
    if resolved is None:
        try:
            resolved, _newkirk = load_radio_user_config(DEFAULT_CONFIG_NAME)
        except ModuleNotFoundError:
            # A wheel need not contain repository event recipes.  The packaged
            # workflow still supports an explicit mapping or importable module.
            resolved = None
    return _impl._run_source_map_workflow(user_config=resolved, argv=argv)


def main(
    user_config: dict | None = None,
    *,
    argv: Sequence[str] | None = None,
) -> int:
    """Run the historical entry point through the package-owned workflow."""

    _run_source_map_workflow(user_config=user_config, argv=argv)
    return 0


def __getattr__(name: str):
    return getattr(_impl, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_impl)))


if __name__ == "__main__":
    raise SystemExit(main())
else:
    # Preserve monkeypatching and module-global cache/config semantics for old
    # imports by making the historical path a true module alias.
    sys.modules[__name__] = _impl
