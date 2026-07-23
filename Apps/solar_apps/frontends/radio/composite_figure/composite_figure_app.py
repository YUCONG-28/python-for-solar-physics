"""All-in-one Streamlit workflow for radio/DART composite figures."""

from __future__ import annotations

import argparse
import copy
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from solar_apps.frontends.radio.composite_figure.composite_figure_application import (
    CompositeArtifactBundle,
    FrequencyBand,
    build_composite_artifacts,
    build_dart_selection_figure,
    build_request_signature,
    build_source_map_selection_figure,
    frequency_band_from_selection,
    save_composite_bundle,
    select_dart_time_overlap,
)
from solar_apps.frontends.radio.roi_lightcurve.roi_lightcurve_app import (
    build_file_manifest,
    discover_frequency_options,
    selection_to_radio_roi,
)
from solar_apps.frontends.radio.source_map.artifacts import (
    validate_source_map_artifact,
)
from solar_apps.frontends.radio.source_map.service import (
    PathPolicy,
    discover_candidates,
    parse_request_config,
)
from solar_apps.frontends.radio.source_map.worker import run_job
from solar_apps.platform.layout import RuntimeLayout
from solar_apps.ui.state import (
    bind_streamlit_fields,
    frontend_path_memory,
    frontend_state_store,
    save_streamlit_fields,
)
from solar_apps.ui.streamlit_paths import (
    PathAccessPolicy,
    render_native_path_input,
    resolve_streamlit_allowed_roots,
)
from solar_apps.ui.theme import apply_plotly_chrome, render_streamlit_theme
from solar_apps.workflows.radio.configs import DEFAULT_CONFIG_NAME
from solar_apps.workflows.radio.spatial_display import SpatialRadioDisplay
from solar_toolkit.radio.dart_spectrogram import (
    DartSpectrogramWindow,
    discover_dart_spectrogram_files,
    extract_dart_narrowband_lightcurves,
    read_dart_spectrogram_window,
)
from solar_toolkit.radio.roi_lightcurve import (
    RadioRoi,
    extract_radio_roi_lightcurve,
    radio_roi_from_json,
)

FRONTEND_ID = "radio-composite"
DEFAULT_OUTPUT_RELATIVE = "outputs/radio_composite"
DEFAULT_PATTERN = "*.fits"
DEFAULT_DPI = 160

UI_FIELD_KEYS = (
    "radio_dir",
    "dart_dir",
    "output_dir",
    "radio_pattern",
    "radio_recursive",
    "source_mode",
    "source_frequencies",
    "source_polarization",
    "source_config",
    "map_transform",
    "map_cmap",
    "map_bad_color",
    "map_range_mode",
    "map_low_percentile",
    "map_high_percentile",
    "map_vmin",
    "map_vmax",
    "map_unit",
    "map_use_fov",
    "map_fov_xmin",
    "map_fov_xmax",
    "map_fov_ymin",
    "map_fov_ymax",
    "gaussian_overlay",
    "background_mode",
    "background_display",
    "background_fit",
    "advanced_source_map_json",
    "selected_map_frequency",
    "selected_candidate_id",
    "roi_mode",
    "roi_label",
    "dart_band_low",
    "dart_band_high",
    "shared_time_start",
    "shared_time_end",
    "composite_dpi",
)

TRANSIENT_KEYS = (
    "radio_manifest",
    "radio_frequency_options",
    "dart_window",
    "dart_files",
    "inspection_signature",
    "source_map_config",
    "source_map_candidates",
    "source_map_discovery_signature",
    "source_map_image_bytes",
    "source_map_metadata",
    "source_map_result",
    "source_map_candidate",
    "source_map_observation_time",
    "source_map_frequency_mhz",
    "candidate_roi",
    "confirmed_roi",
    "composite_bundle",
    "composite_signature",
    "composite_saved_directory",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="solar-apps frontend radio-composite",
        description="Build a Source Map, ROI curve, and DART narrowband composite.",
    )
    parser.add_argument("--radio-dir", default=None)
    parser.add_argument("--dart-dir", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--allowed-roots", default=None)
    parser.add_argument("--pattern", default=None)
    recursive = parser.add_mutually_exclusive_group()
    recursive.add_argument("--recursive", dest="recursive", action="store_true")
    recursive.add_argument("--no-recursive", dest="recursive", action="store_false")
    parser.set_defaults(recursive=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    _run_streamlit_app(argv)
    return 0


def _run_streamlit_app(argv: list[str] | None = None) -> None:
    import streamlit as st

    args, _unknown = build_parser().parse_known_args(argv)
    layout = RuntimeLayout.discover()
    state_store = frontend_state_store(FRONTEND_ID, layout=layout)
    try:
        allowed_roots = resolve_streamlit_allowed_roots(args.allowed_roots)
    except Exception as exc:
        st.error(f"Path configuration error: {exc}")
        return
    protected_output = layout.outputs_dir / "radio_composite"
    path_policy = PathAccessPolicy.create(
        allowed_roots,
        protected_output_roots=(protected_output,),
        base_directory=layout.repo_root,
    )
    path_memory = frontend_path_memory(path_policy.output_roots, layout=layout)

    st.set_page_config(page_title="Radio Composite Figure", layout="wide")
    theme_mode = render_streamlit_theme(
        st,
        frontend_id=FRONTEND_ID,
        state_store=state_store,
        path_memory=path_memory,
    )
    bind_streamlit_fields(
        st,
        state_store,
        frontend_id=FRONTEND_ID,
        field_keys=UI_FIELD_KEYS,
    )
    _apply_pending_band(st)
    st.title("Radio Composite Figure")
    st.caption(
        "Generate one Source Map, confirm one spatial ROI, select one DART "
        "frequency band, and export a reproducible three-row figure."
    )
    if not allowed_roots:
        st.error(
            "No allowed roots are configured. Add the radio, DART, and output "
            "directories to Local/configs/paths.local.yaml."
        )
        return

    default_output = str(Path(args.output_dir) if args.output_dir else protected_output)
    radio_dir_text, dart_dir_text, output_dir_text = _render_path_controls(
        st,
        path_policy,
        state_store,
        radio_default=str(args.radio_dir or ""),
        dart_default=str(args.dart_dir or ""),
        output_default=default_output,
    )
    _render_inspection_step(
        st,
        path_policy,
        radio_dir_text=radio_dir_text,
        dart_dir_text=dart_dir_text,
        pattern_default=str(args.pattern or DEFAULT_PATTERN),
        recursive_default=True if args.recursive is None else bool(args.recursive),
    )

    manifest = st.session_state.get("radio_manifest")
    dart_window = st.session_state.get("dart_window")
    frequency_options = st.session_state.get("radio_frequency_options")
    if not isinstance(manifest, pd.DataFrame) or not isinstance(
        dart_window, DartSpectrogramWindow
    ):
        st.info("Inspect both datasets to unlock Source Map configuration.")
        save_streamlit_fields(st, state_store, UI_FIELD_KEYS)
        return

    _render_source_map_configuration(
        st,
        path_policy,
        radio_dir_text=radio_dir_text,
        frequency_options=frequency_options,
    )
    candidates = st.session_state.get("source_map_candidates")
    source_config = st.session_state.get("source_map_config")
    if not isinstance(candidates, list) or not isinstance(source_config, dict):
        st.info("Discover Source Map frames to choose the map time and frequency.")
        _render_dart_band_step(st, dart_window, theme_mode)
        save_streamlit_fields(st, state_store, UI_FIELD_KEYS)
        return

    candidate, map_frequency, coverage = _render_map_candidate_step(
        st,
        candidates,
        source_config,
        path_policy,
    )
    if candidate is None or map_frequency is None:
        st.warning("Select a valid Source Map frequency and frame.")
        _render_dart_band_step(st, dart_window, theme_mode)
        save_streamlit_fields(st, state_store, UI_FIELD_KEYS)
        return

    _render_roi_step(st, theme_mode)
    _render_dart_band_step(st, dart_window, theme_mode)
    _render_analysis_step(
        st,
        path_policy,
        radio_dir_text=radio_dir_text,
        dart_dir_text=dart_dir_text,
        output_dir_text=output_dir_text,
        map_frequency=map_frequency,
        candidate=candidate,
        radio_coverage=coverage,
        dart_window=dart_window,
    )
    save_streamlit_fields(st, state_store, UI_FIELD_KEYS)


def _render_path_controls(
    st: Any,
    path_policy: PathAccessPolicy,
    state_store: Any,
    *,
    radio_default: str,
    dart_default: str,
    output_default: str,
) -> tuple[str, str, str]:
    st.subheader("1. Data locations")
    radio_dir = render_native_path_input(
        st,
        "Radio FITS sequence directory",
        key="radio_dir",
        initial_value=radio_default,
        roots=path_policy.input_roots,
        kind="directory",
        frontend_id=FRONTEND_ID,
        operation="radio-input",
        state_store=state_store,
        help_text="The same sequence supplies the selected Source Map frame and ROI curve.",
    )
    dart_dir = render_native_path_input(
        st,
        "DART four-FITS directory",
        key="dart_dir",
        initial_value=dart_default,
        roots=path_policy.input_roots,
        kind="directory",
        frontend_id=FRONTEND_ID,
        operation="dart-input",
        state_store=state_store,
    )
    output_dir = render_native_path_input(
        st,
        "Composite output directory",
        key="output_dir",
        initial_value=output_default,
        roots=path_policy.output_roots,
        kind="directory",
        frontend_id=FRONTEND_ID,
        operation="composite-output",
        state_store=state_store,
    )
    return radio_dir, dart_dir, output_dir


def _render_inspection_step(
    st: Any,
    path_policy: PathAccessPolicy,
    *,
    radio_dir_text: str,
    dart_dir_text: str,
    pattern_default: str,
    recursive_default: bool,
) -> None:
    columns = st.columns([2, 1, 1])
    with columns[0]:
        pattern = st.text_input(
            "Radio FITS glob",
            value=pattern_default,
            key="radio_pattern",
        )
    with columns[1]:
        recursive = st.checkbox(
            "Recursive radio scan",
            value=recursive_default,
            key="radio_recursive",
        )
    with columns[2]:
        st.write("")
        inspect_clicked = st.button("Inspect datasets", width="stretch", type="primary")
    _invalidate_if_controls_changed(
        st,
        "inspection_controls_signature",
        {
            "radio_directory": radio_dir_text,
            "dart_directory": dart_dir_text,
            "pattern": pattern,
            "recursive": bool(recursive),
        },
        _invalidate_after_inspection,
    )
    if inspect_clicked:
        try:
            radio_dir = path_policy.input_directory(radio_dir_text)
            dart_dir = path_policy.input_directory(dart_dir_text)
            manifest = build_file_manifest(
                radio_dir,
                pattern=pattern,
                recursive=bool(recursive),
            )
            if manifest.empty:
                raise ValueError("No radio FITS files matched the requested pattern")
            frequencies = discover_frequency_options(
                radio_dir,
                pattern=pattern,
                recursive=bool(recursive),
            )
            if frequencies.empty:
                raise ValueError("No finite radio frequencies were discovered")
            dart_files = discover_dart_spectrogram_files(dart_dir)
            dart_window = read_dart_spectrogram_window(
                dart_files,
                max_frequency_samples=700,
                max_time_samples=1400,
                chunk_memory_mb=64,
            )
            radio_paths = [Path(value) for value in manifest["path"].astype(str)]
            signature = build_request_signature(
                {
                    "radio_dir": str(radio_dir),
                    "dart_dir": str(dart_dir),
                    "pattern": pattern,
                    "recursive": bool(recursive),
                },
                source_paths=[
                    *radio_paths,
                    dart_files.stokes_i_db,
                    dart_files.stokes_v_over_i,
                    dart_files.frequency,
                    dart_files.time,
                ],
            )
        except Exception as exc:
            st.error(str(exc))
        else:
            _invalidate_after_inspection(st)
            st.session_state["radio_manifest"] = manifest
            st.session_state["radio_frequency_options"] = frequencies
            st.session_state["dart_window"] = dart_window
            st.session_state["dart_files"] = dart_files
            st.session_state["inspection_signature"] = signature
            radio_values = _frequency_values(frequencies)
            default_band = _default_band(dart_window.frequency_mhz, radio_values[0])
            st.session_state["dart_band_low"] = default_band.low_mhz
            st.session_state["dart_band_high"] = default_band.high_mhz
            st.success(
                f"Loaded {len(manifest):,} radio file(s), {len(radio_values)} "
                f"frequency option(s), and DART matrix {dart_window.stokes_i_db.shape}."
            )
    if isinstance(st.session_state.get("radio_manifest"), pd.DataFrame):
        manifest = st.session_state["radio_manifest"]
        frequencies = st.session_state["radio_frequency_options"]
        st.dataframe(frequencies, hide_index=True, width="stretch")
        st.caption(f"Radio manifest: {len(manifest):,} file records.")


def _render_source_map_configuration(
    st: Any,
    path_policy: PathAccessPolicy,
    *,
    radio_dir_text: str,
    frequency_options: Any,
) -> None:
    st.subheader("2. Source Map settings")
    frequencies = _frequency_values(frequency_options)
    main_columns = st.columns([1, 2, 1, 1])
    with main_columns[0]:
        mode = st.selectbox(
            "Input organization",
            options=("single_band", "multi_band"),
            key="source_mode",
            format_func=lambda value: (
                "Single-band sequence"
                if value == "single_band"
                else "Synchronized multi-band"
            ),
        )
    with main_columns[1]:
        selected_frequencies = st.multiselect(
            "Source frequencies (MHz)",
            options=frequencies,
            default=frequencies[:1],
            key="source_frequencies",
            format_func=lambda value: f"{value:g}",
        )
    with main_columns[2]:
        polarization = st.selectbox(
            "Polarization",
            options=("RR+LL", "RR", "LL"),
            key="source_polarization",
        )
    with main_columns[3]:
        config_name = st.text_input(
            "Event config",
            value=DEFAULT_CONFIG_NAME,
            key="source_config",
        )

    display_columns = st.columns(4)
    with display_columns[0]:
        transform = st.selectbox(
            "Map transform",
            options=("linear", "log10"),
            key="map_transform",
        )
        cmap = st.selectbox(
            "Color map",
            options=("hot", "inferno", "magma", "viridis", "plasma", "jet", "cividis"),
            key="map_cmap",
        )
        bad_color = st.color_picker(
            "Bad-value color", value="#000080", key="map_bad_color"
        )
    with display_columns[1]:
        range_mode = st.selectbox(
            "Color range",
            options=("auto", "fixed"),
            key="map_range_mode",
        )
        low_percentile = st.number_input(
            "Lower percentile",
            min_value=0.0,
            max_value=99.999,
            value=99.7,
            step=0.1,
            key="map_low_percentile",
        )
        high_percentile = st.number_input(
            "Upper percentile",
            min_value=0.001,
            max_value=100.0,
            value=99.99,
            step=0.01,
            key="map_high_percentile",
        )
    with display_columns[2]:
        vmin = st.number_input("Fixed minimum", value=0.0, key="map_vmin")
        vmax = st.number_input("Fixed maximum", value=1.0, key="map_vmax")
        unit = st.text_input(
            "Display unit override",
            value="",
            key="map_unit",
            placeholder="Use FITS BUNIT",
        )
    with display_columns[3]:
        gaussian_overlay = st.checkbox(
            "Gaussian overlay", value=True, key="gaussian_overlay"
        )
        background_mode = st.selectbox(
            "Background",
            options=("off", "noise_map_only", "local_mesh", "local_median"),
            key="background_mode",
        )
        background_display = st.checkbox(
            "Apply background to display", value=False, key="background_display"
        )
        background_fit = st.checkbox(
            "Apply background to fit", value=False, key="background_fit"
        )

    use_fov = st.checkbox("Custom field of view", value=False, key="map_use_fov")
    fov_columns = st.columns(4)
    fov_values = []
    for column, label, key, default in zip(
        fov_columns,
        ("HPLN min", "HPLN max", "HPLT min", "HPLT max"),
        ("map_fov_xmin", "map_fov_xmax", "map_fov_ymin", "map_fov_ymax"),
        (-1000.0, 1000.0, -1000.0, 1000.0),
        strict=True,
    ):
        with column:
            fov_values.append(
                float(
                    st.number_input(label, value=default, key=key, disabled=not use_fov)
                )
            )
    advanced = st.text_area(
        "Advanced Source Map JSON",
        value="{}",
        key="advanced_source_map_json",
        help="Only established non-path Source Map options are accepted.",
    )
    _invalidate_if_controls_changed(
        st,
        "source_controls_signature",
        {
            "inspection": st.session_state.get("inspection_signature"),
            "radio_directory": radio_dir_text,
            "mode": mode,
            "frequencies": list(selected_frequencies),
            "polarization": polarization,
            "config": config_name,
            "transform": transform,
            "cmap": cmap,
            "bad_color": bad_color,
            "range_mode": range_mode,
            "percentiles": [low_percentile, high_percentile],
            "fixed_range": [vmin, vmax],
            "unit": unit,
            "gaussian_overlay": gaussian_overlay,
            "background": [background_mode, background_display, background_fit],
            "fov": fov_values if use_fov else None,
            "advanced": advanced,
        },
        _invalidate_after_source_controls,
    )
    if st.button("Discover Source Map frames", type="primary", width="stretch"):
        try:
            if not selected_frequencies:
                raise ValueError("Select at least one radio frequency")
            if mode == "single_band" and len(selected_frequencies) > 1:
                raise ValueError(
                    "Single-band organization accepts one selected frequency"
                )
            preview_dir = (
                RuntimeLayout.discover().outputs_dir / "radio_composite" / "source_map"
            )
            policy = PathPolicy(path_policy.output_roots)
            request = {
                "config": config_name,
                "mode": mode,
                "source_path": str(path_policy.input_directory(radio_dir_text)),
                "output_dir": str(preview_dir),
                "frequencies": list(selected_frequencies),
                "polarization": polarization,
                "gaussian_overlay": gaussian_overlay,
                "cmap": cmap,
                "color_range_mode": range_mode,
                "fixed_vmin": vmin if range_mode == "fixed" else None,
                "fixed_vmax": vmax if range_mode == "fixed" else None,
                "radio_unit": unit,
                "background_mode": background_mode,
                "background_display": background_display,
                "background_fit": background_fit,
                "spectrogram_panel": False,
                "advanced": advanced,
            }
            cfg = parse_request_config(request, policy=policy)
            display = SpatialRadioDisplay(
                cmap=str(cmap),
                bad_color=str(bad_color),
                transform=str(transform),
                range_mode=str(range_mode),
                range_scope="frame",
                auto_method="fixed_percentile",
                percentiles=(float(low_percentile), float(high_percentile)),
                vmin=float(vmin) if range_mode == "fixed" else None,
                vmax=float(vmax) if range_mode == "fixed" else None,
                unit=str(unit).strip() or None,
                fov=tuple(fov_values) if use_fov else None,
                render_profile="preview",
            )
            cfg = display.apply_to_legacy_config(cfg)
            cfg["spatial_display"] = display.to_dict()
            cfg["enable_spectrogram_panel"] = False
            candidates = discover_candidates(cfg, policy=policy)
            selected = [float(value) for value in selected_frequencies]
            candidates = [
                candidate
                for candidate in candidates
                if any(_candidate_has_frequency(candidate, value) for value in selected)
            ]
            if not candidates:
                raise ValueError(
                    "No Source Map candidates match the selected frequencies"
                )
            signature = build_request_signature(
                {
                    "inspection": st.session_state.get("inspection_signature"),
                    "request": request,
                    "display": display.to_dict(),
                }
            )
        except Exception as exc:
            st.error(str(exc))
        else:
            _invalidate_after_discovery(st)
            st.session_state["source_map_config"] = cfg
            st.session_state["source_map_candidates"] = candidates
            st.session_state["source_map_discovery_signature"] = signature
            st.success(f"Discovered {len(candidates):,} Source Map frame(s).")


def _render_map_candidate_step(
    st: Any,
    candidates: list[dict[str, Any]],
    source_config: dict[str, Any],
    path_policy: PathAccessPolicy,
) -> tuple[dict[str, Any] | None, float | None, tuple[datetime, datetime] | None]:
    st.subheader("3. Select and render the Source Map")
    frequencies = sorted(
        {
            float(value)
            for candidate in candidates
            for value in candidate.get("frequencies_mhz", [])
            if math.isfinite(float(value))
        }
    )
    if not frequencies:
        st.error("Source Map candidates contain no finite frequency metadata.")
        return None, None, None
    map_frequency = float(
        st.selectbox(
            "Top map frequency (MHz)",
            options=frequencies,
            key="selected_map_frequency",
            format_func=lambda value: f"{value:g}",
        )
    )
    matching = [
        candidate
        for candidate in candidates
        if _candidate_has_frequency(candidate, map_frequency)
        and candidate.get("observation_time")
    ]
    if not matching:
        st.error("No timestamped Source Map frame matches the selected frequency.")
        return None, map_frequency, None
    candidate_by_id = {str(candidate["id"]): candidate for candidate in matching}
    selected_id = st.selectbox(
        "Source Map frame",
        options=list(candidate_by_id),
        key="selected_candidate_id",
        format_func=lambda value: _candidate_label(candidate_by_id[value]),
    )
    candidate = candidate_by_id[str(selected_id)]
    _invalidate_if_controls_changed(
        st,
        "map_selection_controls_signature",
        {
            "discovery": st.session_state.get("source_map_discovery_signature"),
            "frequency_mhz": map_frequency,
            "candidate_id": str(selected_id),
        },
        _invalidate_after_map_selection,
    )
    coverage = _candidate_time_coverage(matching)
    st.caption(
        f"Radio sequence coverage at {map_frequency:g} MHz: "
        f"{coverage[0].isoformat()} to {coverage[1].isoformat()} UTC"
    )
    if st.button("Render selected Source Map", type="primary", width="stretch"):
        try:
            preview_dir = (
                RuntimeLayout.discover().outputs_dir / "radio_composite" / "source_map"
            )
            render_cfg, render_candidate = prepare_single_panel_render(
                source_config,
                candidate,
                map_frequency,
                transform=str(st.session_state.get("map_transform", "linear")),
                output_directory=preview_dir,
            )
            policy = PathPolicy(path_policy.output_roots)
            policy.resolve(preview_dir, must_exist=False).mkdir(
                parents=True, exist_ok=True
            )
            with st.spinner("Rendering the selected Source Map and sidecar..."):
                result = run_job(
                    {"config": render_cfg, "candidate": render_candidate, "sequence": 1}
                )
            image_path = policy.resolve(
                result["image_path"], must_exist=True, kind="file"
            )
            sidecar_path = policy.resolve(
                result["sidecar_path"], must_exist=True, kind="file"
            )
            metadata = validate_source_map_artifact(image_path, sidecar_path)
            if len(metadata.get("panels", [])) != 1:
                raise ValueError(
                    "Rendered Source Map did not contain exactly one panel"
                )
            observed = _utc_datetime(candidate["observation_time"])
        except Exception as exc:
            st.error(str(exc))
        else:
            _invalidate_after_map(st)
            st.session_state["source_map_image_bytes"] = image_path.read_bytes()
            st.session_state["source_map_metadata"] = metadata
            st.session_state["source_map_result"] = result
            st.session_state["source_map_candidate"] = copy.deepcopy(candidate)
            st.session_state["source_map_observation_time"] = observed.isoformat()
            st.session_state["source_map_frequency_mhz"] = map_frequency
            st.session_state["shared_time_start"] = coverage[0].isoformat()
            st.session_state["shared_time_end"] = coverage[1].isoformat()
            st.success("Source Map rendered. Draw and confirm one ROI below.")
    return candidate, map_frequency, coverage


def _render_roi_step(st: Any, theme_mode: str) -> None:
    image_bytes = st.session_state.get("source_map_image_bytes")
    metadata = st.session_state.get("source_map_metadata")
    if not isinstance(image_bytes, bytes) or not isinstance(metadata, dict):
        st.info("Render a Source Map to unlock spatial ROI selection.")
        return
    st.subheader("4. Draw and confirm one ROI")
    controls = st.columns([1, 2, 1, 1])
    with controls[0]:
        roi_mode = st.radio(
            "ROI tool",
            options=("box", "lasso"),
            horizontal=True,
            key="roi_mode",
            format_func=lambda value: "Rectangle" if value == "box" else "Lasso",
        )
    with controls[1]:
        roi_label = st.text_input("ROI label", value="ROI 1", key="roi_label")
    _invalidate_if_controls_changed(
        st,
        "roi_controls_signature",
        {
            "source_map": st.session_state.get("source_map_result"),
            "mode": roi_mode,
            "label": roi_label,
        },
        _invalidate_after_roi_controls,
    )
    candidate = _session_roi(st, "candidate_roi")
    confirmed = _session_roi(st, "confirmed_roi")
    active = candidate or confirmed
    figure = build_source_map_selection_figure(
        image_bytes,
        metadata,
        roi=active,
        roi_mode=roi_mode,
    )
    apply_plotly_chrome(figure, theme_mode)
    event = st.plotly_chart(
        figure,
        width="stretch",
        on_select="rerun",
        selection_mode=(roi_mode,),
        key=f"radio_composite_roi_{roi_mode}_{active.roi_id if active else 'empty'}",
    )
    selected = selection_to_radio_roi(event, mode=roi_mode, label=roi_label)
    if selected is not None and (
        candidate is None or selected.to_json_dict() != candidate.to_json_dict()
    ):
        st.session_state["candidate_roi"] = selected.to_json_dict()
        st.session_state.pop("confirmed_roi", None)
        _invalidate_composite(st)
        candidate = selected
        confirmed = None
    with controls[2]:
        if st.button(
            "Confirm ROI",
            disabled=candidate is None,
            type="primary",
            width="stretch",
        ):
            st.session_state["confirmed_roi"] = candidate.to_json_dict()
            _invalidate_composite(st)
            st.rerun()
    with controls[3]:
        if st.button("Clear ROI", disabled=active is None, width="stretch"):
            st.session_state.pop("candidate_roi", None)
            st.session_state.pop("confirmed_roi", None)
            _invalidate_composite(st)
            st.rerun()
    confirmed = _session_roi(st, "confirmed_roi")
    if confirmed is not None:
        st.success(f"Confirmed {confirmed.label or confirmed.roi_id}.")
        st.json(confirmed.to_json_dict(), expanded=False)
    elif candidate is not None:
        st.warning("ROI is staged. Confirm it before analysis.")


def _render_dart_band_step(
    st: Any, window: DartSpectrogramWindow, theme_mode: str
) -> None:
    st.subheader("5. Select one DART frequency band")
    observed_low = float(np.nanmin(window.frequency_mhz))
    observed_high = float(np.nanmax(window.frequency_mhz))
    current_low = float(
        st.session_state.get(
            "dart_band_low", _default_band(window.frequency_mhz, None).low_mhz
        )
    )
    current_high = float(
        st.session_state.get(
            "dart_band_high", _default_band(window.frequency_mhz, None).high_mhz
        )
    )
    columns = st.columns(2)
    with columns[0]:
        low = float(
            st.number_input(
                "Band lower bound (MHz)",
                min_value=observed_low,
                max_value=observed_high,
                value=current_low,
                key="dart_band_low",
                format="%.6f",
            )
        )
    with columns[1]:
        high = float(
            st.number_input(
                "Band upper bound (MHz)",
                min_value=observed_low,
                max_value=observed_high,
                value=current_high,
                key="dart_band_high",
                format="%.6f",
            )
        )
    _invalidate_if_controls_changed(
        st,
        "dart_band_controls_signature",
        {
            "inspection": st.session_state.get("inspection_signature"),
            "low_mhz": low,
            "high_mhz": high,
        },
        _invalidate_composite,
    )
    band: FrequencyBand | None = None
    try:
        band = FrequencyBand(low, high).validate_observed_range(window.frequency_mhz)
    except ValueError as exc:
        st.error(str(exc))
    figure = build_dart_selection_figure(window, band=band)
    apply_plotly_chrome(figure, theme_mode)
    revision = int(st.session_state.get("dart_band_revision", 0))
    event = st.plotly_chart(
        figure,
        width="stretch",
        on_select="rerun",
        selection_mode=("box",),
        key=f"radio_composite_dart_band_{revision}",
    )
    selected = frequency_band_from_selection(event)
    if selected is not None:
        try:
            selected.validate_observed_range(window.frequency_mhz)
        except ValueError as exc:
            st.error(str(exc))
        else:
            if band is None or (
                not math.isclose(selected.low_mhz, band.low_mhz)
                or not math.isclose(selected.high_mhz, band.high_mhz)
            ):
                st.session_state["_pending_dart_band"] = selected.to_dict()
                st.session_state["dart_band_revision"] = revision + 1
                _invalidate_composite(st)
                st.rerun()
    if band is not None:
        st.caption(
            f"Selected band: {band.low_mhz:g}-{band.high_mhz:g} MHz; "
            f"center {band.center_mhz:g} MHz; bandwidth {band.bandwidth_mhz:g} MHz."
        )


def _render_analysis_step(
    st: Any,
    path_policy: PathAccessPolicy,
    *,
    radio_dir_text: str,
    dart_dir_text: str,
    output_dir_text: str,
    map_frequency: float,
    candidate: dict[str, Any],
    radio_coverage: tuple[datetime, datetime] | None,
    dart_window: DartSpectrogramWindow,
) -> None:
    st.subheader("6. Analyze, preview, and export")
    if radio_coverage is None:
        st.error("Radio time coverage is unavailable.")
        return
    start_default, end_default = radio_coverage
    time_columns = st.columns([2, 2, 1])
    with time_columns[0]:
        start_text = st.text_input(
            "Shared UTC start",
            value=start_default.isoformat(),
            key="shared_time_start",
        )
    with time_columns[1]:
        end_text = st.text_input(
            "Shared UTC end",
            value=end_default.isoformat(),
            key="shared_time_end",
        )
    with time_columns[2]:
        dpi = int(
            st.number_input(
                "Export DPI",
                min_value=100,
                max_value=400,
                value=DEFAULT_DPI,
                step=10,
                key="composite_dpi",
            )
        )
    _invalidate_if_controls_changed(
        st,
        "analysis_controls_signature",
        {
            "map": st.session_state.get("source_map_result"),
            "roi": st.session_state.get("confirmed_roi"),
            "dart_band": [
                st.session_state.get("dart_band_low"),
                st.session_state.get("dart_band_high"),
            ],
            "time_start": start_text,
            "time_end": end_text,
            "dpi": dpi,
        },
        _invalidate_composite,
    )
    confirmed_roi = _session_roi(st, "confirmed_roi")
    image_bytes = st.session_state.get("source_map_image_bytes")
    metadata = st.session_state.get("source_map_metadata")
    map_time_text = st.session_state.get("source_map_observation_time")
    band: FrequencyBand | None = None
    try:
        band = FrequencyBand(
            float(st.session_state.get("dart_band_low")),
            float(st.session_state.get("dart_band_high")),
        ).validate_observed_range(dart_window.frequency_mhz)
        start = _utc_datetime(start_text)
        end = _utc_datetime(end_text)
        map_time = _utc_datetime(map_time_text)
        if start < radio_coverage[0] or end > radio_coverage[1]:
            raise ValueError(
                "Shared time range must stay inside the radio sequence coverage"
            )
        if start >= end:
            raise ValueError("Shared UTC start must be before the end")
        if not start <= map_time <= end:
            raise ValueError(
                "Selected Source Map time must lie inside the shared range"
            )
        overlap_start, overlap_end, partial_dart_coverage = select_dart_time_overlap(
            dart_window.time_utc,
            start,
            end,
        )
    except Exception as exc:
        st.error(str(exc))
        return
    if partial_dart_coverage:
        st.warning(
            "DART covers only part of the shared radio time range. The lower "
            "panel will remain empty outside DART coverage; no values are extrapolated."
        )
    if confirmed_roi is None:
        st.warning("Confirm one ROI before generating the composite.")
    if not isinstance(image_bytes, bytes) or not isinstance(metadata, dict):
        st.warning("Render a Source Map before generating the composite.")
    generate_disabled = confirmed_roi is None or not isinstance(image_bytes, bytes)
    if st.button(
        "Generate three-row composite",
        type="primary",
        width="stretch",
        disabled=generate_disabled,
    ):
        try:
            radio_dir = path_policy.input_directory(radio_dir_text)
            dart_dir = path_policy.input_directory(dart_dir_text)
            manifest = st.session_state["radio_manifest"]
            radio_paths = _manifest_paths_for_request(
                manifest,
                frequency_mhz=map_frequency,
                start=start,
                end=end,
            )
            dart_files = st.session_state["dart_files"]
            signature = build_request_signature(
                {
                    "inspection": st.session_state.get("inspection_signature"),
                    "source_map": st.session_state.get("source_map_result"),
                    "candidate": candidate,
                    "map_frequency_mhz": map_frequency,
                    "map_time": map_time,
                    "polarization": st.session_state.get("source_polarization"),
                    "display": metadata.get("display"),
                    "roi": confirmed_roi.to_json_dict(),
                    "time_start": start,
                    "time_end": end,
                    "dart_band": band.to_dict(),
                    "metric": "raw_sum",
                    "dart_representation": "stokes_i_db",
                    "dpi": dpi,
                },
                source_paths=[
                    *radio_paths,
                    dart_files.stokes_i_db,
                    dart_files.stokes_v_over_i,
                    dart_files.frequency,
                    dart_files.time,
                ],
            )
            cached = st.session_state.get("composite_bundle")
            if (
                isinstance(cached, CompositeArtifactBundle)
                and st.session_state.get("composite_signature") == signature
            ):
                bundle = cached
                st.success(
                    "Reused the current composite; no FITS files were read again."
                )
            else:
                with st.spinner(
                    "Extracting the radio ROI and DART narrowband curves..."
                ):
                    radio_df = extract_radio_roi_lightcurve(
                        radio_dir,
                        confirmed_roi,
                        pattern=str(
                            st.session_state.get("radio_pattern", DEFAULT_PATTERN)
                        ),
                        recursive=bool(st.session_state.get("radio_recursive", True)),
                        files=radio_paths,
                        freqs=[map_frequency],
                        polarization=str(
                            st.session_state.get("source_polarization", "RR+LL")
                        ),
                    )
                    radio_times = pd.to_datetime(
                        radio_df.get("obs_time"), errors="coerce", utc=True
                    )
                    in_range = (radio_times >= pd.Timestamp(start)) & (
                        radio_times <= pd.Timestamp(end)
                    )
                    radio_df = radio_df.loc[in_range].reset_index(drop=True)
                    if radio_df.empty:
                        raise ValueError(
                            "The selected radio files contain no samples in the shared UTC range"
                        )
                    dart_result = extract_dart_narrowband_lightcurves(
                        dart_dir,
                        [band.center_mhz],
                        band.bandwidth_mhz,
                        time_range_utc=(overlap_start, overlap_end),
                    )
                    bundle = build_composite_artifacts(
                        image_bytes,
                        metadata,
                        radio_df,
                        dart_result,
                        roi=confirmed_roi,
                        map_time=map_time,
                        map_frequency_mhz=map_frequency,
                        polarization=str(
                            st.session_state.get("source_polarization", "RR+LL")
                        ),
                        time_start=start,
                        time_end=end,
                        request_signature=signature,
                        source_context={
                            "radio_directory": str(radio_dir),
                            "radio_files": [str(path) for path in radio_paths],
                            "dart_directory": str(dart_dir),
                            "dart_files": {
                                "stokes_i_db": str(dart_files.stokes_i_db),
                                "stokes_v_over_i": str(dart_files.stokes_v_over_i),
                                "frequency": str(dart_files.frequency),
                                "time": str(dart_files.time),
                            },
                        },
                        dpi=dpi,
                    )
                st.session_state["composite_bundle"] = bundle
                st.session_state["composite_signature"] = signature
                st.session_state.pop("composite_saved_directory", None)
                st.success("Composite and reproducibility products generated.")
        except Exception as exc:
            st.error(str(exc))

    bundle = st.session_state.get("composite_bundle")
    if not isinstance(bundle, CompositeArtifactBundle):
        return
    st.image(bundle.files["composite_png"], width="stretch")
    download_columns = st.columns(3)
    _download(
        download_columns[0],
        "Download composite PNG",
        bundle.files["composite_png"],
        bundle.filenames["composite_png"],
        "image/png",
        "download_composite_png",
    )
    _download(
        download_columns[1],
        "Download radio ROI CSV",
        bundle.files["radio_csv"],
        bundle.filenames["radio_csv"],
        "text/csv",
        "download_radio_csv",
    )
    _download(
        download_columns[2],
        "Download DART CSV",
        bundle.files["dart_csv"],
        bundle.filenames["dart_csv"],
        "text/csv",
        "download_dart_csv",
    )
    more_columns = st.columns(3)
    _download(
        more_columns[0],
        "Download ROI JSON",
        bundle.files["roi_json"],
        bundle.filenames["roi_json"],
        "application/json",
        "download_roi_json",
    )
    _download(
        more_columns[1],
        "Download metadata JSON",
        bundle.files["metadata_json"],
        bundle.filenames["metadata_json"],
        "application/json",
        "download_metadata_json",
    )
    _download(
        more_columns[2],
        "Download complete ZIP",
        bundle.zip_bytes,
        bundle.zip_filename,
        "application/zip",
        "download_composite_zip",
    )
    if st.button("Save complete package to output directory", width="stretch"):
        try:
            output_directory = path_policy.output_directory(output_dir_text)
            saved = save_composite_bundle(bundle, output_directory)
        except Exception as exc:
            st.error(str(exc))
        else:
            st.session_state["composite_saved_directory"] = str(saved)
    if saved := st.session_state.get("composite_saved_directory"):
        st.success(f"Saved the complete package to {saved}")


def prepare_single_panel_render(
    config: dict[str, Any],
    candidate: dict[str, Any],
    frequency_mhz: float,
    *,
    transform: str,
    output_directory: str | Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Adapt one discovered Source Map frame to a one-panel render request."""

    cfg = copy.deepcopy(config)
    selected = copy.deepcopy(candidate)
    paths, slot_item = _candidate_frequency_paths(selected, float(frequency_mhz))
    if not paths:
        raise ValueError("The selected frame contains no path for this frequency")
    cfg["output_dir"] = str(Path(output_directory).resolve(strict=False))
    cfg["enable_spectrogram_panel"] = False
    cfg["write_source_map_sidecar"] = True
    cfg["show_plot"] = False
    cfg["save_plot"] = True
    cfg["max_workers"] = 1
    display_payload = dict(cfg.get("spatial_display") or {})
    display_payload["transform"] = str(transform)
    cfg["spatial_display"] = display_payload
    if str(transform).lower() == "linear":
        cfg["mode"] = "single_band"
        cfg["single_file_path"] = paths[0]
        cfg["data_dir"] = str(Path(paths[0]).parent)
        selected = {
            "id": f"{selected['id']}-single-{frequency_mhz:g}",
            "mode": "single_band",
            "run_path": paths[0],
            "paths": paths,
            "frequencies_mhz": [float(frequency_mhz)],
            "observation_time": selected.get("observation_time"),
        }
    elif str(transform).lower() == "log10":
        cfg["mode"] = "multi_band"
        cfg["multi_band_freqs"] = [float(frequency_mhz)]
        selected = {
            "id": f"{selected['id']}-log-{frequency_mhz:g}",
            "mode": "multi_band",
            "slot_index": 0,
            "slot": [slot_item],
            "paths": paths,
            "frequencies_mhz": [float(frequency_mhz)],
            "observation_time": selected.get("observation_time"),
        }
    else:
        raise ValueError("Map transform must be linear or log10")
    return cfg, selected


def _candidate_frequency_paths(
    candidate: dict[str, Any], frequency_mhz: float
) -> tuple[list[str], str | list[str]]:
    frequencies = [float(value) for value in candidate.get("frequencies_mhz", [])]
    index = _matching_frequency_index(frequencies, frequency_mhz)
    if str(candidate.get("mode")) == "multi_band":
        slot = list(candidate.get("slot") or [])
        if index >= len(slot):
            raise ValueError("Source Map slot metadata does not match its frequencies")
        item = slot[index]
        paths = (
            [str(value) for value in item]
            if isinstance(item, list | tuple)
            else [str(item)]
        )
        return paths, paths if len(paths) > 1 else paths[0]
    paths = [str(value) for value in candidate.get("paths", [])]
    return paths, paths if len(paths) > 1 else paths[0]


def _matching_frequency_index(values: list[float], requested: float) -> int:
    tolerance = max(1e-6, abs(float(requested)) * 1e-5)
    for index, value in enumerate(values):
        if abs(float(value) - float(requested)) <= tolerance:
            return index
    raise ValueError(f"Candidate does not contain {requested:g} MHz")


def _candidate_has_frequency(candidate: dict[str, Any], requested: float) -> bool:
    try:
        _matching_frequency_index(
            [float(value) for value in candidate.get("frequencies_mhz", [])],
            float(requested),
        )
    except ValueError:
        return False
    return True


def _candidate_label(candidate: dict[str, Any]) -> str:
    frequencies = ", ".join(
        f"{float(value):g}" for value in candidate.get("frequencies_mhz", [])
    )
    return (
        f"{candidate.get('observation_time') or 'unknown time'} | "
        f"{frequencies or 'unknown'} MHz | {candidate.get('title') or candidate['id']}"
    )


def _candidate_time_coverage(
    candidates: list[dict[str, Any]],
) -> tuple[datetime, datetime]:
    values = sorted(
        _utc_datetime(candidate["observation_time"])
        for candidate in candidates
        if candidate.get("observation_time")
    )
    if not values:
        raise ValueError("Selected radio sequence contains no observation times")
    if values[0] == values[-1]:
        raise ValueError("Selected radio sequence needs at least two distinct times")
    return values[0], values[-1]


def _manifest_paths_for_request(
    manifest: pd.DataFrame,
    *,
    frequency_mhz: float,
    start: datetime,
    end: datetime,
) -> list[Path]:
    data = manifest.copy()
    frequency_column = (
        "inferred_freq_mhz" if "inferred_freq_mhz" in data else "freq_mhz"
    )
    frequencies = pd.to_numeric(data.get(frequency_column), errors="coerce")
    times = pd.to_datetime(data.get("inferred_obs_time"), errors="coerce", utc=True)
    tolerance = max(1e-6, abs(float(frequency_mhz)) * 1e-5)
    frequency_mask = np.isfinite(frequencies.to_numpy(dtype=float, na_value=np.nan)) & (
        np.abs(frequencies - float(frequency_mhz)) <= tolerance
    )
    if times.notna().any():
        time_mask = times.isna() | (
            (times >= pd.Timestamp(start)) & (times <= pd.Timestamp(end))
        )
        mask = frequency_mask & time_mask
    else:
        mask = frequency_mask
    paths = [Path(value) for value in data.loc[mask, "path"].astype(str)]
    if not paths:
        raise ValueError("No radio files match the selected frequency and time range")
    return paths


def _frequency_values(frame: Any) -> list[float]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    column = "freq_mhz" if "freq_mhz" in frame else frame.columns[0]
    values = pd.to_numeric(frame[column], errors="coerce")
    return sorted({float(value) for value in values if np.isfinite(value)})


def _default_band(frequencies: Any, preferred: float | None) -> FrequencyBand:
    values = np.sort(np.unique(np.asarray(frequencies, dtype=float)))
    values = values[np.isfinite(values)]
    if values.size < 2:
        center = float(values[0]) if values.size else float(preferred or 1.0)
        return FrequencyBand(center - 0.5, center + 0.5)
    low_observed = float(values[0])
    high_observed = float(values[-1])
    spacing = float(np.median(np.diff(values)))
    width = max(abs(spacing) * 3.0, (high_observed - low_observed) / 100.0)
    center = (
        float(preferred)
        if preferred is not None and low_observed <= float(preferred) <= high_observed
        else (low_observed + high_observed) / 2.0
    )
    low = max(low_observed, center - width / 2.0)
    high = min(high_observed, center + width / 2.0)
    if low >= high:
        low, high = low_observed, high_observed
    return FrequencyBand(low, high)


def _session_roi(st: Any, key: str) -> RadioRoi | None:
    value = st.session_state.get(key)
    if not isinstance(value, dict):
        return None
    try:
        return radio_roi_from_json(value)
    except Exception:
        return None


def _apply_pending_band(st: Any) -> None:
    pending = st.session_state.pop("_pending_dart_band", None)
    if isinstance(pending, dict):
        st.session_state["dart_band_low"] = float(pending["low_mhz"])
        st.session_state["dart_band_high"] = float(pending["high_mhz"])


def _invalidate_after_inspection(st: Any) -> None:
    for key in TRANSIENT_KEYS:
        st.session_state.pop(key, None)


def _invalidate_after_discovery(st: Any) -> None:
    for key in (
        "source_map_image_bytes",
        "source_map_metadata",
        "source_map_result",
        "source_map_candidate",
        "source_map_observation_time",
        "source_map_frequency_mhz",
        "candidate_roi",
        "confirmed_roi",
        "composite_bundle",
        "composite_signature",
        "composite_saved_directory",
    ):
        st.session_state.pop(key, None)


def _invalidate_after_source_controls(st: Any) -> None:
    for key in (
        "source_map_config",
        "source_map_candidates",
        "source_map_discovery_signature",
    ):
        st.session_state.pop(key, None)
    _invalidate_after_discovery(st)


def _invalidate_after_map_selection(st: Any) -> None:
    for key in (
        "source_map_image_bytes",
        "source_map_metadata",
        "source_map_result",
        "source_map_candidate",
        "source_map_observation_time",
        "source_map_frequency_mhz",
    ):
        st.session_state.pop(key, None)
    _invalidate_after_map(st)


def _invalidate_after_roi_controls(st: Any) -> None:
    st.session_state.pop("candidate_roi", None)
    st.session_state.pop("confirmed_roi", None)
    _invalidate_composite(st)


def _invalidate_after_map(st: Any) -> None:
    for key in (
        "candidate_roi",
        "confirmed_roi",
        "composite_bundle",
        "composite_signature",
        "composite_saved_directory",
    ):
        st.session_state.pop(key, None)


def _invalidate_composite(st: Any) -> None:
    for key in (
        "composite_bundle",
        "composite_signature",
        "composite_saved_directory",
    ):
        st.session_state.pop(key, None)


def _invalidate_if_controls_changed(
    st: Any,
    signature_key: str,
    payload: dict[str, Any],
    invalidator: Any,
) -> str:
    """Invalidate dependent state only when a material control value changes."""

    signature = build_request_signature(payload)
    previous = st.session_state.get(signature_key)
    if isinstance(previous, str) and previous != signature:
        invalidator(st)
    st.session_state[signature_key] = signature
    return signature


def _download(
    column: Any,
    label: str,
    data: bytes,
    filename: str,
    mime: str,
    key: str,
) -> None:
    with column:
        import streamlit as st

        st.download_button(
            label,
            data=data,
            file_name=filename,
            mime=mime,
            on_click="ignore",
            key=key,
            width="stretch",
        )


def _utc_datetime(value: datetime | str | None) -> datetime:
    if value is None:
        raise ValueError("UTC datetime value is missing")
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        normalized = text[:-1] + "+00:00" if text.upper().endswith("Z") else text
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(f"Invalid UTC datetime: {value!r}") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


if __name__ == "__main__":
    main()


__all__ = [
    "FRONTEND_ID",
    "UI_FIELD_KEYS",
    "build_parser",
    "main",
    "prepare_single_panel_render",
]
