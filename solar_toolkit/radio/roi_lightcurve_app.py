"""Streamlit frontend for radio ROI light-curve extraction."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from astropy.io import fits

from solar_toolkit.radio.centers import (
    POL_LCP,
    POL_RCP,
    POL_SUM,
    RadioImage,
    infer_polarization,
    iter_radio_images,
    parse_datetime_value,
    parse_frequency_mhz,
    parse_time_from_filename,
    select_radio_files,
)
from solar_toolkit.radio.roi_lightcurve import (
    DEFAULT_PAIR_TOLERANCE_SEC,
    PRODUCT_FILENAMES,
    RadioRoi,
    build_radio_roi_artifacts,
    extract_radio_roi_lightcurve,
    radio_roi_from_json,
    write_radio_roi_products,
)

__all__ = [
    "DEFAULT_APP_SETTINGS",
    "build_file_manifest",
    "build_parser",
    "build_reference_figure",
    "default_settings_path",
    "discover_frequency_options",
    "load_app_settings",
    "parse_row_selection_expression",
    "main",
    "resolve_app_settings",
    "save_app_settings",
    "selection_to_radio_roi",
]

DEFAULT_APP_SETTINGS: dict[str, Any] = {
    "radio_dir": "",
    "pattern": "*.fits",
    "recursive": True,
    "time_start": "",
    "time_end": "",
    "selected_freqs_mhz": [],
    "output_dir": "radio_roi_lightcurve_outputs",
    "pair_time_tolerance_sec": DEFAULT_PAIR_TOLERANCE_SEC,
    "polarization": POL_SUM,
    "metric": "raw_sum",
    "display_colormap": "Hot",
    "display_transform": "Linear",
    "display_range_mode": "Auto percentile",
    "display_range_scope": "Per frequency",
    "display_low_percentile": 99.7,
    "display_high_percentile": 99.99,
    "display_manual_min": 0.0,
    "display_manual_max": 1.0,
    "display_bad_color": "#000080",
    "display_use_custom_fov": True,
    "display_x_min_arcsec": -3000.0,
    "display_x_max_arcsec": 3000.0,
    "display_y_min_arcsec": -3000.0,
    "display_y_max_arcsec": 3000.0,
    "preview_max_side": 256,
    "page_size": 200,
}

APP_CLI_SETTING_MAP = {
    "radio_dir": "radio_dir",
    "pattern": "pattern",
    "recursive": "recursive",
    "time_start": "time_start",
    "time_end": "time_end",
    "output_dir": "output_dir",
    "pair_time_tolerance_sec": "pair_time_tolerance_sec",
    "polarization": "polarization",
    "metric": "metric",
}

PRODUCT_LABELS = {
    "csv": "Statistics CSV",
    "json": "ROI JSON",
    "reference_png": "Reference PNG",
    "lightcurve_png": "Light-curve PNG",
}
PRODUCT_MIME_TYPES = {
    "csv": "text/csv",
    "json": "application/json",
    "reference_png": "image/png",
    "lightcurve_png": "image/png",
}
DISPLAY_COLORMAPS = [
    "Hot",
    "Viridis",
    "Cividis",
    "Plasma",
    "Inferno",
    "Magma",
    "Turbo",
    "Greys",
    "Jet",
]
DISPLAY_TRANSFORMS = ["Linear", "Log10 positive"]
DISPLAY_RANGE_MODES = ["Auto percentile", "Manual min/max"]
DISPLAY_RANGE_SCOPES = ["Per frequency", "Shared/global"]
SELECTION_ACTIONS = ["Replace", "Add", "Remove"]
ROI_KEYS = ("candidate_roi", "confirmed_roi")
ANALYSIS_KEYS = ("analysis_df", "analysis_signature")
EXPORT_KEYS = ("export_artifacts", "export_signature")
REFERENCE_KEYS = (
    "reference_path",
    "reference_images",
    "reference_image",
    "reference_metadata",
    "reference_grid_signature",
    "reference_reuse_signature",
    "reference_preview_cache_key",
    "reference_preview_cache",
)
_REFERENCE_DECODER_VERSION = "first-2d-v1"
_REFERENCE_PLANE_CACHE_SIZE = 64
_NAT_INT64 = np.datetime64("NaT", "ns").astype("int64")


@dataclass(frozen=True)
class _ReferencePlan:
    freq_mhz: float
    row: int
    path: str
    paired_row: int | None
    paired_path: str | None
    obs_time: str
    delta_from_anchor_sec: float
    polarization: str


@dataclass(frozen=True)
class _ReferencePreview:
    raw_view: np.ndarray
    x_arcsec: np.ndarray
    y_arcsec: np.ndarray


@dataclass(frozen=True)
class _DisplayReferencePreview:
    display_view: np.ndarray
    x_arcsec: np.ndarray
    y_arcsec: np.ndarray


def build_parser() -> argparse.ArgumentParser:
    """Build a help parser for the Streamlit app."""

    parser = argparse.ArgumentParser(
        description=(
            "Launch the Streamlit radio ROI light-curve app. "
            "Run with: streamlit run solar_toolkit/radio/roi_lightcurve_app.py"
        )
    )
    parser.add_argument("--radio-dir", default=None, help="Default radio FITS folder.")
    parser.add_argument("--pattern", default=None, help="Default FITS glob pattern.")
    recursive = parser.add_mutually_exclusive_group()
    recursive.add_argument("--recursive", dest="recursive", action="store_true")
    recursive.add_argument("--no-recursive", dest="recursive", action="store_false")
    parser.set_defaults(recursive=None)
    parser.add_argument(
        "--time-start", default=None, help="Default inclusive time start."
    )
    parser.add_argument("--time-end", default=None, help="Default inclusive time end.")
    parser.add_argument("--output-dir", default=None, help="Default output folder.")
    parser.add_argument(
        "--pair-time-tolerance-sec",
        type=float,
        default=None,
        help="Default LCP/RCP pairing tolerance in seconds.",
    )
    parser.add_argument(
        "--polarization",
        choices=[POL_SUM, POL_LCP, POL_RCP, "all"],
        default=None,
        help="Default polarization mode.",
    )
    parser.add_argument(
        "--metric",
        choices=["raw_sum", "raw_mean", "raw_peak"],
        default=None,
        help="Default plotted metric.",
    )
    parser.add_argument(
        "--settings-file", default=None, help="Local JSON settings file."
    )
    parser.add_argument("--reset-settings", action="store_true")
    return parser


def default_settings_path() -> Path:
    """Return the per-user default app settings path."""

    return Path.home() / ".solar_toolkit" / "radio_roi_lightcurve_app_settings.json"


def load_app_settings(path: str | Path, *, reset: bool = False) -> dict[str, Any]:
    """Load app settings, falling back to defaults."""

    defaults = dict(DEFAULT_APP_SETTINGS)
    if reset:
        return defaults
    settings_path = Path(path).expanduser()
    if not settings_path.exists():
        return defaults
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults
    settings = dict(defaults)
    for key in defaults:
        if key in data:
            settings[key] = data[key]
    return settings


def save_app_settings(path: str | Path, settings: dict[str, Any]) -> Path:
    """Persist app settings to JSON."""

    settings_path = Path(path).expanduser()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        key: settings.get(key, DEFAULT_APP_SETTINGS[key])
        for key in DEFAULT_APP_SETTINGS
    }
    settings_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return settings_path


def resolve_app_settings(
    args: argparse.Namespace, stored: dict[str, Any]
) -> dict[str, Any]:
    """Apply CLI overrides to stored settings."""

    resolved = dict(DEFAULT_APP_SETTINGS)
    resolved.update(stored or {})
    for arg_name, setting_name in APP_CLI_SETTING_MAP.items():
        value = getattr(args, arg_name, None)
        if value is not None:
            resolved[setting_name] = value
    return resolved


def build_file_manifest(
    radio_dir: str | Path,
    *,
    pattern: str = "*.fits",
    recursive: bool = True,
    freqs: list[float] | tuple[float, ...] | None = None,
    time_start: str | datetime | None = None,
    time_end: str | datetime | None = None,
) -> pd.DataFrame:
    """Build a lightweight path manifest without loading FITS image arrays."""

    folder = Path(radio_dir).expanduser().resolve()
    if not folder.exists():
        raise FileNotFoundError(f"Radio data folder does not exist: {folder}")
    files = select_radio_files(
        folder,
        pattern=pattern,
        recursive=recursive,
        time_start=time_start,
        time_end=time_end,
    )
    blank_header = fits.Header()
    freq_set = _normalize_frequency_selection(freqs)
    rows: list[dict[str, Any]] = []
    for path in files:
        freq_mhz = _parse_frequency_hint_mhz(path, blank_header)
        if freq_set and not _frequency_matches_any(freq_mhz, freq_set):
            continue
        stat = path.stat()
        obs_time = parse_time_from_filename(path)
        rows.append(
            {
                "row": len(rows) + 1,
                "path": str(path),
                "relative_path": _relative_path_text(path, folder),
                "size_bytes": int(stat.st_size),
                "mtime_ns": int(stat.st_mtime_ns),
                "size_mib": round(float(stat.st_size) / 1024.0 / 1024.0, 3),
                "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(
                    timespec="seconds"
                ),
                "inferred_freq_mhz": freq_mhz,
                "inferred_polarization": infer_polarization(path, blank_header),
                "inferred_obs_time": (
                    obs_time.isoformat(timespec="milliseconds") if obs_time else ""
                ),
            }
        )
    return pd.DataFrame(rows)


def discover_frequency_options(
    radio_dir: str | Path,
    *,
    pattern: str = "*.fits",
    recursive: bool = True,
) -> pd.DataFrame:
    """Scan FITS paths and return available path-inferred frequency options."""

    folder = Path(radio_dir).expanduser().resolve()
    if not folder.exists():
        raise FileNotFoundError(f"Radio data folder does not exist: {folder}")
    files = select_radio_files(folder, pattern=pattern, recursive=recursive)
    blank_header = fits.Header()
    counts: dict[float, int] = {}
    unknown = 0
    for path in files:
        freq_mhz = _parse_frequency_hint_mhz(path, blank_header)
        if not np.isfinite(freq_mhz):
            unknown += 1
            continue
        key = round(float(freq_mhz), 6)
        counts[key] = counts.get(key, 0) + 1
    rows = [
        {"freq_mhz": freq, "file_count": count}
        for freq, count in sorted(counts.items(), key=lambda item: item[0])
    ]
    result = pd.DataFrame(rows)
    result.attrs["unknown_frequency_count"] = unknown
    result.attrs["total_file_count"] = len(files)
    return result


def selection_to_radio_roi(
    selection_event: dict[str, Any] | None,
    *,
    mode: str = "box",
    label: str = "",
) -> RadioRoi | None:
    """Convert a Plotly selection event into a radio ROI."""

    if not selection_event:
        return None
    selection = _event_get(selection_event, "selection", selection_event)
    mode_norm = str(mode).lower()
    if mode_norm == "lasso":
        coords = _selection_xy(selection, "lasso")
        if coords is None:
            coords = _selection_xy(selection, "lassoPoints")
        if coords is not None:
            xs, ys = coords
            vertices = list(zip(xs, ys, strict=False))
            if len(vertices) >= 3:
                return RadioRoi.from_polygon(vertices, label=label)
    if mode_norm == "box":
        coords = _selection_xy(selection, "box")
        if coords is not None:
            roi = _box_roi_from_xy(*coords, label=label)
            if roi is not None:
                return roi

    points = _event_get(selection, "points", []) or []
    xs = [
        float(_event_get(point, "x"))
        for point in points
        if _event_get(point, "x") is not None
    ]
    ys = [
        float(_event_get(point, "y"))
        for point in points
        if _event_get(point, "y") is not None
    ]
    if mode_norm == "lasso" and len(xs) >= 3 and len(ys) >= 3:
        return RadioRoi.from_polygon(list(zip(xs, ys, strict=False)), label=label)
    if mode_norm == "box" and xs and ys:
        return _box_roi_from_xy(xs, ys, label=label)
    return None


def build_reference_figure(
    item: RadioImage,
    *,
    roi: RadioRoi | None = None,
    low_percentile: float = 1.0,
    high_percentile: float = 99.7,
    max_side: int = 256,
    roi_mode: str = "box",
    display_config: dict[str, Any] | None = None,
    selection_enabled: bool = True,
):
    """Build the Plotly reference image used for ROI selection."""

    raw_preview = _prepare_reference_preview(item, max_side=max_side)
    preview = _DisplayReferencePreview(
        display_view=_display_array(raw_preview.raw_view, display_config),
        x_arcsec=raw_preview.x_arcsec,
        y_arcsec=raw_preview.y_arcsec,
    )
    return _build_reference_figure_from_preview(
        item,
        preview,
        roi=roi,
        low_percentile=low_percentile,
        high_percentile=high_percentile,
        roi_mode=roi_mode,
        display_config=display_config,
        selection_enabled=selection_enabled,
    )


def _build_reference_figure_from_preview(
    item: RadioImage,
    preview: _DisplayReferencePreview,
    *,
    roi: RadioRoi | None = None,
    low_percentile: float = 1.0,
    high_percentile: float = 99.7,
    roi_mode: str = "box",
    display_config: dict[str, Any] | None = None,
    selection_enabled: bool = True,
):
    import plotly.graph_objects as go

    display_view = preview.display_view
    x_arcsec = preview.x_arcsec
    y_arcsec = preview.y_arcsec
    zmin, zmax = _display_limits_for_item(
        item,
        display_view,
        display_config,
        fallback_percentiles=(float(low_percentile), float(high_percentile)),
    )
    fig = go.Figure()
    fig.add_trace(
        go.Heatmap(
            z=display_view,
            x=x_arcsec[0, :],
            y=y_arcsec[:, 0],
            colorscale=str((display_config or {}).get("colormap", "Viridis")),
            zmin=float(zmin),
            zmax=float(zmax),
            colorbar={"title": _display_colorbar_title(item, display_config)},
            hovertemplate="x=%{x:.2f}<br>y=%{y:.2f}<br>value=%{z:.4g}<extra></extra>",
        )
    )
    if selection_enabled:
        fig.add_trace(
            go.Scattergl(
                x=x_arcsec.ravel(),
                y=y_arcsec.ravel(),
                mode="markers",
                marker={"size": 4, "opacity": 0.01, "color": "white"},
                name="Selection grid",
                hoverinfo="skip",
                showlegend=False,
            )
        )
    if roi is not None:
        _add_roi_shape(fig, roi)
    dragmode: str | bool = (
        ("lasso" if str(roi_mode).lower() == "lasso" else "select")
        if selection_enabled
        else False
    )
    fig.update_layout(
        title=_reference_title(item),
        xaxis_title="HPLN / arcsec",
        yaxis_title="HPLT / arcsec",
        dragmode=dragmode,
        height=620,
        margin={"l": 60, "r": 20, "t": 60, "b": 55},
    )
    fig.update_yaxes(scaleanchor="x", scaleratio=1)
    _apply_plotly_fov(fig, display_config)
    return fig


def main(argv: list[str] | None = None) -> int:
    """Run the Streamlit app."""

    _run_streamlit_app(argv)
    return 0


def _run_streamlit_app(argv: list[str] | None = None) -> None:
    import streamlit as st

    args = build_parser().parse_args(argv)
    settings_file = (
        Path(args.settings_file).expanduser()
        if args.settings_file
        else default_settings_path()
    )
    stored = load_app_settings(settings_file, reset=bool(args.reset_settings))
    settings = resolve_app_settings(args, stored)

    st.set_page_config(page_title="Radio ROI Light Curve", layout="wide")
    _init_session_state(st)
    st.title("Radio ROI Light Curve")
    st.caption(
        "Load radio FITS files, select a time series, draw one ROI, preview the curve, then export."
    )

    current_settings = _render_load_step(st, settings, settings_file)
    manifest = st.session_state.get("loaded_manifest")
    if manifest is None:
        st.info("Enter a radio FITS folder and click Load Data.")
        return
    if manifest.empty:
        st.warning("No matching FITS files were found.")
        return

    selected_paths = _render_file_selection_step(st, manifest, current_settings)
    if not selected_paths:
        st.warning("Select one or more FITS files to continue.")
        return

    reference_images = _render_reference_step(
        st, selected_paths, manifest, current_settings
    )
    if not reference_images:
        st.warning("Render selected frequencies as reference images.")
        return

    display_config, reference_previews = _render_display_settings_step(
        st,
        reference_images,
        current_settings,
    )
    roi = _render_roi_step(st, reference_images, reference_previews, display_config)
    if roi is None:
        st.warning("Draw and confirm an ROI on the reference image.")
        return

    df = _render_analysis_step(
        st, selected_paths, reference_images, roi, current_settings, display_config
    )
    if df is None:
        return

    _render_export_step(
        st, df, selected_paths, reference_images, roi, current_settings, display_config
    )


def _render_load_step(
    st: Any, settings: dict[str, Any], settings_file: Path
) -> dict[str, Any]:
    st.subheader("Step 1. Load Data")
    c1, c2 = st.columns([3, 1])
    with c1:
        radio_dir = st.text_input(
            "Radio FITS folder",
            value=str(settings["radio_dir"]),
            placeholder=r"<PROJECT_ROOT>\2025\20250124\RS_0447-0450",
            help="Folder that contains the radio source FITS files. Subfolders such as 149MHz/LL are supported.",
        )
    with c2:
        pattern = st.text_input(
            "FITS pattern",
            value=str(settings["pattern"]),
            placeholder="*.fits",
            help="Glob pattern used to find FITS files before frequency and time filtering.",
        )
    c3, c4 = st.columns([1, 3])
    with c3:
        recursive = st.checkbox(
            "Search subfolders",
            value=bool(settings["recursive"]),
            help="Enable this when frequency and polarization files live in nested folders.",
        )
    source_settings = {
        "radio_dir": radio_dir,
        "pattern": pattern,
        "recursive": recursive,
    }
    source_signature = _source_signature(source_settings)
    with c4:
        if st.button(
            "Discover Frequencies",
            type="primary",
            help="Scan matching FITS paths and list available observing frequencies without loading image arrays.",
        ):
            _discover_frequencies_into_state(st, source_settings)

    frequency_options = st.session_state.get("frequency_options")
    if frequency_options is None:
        st.info("Click Discover Frequencies to list the bands available in the folder.")
    elif st.session_state.get("frequency_source_signature") != source_signature:
        st.warning(
            "The folder, pattern, or recursive setting changed. Discover frequencies again before loading."
        )
    elif frequency_options.empty:
        st.warning(
            "No path-inferred frequencies were found. You can still load all matching FITS files."
        )
    else:
        st.dataframe(frequency_options, hide_index=True, width="stretch")

    freq_values = _frequency_options_list(frequency_options)
    default_freqs = _default_selected_frequencies(
        freq_values, settings.get("selected_freqs_mhz", [])
    )
    selected_freqs = st.multiselect(
        "Frequencies to load (MHz)",
        options=freq_values,
        default=default_freqs,
        format_func=lambda value: f"{value:g} MHz",
        placeholder="Select one or more frequencies",
        help="Choose one or more radio bands. Empty means load all matching frequencies.",
    )

    range_hint = _manifest_time_range_hint(st.session_state.get("loaded_full_manifest"))
    c5, c6 = st.columns([1, 1])
    with c5:
        time_start = st.text_input(
            "Start time",
            value=str(settings["time_start"]),
            placeholder=range_hint.get("start", "2025-01-24T04:48:30"),
            help="Inclusive UTC start time. Leave blank to use the first available time shown in the data range hint.",
        )
    with c6:
        time_end = st.text_input(
            "End time",
            value=str(settings["time_end"]),
            placeholder=range_hint.get("end", "2025-01-24T04:49:00"),
            help="Inclusive UTC end time. Leave blank to use the last available time shown in the data range hint.",
        )
    if range_hint:
        st.caption(
            "Available selected-data time range: "
            f"{range_hint['start']} to {range_hint['end']} UTC "
            f"({range_hint['timed_count']:,} timed files; {range_hint['untimed_count']:,} without filename time)."
        )

    c6, c7, c8 = st.columns([1, 1, 2])
    with c6:
        pair_tolerance = st.number_input(
            "LCP/RCP pair tolerance (s)",
            min_value=0.0,
            value=float(settings["pair_time_tolerance_sec"]),
            step=0.1,
            help="Maximum time difference allowed when pairing LCP and RCP files for L+R analysis.",
        )
    with c7:
        polarization = st.selectbox(
            "Polarization",
            [POL_SUM, POL_LCP, POL_RCP, "all"],
            index=[POL_SUM, POL_LCP, POL_RCP, "all"].index(
                str(settings["polarization"])
            ),
            help="Analysis polarization mode. L+R pairs matching LCP/RCP files; all keeps individual planes.",
        )
    with c8:
        metric = st.selectbox(
            "Curve metric",
            ["raw_sum", "raw_mean", "raw_peak"],
            index=["raw_sum", "raw_mean", "raw_peak"].index(str(settings["metric"])),
            help="Statistic plotted in the preview light curve and exported PNG.",
        )
    output_dir = st.text_input(
        "Output folder",
        value=str(settings["output_dir"]),
        placeholder="radio_roi_lightcurve_outputs",
        help="Folder used by Save Selected Products. Browser downloads are available without saving locally.",
    )

    current_settings = {
        "radio_dir": radio_dir,
        "pattern": pattern,
        "recursive": recursive,
        "selected_freqs_mhz": [float(item) for item in selected_freqs],
        "time_start": time_start,
        "time_end": time_end,
        "output_dir": output_dir,
        "pair_time_tolerance_sec": pair_tolerance,
        "polarization": polarization,
        "metric": metric,
        "display_colormap": settings["display_colormap"],
        "display_transform": settings["display_transform"],
        "display_range_mode": settings["display_range_mode"],
        "display_range_scope": settings["display_range_scope"],
        "display_low_percentile": float(settings["display_low_percentile"]),
        "display_high_percentile": float(settings["display_high_percentile"]),
        "display_manual_min": float(settings["display_manual_min"]),
        "display_manual_max": float(settings["display_manual_max"]),
        "display_bad_color": settings["display_bad_color"],
        "display_use_custom_fov": bool(settings["display_use_custom_fov"]),
        "display_x_min_arcsec": float(settings["display_x_min_arcsec"]),
        "display_x_max_arcsec": float(settings["display_x_max_arcsec"]),
        "display_y_min_arcsec": float(settings["display_y_min_arcsec"]),
        "display_y_max_arcsec": float(settings["display_y_max_arcsec"]),
        "preview_max_side": int(settings["preview_max_side"]),
        "page_size": int(settings["page_size"]),
    }
    c9, c10, c11 = st.columns([1, 1, 3])
    with c9:
        if st.button(
            "Load Selected Frequencies",
            type="primary",
            help="Build a lightweight file index for the chosen frequencies, then apply the optional time range.",
        ):
            _load_manifest_into_state(st, current_settings)
    with c10:
        if st.button(
            "Apply Time Range",
            help="Reuse the already loaded frequency index and apply the start/end time fields without rescanning.",
        ):
            _apply_loaded_time_filter(st, current_settings)
    with c11:
        if st.button(
            "Save Defaults",
            help="Save the current form values as the app defaults on this machine.",
        ):
            save_app_settings(settings_file, current_settings)
            st.success(f"Saved {settings_file}")
    return current_settings


def _load_manifest_into_state(st: Any, settings: dict[str, Any]) -> None:
    try:
        manifest = build_file_manifest(
            settings["radio_dir"],
            pattern=settings["pattern"],
            recursive=bool(settings["recursive"]),
            freqs=settings.get("selected_freqs_mhz") or None,
        )
    except Exception as exc:  # noqa: BLE001 - visible app error.
        st.error(str(exc))
        return
    st.session_state["loaded_full_manifest"] = manifest
    st.session_state["loaded_source_signature"] = _source_signature(settings)
    _apply_loaded_time_filter(st, settings, clear_selection=True)


def _apply_loaded_time_filter(
    st: Any, settings: dict[str, Any], *, clear_selection: bool = False
) -> None:
    full_manifest = st.session_state.get("loaded_full_manifest")
    if full_manifest is None:
        st.warning("Load selected frequencies before applying a time range.")
        return
    try:
        manifest = _filter_manifest_by_time(
            full_manifest,
            time_start=settings.get("time_start") or None,
            time_end=settings.get("time_end") or None,
        )
    except ValueError as exc:
        st.error(str(exc))
        return
    st.session_state["loaded_manifest"] = manifest
    st.session_state["dataset_signature"] = _dataset_signature(settings, manifest)
    if clear_selection:
        _clear_keys(
            st,
            (
                "selected_paths",
                *REFERENCE_KEYS,
                *ROI_KEYS,
                *ANALYSIS_KEYS,
                *EXPORT_KEYS,
            ),
        )
    else:
        selected = set(st.session_state.get("selected_paths", []))
        valid = set(manifest["path"].astype(str)) if not manifest.empty else set()
        _set_selected_paths(st, selected & valid, manifest)
        _clear_keys(st, (*REFERENCE_KEYS, *ROI_KEYS, *ANALYSIS_KEYS, *EXPORT_KEYS))
    st.session_state["roi_chart_generation"] = (
        int(st.session_state.get("roi_chart_generation", 0)) + 1
    )
    st.success(f"Loaded {len(manifest):,} FITS files.")


def _render_file_selection_step(
    st: Any,
    manifest: pd.DataFrame,
    settings: dict[str, Any],
) -> list[str]:
    st.subheader("Step 2. Choose Data Files")
    query = st.text_input(
        "Filter files",
        value="",
        placeholder="Search relative path, time, frequency, or polarization",
        help="Narrows the table before selecting by page, all filtered files, or File # expression.",
    )
    filtered = _filter_manifest(manifest, query)
    page_size = int(settings.get("page_size", 200))
    page_count = max(1, int(np.ceil(len(filtered) / max(1, page_size))))
    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 1])
    with c1:
        page = int(
            st.number_input(
                "Page",
                min_value=1,
                max_value=page_count,
                value=1,
                step=1,
                help="Table page number. File # values remain stable across pages.",
            )
        )
    with c2:
        if st.button(
            "Select Page", help="Add every file visible on the current table page."
        ):
            page_paths = _page_paths(filtered, page=page, page_size=page_size)
            _set_selected_paths(
                st,
                set(st.session_state.get("selected_paths", [])) | set(page_paths),
                manifest,
            )
    with c3:
        if st.button(
            "Select All Filtered", help="Add all rows matching the current filter."
        ):
            _set_selected_paths(
                st,
                set(st.session_state.get("selected_paths", []))
                | set(filtered["path"].astype(str)),
                manifest,
            )
    with c4:
        if st.button(
            "Invert Filtered",
            help="Toggle selection for all rows matching the current filter.",
        ):
            filtered_paths = set(filtered["path"].astype(str))
            current = set(st.session_state.get("selected_paths", []))
            _set_selected_paths(
                st, (current - filtered_paths) | (filtered_paths - current), manifest
            )
    with c5:
        if st.button("Clear Selection", help="Remove every selected file."):
            _set_selected_paths(st, set(), manifest)

    q1, q2, q3 = st.columns([2, 1, 1])
    with q1:
        number_expression = st.text_input(
            "Quick select by File #",
            value="",
            placeholder="1, 3, 8-20",
            help="Use comma-separated File # values or inclusive ranges. Example: 1,3,8-20.",
        )
    with q2:
        selection_action = st.selectbox(
            "Quick action",
            SELECTION_ACTIONS,
            help="Replace uses only the entered numbers; Add and Remove modify the current selection.",
        )
    with q3:
        if st.button(
            "Apply Numbers",
            help="Apply the File # expression to rows that are still present after filtering.",
        ):
            _apply_number_selection(
                st, manifest, filtered, number_expression, selection_action
            )

    start = (page - 1) * page_size
    end = start + page_size
    page_df = filtered.iloc[start:end].copy()
    selected = set(st.session_state.get("selected_paths", []))
    page_df.insert(0, "selected", page_df["path"].astype(str).isin(selected))
    edited = st.data_editor(
        page_df[
            [
                "selected",
                "row",
                "relative_path",
                "inferred_obs_time",
                "inferred_freq_mhz",
                "inferred_polarization",
                "size_mib",
                "path",
            ]
        ],
        key=f"radio_roi_file_editor_{st.session_state.get('dataset_signature', '')}_{page}",
        disabled=[
            "row",
            "relative_path",
            "inferred_obs_time",
            "inferred_freq_mhz",
            "inferred_polarization",
            "size_bytes",
            "mtime_ns",
            "size_mib",
            "path",
        ],
        column_config={
            "selected": st.column_config.CheckboxColumn(
                "Select", help="Toggle this file in the selected set."
            ),
            "row": st.column_config.NumberColumn(
                "File #", help="Stable sequence number for quick selection."
            ),
            "relative_path": st.column_config.TextColumn(
                "Relative path", help="Path relative to the radio FITS folder."
            ),
            "inferred_obs_time": st.column_config.TextColumn(
                "Time", help="UTC time inferred from the filename."
            ),
            "inferred_freq_mhz": st.column_config.NumberColumn(
                "MHz", help="Frequency inferred from path or FITS-style naming."
            ),
            "inferred_polarization": st.column_config.TextColumn(
                "Pol",
                help="Polarization inferred from folder, header text, or filename.",
            ),
            "size_bytes": None,
            "mtime_ns": None,
            "size_mib": st.column_config.NumberColumn("MiB", help="File size in MiB."),
            "path": st.column_config.TextColumn(
                "Absolute path", help="Full FITS file path used during analysis."
            ),
        },
        hide_index=True,
        width="stretch",
    )
    current_page_paths = set(page_df["path"].astype(str))
    edited_selected = set(
        edited.loc[edited["selected"].astype(bool), "path"].astype(str)
    )
    _set_selected_paths(
        st,
        (set(st.session_state.get("selected_paths", [])) - current_page_paths)
        | edited_selected,
        manifest,
    )
    selected_paths = _order_paths_by_manifest(
        st.session_state.get("selected_paths", []), manifest
    )
    st.caption(
        f"Showing {len(page_df):,} of {len(filtered):,} filtered files. Selected {len(selected_paths):,} files."
    )
    return selected_paths


def _render_reference_step(
    st: Any,
    selected_paths: list[str],
    manifest: pd.DataFrame,
    settings: dict[str, Any],
) -> list[RadioImage]:
    st.subheader("Step 3. Render Reference Images")
    selected_set = set(selected_paths)
    available = manifest.loc[manifest["path"].astype(str).isin(selected_set)].copy()
    if available.empty:
        return []
    frequencies = _manifest_frequency_values(available)
    current_primary = st.session_state.get("primary_reference_freq_mhz")
    primary_default = (
        current_primary
        if current_primary in frequencies
        else (frequencies[0] if frequencies else math.nan)
    )
    selected_rows = set(available["row"].astype(int).tolist())
    current_anchor = st.session_state.get("reference_file_number")
    anchor_default = (
        int(current_anchor)
        if current_anchor in selected_rows
        else int(available.iloc[0]["row"])
    )
    preview_pol_options = [POL_SUM, POL_LCP, POL_RCP]
    stored_preview_pol = st.session_state.get("preview_polarization")
    default_preview_pol = (
        stored_preview_pol
        if stored_preview_pol in preview_pol_options
        else (
            settings["polarization"]
            if settings["polarization"] in preview_pol_options
            else POL_SUM
        )
    )
    with st.form("radio_roi_reference_grid_form"):
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            primary_frequency = st.selectbox(
                "Primary ROI frequency",
                frequencies,
                index=(
                    frequencies.index(primary_default)
                    if primary_default in frequencies
                    else 0
                ),
                format_func=lambda value: f"{value:g} MHz",
                help="The first rendered panel is interactive. Draw the ROI there; it is stored in HPLN/HPLT arcsec and applied to all frequencies.",
            )
        with c2:
            anchor_number = int(
                st.number_input(
                    "Anchor File #",
                    min_value=int(manifest["row"].min()),
                    max_value=int(manifest["row"].max()),
                    value=anchor_default,
                    step=1,
                    help="Representative images are chosen nearest to this selected file's time in each frequency.",
                )
            )
        with c3:
            preview_polarization = st.selectbox(
                "Preview polarization",
                preview_pol_options,
                index=preview_pol_options.index(default_preview_pol),
                help="Display-only polarization used for reference images. Analysis uses the Step 1 polarization setting.",
            )
        submitted = st.form_submit_button(
            "Render Reference Grid",
            type="primary",
            help="Submit these controls once, then load or reuse one representative image for each selected frequency.",
        )

    if submitted and anchor_number not in selected_rows:
        st.error("Anchor File # must be one of the selected rows.")
    elif submitted:
        try:
            pair_tolerance_sec = float(settings["pair_time_tolerance_sec"])
            references = list(st.session_state.get("reference_images") or [])
            reuse_signature = _reference_reuse_signature(
                st,
                primary_frequency=float(primary_frequency),
                anchor_number=anchor_number,
                preview_polarization=str(preview_polarization),
                pair_tolerance_sec=pair_tolerance_sec,
            )
            if references and reuse_signature == st.session_state.get(
                "reference_reuse_signature"
            ):
                st.info("Reused the cached reference grid; no FITS files were reread.")
            else:
                plans = _plan_reference_grid(
                    available,
                    primary_frequency=float(primary_frequency),
                    anchor_number=anchor_number,
                    preview_polarization=str(preview_polarization),
                    pair_tolerance_sec=pair_tolerance_sec,
                )
                signature = _reference_grid_signature(
                    available,
                    plans,
                    primary_frequency=float(primary_frequency),
                    anchor_number=anchor_number,
                    preview_polarization=str(preview_polarization),
                    pair_tolerance_sec=pair_tolerance_sec,
                )
                if (
                    signature == st.session_state.get("reference_grid_signature")
                    and references
                ):
                    st.info(
                        "Reused the cached reference grid; no FITS files were reread."
                    )
                else:
                    references, reference_meta = _materialize_reference_grid(plans)
                    if not references:
                        raise RuntimeError(
                            "No usable representative image could be loaded."
                        )
                    _clear_keys(
                        st,
                        ("reference_preview_cache_key", "reference_preview_cache"),
                    )
                    st.session_state["reference_images"] = references
                    st.session_state["reference_metadata"] = reference_meta
                    st.session_state["reference_path"] = str(references[0].path)
                    st.session_state["reference_grid_signature"] = signature
                    _clear_keys(st, (*ROI_KEYS, *ANALYSIS_KEYS, *EXPORT_KEYS))
                    st.session_state["roi_chart_generation"] = (
                        int(st.session_state.get("roi_chart_generation", 0)) + 1
                    )
            if not references:
                raise RuntimeError("No usable representative image could be loaded.")
            st.session_state["reference_file_number"] = anchor_number
            st.session_state["primary_reference_freq_mhz"] = float(primary_frequency)
            st.session_state["preview_polarization"] = str(preview_polarization)
            st.session_state["reference_pair_tolerance_sec"] = pair_tolerance_sec
            st.session_state["reference_reuse_signature"] = _reference_reuse_signature(
                st,
                primary_frequency=float(primary_frequency),
                anchor_number=anchor_number,
                preview_polarization=str(preview_polarization),
                pair_tolerance_sec=pair_tolerance_sec,
            )
        except Exception as exc:  # noqa: BLE001 - visible app error.
            st.error(str(exc))
            return []
    references = list(st.session_state.get("reference_images") or [])
    reference_meta = list(st.session_state.get("reference_metadata") or [])
    referenced_paths = {
        str(path)
        for meta in reference_meta
        for path in (meta.get("path"), meta.get("paired_path"))
        if path
    }
    if not references or not referenced_paths.issubset(selected_set):
        _clear_keys(st, (*REFERENCE_KEYS, *ROI_KEYS, *ANALYSIS_KEYS, *EXPORT_KEYS))
        return []
    return references


def _render_display_settings_step(
    st: Any,
    reference_images: list[RadioImage],
    settings: dict[str, Any],
) -> tuple[dict[str, Any], list[_DisplayReferencePreview]]:
    st.subheader("Step 4. Display Settings")
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    with c1:
        colormap = st.selectbox(
            "Colormap",
            DISPLAY_COLORMAPS,
            index=_option_index(DISPLAY_COLORMAPS, str(settings["display_colormap"])),
            help="Common radio image color map. Hot matches the source-visibility preset from the existing radio plots.",
        )
    with c2:
        transform = st.selectbox(
            "Intensity transform",
            DISPLAY_TRANSFORMS,
            index=_option_index(DISPLAY_TRANSFORMS, str(settings["display_transform"])),
            help="Linear shows raw values; Log10 positive shows log10 only for positive pixels.",
        )
    with c3:
        range_mode = st.selectbox(
            "Intensity range",
            DISPLAY_RANGE_MODES,
            index=_option_index(
                DISPLAY_RANGE_MODES, str(settings["display_range_mode"])
            ),
            help="Auto percentile derives limits from the displayed representative images; manual uses entered raw FITS values.",
        )
    with c4:
        range_scope = st.selectbox(
            "Range scope",
            DISPLAY_RANGE_SCOPES,
            index=_option_index(
                DISPLAY_RANGE_SCOPES, str(settings["display_range_scope"])
            ),
            help="Per frequency computes limits per panel; shared/global uses one scale for every displayed frequency.",
        )

    config: dict[str, Any] = {
        "colormap": colormap,
        "transform": transform,
        "range_mode": range_mode,
        "range_scope": range_scope,
        "bad_color": str(settings["display_bad_color"]),
        "preview_max_side": int(settings["preview_max_side"]),
    }
    if range_mode == "Auto percentile":
        c5, c6 = st.columns([1, 1])
        with c5:
            low = st.number_input(
                "Low percentile",
                min_value=0.0,
                max_value=100.0,
                value=float(settings["display_low_percentile"]),
                step=0.1,
                help="Lower auto display percentile. The source-visibility preset uses 99.7.",
            )
        with c6:
            high = st.number_input(
                "High percentile",
                min_value=0.0,
                max_value=100.0,
                value=float(settings["display_high_percentile"]),
                step=0.01,
                help="Upper auto display percentile. The source-visibility preset uses 99.99.",
            )
        config["low_percentile"] = min(float(low), float(high))
        config["high_percentile"] = max(float(low), float(high))
    elif range_scope == "Per frequency":
        display_limits, raw_limits = _manual_range_editor(
            st, reference_images, settings, transform=transform
        )
        config["limits_by_frequency"] = display_limits
        config["manual_ranges_raw"] = raw_limits
        config["range_mode"] = "Manual min/max"
    else:
        c7, c8 = st.columns([1, 1])
        with c7:
            manual_min = st.number_input(
                "Manual min",
                value=float(settings["display_manual_min"]),
                help="Raw FITS-unit lower display limit. In log mode this value must be positive.",
            )
        with c8:
            manual_max = st.number_input(
                "Manual max",
                value=float(settings["display_manual_max"]),
                help="Raw FITS-unit upper display limit. In log mode this value must be positive.",
            )
        config["manual_min"] = float(manual_min)
        config["manual_max"] = float(manual_max)

    f1, f2, f3, f4, f5 = st.columns([1, 1, 1, 1, 1])
    with f1:
        use_custom_fov = st.checkbox(
            "Use custom FOV",
            value=bool(settings["display_use_custom_fov"]),
            help="Limit the displayed HPLN/HPLT range. It does not crop the scientific ROI extraction.",
        )
    with f2:
        x_min = st.number_input(
            "HPLN min",
            value=float(settings["display_x_min_arcsec"]),
            help="Left display bound in arcsec.",
        )
    with f3:
        x_max = st.number_input(
            "HPLN max",
            value=float(settings["display_x_max_arcsec"]),
            help="Right display bound in arcsec.",
        )
    with f4:
        y_min = st.number_input(
            "HPLT min",
            value=float(settings["display_y_min_arcsec"]),
            help="Bottom display bound in arcsec.",
        )
    with f5:
        y_max = st.number_input(
            "HPLT max",
            value=float(settings["display_y_max_arcsec"]),
            help="Top display bound in arcsec.",
        )
    config.update(
        {
            "use_custom_fov": bool(use_custom_fov),
            "x_min_arcsec": float(x_min),
            "x_max_arcsec": float(x_max),
            "y_min_arcsec": float(y_min),
            "y_max_arcsec": float(y_max),
        }
    )
    raw_previews = _reference_previews_from_state(
        st,
        reference_images,
        max_side=int(settings["preview_max_side"]),
    )
    display_previews = [
        _DisplayReferencePreview(
            display_view=_display_array(preview.raw_view, config),
            x_arcsec=preview.x_arcsec,
            y_arcsec=preview.y_arcsec,
        )
        for preview in raw_previews
    ]
    _attach_auto_display_limits(
        reference_images,
        config,
        previews=display_previews,
    )
    return config, display_previews


def _render_roi_step(
    st: Any,
    references: list[RadioImage],
    previews: list[_DisplayReferencePreview],
    display_config: dict[str, Any],
) -> RadioRoi | None:
    st.subheader("Step 5. Draw and Confirm ROI")
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        roi_mode = st.radio(
            "ROI mode",
            ["box", "lasso"],
            horizontal=True,
            help="Box creates a rectangular HPLN/HPLT ROI; lasso creates a polygon ROI.",
        )
    candidate = _session_roi(st, "candidate_roi")
    confirmed = _session_roi(st, "confirmed_roi")
    active_roi = candidate or confirmed
    chart_key = (
        f"radio_roi_selection_chart_"
        f"{st.session_state.get('roi_chart_generation', 0)}_{roi_mode}"
    )
    st.caption(
        "Draw once on the first panel. The confirmed HPLN/HPLT ROI is overlaid on every loaded frequency."
    )
    columns = st.columns(min(3, max(1, len(references))))
    event = None
    for index, (reference, preview) in enumerate(
        zip(references, previews, strict=True)
    ):
        with columns[index % len(columns)]:
            figure = _build_reference_figure_from_preview(
                reference,
                preview,
                roi=active_roi,
                roi_mode=roi_mode,
                display_config=display_config,
                selection_enabled=index == 0,
            )
            if index == 0:
                event = st.plotly_chart(
                    figure,
                    width="stretch",
                    on_select="rerun",
                    selection_mode=(roi_mode,),
                    key=chart_key,
                )
            else:
                st.plotly_chart(
                    figure,
                    width="stretch",
                    key=f"{chart_key}_{index}",
                )
    selected_roi = selection_to_radio_roi(event, mode=roi_mode, label="active")
    if selected_roi is not None:
        st.session_state["candidate_roi"] = selected_roi.to_json_dict()
        candidate = selected_roi
    with c2:
        if st.button(
            "Confirm ROI",
            type="primary",
            disabled=candidate is None,
            help="Lock the staged ROI for analysis and export.",
        ):
            st.session_state["confirmed_roi"] = candidate.to_json_dict()
            _clear_keys(st, ANALYSIS_KEYS + EXPORT_KEYS)
            confirmed = candidate
    with c3:
        uploaded = st.file_uploader(
            "Load ROI JSON",
            type=["json"],
            help="Load a previously exported ROI JSON and stage its HPLN/HPLT selection.",
        )
        if uploaded is not None:
            try:
                st.session_state["candidate_roi"] = radio_roi_from_json(
                    json.loads(uploaded.getvalue())
                ).to_json_dict()
                _clear_keys(st, ANALYSIS_KEYS + EXPORT_KEYS)
                candidate = _session_roi(st, "candidate_roi")
            except Exception as exc:  # noqa: BLE001 - visible app error.
                st.error(str(exc))
    if st.button("Clear ROI", help="Remove both staged and confirmed ROI selections."):
        _clear_keys(st, (*ROI_KEYS, *ANALYSIS_KEYS, *EXPORT_KEYS))
        st.session_state["roi_chart_generation"] = (
            int(st.session_state.get("roi_chart_generation", 0)) + 1
        )
        return None
    if confirmed is not None:
        st.success("ROI confirmed.")
        st.json(confirmed.to_json_dict(), expanded=False)
    elif candidate is not None:
        st.info("ROI is staged. Click Confirm ROI before analysis.")
        st.json(candidate.to_json_dict(), expanded=False)
    return confirmed


def _render_analysis_step(
    st: Any,
    selected_paths: list[str],
    references: list[RadioImage],
    roi: RadioRoi,
    settings: dict[str, Any],
    display_config: dict[str, Any],
) -> pd.DataFrame | None:
    st.subheader("Step 6. Analyze and Preview")
    signature = _analysis_signature(selected_paths, roi, settings)
    if st.button(
        "Analyze Selected Files",
        type="primary",
        help="Extract full-resolution ROI statistics from every selected file using the confirmed HPLN/HPLT ROI.",
    ):
        with st.spinner(
            "Extracting full-resolution ROI statistics from selected files..."
        ):
            try:
                df = extract_radio_roi_lightcurve(
                    settings["radio_dir"],
                    roi,
                    pattern=settings["pattern"],
                    recursive=bool(settings["recursive"]),
                    files=selected_paths,
                    polarization=settings["polarization"],
                    pair_time_tolerance_sec=float(settings["pair_time_tolerance_sec"]),
                )
            except Exception as exc:  # noqa: BLE001 - visible app error.
                st.error(str(exc))
                return None
        st.session_state["analysis_df"] = df
        st.session_state["analysis_signature"] = signature
        _clear_keys(st, EXPORT_KEYS)
    df = st.session_state.get("analysis_df")
    if df is None or st.session_state.get("analysis_signature") != signature:
        st.info("Click Analyze Selected Files to compute the light curve.")
        return None
    st.dataframe(df, width="stretch")
    preview = build_radio_roi_artifacts(
        df,
        roi,
        reference_images=references,
        display_config=display_config,
        run_metadata=_run_metadata(
            selected_paths, _settings_with_reference(st, settings, display_config)
        ),
        metric=str(settings["metric"]),
        selected_products=("lightcurve_png",),
    )
    st.image(preview["lightcurve_png"])
    return df


def _render_export_step(
    st: Any,
    df: pd.DataFrame,
    selected_paths: list[str],
    references: list[RadioImage],
    roi: RadioRoi,
    settings: dict[str, Any],
    display_config: dict[str, Any],
) -> None:
    st.subheader("Step 7. Export and Download")
    c1, c2, c3, c4 = st.columns(4)
    product_keys = []
    for column, key in zip((c1, c2, c3, c4), PRODUCT_FILENAMES, strict=False):
        with column:
            if st.checkbox(
                PRODUCT_LABELS[key],
                value=True,
                key=f"export_{key}",
                help=f"Include {PRODUCT_FILENAMES[key]} in browser downloads and local save.",
            ):
                product_keys.append(key)
    if not product_keys:
        st.warning("Select at least one export product.")
        return
    artifacts = build_radio_roi_artifacts(
        df,
        roi,
        reference_images=references,
        display_config=display_config,
        run_metadata=_run_metadata(
            selected_paths, _settings_with_reference(st, settings, display_config)
        ),
        metric=str(settings["metric"]),
        selected_products=tuple(product_keys),
    )
    if len(artifacts) > 1:
        st.download_button(
            "Download ZIP",
            data=_zip_artifacts(artifacts),
            file_name="radio_roi_lightcurve_exports.zip",
            mime="application/zip",
            on_click="ignore",
            help="Download all selected products as one ZIP archive.",
        )
    for key, payload in artifacts.items():
        st.download_button(
            f"Download {PRODUCT_LABELS[key]}",
            data=payload,
            file_name=PRODUCT_FILENAMES[key],
            mime=PRODUCT_MIME_TYPES[key],
            on_click="ignore",
            help=f"Download only {PRODUCT_FILENAMES[key]}.",
        )
    if st.button(
        "Save Selected Products",
        help="Write selected products to the output folder on disk.",
    ):
        products = write_radio_roi_products(
            df,
            roi,
            settings["output_dir"],
            reference_images=references,
            display_config=display_config,
            run_metadata=_run_metadata(
                selected_paths, _settings_with_reference(st, settings, display_config)
            ),
            metric=str(settings["metric"]),
            selected_products=tuple(product_keys),
        )
        st.success(f"Saved products to {products['output_dir']}")


def _init_session_state(st: Any) -> None:
    st.session_state.setdefault("selected_paths", [])
    st.session_state.setdefault("selection_revision", 0)
    st.session_state.setdefault("roi_chart_generation", 0)


def _clear_keys(st: Any, keys: tuple[str, ...]) -> None:
    for key in keys:
        st.session_state.pop(key, None)


def _set_selected_paths(
    st: Any, paths: set[str], manifest: pd.DataFrame | None = None
) -> None:
    selected = _order_paths_by_manifest(paths, manifest)
    previous = _order_paths_by_manifest(
        st.session_state.get("selected_paths", []), manifest
    )
    if selected == previous:
        return
    st.session_state["selected_paths"] = selected
    st.session_state["selection_revision"] = (
        int(st.session_state.get("selection_revision", 0)) + 1
    )
    _clear_keys(st, (*REFERENCE_KEYS, *ROI_KEYS, *ANALYSIS_KEYS, *EXPORT_KEYS))
    st.session_state["roi_chart_generation"] = (
        int(st.session_state.get("roi_chart_generation", 0)) + 1
    )


def _discover_frequencies_into_state(st: Any, settings: dict[str, Any]) -> None:
    try:
        options = discover_frequency_options(
            settings["radio_dir"],
            pattern=settings["pattern"],
            recursive=bool(settings["recursive"]),
        )
    except Exception as exc:  # noqa: BLE001 - visible app error.
        st.error(str(exc))
        return
    st.session_state["frequency_options"] = options
    st.session_state["frequency_source_signature"] = _source_signature(settings)
    _clear_keys(
        st,
        (
            "loaded_manifest",
            "loaded_full_manifest",
            "selected_paths",
            *REFERENCE_KEYS,
            *ROI_KEYS,
            *ANALYSIS_KEYS,
            *EXPORT_KEYS,
        ),
    )
    total = int(options.attrs.get("total_file_count", 0))
    unknown = int(options.attrs.get("unknown_frequency_count", 0))
    st.success(
        f"Discovered {len(options):,} frequency bands from {total:,} matching FITS files."
    )
    if unknown:
        st.warning(
            f"{unknown:,} matching files did not expose a frequency in the path or filename."
        )


def _source_signature(settings: dict[str, Any]) -> str:
    payload = {
        "radio_dir": str(settings.get("radio_dir", "")),
        "pattern": str(settings.get("pattern", "")),
        "recursive": bool(settings.get("recursive", True)),
    }
    return json.dumps(payload, sort_keys=True)


def _frequency_options_list(options: pd.DataFrame | None) -> list[float]:
    if options is None or options.empty or "freq_mhz" not in options.columns:
        return []
    return [float(item) for item in options["freq_mhz"].dropna().tolist()]


def _default_selected_frequencies(options: list[float], stored: Any) -> list[float]:
    if not options:
        return []
    requested = _normalize_frequency_selection(stored)
    if not requested:
        return options
    selected = [freq for freq in options if _frequency_matches_any(freq, requested)]
    return selected or options


def _normalize_frequency_selection(freqs: Any) -> set[float]:
    if freqs in (None, ""):
        return set()
    values = freqs if isinstance(freqs, (list, tuple, set)) else [freqs]
    selected: set[float] = set()
    for value in values:
        try:
            freq = float(value)
        except (TypeError, ValueError):
            continue
        if np.isfinite(freq):
            selected.add(freq)
    return selected


def _frequency_matches_any(value: float, freqs: set[float]) -> bool:
    if not np.isfinite(value):
        return False
    return any(
        abs(float(value) - float(freq)) <= max(1e-6, abs(float(freq)) * 1e-5)
        for freq in freqs
    )


def _parse_frequency_hint_mhz(path: Path, header: fits.Header) -> float:
    for part in reversed(path.parts):
        match = re.search(
            r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>ghz|mhz|khz|hz)\b",
            part,
            flags=re.IGNORECASE,
        )
        if match:
            value = float(match.group("value"))
            unit = match.group("unit").lower()
            if unit == "ghz":
                return value * 1000.0
            if unit == "khz":
                return value / 1000.0
            if unit == "hz":
                return value / 1_000_000.0
            return value
    return parse_frequency_mhz(path, header)


def _manifest_time_range_hint(manifest: pd.DataFrame | None) -> dict[str, Any]:
    if (
        manifest is None
        or manifest.empty
        or "inferred_obs_time" not in manifest.columns
    ):
        return {}
    times = pd.to_datetime(
        manifest["inferred_obs_time"].replace("", pd.NA), errors="coerce"
    )
    timed = times.dropna()
    if timed.empty:
        return {
            "start": "",
            "end": "",
            "timed_count": 0,
            "untimed_count": len(manifest),
        }
    return {
        "start": timed.min().isoformat(timespec="milliseconds"),
        "end": timed.max().isoformat(timespec="milliseconds"),
        "timed_count": int(timed.size),
        "untimed_count": int(times.isna().sum()),
    }


def _filter_manifest_by_time(
    manifest: pd.DataFrame,
    *,
    time_start: str | datetime | None,
    time_end: str | datetime | None,
) -> pd.DataFrame:
    start = _parse_optional_time(time_start, "Start time")
    end = _parse_optional_time(time_end, "End time")
    if start is not None and end is not None and start > end:
        raise ValueError("Start time must be earlier than or equal to end time.")
    if start is None and end is None:
        return manifest.copy()
    times = pd.to_datetime(
        manifest["inferred_obs_time"].replace("", pd.NA), errors="coerce"
    )
    mask = times.notna()
    if start is not None:
        mask &= times >= pd.Timestamp(start)
    if end is not None:
        mask &= times <= pd.Timestamp(end)
    return manifest.loc[mask].copy()


def _parse_optional_time(value: str | datetime | None, label: str) -> datetime | None:
    if value in (None, ""):
        return None
    parsed = parse_datetime_value(value)
    if parsed is None:
        raise ValueError(f"{label} is not a recognized time: {value}")
    return parsed


def parse_row_selection_expression(raw: str) -> list[int]:
    """Parse comma-separated File # values and inclusive ranges."""

    text = str(raw or "").strip()
    if not text:
        return []
    values: list[int] = []
    seen: set[int] = set()
    for token in [item.strip() for item in text.split(",") if item.strip()]:
        match = re.fullmatch(r"(?P<start>\d+)(?:\s*-\s*(?P<end>\d+))?", token)
        if not match:
            raise ValueError(f"Invalid File # token: {token!r}")
        start = int(match.group("start"))
        end = int(match.group("end") or start)
        if end < start:
            raise ValueError(f"File # ranges must be increasing: {token!r}")
        for value in range(start, end + 1):
            if value not in seen:
                seen.add(value)
                values.append(value)
    return values


def _apply_number_selection(
    st: Any,
    manifest: pd.DataFrame,
    filtered: pd.DataFrame,
    expression: str,
    action: str,
) -> None:
    try:
        numbers = parse_row_selection_expression(expression)
    except ValueError as exc:
        st.error(str(exc))
        return
    if not numbers:
        st.warning("Enter one or more File # values, for example 1,3,8-20.")
        return
    row_to_path = dict(
        zip(filtered["row"].astype(int), filtered["path"].astype(str), strict=False)
    )
    selected_paths = {
        row_to_path[number] for number in numbers if number in row_to_path
    }
    skipped = [number for number in numbers if number not in row_to_path]
    current = set(st.session_state.get("selected_paths", []))
    if action == "Replace":
        updated = selected_paths
    elif action == "Remove":
        updated = current - selected_paths
    else:
        updated = current | selected_paths
    _set_selected_paths(st, updated, manifest)
    if skipped:
        st.warning(
            f"Skipped {len(skipped):,} File # values outside the current filtered table."
        )


def _order_paths_by_manifest(paths: Any, manifest: pd.DataFrame | None) -> list[str]:
    unique_paths = {str(path) for path in (paths or [])}
    if (
        manifest is None
        or manifest.empty
        or "path" not in manifest.columns
        or "row" not in manifest.columns
    ):
        return sorted(unique_paths)
    row_by_path = dict(
        zip(manifest["path"].astype(str), manifest["row"].astype(int), strict=False)
    )
    return sorted(unique_paths, key=lambda path: (row_by_path.get(path, 10**12), path))


def _filter_manifest(manifest: pd.DataFrame, query: str) -> pd.DataFrame:
    if not query.strip():
        return manifest
    text = query.strip().casefold()
    searchable = manifest[
        [
            "relative_path",
            "inferred_obs_time",
            "inferred_polarization",
            "inferred_freq_mhz",
        ]
    ].astype(str)
    mask = searchable.apply(
        lambda column: column.str.casefold().str.contains(text, regex=False)
    ).any(axis=1)
    return manifest.loc[mask].copy()


def _page_paths(filtered: pd.DataFrame, *, page: int, page_size: int) -> list[str]:
    start = (int(page) - 1) * int(page_size)
    end = start + int(page_size)
    return filtered.iloc[start:end]["path"].astype(str).tolist()


def _load_first_radio_image(path: str | Path) -> RadioImage:
    for item in iter_radio_images(path):
        return item
    raise RuntimeError(f"No usable 2D radio image plane found in {path}")


@lru_cache(maxsize=_REFERENCE_PLANE_CACHE_SIZE)
def _cached_first_radio_image(
    path: str,
    size_bytes: int,
    mtime_ns: int,
    decoder_version: str = _REFERENCE_DECODER_VERSION,
) -> RadioImage:
    del size_bytes, mtime_ns, decoder_version
    item = _load_first_radio_image(path)
    image = np.asarray(item.image, dtype=float)
    image.setflags(write=False)
    return RadioImage(
        path=Path(path),
        hdu_index=item.hdu_index,
        image=image,
        header=item.header.copy(),
        pol=item.pol,
        freq_mhz=float(item.freq_mhz),
        obs_time=item.obs_time,
        source_label=item.source_label,
    )


def _cached_reference_image(path: str | Path) -> RadioImage:
    resolved = Path(path).expanduser().resolve()
    stat = resolved.stat()
    return _cached_first_radio_image(
        str(resolved),
        int(stat.st_size),
        int(stat.st_mtime_ns),
    )


def _clone_reference_image(item: RadioImage, *, source_label: str) -> RadioImage:
    return RadioImage(
        path=item.path,
        hdu_index=item.hdu_index,
        image=item.image,
        header=item.header.copy(),
        pol=item.pol,
        freq_mhz=float(item.freq_mhz),
        obs_time=item.obs_time,
        source_label=source_label,
    )


def _manifest_frequency_values(manifest: pd.DataFrame) -> list[float]:
    values = [
        float(item)
        for item in manifest.get("inferred_freq_mhz", pd.Series(dtype=float))
        .dropna()
        .unique()
        .tolist()
        if np.isfinite(float(item))
    ]
    return sorted(values)


def _load_reference_grid(
    available: pd.DataFrame,
    *,
    primary_frequency: float,
    anchor_number: int,
    preview_polarization: str,
    pair_tolerance_sec: float,
) -> tuple[list[RadioImage], list[dict[str, Any]]]:
    plans = _plan_reference_grid(
        available,
        primary_frequency=primary_frequency,
        anchor_number=anchor_number,
        preview_polarization=preview_polarization,
        pair_tolerance_sec=pair_tolerance_sec,
    )
    return _materialize_reference_grid(plans)


def _plan_reference_grid(
    available: pd.DataFrame,
    *,
    primary_frequency: float,
    anchor_number: int,
    preview_polarization: str,
    pair_tolerance_sec: float,
) -> list[_ReferencePlan]:
    if available.empty:
        return []
    working = available.copy()
    working["_freq_value"] = pd.to_numeric(
        working["inferred_freq_mhz"], errors="coerce"
    )
    finite_values = sorted(
        float(value)
        for value in working["_freq_value"].dropna().unique().tolist()
        if np.isfinite(float(value))
    )
    canonical: list[float] = []
    value_to_group: dict[float, float] = {}
    for value in finite_values:
        matched = next(
            (item for item in canonical if _frequency_matches_any(value, {item})),
            None,
        )
        if matched is None:
            matched = value
            canonical.append(value)
        value_to_group[value] = matched
    working["_freq_group"] = working["_freq_value"].map(value_to_group)
    working["_obs_time_parsed"] = pd.to_datetime(
        working["inferred_obs_time"],
        utc=True,
        errors="coerce",
    )
    anchor_rows = working.loc[working["row"].astype(int).eq(int(anchor_number))]
    if anchor_rows.empty:
        raise ValueError("Anchor File # must be one of the selected rows.")
    anchor_time = _row_time(anchor_rows.iloc[0])
    primary_group = next(
        (
            freq
            for freq in canonical
            if _frequency_matches_any(freq, {primary_frequency})
        ),
        None,
    )
    ordered_freqs = ([primary_group] if primary_group is not None else []) + [
        freq for freq in canonical if freq != primary_group
    ]
    grouped = {
        float(freq): group.copy()
        for freq, group in working.dropna(subset=["_freq_group"]).groupby(
            "_freq_group",
            sort=False,
        )
    }
    plans: list[_ReferencePlan] = []
    for freq in ordered_freqs:
        same_freq = grouped.get(float(freq))
        if same_freq is None or same_freq.empty:
            continue
        row: pd.Series | None = None
        paired_row: pd.Series | None = None
        if preview_polarization == POL_SUM:
            left_rows = same_freq.loc[
                same_freq["inferred_polarization"].astype(str).eq(POL_LCP)
            ]
            right_rows = same_freq.loc[
                same_freq["inferred_polarization"].astype(str).eq(POL_RCP)
            ]
            row, paired_row = _select_paired_rows(
                left_rows,
                right_rows,
                anchor_time=anchor_time,
                pair_tolerance_sec=pair_tolerance_sec,
            )
        if row is None:
            candidates = same_freq
            if preview_polarization in {POL_LCP, POL_RCP}:
                filtered = same_freq.loc[
                    same_freq["inferred_polarization"]
                    .astype(str)
                    .eq(preview_polarization)
                ]
                if not filtered.empty:
                    candidates = filtered
            row = _nearest_manifest_row(candidates, anchor_time)
            paired_row = None
        if row is None:
            continue
        row_time = _row_time(row)
        delta_sec = (
            abs((row_time - anchor_time).total_seconds())
            if row_time is not None and anchor_time is not None
            else math.nan
        )
        plans.append(
            _ReferencePlan(
                freq_mhz=float(freq),
                row=int(row["row"]),
                path=str(row["path"]),
                paired_row=int(paired_row["row"]) if paired_row is not None else None,
                paired_path=str(paired_row["path"]) if paired_row is not None else None,
                obs_time=str(row.get("inferred_obs_time", "")),
                delta_from_anchor_sec=float(delta_sec),
                polarization=(
                    POL_SUM
                    if paired_row is not None
                    else str(row.get("inferred_polarization", preview_polarization))
                ),
            )
        )
    return plans


def _select_paired_rows(
    left_rows: pd.DataFrame,
    right_rows: pd.DataFrame,
    *,
    anchor_time: datetime | None,
    pair_tolerance_sec: float,
) -> tuple[pd.Series | None, pd.Series | None]:
    if left_rows.empty or right_rows.empty:
        return None, None
    left_ns = _manifest_time_ns(left_rows)
    right_ns = _manifest_time_ns(right_rows)
    left_positions = np.flatnonzero(left_ns != _NAT_INT64)
    right_positions = np.flatnonzero(right_ns != _NAT_INT64)
    if not left_positions.size or not right_positions.size:
        return None, None
    right_row_numbers = pd.to_numeric(right_rows["row"], errors="coerce").to_numpy(
        dtype=float
    )
    order = np.lexsort((right_row_numbers[right_positions], right_ns[right_positions]))
    sorted_right_positions = right_positions[order]
    sorted_right_ns = right_ns[sorted_right_positions]
    insertion = np.searchsorted(sorted_right_ns, left_ns[left_positions])
    candidate_slots = np.stack(
        (
            np.clip(insertion - 1, 0, len(sorted_right_ns) - 1),
            np.clip(insertion, 0, len(sorted_right_ns) - 1),
        ),
        axis=1,
    )
    candidate_right_positions = sorted_right_positions[candidate_slots]
    pair_delta_ns = np.abs(
        right_ns[candidate_right_positions] - left_ns[left_positions, None]
    )
    tolerance_ns = max(0, int(round(float(pair_tolerance_sec) * 1_000_000_000.0)))
    valid = pair_delta_ns <= tolerance_ns
    if not np.any(valid):
        return None, None
    if anchor_time is None:
        anchor_delta_ns = np.zeros(left_positions.size, dtype=np.int64)
    else:
        anchor_ns = int(pd.Timestamp(anchor_time).value)
        anchor_delta_ns = np.abs(left_ns[left_positions] - anchor_ns)
    score = anchor_delta_ns[:, None] + pair_delta_ns
    valid_left_slots, valid_candidate_slots = np.nonzero(valid)
    selected_left_positions = left_positions[valid_left_slots]
    selected_right_positions = candidate_right_positions[
        valid_left_slots,
        valid_candidate_slots,
    ]
    left_row_numbers = pd.to_numeric(left_rows["row"], errors="coerce").to_numpy(
        dtype=float
    )
    ranking = np.lexsort(
        (
            right_row_numbers[selected_right_positions],
            left_row_numbers[selected_left_positions],
            score[valid_left_slots, valid_candidate_slots],
        )
    )
    best = int(ranking[0])
    return (
        left_rows.iloc[int(selected_left_positions[best])],
        right_rows.iloc[int(selected_right_positions[best])],
    )


def _materialize_reference_grid(
    plans: list[_ReferencePlan],
) -> tuple[list[RadioImage], list[dict[str, Any]]]:
    references: list[RadioImage] = []
    metadata: list[dict[str, Any]] = []
    for plan in plans:
        left_item = _cached_reference_image(plan.path)
        paired_row = plan.paired_row
        paired_path = plan.paired_path
        if paired_path:
            right_item = _cached_reference_image(paired_path)
            if left_item.image.shape == right_item.image.shape:
                image = np.asarray(left_item.image, dtype=float) + np.asarray(
                    right_item.image,
                    dtype=float,
                )
                image.setflags(write=False)
                item = RadioImage(
                    path=Path(plan.path),
                    hdu_index=left_item.hdu_index,
                    image=image,
                    header=left_item.header.copy(),
                    pol=POL_SUM,
                    freq_mhz=float(left_item.freq_mhz),
                    obs_time=left_item.obs_time or right_item.obs_time,
                    source_label=f"File #{plan.row} + #{paired_row} LCP+RCP preview",
                )
            else:
                paired_row = None
                paired_path = None
                item = _clone_reference_image(
                    left_item,
                    source_label=f"File #{plan.row}",
                )
        else:
            item = _clone_reference_image(
                left_item,
                source_label=f"File #{plan.row}",
            )
        references.append(item)
        metadata.append(
            {
                "freq_mhz": float(plan.freq_mhz),
                "file_number": int(plan.row),
                "path": str(plan.path),
                "paired_file_number": paired_row,
                "paired_path": str(paired_path or ""),
                "obs_time": plan.obs_time,
                "delta_from_anchor_sec": float(plan.delta_from_anchor_sec),
                "polarization": item.pol,
            }
        )
    return references, metadata


def _reference_grid_signature(
    available: pd.DataFrame,
    plans: list[_ReferencePlan],
    *,
    primary_frequency: float,
    anchor_number: int,
    preview_polarization: str,
    pair_tolerance_sec: float,
) -> str:
    digest = hashlib.sha256()
    request = (
        "reference-grid-v2",
        f"{float(primary_frequency):.12g}",
        str(int(anchor_number)),
        str(preview_polarization),
        f"{float(pair_tolerance_sec):.9f}",
    )
    digest.update("|".join(request).encode("utf-8"))
    digest.update(b"\n")
    columns = [
        "row",
        "path",
        "inferred_freq_mhz",
        "inferred_polarization",
        "inferred_obs_time",
    ]
    for values in available.sort_values("row")[columns].itertuples(
        index=False, name=None
    ):
        digest.update("|".join(str(value) for value in values).encode("utf-8"))
        digest.update(b"\n")
    for plan in plans:
        for path in (plan.path, plan.paired_path):
            if not path:
                continue
            resolved = Path(path).expanduser().resolve()
            stat = resolved.stat()
            digest.update(f"{resolved}|{stat.st_size}|{stat.st_mtime_ns}".encode())
            digest.update(b"\n")
    return digest.hexdigest()


def _reference_reuse_signature(
    st: Any,
    *,
    primary_frequency: float,
    anchor_number: int,
    preview_polarization: str,
    pair_tolerance_sec: float,
) -> str:
    digest = hashlib.sha256()
    request = (
        "reference-reuse-v1",
        str(st.session_state.get("dataset_signature", "")),
        str(int(st.session_state.get("selection_revision", 0))),
        f"{float(primary_frequency):.12g}",
        str(int(anchor_number)),
        str(preview_polarization),
        f"{float(pair_tolerance_sec):.9f}",
    )
    digest.update("|".join(request).encode())
    digest.update(b"\n")
    metadata = list(st.session_state.get("reference_metadata") or [])
    for meta in metadata:
        for path in (meta.get("path"), meta.get("paired_path")):
            if not path:
                continue
            resolved = Path(path).expanduser().resolve()
            try:
                stat = resolved.stat()
                identity = f"{resolved}|{stat.st_size}|{stat.st_mtime_ns}"
            except OSError:
                identity = f"{resolved}|missing"
            digest.update(identity.encode())
            digest.update(b"\n")
    return digest.hexdigest()


def _nearest_manifest_row(
    candidates: pd.DataFrame, anchor_time: datetime | None
) -> pd.Series | None:
    if candidates.empty:
        return None
    if anchor_time is None:
        return candidates.sort_values("row").iloc[0]
    scored = candidates.copy()
    time_ns = _manifest_time_ns(scored)
    anchor_ns = int(pd.Timestamp(anchor_time).value)
    time_delta = np.full(time_ns.shape, np.inf, dtype=float)
    valid = time_ns != _NAT_INT64
    time_delta[valid] = np.abs(time_ns[valid] - anchor_ns) / 1_000_000_000.0
    scored["_time_delta"] = time_delta
    return scored.sort_values(["_time_delta", "row"]).iloc[0]


def _manifest_time_ns(frame: pd.DataFrame) -> np.ndarray:
    source = (
        frame["_obs_time_parsed"]
        if "_obs_time_parsed" in frame.columns
        else pd.to_datetime(frame["inferred_obs_time"], utc=True, errors="coerce")
    )
    return (
        pd.to_datetime(source, utc=True, errors="coerce")
        .to_numpy(dtype="datetime64[ns]")
        .astype("int64")
    )


def _row_time(row: pd.Series) -> datetime | None:
    value = row.get("inferred_obs_time", "")
    parsed = parse_datetime_value(value)
    return parsed


def _option_index(options: list[str], value: str) -> int:
    return options.index(value) if value in options else 0


def _manual_range_editor(
    st: Any,
    reference_images: list[RadioImage],
    settings: dict[str, Any],
    *,
    transform: str,
) -> tuple[dict[str, list[float]], dict[str, list[float]]]:
    rows = []
    for item in reference_images:
        key = _display_frequency_key(item.freq_mhz)
        rows.append(
            {
                "freq_mhz": float(item.freq_mhz),
                "vmin": float(settings["display_manual_min"]),
                "vmax": float(settings["display_manual_max"]),
                "key": key,
            }
        )
    edited = st.data_editor(
        pd.DataFrame(rows),
        hide_index=True,
        disabled=["freq_mhz", "key"],
        column_config={
            "freq_mhz": st.column_config.NumberColumn(
                "MHz", help="Frequency for this display limit row."
            ),
            "vmin": st.column_config.NumberColumn(
                "Manual min",
                help="Raw FITS-unit lower display limit for this frequency.",
            ),
            "vmax": st.column_config.NumberColumn(
                "Manual max",
                help="Raw FITS-unit upper display limit for this frequency.",
            ),
            "key": st.column_config.TextColumn(
                "Key", help="Internal frequency key written to exported metadata."
            ),
        },
        width="stretch",
        key="radio_roi_manual_display_ranges",
    )
    raw_limits: dict[str, list[float]] = {}
    display_limits: dict[str, list[float]] = {}
    transform_config = {"transform": transform}
    for _, row in edited.iterrows():
        key = str(row["key"])
        raw_min = float(row["vmin"])
        raw_max = float(row["vmax"])
        raw_limits[key] = [raw_min, raw_max]
        display_limits[key] = [
            _transform_display_limit(raw_min, transform_config),
            _transform_display_limit(raw_max, transform_config),
        ]
    return display_limits, raw_limits


def _attach_auto_display_limits(
    reference_images: list[RadioImage],
    config: dict[str, Any],
    *,
    previews: list[_DisplayReferencePreview],
) -> None:
    if str(config.get("range_mode", "")).lower() != "auto percentile":
        return
    low = float(config.get("low_percentile", 1.0))
    high = float(config.get("high_percentile", 99.7))
    by_freq: dict[str, list[np.ndarray]] = {}
    for item, preview in zip(reference_images, previews, strict=True):
        finite = preview.display_view[np.isfinite(preview.display_view)]
        if finite.size:
            by_freq.setdefault(_display_frequency_key(item.freq_mhz), []).append(finite)
    if not by_freq:
        return
    if config.get("range_scope") == "Shared/global":
        all_values = np.concatenate(
            [np.concatenate(values) for values in by_freq.values()]
        )
        config["shared_limits"] = _clean_display_limits(
            np.nanpercentile(all_values, [low, high])
        )
        return
    config["limits_by_frequency"] = {
        key: _clean_display_limits(
            np.nanpercentile(np.concatenate(values), [low, high])
        )
        for key, values in by_freq.items()
    }


def _display_array(
    arr: np.ndarray, display_config: dict[str, Any] | None
) -> np.ndarray:
    values = np.asarray(arr, dtype=float)
    transform = str((display_config or {}).get("transform", "Linear")).strip().lower()
    if transform in {"log10 positive", "log10", "log"}:
        return np.where(values > 0.0, np.log10(values), np.nan)
    return values


def _display_limits_for_item(
    item: RadioImage,
    display_view: np.ndarray,
    display_config: dict[str, Any] | None,
    *,
    fallback_percentiles: tuple[float, float],
) -> tuple[float, float]:
    config = display_config or {}
    freq_key = _display_frequency_key(item.freq_mhz)
    limits_by_frequency = config.get("limits_by_frequency", {})
    if isinstance(limits_by_frequency, dict) and freq_key in limits_by_frequency:
        return _clean_display_limits(limits_by_frequency[freq_key])
    if config.get("shared_limits") is not None:
        return _clean_display_limits(config["shared_limits"])
    mode = str(config.get("range_mode", "Auto percentile")).lower()
    if mode.startswith("manual"):
        return _clean_display_limits(
            [
                _transform_display_limit(float(config.get("manual_min", 0.0)), config),
                _transform_display_limit(float(config.get("manual_max", 1.0)), config),
            ]
        )
    finite = display_view[np.isfinite(display_view)]
    if not finite.size:
        return 0.0, 1.0
    low, high = fallback_percentiles
    return _clean_display_limits(np.nanpercentile(finite, [low, high]))


def _transform_display_limit(value: float, display_config: dict[str, Any]) -> float:
    transform = str(display_config.get("transform", "Linear")).strip().lower()
    if transform in {"log10 positive", "log10", "log"}:
        return math.log10(value) if value > 0.0 else math.nan
    return float(value)


def _clean_display_limits(values: Any) -> list[float]:
    zmin, zmax = [float(item) for item in list(values)[:2]]
    if not np.isfinite(zmin) or not np.isfinite(zmax):
        return [0.0, 1.0]
    if zmin > zmax:
        zmin, zmax = zmax, zmin
    if zmin == zmax:
        pad = abs(zmin) * 0.01 or 1.0
        zmin -= pad
        zmax += pad
    return [float(zmin), float(zmax)]


def _display_frequency_key(freq_mhz: float) -> str:
    if not np.isfinite(freq_mhz):
        return "nan"
    return f"{float(freq_mhz):.6g}"


def _display_colorbar_title(
    item: RadioImage, display_config: dict[str, Any] | None
) -> str:
    unit = str(item.header.get("BUNIT", "")).strip() or "raw"
    transform = str((display_config or {}).get("transform", "Linear")).strip().lower()
    if transform in {"log10 positive", "log10", "log"}:
        return f"log10({unit})"
    return unit


def _apply_plotly_fov(fig: Any, display_config: dict[str, Any] | None) -> None:
    config = display_config or {}
    if not bool(config.get("use_custom_fov", False)):
        return
    try:
        left = float(config["x_min_arcsec"])
        right = float(config["x_max_arcsec"])
        bottom = float(config["y_min_arcsec"])
        top = float(config["y_max_arcsec"])
    except (KeyError, TypeError, ValueError):
        return
    fig.update_xaxes(range=[min(left, right), max(left, right)])
    fig.update_yaxes(range=[min(bottom, top), max(bottom, top)])


def _session_roi(st: Any, key: str) -> RadioRoi | None:
    payload = st.session_state.get(key)
    if payload is None:
        return None
    try:
        return radio_roi_from_json(payload)
    except Exception:
        return None


def _dataset_signature(settings: dict[str, Any], manifest: pd.DataFrame) -> str:
    return str(
        hash(
            (
                settings["radio_dir"],
                settings["pattern"],
                bool(settings["recursive"]),
                tuple(
                    float(item) for item in settings.get("selected_freqs_mhz", []) or []
                ),
                settings["time_start"],
                settings["time_end"],
                len(manifest),
            )
        )
    )


def _analysis_signature(
    selected_paths: list[str], roi: RadioRoi, settings: dict[str, Any]
) -> str:
    payload = {
        "selected_paths": selected_paths,
        "roi": roi.to_json_dict(),
        "polarization": settings["polarization"],
        "pair_time_tolerance_sec": float(settings["pair_time_tolerance_sec"]),
    }
    return json.dumps(payload, sort_keys=True, default=str)


def _run_metadata(
    selected_paths: list[str], settings: dict[str, Any]
) -> dict[str, Any]:
    return {
        "radio_dir": settings["radio_dir"],
        "pattern": settings["pattern"],
        "recursive": bool(settings["recursive"]),
        "selected_freqs_mhz": settings.get("selected_freqs_mhz", []),
        "time_start": settings.get("time_start", ""),
        "time_end": settings.get("time_end", ""),
        "selected_files": selected_paths,
        "selected_file_count": len(selected_paths),
        "selected_file_numbers": settings.get("selected_file_numbers", []),
        "reference_file": settings.get("reference_path", ""),
        "reference_images": settings.get("reference_images", []),
        "anchor_file_number": settings.get("reference_file_number", ""),
        "primary_reference_freq_mhz": settings.get("primary_reference_freq_mhz", ""),
        "display_config": settings.get("display_config", {}),
        "polarization": settings["polarization"],
        "pair_time_tolerance_sec": float(settings["pair_time_tolerance_sec"]),
        "metric": settings["metric"],
    }


def _settings_with_reference(
    st: Any, settings: dict[str, Any], display_config: dict[str, Any]
) -> dict[str, Any]:
    enriched = dict(settings)
    enriched["reference_path"] = st.session_state.get("reference_path", "")
    enriched["reference_file_number"] = st.session_state.get(
        "reference_file_number", ""
    )
    enriched["primary_reference_freq_mhz"] = st.session_state.get(
        "primary_reference_freq_mhz", ""
    )
    enriched["reference_images"] = st.session_state.get("reference_metadata", [])
    enriched["display_config"] = display_config
    manifest = st.session_state.get("loaded_manifest")
    if manifest is not None:
        path_to_row = dict(
            zip(manifest["path"].astype(str), manifest["row"].astype(int), strict=False)
        )
        enriched["selected_file_numbers"] = [
            path_to_row.get(str(path))
            for path in st.session_state.get("selected_paths", [])
        ]
    return enriched


def _zip_artifacts(artifacts: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for key, payload in artifacts.items():
            archive.writestr(PRODUCT_FILENAMES[key], payload)
    return buffer.getvalue()


def _downsample_for_preview(
    arr: np.ndarray, *, max_side: int
) -> tuple[np.ndarray, slice, slice]:
    ny, nx = arr.shape
    stride = max(1, int(np.ceil(max(ny, nx) / max(1, int(max_side)))))
    y_slice = slice(0, ny, stride)
    x_slice = slice(0, nx, stride)
    return arr[y_slice, x_slice], y_slice, x_slice


def _preview_coordinate_grid(
    item: RadioImage,
    preview_shape: tuple[int, int],
    y_slice: slice,
    x_slice: slice,
) -> tuple[np.ndarray, np.ndarray]:
    from solar_toolkit.radio.roi_lightcurve import _pixel_coordinates_hpc_arcsec

    y_indices = np.arange(item.image.shape[0])[y_slice][: preview_shape[0]]
    x_indices = np.arange(item.image.shape[1])[x_slice][: preview_shape[1]]
    y_grid, x_grid = np.meshgrid(y_indices, x_indices, indexing="ij")
    return _pixel_coordinates_hpc_arcsec(item.header, x_grid, y_grid)


def _prepare_reference_preview(
    item: RadioImage,
    *,
    max_side: int,
) -> _ReferencePreview:
    arr = np.asarray(item.image, dtype=float)
    view, y_slice, x_slice = _downsample_for_preview(arr, max_side=max_side)
    x_arcsec, y_arcsec = _preview_coordinate_grid(
        item,
        view.shape,
        y_slice,
        x_slice,
    )
    x_arcsec.setflags(write=False)
    y_arcsec.setflags(write=False)
    return _ReferencePreview(
        raw_view=view,
        x_arcsec=x_arcsec,
        y_arcsec=y_arcsec,
    )


def _reference_previews_from_state(
    st: Any,
    reference_images: list[RadioImage],
    *,
    max_side: int,
) -> list[_ReferencePreview]:
    identity = tuple(
        (
            str(item.path),
            int(item.hdu_index),
            tuple(int(value) for value in item.image.shape),
            id(item.image),
        )
        for item in reference_images
    )
    cache_key = (
        str(st.session_state.get("reference_grid_signature", "")),
        int(max_side),
        identity,
    )
    cached = st.session_state.get("reference_preview_cache")
    if (
        st.session_state.get("reference_preview_cache_key") == cache_key
        and isinstance(cached, list)
        and len(cached) == len(reference_images)
    ):
        return cached
    previews = [
        _prepare_reference_preview(item, max_side=max_side) for item in reference_images
    ]
    st.session_state["reference_preview_cache_key"] = cache_key
    st.session_state["reference_preview_cache"] = previews
    return previews


def _add_roi_shape(fig: Any, roi: RadioRoi) -> None:
    vertices = list(roi.vertices_arcsec)
    xs = [item[0] for item in vertices] + [vertices[0][0]]
    ys = [item[1] for item in vertices] + [vertices[0][1]]
    fig.add_trace(
        {
            "type": "scatter",
            "x": xs,
            "y": ys,
            "mode": "lines",
            "line": {"color": "white", "width": 2},
            "name": "Active ROI",
            "hoverinfo": "skip",
        }
    )


def _reference_title(item: RadioImage) -> str:
    time_label = (
        item.obs_time.isoformat(timespec="milliseconds")
        if item.obs_time
        else "unknown time"
    )
    freq_label = (
        f"{item.freq_mhz:g} MHz" if np.isfinite(item.freq_mhz) else "unknown frequency"
    )
    source = str(getattr(item, "source_label", "") or "").strip()
    prefix = f"{source} | " if source and source.lower() != "main" else ""
    return f"{prefix}{freq_label} {item.pol} {time_label}"


def _selection_xy(selection: Any, key: str) -> tuple[list[float], list[float]] | None:
    payload = _event_get(selection, key, None)
    if isinstance(payload, (list, tuple)):
        payload = payload[-1] if payload else None
    if payload is None:
        return None
    xs = _float_list(_event_get(payload, "x", []))
    ys = _float_list(_event_get(payload, "y", []))
    if not xs or not ys:
        return None
    return xs, ys


def _float_list(values: Any) -> list[float]:
    if isinstance(values, (int, float, np.integer, np.floating)):
        return [float(values)]
    if values is None:
        return []
    return [
        float(value)
        for value in values
        if value is not None and np.isfinite(float(value))
    ]


def _box_roi_from_xy(
    xs: list[float], ys: list[float], *, label: str
) -> RadioRoi | None:
    left, right = min(xs), max(xs)
    bottom, top = min(ys), max(ys)
    if left == right or bottom == top:
        return None
    return RadioRoi.from_box(left, bottom, right, top, label=label)


def _event_get(source: Any, key: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _relative_path_text(path: Path, folder: Path) -> str:
    try:
        return str(path.relative_to(folder))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
