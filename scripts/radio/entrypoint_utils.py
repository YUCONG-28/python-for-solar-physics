"""Shared CLI and output helpers for radio entrypoints.

Entrypoints use this module to parse config/output overrides before importing
legacy plotting code. Keeping this layer light makes dry-run, docs, and import
tests independent of NumPy/Pandas/Matplotlib.
"""

from __future__ import annotations

import argparse
import copy
import os
from pathlib import Path

from scripts.radio.core.radio_output_paths import plot_output_subdir


def build_common_parser(
    description: str,
    *,
    default_config: str = "radio_20250124_config",
    include_pipeline_outputs: bool = False,
) -> argparse.ArgumentParser:
    """Build the small user-facing CLI shared by radio entrypoints."""
    parser = argparse.ArgumentParser(description=description, add_help=True)
    parser.add_argument("--config", default=default_config)
    parser.add_argument("--output-dir")
    parser.add_argument("--analysis-subdir")
    parser.add_argument("--gaussian-csv")
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
):
    """Parse shared options while leaving legacy-specific arguments untouched."""
    parser = build_common_parser(
        description,
        default_config=default_config,
        include_pipeline_outputs=include_pipeline_outputs,
    )
    args, _unknown = parser.parse_known_args()
    return args


def apply_output_overrides(user_config: dict, args) -> dict:
    """Return a copied USER_CONFIG with CLI output overrides applied."""
    config = copy.deepcopy(user_config or {})
    output = config.setdefault("output", {})
    gaussian = config.setdefault("gaussian", {})

    if getattr(args, "output_dir", None):
        output["output_dir"] = args.output_dir
    if getattr(args, "analysis_subdir", None):
        output["analysis_subdir"] = args.analysis_subdir
    if getattr(args, "gaussian_csv", None):
        gaussian["gaussian_diagnostics_csv"] = args.gaussian_csv
    return config


def apply_pipeline_output_overrides(
    output_config: dict,
    newkirk_config: dict,
    drift_product_config: dict,
    presentation_config: dict,
    args,
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
    """Build the flat legacy config used by the retained plotting workflow."""
    cfg = legacy_module.build_config(user_config, legacy_module.DEFAULT_CONFIG)
    cfg = legacy_module._migrate_config(cfg)
    return cfg


def resolve_analysis_dir(cfg: dict) -> Path:
    """Resolve the analysis output directory for source-map and pipeline products."""
    output_dir = Path(cfg.get("output_dir") or os.getcwd())
    return output_dir / plot_output_subdir(cfg)
