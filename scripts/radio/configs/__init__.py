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
    "los_sign": 1,
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
DEFAULT_NEWKIRK_SPATIAL_CONFIG = {
    "enable": False,
    "aia_channel": 171,
    "aia171_path": None,
    "geometry": "plane_of_sky_radial_anchor",
    "documentation_status": "illustrative plane-of-sky projection only, not a physical 2D reconstruction",
    "harmonic": 1,
    "newkirk_multiplier": 1.0,
    "solar_radius_arcsec": None,
    "color_by": "frequency",
    "plot_typeIII": True,
    "plot_spike": True,
    "draw_gaussian_ellipse": True,
    "draw_residual_arrows": True,
    "max_residual_arrow_arcsec": None,
    "output_name": "aia171_typeIII_spike_newkirk_projection_schematic.png",
    "comparison_csv_name": "gaussian_newkirk_projection_schematic_table.csv",
    "TYPEIII_TIME_WINDOWS": [],
    "SPIKE_TIME_WINDOWS": [],
    "TYPEIII_FREQ_RANGE": None,
    "SPIKE_FREQ_RANGE": None,
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
    newkirk_config = dict(DEFAULT_NEWKIRK_CONFIG)
    newkirk_config.update(
        copy.deepcopy(_event_section(module, "newkirk", "NEWKIRK_CONFIG"))
    )
    return user_config, newkirk_config


def load_aia_radio_hmi_user_config(config_name: str | None = None):
    """Load AIA/HMI/radio overlay config from a config module."""
    module = load_radio_config_module(config_name)
    return copy.deepcopy(
        _event_section(module, "aia_radio_hmi", "AIA_RADIO_HMI_CONFIG")
    )


def load_newkirk_spatial_config(config_name: str | None = None):
    """Load optional illustrative plane-of-sky projection config."""
    module = load_radio_config_module(config_name)
    config = copy.deepcopy(DEFAULT_NEWKIRK_SPATIAL_CONFIG)
    config.update(
        copy.deepcopy(
            _event_section(module, "newkirk_spatial", "NEWKIRK_SPATIAL_CONFIG")
        )
    )
    return config


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
    config = copy.deepcopy(DEFAULT_DRIFT_SELECTION_PRODUCT_CONFIG)
    config.update(
        copy.deepcopy(
            _event_section(
                module, "drift_selection_products", "DRIFT_SELECTION_PRODUCT_CONFIG"
            )
        )
    )
    return config


def load_radio_diagnostic_presentation_config(config_name: str | None = None):
    """Load frequency-priority diagnostic presentation config."""
    module = load_radio_config_module(config_name)
    user_config = copy.deepcopy(_event_section(module, "user", "USER_CONFIG"))
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
    if not config.get("comparison_frequency_mhz"):
        data_cfg = user_config.get("data", {}) if isinstance(user_config, dict) else {}
        freqs = data_cfg.get("multi_band_freqs") or []
        config["comparison_frequency_mhz"] = [float(freq) for freq in freqs]
    return config
