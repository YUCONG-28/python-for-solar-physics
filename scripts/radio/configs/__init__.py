"""Configuration loading helpers for radio entrypoints."""

from __future__ import annotations

import copy
import importlib
from types import ModuleType

DEFAULT_CONFIG_NAME = "radio_20250124_config"
DEFAULT_NEWKIRK_CONFIG = {
    "enabled": True,
    "multipliers": [1, 2, 4],
    "harmonics": [1, 2],
    "solar_radius_arcsec": 959.63,
}
DEFAULT_NEWKIRK_HEIGHT_COMPARISON_CONFIG = {
    "enable": True,
    "selected_models": [
        {"multiplier": 1.0, "harmonic": 1},
        {"multiplier": 1.0, "harmonic": 2},
        {"multiplier": 2.0, "harmonic": 1},
        {"multiplier": 2.0, "harmonic": 2},
        {"multiplier": 4.0, "harmonic": 1},
        {"multiplier": 4.0, "harmonic": 2},
    ],
    "solar_radius_arcsec": None,
    "plot_height_frequency": True,
    "plot_height_time": True,
    "plot_residual_frequency": True,
    "output_table_name": "gaussian_newkirk_height_comparison_table.csv",
    "raw_output_table_name": "gaussian_newkirk_height_rows.csv",
    "height_frequency_plot_name": "gaussian_vs_newkirk_height_frequency.png",
    "height_time_plot_name": "gaussian_vs_newkirk_height_time.png",
    "height_residual_plot_name": "gaussian_newkirk_height_residual_vs_frequency.png",
    "height_residual_summary_name": "gaussian_newkirk_height_residual_summary.csv",
    "reverse_frequency_axis": False,
    "color_by": "source_type",
    "drift_time_tolerance_s": 0.75,
    "drift_frequency_tolerance_mhz": "adaptive_half_band_spacing",
    "max_adaptive_frequency_tolerance_mhz": 15.0,
    "min_adaptive_frequency_tolerance_mhz": 5.0,
}
DEFAULT_OUTPUT_CONFIG = {
    "output_dir": None,
    "analysis_subdir": "auto",
    "gaussian_diagnostics_csv": "radio_gaussian_fit_diagnostics.csv",
    "valid_centers_csv": "radio_gaussian_valid_centers.csv",
    "newkirk_csv": "radio_gaussian_newkirk_extrapolated.csv",
    "drift_speed_csv": "radio_drift_newkirk_speed.csv",
    "drift_selection_subdir": "drift_selection",
    "enable_static_summary": None,
    "enable_html_dashboard": None,
}
DEFAULT_DRIFT_SELECTION_PRODUCT_CONFIG = {
    "enable": True,
    "save_raw_preview": True,
    "save_annotated_preview": True,
    "save_selection_csv": True,
    "save_metadata_json": True,
    "save_per_drift_cutouts": True,
    "cutout_time_padding_s": 2.0,
    "cutout_frequency_padding_mhz": 20.0,
    "annotate_drift_rate": True,
    "annotate_endpoints": True,
    "preserve_existing": True,
    "dpi": 200,
    "output_subdir": "drift_selection",
}
DEFAULT_RADIO_DIAGNOSTIC_PRESENTATION_CONFIG = {
    "enable": True,
    "enable_static_summary": True,
    "enable_html_dashboard": True,
    "comparison_frequency_mhz": None,
    "drift_source_type_map": {
        "drift_001": "typeIII",
        "drift_002": "typeIII",
        "drift_003": "spike",
        "drift_004": "spike",
    },
    "drift_time_tolerance_s": 0.75,
    "drift_frequency_tolerance_mhz": "adaptive_half_band_spacing",
    "max_adaptive_frequency_tolerance_mhz": 15.0,
    "min_adaptive_frequency_tolerance_mhz": 5.0,
    "selected_newkirk_multiplier": 2.0,
    "selected_newkirk_harmonic": 2,
    "reference_newkirk_assumption": "2xH2",
    "connect_same_drift_only": False,
    "reverse_frequency_axis": False,
    "enable_debug_center_facets": False,
    "enable_debug_height_time_facets": False,
    "enable_debug_drift_band_matching": False,
    "enable_debug_trajectory_by_frequency": False,
    "enable_event_height_comparison": True,
    "enable_event_speed_frequency": True,
    "best_model_metric": "median_abs_residual_rsun",
    "top_residual_models": 3,
    "summary_panel_name": "radio_newkirk_frequency_priority_summary.png",
    "center_facets_name": "gaussian_center_by_frequency_facets.png",
    "trajectory_by_frequency_name_template": "gaussian_center_trajectory_time_colored_{frequency:g}MHz.png",
    "drift_band_matching_name": "drift_frequency_band_matching.png",
    "height_time_facets_name": "height_time_by_frequency_facets.png",
    "event_height_comparison_name": "event_gaussian_newkirk_height_comparison.png",
    "event_speed_frequency_name": "event_newkirk_speed_frequency_scatter.png",
    "selected_band_newkirk_table_name": "event_selected_band_newkirk_table.csv",
    "physical_consistency_report_name": "newkirk_physical_consistency_report.md",
    "dashboard_name": "radio_newkirk_frequency_priority_dashboard.html",
    "summary_csv_name": "radio_newkirk_frequency_priority_summary.csv",
}


def _normalize_config_module_name(config_name: str | None) -> str:
    name = (config_name or DEFAULT_CONFIG_NAME).strip()
    if not name:
        name = DEFAULT_CONFIG_NAME
    if name.endswith(".py"):
        name = name[:-3]
    if name.startswith("scripts.radio.configs."):
        return name
    if "." in name:
        return name
    return f"scripts.radio.configs.{name}"


def load_radio_config_module(config_name: str | None = None) -> ModuleType:
    """Load a config module from ``scripts.radio.configs``."""
    return importlib.import_module(_normalize_config_module_name(config_name))


def _event_section(module: ModuleType, section: str, legacy_name: str):
    event_config = getattr(module, "EVENT_CONFIG", None)
    if isinstance(event_config, dict) and section in event_config:
        return event_config.get(section) or {}
    return getattr(module, legacy_name, {}) or {}


def load_radio_user_config(config_name: str | None = None):
    """
    Load a radio event config.

    Returns ``(USER_CONFIG, NEWKIRK_CONFIG)``. The config name may be either a
    short module name such as ``radio_20250124_config`` or a fully qualified
    module path such as ``scripts.radio.configs.radio_20250124_config``.
    """
    module = load_radio_config_module(config_name)
    user_config = copy.deepcopy(_event_section(module, "user", "USER_CONFIG"))
    output_config = _load_output_config_from_module(module)
    _apply_output_config_to_user_config(user_config, output_config)
    newkirk_config = dict(DEFAULT_NEWKIRK_CONFIG)
    newkirk_config.update(
        copy.deepcopy(_event_section(module, "newkirk", "NEWKIRK_CONFIG"))
    )
    if output_config.get("newkirk_csv"):
        newkirk_config["output_csv"] = output_config["newkirk_csv"]
    if output_config.get("drift_speed_csv"):
        newkirk_config["drift_speed_csv"] = output_config["drift_speed_csv"]
    return user_config, newkirk_config


def _legacy_overlay_config_name(section: str) -> str:
    name = (section or "aia_radio_hmi").strip()
    if name == "aia_radio_hmi":
        return "AIA_RADIO_HMI_CONFIG"
    return f"{name.upper()}_CONFIG"


def load_aia_radio_overlay_user_config(
    config_name: str | None = None, *, section: str = "aia_radio_hmi"
):
    """Load a named AIA/HMI/radio overlay config section."""
    module = load_radio_config_module(config_name)
    section_name = (section or "aia_radio_hmi").strip()
    return copy.deepcopy(
        _event_section(module, section_name, _legacy_overlay_config_name(section_name))
    )


def load_aia_radio_hmi_user_config(config_name: str | None = None):
    """Load the default AIA/HMI/radio overlay config from a config module."""
    return load_aia_radio_overlay_user_config(config_name, section="aia_radio_hmi")


def load_newkirk_height_comparison_config(config_name: str | None = None):
    """Load Gaussian-Newkirk height comparison config."""
    module = load_radio_config_module(config_name)
    config = copy.deepcopy(DEFAULT_NEWKIRK_HEIGHT_COMPARISON_CONFIG)
    config.update(
        copy.deepcopy(
            _event_section(
                module, "newkirk_height_comparison", "NEWKIRK_HEIGHT_COMPARISON_CONFIG"
            )
        )
    )
    return config


def load_drift_selection_product_config(config_name: str | None = None):
    """Load persistent drift-selection product config."""
    module = load_radio_config_module(config_name)
    output_config = _load_output_config_from_module(module)
    config = copy.deepcopy(DEFAULT_DRIFT_SELECTION_PRODUCT_CONFIG)
    config.update(
        copy.deepcopy(
            _event_section(
                module, "drift_selection_products", "DRIFT_SELECTION_PRODUCT_CONFIG"
            )
        )
    )
    if output_config.get("drift_selection_subdir"):
        config["output_subdir"] = output_config["drift_selection_subdir"]
    return config


def load_radio_output_config(config_name: str | None = None):
    """Load common user-facing output controls from an event config."""
    return _load_output_config_from_module(load_radio_config_module(config_name))


def load_radio_diagnostic_presentation_config(config_name: str | None = None):
    """Load frequency-priority diagnostic presentation config."""
    module = load_radio_config_module(config_name)
    user_config = copy.deepcopy(_event_section(module, "user", "USER_CONFIG"))
    output_config = _load_output_config_from_module(module)
    config = copy.deepcopy(DEFAULT_RADIO_DIAGNOSTIC_PRESENTATION_CONFIG)
    config.update(
        copy.deepcopy(
            _event_section(
                module,
                "diagnostic_presentation",
                "RADIO_DIAGNOSTIC_PRESENTATION_CONFIG",
            )
        )
    )
    if output_config.get("enable_static_summary") is not None:
        config["enable_static_summary"] = bool(output_config["enable_static_summary"])
    if output_config.get("enable_html_dashboard") is not None:
        config["enable_html_dashboard"] = bool(output_config["enable_html_dashboard"])
    if not config.get("comparison_frequency_mhz"):
        data_cfg = user_config.get("data", {}) if isinstance(user_config, dict) else {}
        freqs = data_cfg.get("multi_band_freqs") or []
        config["comparison_frequency_mhz"] = [float(freq) for freq in freqs]
    return config


def _load_output_config_from_module(module: ModuleType) -> dict:
    config = copy.deepcopy(DEFAULT_OUTPUT_CONFIG)
    config.update(copy.deepcopy(_event_section(module, "output", "OUTPUT_CONFIG")))
    return config


def _apply_output_config_to_user_config(user_config: dict, output_config: dict) -> None:
    output = user_config.setdefault("output", {})
    gaussian = user_config.setdefault("gaussian", {})
    for key in ("output_dir", "analysis_subdir"):
        value = output_config.get(key)
        if value not in (None, ""):
            output[key] = value
    gaussian_csv = output_config.get("gaussian_diagnostics_csv")
    if gaussian_csv:
        gaussian["gaussian_diagnostics_csv"] = gaussian_csv
