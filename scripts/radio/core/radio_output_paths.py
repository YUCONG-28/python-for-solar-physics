"""Lightweight output-path helpers for radio workflows.

The scientific I/O module re-exports these helpers for compatibility, but this
small module lets entrypoints decide output locations without importing the
numeric stack.
"""

from __future__ import annotations

import os


def spectrogram_panel_enabled(cfg: dict) -> bool:
    """Return whether the source-map plot should include a spectrogram panel."""
    return bool(cfg.get("enable_spectrogram_panel", False))


def background_enabled_for_display(cfg: dict) -> bool:
    """Return whether background-subtracted images should be shown in figures."""
    return resolve_background_workflow(cfg) in {"display_only", "display_and_fit"}


def background_enabled_for_fit(cfg: dict) -> bool:
    """Return whether Gaussian fitting should use background-subtracted data."""
    return resolve_background_workflow(cfg) in {"fit_only", "display_and_fit"}


def resolve_background_workflow(cfg: dict) -> str:
    """Normalize legacy boolean flags into the current background workflow name."""
    workflow = str(cfg.get("radio_background_workflow", "off") or "off").lower()
    if workflow in {"off", "display_only", "fit_only", "display_and_fit"}:
        return workflow
    display = bool(cfg.get("background_use_for_display", False))
    fit = bool(cfg.get("background_use_for_fit", False))
    if display and fit:
        return "display_and_fit"
    if display:
        return "display_only"
    if fit:
        return "fit_only"
    return "off"


def plot_output_subdir(cfg: dict) -> str:
    """Choose the analysis subdirectory from explicit config or enabled products."""
    configured = str(cfg.get("analysis_subdir") or "").strip()
    if configured and configured.lower() != "auto":
        return configured
    use_gaussian = cfg.get("enable_gaussian_overlay", False)
    use_spec = spectrogram_panel_enabled(cfg)
    show_bgsub = background_enabled_for_display(cfg)
    bgfit = background_enabled_for_fit(cfg) and use_gaussian and not show_bgsub
    if show_bgsub:
        parts = []
        if use_gaussian:
            parts.append("gaussian")
        if use_spec:
            parts.append("spectrogram")
        parts.append("background_subtracted")
        return "_".join(parts)
    if bgfit:
        return "gaussian_bgfit_overlay"
    if use_gaussian and use_spec:
        return "gaussian_spectrogram_overlay"
    if use_spec:
        return cfg.get("spectrogram_output_subdir", "radio_spectrogram_composite")
    if use_gaussian:
        return "gaussian_overlay"
    return "radio_source_maps"


def drift_output_path(cfg: dict, key: str) -> str:
    """Resolve drift product paths relative to the active analysis directory."""
    if key == "drift_rate_diagnostics_csv" and key not in cfg:
        key = "drift_diagnostics_csv"
    path = str(cfg.get(key, "") or "")
    if not path:
        path = str(key)
    if os.path.isabs(path):
        return path
    if key == "drift_rate_selection_json":
        return os.path.abspath(path)
    output_dir = cfg.get("output_dir") or os.getcwd()
    return os.path.join(output_dir, plot_output_subdir(cfg), path)
