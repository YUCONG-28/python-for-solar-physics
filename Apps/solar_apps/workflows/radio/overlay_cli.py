"""Command-line contract for the AIA/radio/HMI overlay workflow."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

from solar_toolkit.radio.config import (
    DEFAULT_CONFIG_NAME,
    load_aia_radio_overlay_user_config,
)
from solar_toolkit.radio.provenance import (
    resolve_provenance_output_dir,
    write_radio_provenance,
)

__all__ = ["build_parser", "main"]


def build_parser() -> argparse.ArgumentParser:
    """Build the overlay parser without importing its scientific renderer."""

    parser = argparse.ArgumentParser(
        prog="solar-apps workflow radio overlay",
        description="Generate an AIA/radio/HMI overlay.",
        add_help=True,
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_NAME,
        help="Event configuration module name.",
    )
    parser.add_argument(
        "--config-file",
        type=Path,
        help=(
            "Install-safe JSON configuration file. It may contain the selected "
            "overlay section or the section mapping directly."
        ),
    )
    parser.add_argument(
        "--overlay-section",
        default="aia_radio_hmi",
        help=(
            "EVENT_CONFIG section to run. Defaults to the stable "
            "aia_radio_hmi overlay."
        ),
    )
    parser.add_argument(
        "--output-dir",
        help="Override the resolved overlay output directory.",
    )
    parser.add_argument(
        "--workspace-config-json",
        help="Structured Radio Workspace overrides encoded as a JSON object.",
    )
    parser.add_argument(
        "--aia-file-start-idx",
        type=int,
        help="Override the inclusive AIA selection start index.",
    )
    parser.add_argument(
        "--aia-file-end-idx",
        type=int,
        help="Override the exclusive AIA selection end index.",
    )
    return parser


def _load_json_overlay_config(path: Path, section: str) -> dict:
    """Load an overlay section from an install-safe JSON configuration file."""

    with path.expanduser().open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise TypeError("Overlay JSON configuration must contain an object.")
    selected = payload.get(section, payload)
    if not isinstance(selected, dict):
        raise TypeError(f"Overlay configuration section {section!r} must be an object.")
    return selected


def _apply_cli_overrides(user_config: dict, args: argparse.Namespace) -> dict:
    """Apply explicit CLI values after the selected config section."""

    resolved = deepcopy(user_config)
    if args.workspace_config_json:
        overrides = json.loads(args.workspace_config_json)
        if not isinstance(overrides, dict):
            raise TypeError("--workspace-config-json must contain a JSON object")
        resolved = _deep_merge(resolved, overrides)
    if args.output_dir is not None:
        resolved.setdefault("paths", {})["output_dir"] = args.output_dir
        resolved.setdefault("output", {})["output_dir"] = args.output_dir
    if args.aia_file_start_idx is not None:
        resolved.setdefault("aia", {})["aia_file_start_idx"] = args.aia_file_start_idx
    if args.aia_file_end_idx is not None:
        resolved.setdefault("aia", {})["aia_file_end_idx"] = args.aia_file_end_idx
    return resolved


def _deep_merge(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: Callable[[dict], Any] | None = None,
) -> int:
    """Run the package-owned overlay workflow."""

    args, _unknown = build_parser().parse_known_args(argv)
    if args.config_file is not None:
        user_config = _load_json_overlay_config(
            args.config_file,
            section=args.overlay_section,
        )
        config_source = str(args.config_file)
    else:
        user_config = load_aia_radio_overlay_user_config(
            args.config,
            section=args.overlay_section,
        )
        config_source = args.config
    user_config = _apply_cli_overrides(user_config, args)
    if runner is None:
        from .overlay_workflow import run_overlay_workflow

        runner = run_overlay_workflow
    result = runner(user_config)
    output_dir = resolve_provenance_output_dir(user_config)
    if (not isinstance(result, int) or result == 0) and output_dir is not None:
        write_radio_provenance(
            output_dir,
            user_config,
            config_source=config_source,
            cli_overrides=vars(args),
        )
    return result if isinstance(result, int) else 0


if __name__ == "__main__":
    raise SystemExit(main())
