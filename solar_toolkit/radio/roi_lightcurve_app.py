"""Streamlit frontend for radio ROI light-curve extraction."""

from __future__ import annotations

import argparse
import io
import json
import zipfile
from datetime import datetime
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
    "load_app_settings",
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
    "output_dir": "radio_roi_lightcurve_outputs",
    "pair_time_tolerance_sec": DEFAULT_PAIR_TOLERANCE_SEC,
    "polarization": POL_SUM,
    "metric": "raw_sum",
    "display_low_percentile": 1.0,
    "display_high_percentile": 99.7,
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
ROI_KEYS = ("candidate_roi", "confirmed_roi")
ANALYSIS_KEYS = ("analysis_df", "analysis_signature")
EXPORT_KEYS = ("export_artifacts", "export_signature")


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
    parser.add_argument("--time-start", default=None, help="Default inclusive time start.")
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
    parser.add_argument("--settings-file", default=None, help="Local JSON settings file.")
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
    payload = {key: settings.get(key, DEFAULT_APP_SETTINGS[key]) for key in DEFAULT_APP_SETTINGS}
    settings_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return settings_path


def resolve_app_settings(args: argparse.Namespace, stored: dict[str, Any]) -> dict[str, Any]:
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
    rows: list[dict[str, Any]] = []
    for index, path in enumerate(files):
        stat = path.stat()
        obs_time = parse_time_from_filename(path)
        rows.append(
            {
                "row": index + 1,
                "path": str(path),
                "relative_path": _relative_path_text(path, folder),
                "size_mib": round(float(stat.st_size) / 1024.0 / 1024.0, 3),
                "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                "inferred_freq_mhz": parse_frequency_mhz(path, blank_header),
                "inferred_polarization": infer_polarization(path, blank_header),
                "inferred_obs_time": obs_time.isoformat(timespec="milliseconds") if obs_time else "",
            }
        )
    return pd.DataFrame(rows)


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
    xs = [float(_event_get(point, "x")) for point in points if _event_get(point, "x") is not None]
    ys = [float(_event_get(point, "y")) for point in points if _event_get(point, "y") is not None]
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
):
    """Build the Plotly reference image used for ROI selection."""

    import plotly.graph_objects as go

    arr = np.asarray(item.image, dtype=float)
    view, y_slice, x_slice = _downsample_for_preview(arr, max_side=max_side)
    x_arcsec, y_arcsec = _preview_coordinate_grid(item, view.shape, y_slice, x_slice)
    finite = view[np.isfinite(view)]
    if finite.size:
        zmin, zmax = np.nanpercentile(finite, [float(low_percentile), float(high_percentile)])
    else:
        zmin, zmax = 0.0, 1.0
    fig = go.Figure()
    fig.add_trace(
        go.Heatmap(
            z=view,
            x=x_arcsec[0, :],
            y=y_arcsec[:, 0],
            colorscale="Viridis",
            zmin=float(zmin),
            zmax=float(zmax),
            colorbar={"title": str(item.header.get("BUNIT", "")).strip() or "raw"},
            hovertemplate="x=%{x:.2f}<br>y=%{y:.2f}<br>value=%{z:.4g}<extra></extra>",
        )
    )
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
    dragmode = "lasso" if str(roi_mode).lower() == "lasso" else "select"
    fig.update_layout(
        title=_reference_title(item),
        xaxis_title="HPLN / arcsec",
        yaxis_title="HPLT / arcsec",
        dragmode=dragmode,
        height=620,
        margin={"l": 60, "r": 20, "t": 60, "b": 55},
    )
    fig.update_yaxes(scaleanchor="x", scaleratio=1)
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
    st.caption("Load radio FITS files, select a time series, draw one ROI, preview the curve, then export.")

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

    reference = _render_reference_step(st, selected_paths, manifest, current_settings)
    if reference is None:
        st.warning("Render one selected file as the reference image.")
        return

    roi = _render_roi_step(st, reference, settings)
    if roi is None:
        st.warning("Draw and confirm an ROI on the reference image.")
        return

    df = _render_analysis_step(st, selected_paths, reference, roi, current_settings)
    if df is None:
        return

    _render_export_step(st, df, selected_paths, reference, roi, current_settings)


def _render_load_step(st: Any, settings: dict[str, Any], settings_file: Path) -> dict[str, Any]:
    st.subheader("Step 1. Load Data")
    with st.form("radio_roi_load_form"):
        c1, c2 = st.columns([3, 1])
        with c1:
            radio_dir = st.text_input("Radio FITS folder", value=str(settings["radio_dir"]))
        with c2:
            pattern = st.text_input("FITS pattern", value=str(settings["pattern"]))
        c3, c4, c5 = st.columns([1, 1, 1])
        with c3:
            recursive = st.checkbox("Search subfolders", value=bool(settings["recursive"]))
        with c4:
            time_start = st.text_input("Start time", value=str(settings["time_start"]))
        with c5:
            time_end = st.text_input("End time", value=str(settings["time_end"]))
        submitted = st.form_submit_button("Load Data", type="primary")
    c6, c7, c8 = st.columns([1, 1, 2])
    with c6:
        pair_tolerance = st.number_input(
            "LCP/RCP pair tolerance (s)",
            min_value=0.0,
            value=float(settings["pair_time_tolerance_sec"]),
            step=0.1,
        )
    with c7:
        polarization = st.selectbox(
            "Polarization",
            [POL_SUM, POL_LCP, POL_RCP, "all"],
            index=[POL_SUM, POL_LCP, POL_RCP, "all"].index(str(settings["polarization"])),
        )
    with c8:
        metric = st.selectbox(
            "Curve metric",
            ["raw_sum", "raw_mean", "raw_peak"],
            index=["raw_sum", "raw_mean", "raw_peak"].index(str(settings["metric"])),
        )
    output_dir = st.text_input("Output folder", value=str(settings["output_dir"]))

    current_settings = {
        "radio_dir": radio_dir,
        "pattern": pattern,
        "recursive": recursive,
        "time_start": time_start,
        "time_end": time_end,
        "output_dir": output_dir,
        "pair_time_tolerance_sec": pair_tolerance,
        "polarization": polarization,
        "metric": metric,
        "display_low_percentile": settings["display_low_percentile"],
        "display_high_percentile": settings["display_high_percentile"],
        "preview_max_side": settings["preview_max_side"],
        "page_size": int(settings["page_size"]),
    }
    c9, c10 = st.columns([1, 4])
    with c9:
        if st.button("Save Defaults"):
            save_app_settings(settings_file, current_settings)
            st.success(f"Saved {settings_file}")
    if submitted:
        _load_manifest_into_state(st, current_settings)
    return current_settings


def _load_manifest_into_state(st: Any, settings: dict[str, Any]) -> None:
    try:
        manifest = build_file_manifest(
            settings["radio_dir"],
            pattern=settings["pattern"],
            recursive=bool(settings["recursive"]),
            time_start=settings["time_start"] or None,
            time_end=settings["time_end"] or None,
        )
    except Exception as exc:  # noqa: BLE001 - visible app error.
        st.error(str(exc))
        return
    st.session_state["loaded_manifest"] = manifest
    st.session_state["dataset_signature"] = _dataset_signature(settings, manifest)
    _clear_keys(st, ("selected_paths", "reference_path", "reference_image", *ROI_KEYS, *ANALYSIS_KEYS, *EXPORT_KEYS))
    st.session_state["roi_chart_generation"] = int(st.session_state.get("roi_chart_generation", 0)) + 1
    st.success(f"Loaded {len(manifest):,} FITS files.")


def _render_file_selection_step(
    st: Any,
    manifest: pd.DataFrame,
    settings: dict[str, Any],
) -> list[str]:
    st.subheader("Step 2. Choose Data Files")
    query = st.text_input("Filter files", value="", placeholder="Search relative path, time, frequency, or polarization")
    filtered = _filter_manifest(manifest, query)
    page_size = int(settings.get("page_size", 200))
    page_count = max(1, int(np.ceil(len(filtered) / max(1, page_size))))
    c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
    with c1:
        page = int(st.number_input("Page", min_value=1, max_value=page_count, value=1, step=1))
    with c2:
        if st.button("Select Page"):
            page_paths = _page_paths(filtered, page=page, page_size=page_size)
            _set_selected_paths(st, set(st.session_state.get("selected_paths", [])) | set(page_paths))
    with c3:
        if st.button("Select All Filtered"):
            _set_selected_paths(st, set(st.session_state.get("selected_paths", [])) | set(filtered["path"].astype(str)))
    with c4:
        if st.button("Clear Selection"):
            _set_selected_paths(st, set())

    start = (page - 1) * page_size
    end = start + page_size
    page_df = filtered.iloc[start:end].copy()
    selected = set(st.session_state.get("selected_paths", []))
    page_df.insert(0, "selected", page_df["path"].astype(str).isin(selected))
    edited = st.data_editor(
        page_df[
            [
                "selected",
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
            "relative_path",
            "inferred_obs_time",
            "inferred_freq_mhz",
            "inferred_polarization",
            "size_mib",
            "path",
        ],
        hide_index=True,
        width="stretch",
    )
    current_page_paths = set(page_df["path"].astype(str))
    edited_selected = set(edited.loc[edited["selected"].astype(bool), "path"].astype(str))
    _set_selected_paths(st, (set(st.session_state.get("selected_paths", [])) - current_page_paths) | edited_selected)
    selected_paths = sorted(st.session_state.get("selected_paths", []))
    st.caption(f"Showing {len(page_df):,} of {len(filtered):,} filtered files. Selected {len(selected_paths):,} files.")
    return selected_paths


def _render_reference_step(
    st: Any,
    selected_paths: list[str],
    manifest: pd.DataFrame,
    settings: dict[str, Any],
) -> RadioImage | None:
    st.subheader("Step 3. Render Reference Image")
    selected_set = set(selected_paths)
    available = manifest.loc[manifest["path"].astype(str).isin(selected_set)].copy()
    path_to_label = dict(zip(available["path"].astype(str), available["relative_path"].astype(str), strict=False))
    current_ref = st.session_state.get("reference_path")
    index = selected_paths.index(current_ref) if current_ref in selected_paths else 0
    reference_path = st.selectbox(
        "Reference file",
        selected_paths,
        index=index,
        format_func=lambda value: path_to_label.get(str(value), str(value)),
    )
    if st.button("Render Selected Image", type="primary"):
        try:
            st.session_state["reference_image"] = _load_first_radio_image(reference_path)
            st.session_state["reference_path"] = reference_path
        except Exception as exc:  # noqa: BLE001 - visible app error.
            st.error(str(exc))
            return None
        _clear_keys(st, (*ROI_KEYS, *ANALYSIS_KEYS, *EXPORT_KEYS))
        st.session_state["roi_chart_generation"] = int(st.session_state.get("roi_chart_generation", 0)) + 1
    if st.session_state.get("reference_path") not in selected_set:
        _clear_keys(st, ("reference_path", "reference_image", *ROI_KEYS, *ANALYSIS_KEYS, *EXPORT_KEYS))
        return None
    return st.session_state.get("reference_image")


def _render_roi_step(st: Any, reference: RadioImage, settings: dict[str, Any]) -> RadioRoi | None:
    st.subheader("Step 4. Draw and Confirm ROI")
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        roi_mode = st.radio("ROI mode", ["box", "lasso"], horizontal=True)
    candidate = _session_roi(st, "candidate_roi")
    confirmed = _session_roi(st, "confirmed_roi")
    active_roi = candidate or confirmed
    chart_key = (
        f"radio_roi_selection_chart_"
        f"{st.session_state.get('roi_chart_generation', 0)}_{roi_mode}"
    )
    event = st.plotly_chart(
        build_reference_figure(
            reference,
            roi=active_roi,
            low_percentile=float(settings["display_low_percentile"]),
            high_percentile=float(settings["display_high_percentile"]),
            max_side=int(settings["preview_max_side"]),
            roi_mode=roi_mode,
        ),
        width="stretch",
        on_select="rerun",
        selection_mode=(roi_mode,),
        key=chart_key,
    )
    selected_roi = selection_to_radio_roi(event, mode=roi_mode, label="active")
    if selected_roi is not None:
        st.session_state["candidate_roi"] = selected_roi.to_json_dict()
        candidate = selected_roi
    with c2:
        if st.button("Confirm ROI", type="primary", disabled=candidate is None):
            st.session_state["confirmed_roi"] = candidate.to_json_dict()
            _clear_keys(st, ANALYSIS_KEYS + EXPORT_KEYS)
            confirmed = candidate
    with c3:
        uploaded = st.file_uploader("Load ROI JSON", type=["json"])
        if uploaded is not None:
            try:
                st.session_state["candidate_roi"] = radio_roi_from_json(json.loads(uploaded.getvalue())).to_json_dict()
                _clear_keys(st, ANALYSIS_KEYS + EXPORT_KEYS)
                candidate = _session_roi(st, "candidate_roi")
            except Exception as exc:  # noqa: BLE001 - visible app error.
                st.error(str(exc))
    if st.button("Clear ROI"):
        _clear_keys(st, (*ROI_KEYS, *ANALYSIS_KEYS, *EXPORT_KEYS))
        st.session_state["roi_chart_generation"] = int(st.session_state.get("roi_chart_generation", 0)) + 1
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
    reference: RadioImage,
    roi: RadioRoi,
    settings: dict[str, Any],
) -> pd.DataFrame | None:
    st.subheader("Step 5. Analyze and Preview")
    signature = _analysis_signature(selected_paths, roi, settings)
    if st.button("Analyze Selected Files", type="primary"):
        with st.spinner("Extracting full-resolution ROI statistics from selected files..."):
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
        reference_image=reference,
        run_metadata=_run_metadata(selected_paths, _settings_with_reference(st, settings)),
        metric=str(settings["metric"]),
        selected_products=("lightcurve_png",),
    )
    st.image(preview["lightcurve_png"])
    return df


def _render_export_step(
    st: Any,
    df: pd.DataFrame,
    selected_paths: list[str],
    reference: RadioImage,
    roi: RadioRoi,
    settings: dict[str, Any],
) -> None:
    st.subheader("Step 6. Export and Download")
    c1, c2, c3, c4 = st.columns(4)
    product_keys = []
    for column, key in zip((c1, c2, c3, c4), PRODUCT_FILENAMES, strict=False):
        with column:
            if st.checkbox(PRODUCT_LABELS[key], value=True, key=f"export_{key}"):
                product_keys.append(key)
    if not product_keys:
        st.warning("Select at least one export product.")
        return
    artifacts = build_radio_roi_artifacts(
        df,
        roi,
        reference_image=reference,
        run_metadata=_run_metadata(selected_paths, _settings_with_reference(st, settings)),
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
        )
    for key, payload in artifacts.items():
        st.download_button(
            f"Download {PRODUCT_LABELS[key]}",
            data=payload,
            file_name=PRODUCT_FILENAMES[key],
            mime=PRODUCT_MIME_TYPES[key],
            on_click="ignore",
        )
    if st.button("Save Selected Products"):
        products = write_radio_roi_products(
            df,
            roi,
            settings["output_dir"],
            reference_image=reference,
            run_metadata=_run_metadata(selected_paths, _settings_with_reference(st, settings)),
            metric=str(settings["metric"]),
            selected_products=tuple(product_keys),
        )
        st.success(f"Saved products to {products['output_dir']}")


def _init_session_state(st: Any) -> None:
    st.session_state.setdefault("selected_paths", [])
    st.session_state.setdefault("roi_chart_generation", 0)


def _clear_keys(st: Any, keys: tuple[str, ...]) -> None:
    for key in keys:
        st.session_state.pop(key, None)


def _set_selected_paths(st: Any, paths: set[str]) -> None:
    selected = sorted(str(path) for path in paths)
    previous = sorted(str(path) for path in st.session_state.get("selected_paths", []))
    if selected == previous:
        return
    st.session_state["selected_paths"] = selected
    _clear_keys(st, ANALYSIS_KEYS + EXPORT_KEYS)
    if st.session_state.get("reference_path") not in set(selected):
        _clear_keys(st, ("reference_path", "reference_image", *ROI_KEYS))
        st.session_state["roi_chart_generation"] = int(st.session_state.get("roi_chart_generation", 0)) + 1


def _filter_manifest(manifest: pd.DataFrame, query: str) -> pd.DataFrame:
    if not query.strip():
        return manifest
    text = query.strip().casefold()
    searchable = manifest[
        ["relative_path", "inferred_obs_time", "inferred_polarization", "inferred_freq_mhz"]
    ].astype(str)
    mask = searchable.apply(lambda column: column.str.casefold().str.contains(text, regex=False)).any(axis=1)
    return manifest.loc[mask].copy()


def _page_paths(filtered: pd.DataFrame, *, page: int, page_size: int) -> list[str]:
    start = (int(page) - 1) * int(page_size)
    end = start + int(page_size)
    return filtered.iloc[start:end]["path"].astype(str).tolist()


def _load_first_radio_image(path: str | Path) -> RadioImage:
    for item in iter_radio_images(path):
        return item
    raise RuntimeError(f"No usable 2D radio image plane found in {path}")


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
                settings["time_start"],
                settings["time_end"],
                len(manifest),
            )
        )
    )


def _analysis_signature(selected_paths: list[str], roi: RadioRoi, settings: dict[str, Any]) -> str:
    payload = {
        "selected_paths": selected_paths,
        "roi": roi.to_json_dict(),
        "polarization": settings["polarization"],
        "pair_time_tolerance_sec": float(settings["pair_time_tolerance_sec"]),
    }
    return json.dumps(payload, sort_keys=True, default=str)


def _run_metadata(selected_paths: list[str], settings: dict[str, Any]) -> dict[str, Any]:
    return {
        "radio_dir": settings["radio_dir"],
        "pattern": settings["pattern"],
        "recursive": bool(settings["recursive"]),
        "selected_files": selected_paths,
        "selected_file_count": len(selected_paths),
        "reference_file": settings.get("reference_path", ""),
        "polarization": settings["polarization"],
        "pair_time_tolerance_sec": float(settings["pair_time_tolerance_sec"]),
        "metric": settings["metric"],
    }


def _settings_with_reference(st: Any, settings: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(settings)
    enriched["reference_path"] = st.session_state.get("reference_path", "")
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
    from solar_toolkit.radio.roi_lightcurve import _pixel_center_grid_hpc_arcsec

    y_indices = np.arange(item.image.shape[0])[y_slice][: preview_shape[0]]
    x_indices = np.arange(item.image.shape[1])[x_slice][: preview_shape[1]]
    y_grid, x_grid = np.meshgrid(y_indices, x_indices, indexing="ij")
    full_shape = item.image.shape
    x_full, y_full = _pixel_center_grid_hpc_arcsec(item.header, full_shape)
    return x_full[y_grid, x_grid], y_full[y_grid, x_grid]


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
    time_label = item.obs_time.isoformat(timespec="milliseconds") if item.obs_time else "unknown time"
    freq_label = f"{item.freq_mhz:g} MHz" if np.isfinite(item.freq_mhz) else "unknown frequency"
    return f"{freq_label} {item.pol} {time_label}"


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
    return [float(value) for value in values if value is not None and np.isfinite(float(value))]


def _box_roi_from_xy(xs: list[float], ys: list[float], *, label: str) -> RadioRoi | None:
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
