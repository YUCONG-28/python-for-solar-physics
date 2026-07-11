"""Command-line contract for radio source-map generation."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from .config import DEFAULT_CONFIG_NAME, load_radio_user_config
from .entrypoint_utils import apply_output_overrides, build_common_parser
from .provenance import resolve_provenance_output_dir, write_radio_provenance

__all__ = ["build_parser", "main"]


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
    """Run source-map generation or an explicit compatibility hook."""

    args, unknown = build_parser().parse_known_args(argv)

    user_config, newkirk_config = load_radio_user_config(args.config)
    resolved_config = apply_output_overrides(user_config, args)
    if runner is None:
        from .source_map_workflow import run_source_map

        result = run_source_map(resolved_config, argv=unknown)
    else:
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


if __name__ == "__main__":
    raise SystemExit(main())
