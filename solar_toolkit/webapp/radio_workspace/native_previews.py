"""Explicit, browser-native preview adapters for the radio workspace.

This module intentionally keeps its import surface lightweight. Scientific and
Plotly dependencies are imported only by the adapter that needs them, after the
caller explicitly requests a preview and all user-supplied paths have passed the
injected validator.
"""

from __future__ import annotations

import base64
import json
import math
import mimetypes
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = ["build_native_preview"]

PathValidator = Callable[[str | Path], str | Path | None]


def build_native_preview(
    adapter: str,
    form: Mapping[str, Any] | None,
    *,
    validate_path: PathValidator,
) -> dict[str, Any]:
    """Build one explicitly requested native preview.

    Successful adapters return a JSON-compatible mapping with ``status`` set to
    ``"ready"``. Adapters that require state owned by another layer return an
    ``"unavailable"`` result rather than importing that layer. Invalid inputs
    and rejected paths raise an exception for the route boundary to report.
    """

    adapter_name = str(adapter or "").strip().lower()
    payload = dict(form or {})
    if not callable(validate_path):
        raise TypeError("validate_path must be callable")

    if adapter_name == "roi-selection":
        return _build_roi_selection_preview(payload, validate_path=validate_path)
    if adapter_name == "trajectory-media":
        return _build_trajectory_preview(payload, validate_path=validate_path)
    if adapter_name == "drift-selection":
        return _build_drift_selection_preview(payload, validate_path=validate_path)
    if adapter_name == "file-browser":
        return _build_file_browser(payload, validate_path=validate_path)
    if adapter_name in {"run-index", "artifact-index"}:
        return _unavailable_index(adapter_name)
    raise ValueError(f"Unknown native preview adapter: {adapter!r}")


def _build_roi_selection_preview(
    form: Mapping[str, Any], *, validate_path: PathValidator
) -> dict[str, Any]:
    radio_dir = _required_validated_path(form, "radio_dir", validate_path=validate_path)
    if not radio_dir.is_dir():
        raise NotADirectoryError(f"Radio data folder does not exist: {radio_dir}")

    pattern = _safe_glob_pattern(form.get("pattern", "*.fits"))
    recursive = _as_bool(form.get("recursive", True), default=True)
    max_side = _bounded_int(form.get("max_side", 256), minimum=32, maximum=1024)
    low_percentile = _bounded_float(
        form.get("low_percentile", 1.0), minimum=0.0, maximum=100.0
    )
    high_percentile = _bounded_float(
        form.get("high_percentile", 99.7), minimum=0.0, maximum=100.0
    )
    if low_percentile >= high_percentile:
        raise ValueError("low_percentile must be less than high_percentile")
    roi_mode = str(form.get("roi_mode", "box") or "box").strip().lower()
    if roi_mode not in {"box", "lasso"}:
        raise ValueError("roi_mode must be 'box' or 'lasso'")

    # Deliberately lazy: importing these modules loads NumPy, Astropy, and Plotly.
    import numpy as np

    from solar_toolkit.radio.centers import iter_radio_images, select_radio_files
    from solar_toolkit.radio.roi_lightcurve import RadioRoi, build_radio_roi_mask
    from solar_toolkit.radio.roi_lightcurve_app import build_reference_figure

    files = select_radio_files(
        radio_dir,
        pattern=pattern,
        recursive=recursive,
    )
    if not files:
        raise FileNotFoundError(
            f"No compatible FITS paths found under {radio_dir} matching {pattern!r}"
        )

    candidate_limit = 2000
    discovered_count = len(files)
    files = files[:candidate_limit]
    compatibility_probe = RadioRoi.from_box(-1.0, -1.0, 1.0, 1.0)
    candidates: list[dict[str, Any]] = []
    skipped: list[str] = []
    for discovered_path in files:
        source_path = _validated_path(discovered_path, validate_path=validate_path)
        if not source_path.is_file():
            skipped.append(f"{source_path.name}: not a file")
            continue

        images = iter_radio_images(source_path)
        compatible_item = None
        try:
            for item in images:
                try:
                    image = np.asarray(item.image)
                    if image.ndim != 2 or image.size == 0:
                        raise ValueError("not a non-empty 2D image")
                    if not bool(np.isfinite(image).any()):
                        raise ValueError("image contains no finite pixels")

                    # This public ROI API validates the HPLN/HPLT WCS contract.
                    build_radio_roi_mask(
                        item.header,
                        (1, 1),
                        compatibility_probe,
                    )
                except (TypeError, ValueError, RuntimeError):
                    continue
                compatible_item = item
                candidates.append(
                    {
                        "path": str(source_path),
                        "relative_path": _relative_text(source_path, radio_dir),
                        "name": source_path.name,
                        "hdu_index": int(item.hdu_index),
                        "image_shape": [int(value) for value in image.shape],
                        "polarization": str(item.pol),
                        "frequency_mhz": _finite_float_or_none(item.freq_mhz),
                        "observation_time": _iso_or_none(item.obs_time),
                    }
                )
                # The browser selects files, not individual HDUs. Use the first
                # ROI-compatible plane as that file's deterministic reference.
                break
        finally:
            close = getattr(images, "close", None)
            if callable(close):
                close()
        if compatible_item is None:
            skipped.append(f"{source_path.name}: no ROI-compatible image plane")

    if not candidates:
        last_reason = skipped[-1] if skipped else "no readable image plane"
        raise RuntimeError(
            "No ROI-compatible HPLN/HPLT radio image was found; "
            f"last reason: {last_reason}"
        )

    requested_paths = _selected_roi_preview_paths(
        form.get("selected_files_json"), validate_path=validate_path
    )
    if requested_paths is None:
        selected_indices = _representative_frequency_indices(candidates, maximum=9)
    else:
        candidate_indices = {
            Path(candidate["path"]).resolve(strict=False): index
            for index, candidate in enumerate(candidates)
        }
        selected_indices = []
        for requested in requested_paths:
            try:
                index = candidate_indices[requested]
            except KeyError as exc:
                raise ValueError(
                    "Every selected ROI preview file must be a compatible candidate "
                    "from the validated radio folder."
                ) from exc
            if index not in selected_indices:
                selected_indices.append(index)
        if not selected_indices:
            raise ValueError("Select at least one ROI reference file.")
        if len(selected_indices) > 9:
            raise ValueError("Select at most 9 ROI reference files.")

    selected_paths = [str(candidates[index]["path"]) for index in selected_indices]
    selected_path_set = set(selected_paths)
    for candidate in candidates:
        candidate["selected"] = candidate["path"] in selected_path_set

    selected_items = [
        _load_roi_candidate_image(
            candidates[index],
            validate_path=validate_path,
            compatibility_probe=compatibility_probe,
        )
        for index in selected_indices
    ]

    figures = [
        build_reference_figure(
            item,
            low_percentile=low_percentile,
            high_percentile=high_percentile,
            max_side=max_side,
            roi_mode=roi_mode,
            selection_enabled=True,
        )
        for item in selected_items
    ]
    figure = _build_roi_reference_grid(figures, selected_items, roi_mode=roi_mode)
    first_index = selected_indices[0]
    first_item = selected_items[0]
    first_candidate = candidates[first_index]
    return {
        "adapter": "roi-selection",
        "status": "ready",
        "kind": "plotly",
        "figure": _plotly_figure_dict(figure),
        "candidates": candidates,
        "selected_files": selected_paths,
        "selection": {
            "coordinate_system": "HPLN/HPLT arcsec",
            "default_mode": roi_mode,
            "supported_modes": ["box", "lasso"],
            "event_source": "plotly_selected",
            "x_field": "x",
            "y_field": "y",
        },
        "metadata": {
            "source_path": first_candidate["path"],
            "source_name": first_candidate["name"],
            "relative_path": first_candidate["relative_path"],
            "hdu_index": int(first_item.hdu_index),
            "image_shape": [int(value) for value in first_item.image.shape],
            "polarization": str(first_item.pol),
            "frequency_mhz": _finite_float_or_none(first_item.freq_mhz),
            "observation_time": _iso_or_none(first_item.obs_time),
            "pattern": pattern,
            "recursive": recursive,
            "candidate_count": len(candidates),
            "discovered_file_count": discovered_count,
            "candidate_limit": candidate_limit,
            "candidates_truncated": discovered_count > len(files),
            "selected_count": len(selected_items),
            "selection_limit": 9,
            "skipped_before_match": len(skipped),
            "selected_files_scope": "reference_preview_only",
        },
    }


def _load_roi_candidate_image(
    candidate: Mapping[str, Any],
    *,
    validate_path: PathValidator,
    compatibility_probe: Any,
) -> Any:
    """Reload one selected candidate without retaining all scanned FITS arrays."""

    import numpy as np

    from solar_toolkit.radio.centers import iter_radio_images
    from solar_toolkit.radio.roi_lightcurve import build_radio_roi_mask

    source_path = _validated_path(candidate["path"], validate_path=validate_path)
    expected_path = Path(str(candidate["path"])).resolve(strict=False)
    if source_path != expected_path:
        raise ValueError(
            "Validated ROI candidate path changed before preview rendering."
        )
    expected_hdu = int(candidate["hdu_index"])
    images = iter_radio_images(source_path)
    try:
        for item in images:
            if int(item.hdu_index) != expected_hdu:
                continue
            image = np.asarray(item.image)
            if image.ndim != 2 or image.size == 0 or not bool(np.isfinite(image).any()):
                break
            build_radio_roi_mask(item.header, (1, 1), compatibility_probe)
            return item
    finally:
        close = getattr(images, "close", None)
        if callable(close):
            close()
    raise RuntimeError(f"Selected ROI candidate is no longer readable: {source_path}")


def _selected_roi_preview_paths(
    raw_value: Any, *, validate_path: PathValidator
) -> list[Path] | None:
    if raw_value in (None, ""):
        return None
    if isinstance(raw_value, str):
        try:
            decoded = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "selected_files_json must be a JSON array of paths."
            ) from exc
    else:
        decoded = raw_value
    if not isinstance(decoded, list) or any(
        not isinstance(value, str) or not value.strip() for value in decoded
    ):
        raise ValueError("selected_files_json must be a JSON array of paths.")
    return [_validated_path(value, validate_path=validate_path) for value in decoded]


def _representative_frequency_indices(
    candidates: list[dict[str, Any]], *, maximum: int
) -> list[int]:
    selected: list[int] = []
    seen: set[float | str] = set()
    for index, candidate in enumerate(candidates):
        frequency = candidate.get("frequency_mhz")
        key: float | str = (
            round(float(frequency), 6) if frequency is not None else "unknown"
        )
        if key in seen:
            continue
        seen.add(key)
        selected.append(index)
        if len(selected) >= maximum:
            break
    return selected or [0]


def _build_roi_reference_grid(
    figures: list[Any], items: list[Any], *, roi_mode: str
) -> Any:
    if len(figures) == 1:
        return figures[0]

    from plotly.subplots import make_subplots

    count = len(figures)
    columns = min(3, count)
    rows = math.ceil(count / columns)
    titles = [
        (
            f"{_finite_float_or_none(item.freq_mhz):g} MHz | {item.pol}"
            if _finite_float_or_none(item.freq_mhz) is not None
            else f"Unknown frequency | {item.pol}"
        )
        for item in items
    ]
    grid = make_subplots(rows=rows, cols=columns, subplot_titles=titles)
    for index, source in enumerate(figures):
        row = index // columns + 1
        column = index % columns + 1
        for trace in source.data:
            grid.add_trace(trace, row=row, col=column)
        axis_suffix = "" if index == 0 else str(index + 1)
        grid.update_xaxes(title_text="HPLN / arcsec", row=row, col=column)
        grid.update_yaxes(
            title_text="HPLT / arcsec",
            scaleanchor=f"x{axis_suffix}",
            scaleratio=1,
            row=row,
            col=column,
        )
    grid.update_layout(
        title="Multi-frequency ROI reference grid",
        dragmode="lasso" if str(roi_mode).lower() == "lasso" else "select",
        height=max(620, rows * 430),
        margin={"l": 55, "r": 20, "t": 85, "b": 50},
        showlegend=False,
    )
    return grid


def _build_trajectory_preview(
    form: Mapping[str, Any], *, validate_path: PathValidator
) -> dict[str, Any]:
    centers_path = _required_validated_path(
        form, "centers", validate_path=validate_path
    )
    if not centers_path.is_file():
        raise FileNotFoundError(f"Center table does not exist: {centers_path}")
    if centers_path.suffix.lower() not in {".csv", ".xlsx", ".xls"}:
        raise ValueError("Center table must be CSV or XLSX/XLS")

    # Deliberately lazy: table readers and Plotly are only needed for this adapter.
    import pandas as pd

    from solar_toolkit.aia.background import scan_aia_folder
    from solar_toolkit.radio.source_app import build_preloaded_playback_payload
    from solar_toolkit.radio.trajectory import (
        filter_centers,
        frame_times,
        load_centers_table,
        select_visible_centers,
    )
    from solar_toolkit.visualization.radio_source_trajectory import (
        build_trajectory_figure,
    )

    centers = load_centers_table(
        centers_path,
        valid_only=_as_bool(form.get("valid_only", True), default=True),
    )
    centers = filter_centers(
        centers,
        freqs=_float_list(form.get("freqs")),
        polarizations=_text_list(form.get("polarizations")),
        center_methods=_text_list(form.get("center_methods")),
    )
    if centers.empty:
        raise ValueError("Center table contains no valid rows after filtering")

    times = frame_times(centers)
    if not times:
        raise ValueError("Center table contains no usable observation times")
    frame_time = _select_frame_time(times, form)
    mode = str(form.get("frame_mode", form.get("mode", "all")) or "all").strip().lower()
    tail_n = _bounded_int(form.get("tail_n", 5), minimum=1, maximum=10000)
    visible = select_visible_centers(
        centers,
        frame_time,
        mode=mode,
        tail_n=tail_n,
    )
    if visible.empty:
        raise ValueError("Selected trajectory frame contains no visible centers")

    figure, compare_table = build_trajectory_figure(
        visible,
        frame_time,
        draw_lines=_as_bool(form.get("draw_lines", True), default=True),
        compare_lr=_as_bool(form.get("compare_lr", False), default=False),
        compare_tolerance_sec=float(form.get("compare_tolerance_sec", 1.0)),
        height=_bounded_int(form.get("height", 760), minimum=320, maximum=2400),
        theme_mode=str(form.get("theme_mode", form.get("theme", "auto")) or "auto"),
        use_webgl=_as_bool(form.get("use_webgl", True), default=True),
        plot_layout=str(form.get("plot_layout", "overlay") or "overlay"),
        facet_by=str(form.get("facet_by", "freq_mhz") or "freq_mhz"),
        marker_size=_bounded_int(form.get("marker_size", 9), minimum=1, maximum=64),
    )
    playback_times = _sample_times(
        times,
        _bounded_int(form.get("max_playback_frames", 600), minimum=1, maximum=2000),
    )
    use_aia = _as_bool(form.get("use_aia", False), default=False)
    aia_table = None
    if use_aia:
        aia_dir = _required_validated_path(form, "aia_dir", validate_path=validate_path)
        if not aia_dir.is_dir():
            raise NotADirectoryError(f"AIA folder does not exist: {aia_dir}")
        aia_table = scan_aia_folder(
            aia_dir,
            pattern=str(form.get("aia_pattern", "*.fits") or "*.fits"),
        )
        if aia_table.empty:
            raise ValueError("AIA folder contains no time-resolvable FITS files")
    playback = build_preloaded_playback_payload(
        centers,
        playback_times,
        frame_mode=mode,
        tail_n=tail_n,
        aia_table=aia_table,
        use_aia=use_aia,
        max_aia_dt_sec=_bounded_float(
            form.get("max_aia_dt_sec", 3600.0), minimum=0.1, maximum=86400.0
        ),
        playback_aia_max_pixels=_bounded_int(
            form.get("aia_max_pixels", 384), minimum=64, maximum=2048
        ),
        theme_mode=str(form.get("theme_mode", form.get("theme", "auto")) or "auto"),
        draw_lines=_as_bool(form.get("draw_lines", True), default=True),
        fps=_bounded_float(form.get("fps", 2.0), minimum=0.2, maximum=60.0),
        plot_layout=str(form.get("plot_layout", "overlay") or "overlay"),
        facet_by=str(form.get("facet_by", "freq_mhz") or "freq_mhz"),
        marker_size=_bounded_int(form.get("marker_size", 9), minimum=1, maximum=64),
    )
    selected_timestamp = pd.Timestamp(frame_time)
    return {
        "adapter": "trajectory-media",
        "status": "ready",
        "kind": "plotly",
        "figure": _plotly_figure_dict(figure),
        "playback": playback,
        "metadata": {
            "source_path": str(centers_path),
            "source_name": centers_path.name,
            "row_count": int(len(centers)),
            "visible_row_count": int(len(visible)),
            "frame_count": int(len(times)),
            "playback_frame_count": int(len(playback_times)),
            "playback_sampled": len(playback_times) < len(times),
            "frame_time": selected_timestamp.isoformat(),
            "first_frame_time": pd.Timestamp(times[0]).isoformat(),
            "last_frame_time": pd.Timestamp(times[-1]).isoformat(),
            "mode": mode,
            "tail_n": tail_n,
            "lr_comparison_count": int(len(compare_table)),
        },
    }


def _build_drift_selection_preview(
    form: Mapping[str, Any], *, validate_path: PathValidator
) -> dict[str, Any]:
    preview_path = _required_validated_path(
        form, "spectrogram_image", validate_path=validate_path
    )
    metadata_path = _required_validated_path(
        form, "spectrogram_metadata", validate_path=validate_path
    )
    if not preview_path.is_file():
        raise FileNotFoundError(f"Spectrogram image does not exist: {preview_path}")
    if not metadata_path.is_file():
        raise FileNotFoundError(f"Spectrogram metadata does not exist: {metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise TypeError("Spectrogram metadata must be a JSON object")
    x_start = metadata.get("x_start_iso") or metadata.get("spectrogram_time_start")
    x_end = metadata.get("x_end_iso") or metadata.get("spectrogram_time_end")
    f_min = metadata.get("f_min_mhz", metadata.get("spectrogram_f_start"))
    f_max = metadata.get("f_max_mhz", metadata.get("spectrogram_f_end"))
    if x_start in (None, "") or x_end in (None, ""):
        raise ValueError("Spectrogram metadata is missing x_start_iso/x_end_iso")
    try:
        f_min_value = float(f_min)
        f_max_value = float(f_max)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Spectrogram metadata is missing finite frequency bounds"
        ) from exc
    if not all(math.isfinite(value) for value in (f_min_value, f_max_value)):
        raise ValueError("Spectrogram frequency bounds must be finite")
    if f_min_value > f_max_value:
        f_min_value, f_max_value = f_max_value, f_min_value

    mime_type = mimetypes.guess_type(preview_path.name)[0] or "image/png"
    source = f"data:{mime_type};base64," + base64.b64encode(
        preview_path.read_bytes()
    ).decode("ascii")
    figure = {
        "data": [
            {
                "type": "heatmap",
                "x": [str(x_start), str(x_end)],
                "y": [f_min_value, f_max_value],
                "z": [[0.0, 0.0], [0.0, 0.0]],
                "opacity": 0.01,
                "showscale": False,
                "hovertemplate": "Time: %{x}<br>Frequency: %{y:.2f} MHz<extra></extra>",
            }
        ],
        "layout": {
            "title": "Drift-rate endpoint selection",
            "height": 650,
            "xaxis": {"title": "Time (UT)", "range": [str(x_start), str(x_end)]},
            "yaxis": {
                "title": "Frequency (MHz)",
                "range": [f_min_value, f_max_value],
            },
            "images": [
                {
                    "source": source,
                    "xref": "x",
                    "yref": "y",
                    "x": str(x_start),
                    "y": f_max_value,
                    "sizex": _datetime_span_milliseconds(x_start, x_end),
                    "sizey": f_max_value - f_min_value,
                    "xanchor": "left",
                    "yanchor": "top",
                    "sizing": "stretch",
                    "layer": "below",
                }
            ],
            "clickmode": "event",
        },
    }
    return {
        "adapter": "drift-selection",
        "status": "ready",
        "kind": "plotly",
        "figure": figure,
        "selection": {
            "mode": "two-point-lines",
            "event_source": "continuous-plot-click",
            "output_field": "drift_lines_json",
        },
        "metadata": {
            "source_path": str(preview_path),
            "metadata_path": str(metadata_path),
            "x_start_iso": str(x_start),
            "x_end_iso": str(x_end),
            "f_min_mhz": f_min_value,
            "f_max_mhz": f_max_value,
        },
    }


def _build_file_browser(
    form: Mapping[str, Any], *, validate_path: PathValidator
) -> dict[str, Any]:
    raw_path = form.get("path") or form.get("radio_dir")
    if raw_path in (None, ""):
        return {
            "adapter": "file-browser",
            "status": "unavailable",
            "kind": "file-browser",
            "items": [],
            "reason": "Choose a local folder to browse.",
        }

    root = _validated_path(raw_path, validate_path=validate_path)
    if not root.exists():
        raise FileNotFoundError(f"Browse path does not exist: {root}")
    limit = _bounded_int(form.get("limit", 200), minimum=1, maximum=1000)
    candidates = (
        [root]
        if root.is_file()
        else sorted(
            root.iterdir(), key=lambda item: (not item.is_dir(), item.name.casefold())
        )
    )
    selected = candidates[:limit]
    items = [_file_item(path, root=root) for path in selected]
    return {
        "adapter": "file-browser",
        "status": "ready",
        "kind": "file-browser",
        "items": items,
        "metadata": {
            "root": str(root),
            "count": len(items),
            "total_count": len(candidates),
            "truncated": len(candidates) > len(items),
            "limit": limit,
        },
    }


def _unavailable_index(adapter: str) -> dict[str, Any]:
    label = "run manifests" if adapter == "run-index" else "artifact manifests"
    return {
        "adapter": adapter,
        "status": "unavailable",
        "kind": adapter,
        "items": [],
        "reason": f"{label.capitalize()} require an injected workspace store.",
    }


def _required_validated_path(
    form: Mapping[str, Any], key: str, *, validate_path: PathValidator
) -> Path:
    value = form.get(key)
    if value in (None, ""):
        raise ValueError(f"Missing required path field: {key}")
    return _validated_path(value, validate_path=validate_path)


def _validated_path(value: Any, *, validate_path: PathValidator) -> Path:
    validated = validate_path(value)
    resolved_value = value if validated is None else validated
    return Path(str(resolved_value)).expanduser().resolve(strict=False)


def _safe_glob_pattern(value: Any) -> str:
    pattern = str(value or "*.fits").strip()
    if not pattern:
        raise ValueError("FITS pattern cannot be empty")
    path = Path(pattern)
    if path.is_absolute() or path.drive or ".." in path.parts:
        raise ValueError("FITS pattern must stay within the validated radio folder")
    return pattern


def _select_frame_time(times: list[Any], form: Mapping[str, Any]) -> Any:
    requested = form.get("frame_time")
    if requested not in (None, ""):
        import pandas as pd

        timestamp = pd.Timestamp(requested)
        if pd.isna(timestamp):
            raise ValueError(f"Invalid frame_time: {requested!r}")
        return timestamp
    index = int(form.get("frame_index", -1))
    if index < 0:
        index += len(times)
    if not 0 <= index < len(times):
        raise IndexError(f"frame_index is outside 0..{len(times) - 1}")
    return times[index]


def _sample_times(times: list[Any], maximum: int) -> list[Any]:
    """Bound browser payload size while preserving the first and last frames."""

    if len(times) <= maximum:
        return list(times)
    if maximum == 1:
        return [times[-1]]
    step = (len(times) - 1) / (maximum - 1)
    indices = [round(index * step) for index in range(maximum)]
    return [times[index] for index in dict.fromkeys(indices)]


def _plotly_figure_dict(figure: Any) -> dict[str, Any]:
    """Return a plain mapping accepted by the standard-library JSON encoder."""

    return json.loads(figure.to_json())


def _file_item(path: Path, *, root: Path) -> dict[str, Any]:
    stat = path.stat()
    if path.is_dir():
        kind = "directory"
        size: int | None = None
    elif path.is_file():
        kind = "file"
        size = int(stat.st_size)
    else:
        kind = "other"
        size = int(stat.st_size)
    return {
        "name": path.name,
        "path": str(path),
        "relative_path": _relative_text(path, root),
        "kind": kind,
        "size": size,
        "modified_at": datetime.fromtimestamp(
            stat.st_mtime, tz=timezone.utc
        ).isoformat(),
        "suffix": path.suffix.lower(),
    }


def _relative_text(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return path.name


def _finite_float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _iso_or_none(value: Any) -> str | None:
    if value is None:
        return None
    method = getattr(value, "isoformat", None)
    return str(method()) if callable(method) else str(value)


def _datetime_span_milliseconds(start: Any, end: Any) -> float:
    def parse(value: Any) -> datetime:
        text = str(value).strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    span = (parse(end) - parse(start)).total_seconds() * 1000.0
    if not math.isfinite(span) or span <= 0:
        raise ValueError("Spectrogram time bounds must be increasing")
    return span


def _as_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off", ""}:
        return False
    raise ValueError(f"Invalid boolean value: {value!r}")


def _bounded_int(value: Any, *, minimum: int, maximum: int) -> int:
    number = int(value)
    if not minimum <= number <= maximum:
        raise ValueError(f"Expected an integer between {minimum} and {maximum}")
    return number


def _bounded_float(value: Any, *, minimum: float, maximum: float) -> float:
    number = float(value)
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise ValueError(f"Expected a finite number between {minimum} and {maximum}")
    return number


def _text_list(value: Any) -> list[str] | None:
    if value in (None, "", [], ()):
        return None
    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        items = value
    else:
        items = [value]
    result = [str(item).strip() for item in items if str(item).strip()]
    return result or None


def _float_list(value: Any) -> list[float] | None:
    items = _text_list(value)
    return [float(item) for item in items] if items else None
