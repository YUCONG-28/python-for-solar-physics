"""Shared, import-safe helpers for radio command-line entrypoints."""

from __future__ import annotations

import argparse
import copy
import json
import os
from collections.abc import Sequence
from pathlib import Path

from solar_toolkit.radio.output_paths import plot_output_subdir

__all__ = [
    "apply_output_overrides",
    "apply_pipeline_output_overrides",
    "build_common_parser",
    "build_legacy_config",
    "load_workspace_config_overrides",
    "parse_known_common_args",
    "resolve_analysis_dir",
]


def build_common_parser(
    description: str,
    *,
    prog: str | None = None,
    default_config: str = "radio_20250124_config",
    include_pipeline_outputs: bool = False,
) -> argparse.ArgumentParser:
    """Build the small user-facing CLI shared by radio entrypoints."""

    parser = argparse.ArgumentParser(
        prog=prog,
        description=description,
        add_help=True,
    )
    parser.add_argument("--config", default=default_config)
    parser.add_argument("--output-dir")
    parser.add_argument("--analysis-subdir")
    parser.add_argument("--gaussian-csv")
    parser.add_argument(
        "--workspace-config-json",
        help="Structured Radio Workspace overrides encoded as a JSON object.",
    )
    if include_pipeline_outputs:
        parser.add_argument("--valid-centers-csv")
        parser.add_argument("--newkirk-csv")
        parser.add_argument("--drift-speed-csv")
    return parser


def parse_known_common_args(
    description: str,
    *,
    default_config: str,
    include_pipeline_outputs: bool = False,
    argv: Sequence[str] | None = None,
) -> argparse.Namespace:
    """Parse shared options while leaving legacy-specific arguments untouched."""

    parser = build_common_parser(
        description,
        default_config=default_config,
        include_pipeline_outputs=include_pipeline_outputs,
    )
    args, _unknown = parser.parse_known_args(argv)
    return args


def apply_output_overrides(user_config: dict, args: argparse.Namespace) -> dict:
    """Return a copied event configuration with CLI overrides applied."""

    config = _deep_merge(
        copy.deepcopy(user_config or {}),
        load_workspace_config_overrides(args),
    )
    output = config.setdefault("output", {})
    gaussian = config.setdefault("gaussian", {})

    if getattr(args, "output_dir", None):
        output["output_dir"] = args.output_dir
    if getattr(args, "analysis_subdir", None):
        output["analysis_subdir"] = args.analysis_subdir
    if getattr(args, "gaussian_csv", None):
        gaussian["gaussian_diagnostics_csv"] = args.gaussian_csv
    return config


def load_workspace_config_overrides(args: argparse.Namespace) -> dict:
    """Decode structured overrides supplied by the integrated workspace."""

    raw = getattr(args, "workspace_config_json", None)
    if raw in (None, ""):
        return {}
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise TypeError("--workspace-config-json must contain a JSON object")
    return payload


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def apply_pipeline_output_overrides(
    output_config: dict,
    newkirk_config: dict,
    drift_product_config: dict,
    presentation_config: dict,
    args: argparse.Namespace,
) -> dict:
    """Apply config-file and CLI output names to downstream pipeline sections."""

    output = dict(output_config or {})
    if getattr(args, "output_dir", None):
        output["output_dir"] = args.output_dir
    if getattr(args, "analysis_subdir", None):
        output["analysis_subdir"] = args.analysis_subdir
    if getattr(args, "gaussian_csv", None):
        output["gaussian_diagnostics_csv"] = args.gaussian_csv
    if getattr(args, "valid_centers_csv", None):
        output["valid_centers_csv"] = args.valid_centers_csv
    if getattr(args, "newkirk_csv", None):
        output["newkirk_csv"] = args.newkirk_csv
    if getattr(args, "drift_speed_csv", None):
        output["drift_speed_csv"] = args.drift_speed_csv

    if output.get("newkirk_csv"):
        newkirk_config["output_csv"] = output["newkirk_csv"]
    if output.get("drift_speed_csv"):
        newkirk_config["drift_speed_csv"] = output["drift_speed_csv"]
    if output.get("drift_selection_subdir"):
        drift_product_config["output_subdir"] = output["drift_selection_subdir"]
    if output.get("enable_static_summary") is not None:
        presentation_config["enable_static_summary"] = bool(
            output["enable_static_summary"]
        )
    if output.get("enable_html_dashboard") is not None:
        presentation_config["enable_html_dashboard"] = bool(
            output["enable_html_dashboard"]
        )
    return output


def build_legacy_config(user_config: dict, legacy_module) -> dict:
    """Build the flat configuration expected by a retained compatibility runner."""

    cfg = legacy_module.build_config(user_config, legacy_module.DEFAULT_CONFIG)
    return legacy_module._migrate_config(cfg)


def resolve_analysis_dir(cfg: dict) -> Path:
    """Resolve the analysis output directory for source-map products."""

    output_dir = Path(cfg.get("output_dir") or os.getcwd())
    return output_dir / plot_output_subdir(cfg)
