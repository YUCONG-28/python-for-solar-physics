"""Pure rendering and export helpers for the radio composite frontend."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import zipfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from solar_apps.frontends.radio.source_map.artifacts import data_to_image_pixel
from solar_apps.workflows.common.image_naming import build_scientific_image_filename
from solar_toolkit.radio.dart_spectrogram import (
    DartNarrowbandResult,
    DartSpectrogramWindow,
)
from solar_toolkit.radio.roi_lightcurve import RadioRoi

COMPOSITE_SCHEMA_VERSION = "radio-composite-v1"
MAP_TIME_COLOR = "#c2410c"
ROI_COLOR = "#00d4ff"


@dataclass(frozen=True, slots=True)
class FrequencyBand:
    """One validated DART frequency band in MHz."""

    low_mhz: float
    high_mhz: float

    def __post_init__(self) -> None:
        low = float(self.low_mhz)
        high = float(self.high_mhz)
        if not math.isfinite(low) or not math.isfinite(high):
            raise ValueError("DART frequency bounds must be finite")
        if low >= high:
            raise ValueError("DART frequency lower bound must be below the upper bound")
        object.__setattr__(self, "low_mhz", low)
        object.__setattr__(self, "high_mhz", high)

    @property
    def center_mhz(self) -> float:
        return (self.low_mhz + self.high_mhz) / 2.0

    @property
    def bandwidth_mhz(self) -> float:
        return self.high_mhz - self.low_mhz

    def validate_observed_range(self, observed: Sequence[float]) -> FrequencyBand:
        values = np.asarray(list(observed), dtype=float)
        finite = values[np.isfinite(values)]
        if not finite.size:
            raise ValueError("DART frequency axis contains no finite values")
        observed_low = float(np.min(finite))
        observed_high = float(np.max(finite))
        tolerance = max(1e-9, abs(observed_high - observed_low) * 1e-12)
        if (
            self.low_mhz < observed_low - tolerance
            or self.high_mhz > observed_high + tolerance
        ):
            raise ValueError(
                "Selected DART band is outside the observed frequency range: "
                f"{observed_low:g}-{observed_high:g} MHz"
            )
        selected = finite[(finite >= self.low_mhz) & (finite <= self.high_mhz)]
        if not selected.size:
            raise ValueError(
                "Selected DART band contains no original frequency channel"
            )
        return self

    def to_dict(self) -> dict[str, float]:
        return {
            "low_mhz": self.low_mhz,
            "high_mhz": self.high_mhz,
            "center_mhz": self.center_mhz,
            "bandwidth_mhz": self.bandwidth_mhz,
        }


@dataclass(frozen=True, slots=True)
class CompositeArtifactBundle:
    """In-memory composite products and their public filenames."""

    files: Mapping[str, bytes]
    filenames: Mapping[str, str]
    zip_bytes: bytes
    zip_filename: str
    metadata: Mapping[str, Any]


def build_request_signature(
    payload: Mapping[str, Any],
    *,
    source_paths: Iterable[str | Path] = (),
) -> str:
    """Hash material controls plus file size and modification identities."""

    identities = []
    for raw_path in sorted((Path(path).resolve() for path in source_paths), key=str):
        stat = raw_path.stat()
        identities.append(
            {
                "path": str(raw_path),
                "size": int(stat.st_size),
                "mtime_ns": int(stat.st_mtime_ns),
            }
        )
    encoded = json.dumps(
        {"schema": COMPOSITE_SCHEMA_VERSION, "request": payload, "files": identities},
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def frequency_band_from_selection(event: Any) -> FrequencyBand | None:
    """Read one vertical MHz range from a Streamlit Plotly selection event."""

    selection = _event_get(event, "selection")
    if selection is None:
        return None
    boxes = _event_get(selection, "box") or _event_get(selection, "boxes") or []
    if isinstance(boxes, Mapping):
        boxes = [boxes]
    for box in boxes:
        y0 = _event_get(box, "y0")
        y1 = _event_get(box, "y1")
        if y0 is None or y1 is None:
            values = _event_get(box, "y")
            if isinstance(values, Sequence) and len(values) >= 2:
                y0, y1 = values[0], values[-1]
        if y0 is not None and y1 is not None and float(y0) != float(y1):
            return FrequencyBand(*sorted((float(y0), float(y1))))
    points = _event_get(selection, "points") or []
    ys = [
        float(value)
        for point in points
        if (value := _event_get(point, "y")) is not None and math.isfinite(float(value))
    ]
    if len(ys) >= 2 and min(ys) < max(ys):
        return FrequencyBand(float(min(ys)), float(max(ys)))
    return None


def select_dart_time_overlap(
    time_utc: Sequence[datetime | str],
    time_start: datetime | str,
    time_end: datetime | str,
) -> tuple[datetime, datetime, bool]:
    """Return actual DART sample bounds inside a requested radio time range.

    The final boolean is true when DART does not cover the entire requested
    range.  No interpolation or extrapolation is performed.
    """

    start = _utc_datetime(time_start)
    end = _utc_datetime(time_end)
    if start >= end:
        raise ValueError("Shared UTC start must be before the end")
    samples = sorted(_utc_datetime(value) for value in time_utc)
    selected = [value for value in samples if start <= value <= end]
    if not selected:
        raise ValueError("The radio time range contains no DART sample")
    partial = start < samples[0] or end > samples[-1]
    return selected[0], selected[-1], partial


def build_dart_selection_figure(
    window: DartSpectrogramWindow,
    *,
    band: FrequencyBand | None = None,
):
    """Build a downsampled DART spectrum with a box-selectable frequency grid."""

    import plotly.graph_objects as go

    frequencies = np.asarray(window.frequency_mhz, dtype=float)
    values = np.asarray(window.stokes_i_db, dtype=float)
    if values.shape != (frequencies.size, len(window.time_utc)):
        raise ValueError("DART preview arrays do not share frequency and time axes")
    figure = go.Figure()
    figure.add_trace(
        go.Heatmap(
            z=values,
            x=list(window.time_utc),
            y=frequencies,
            colorscale="Turbo",
            colorbar={"title": "Stokes I (dB)"},
            hovertemplate=(
                "UTC=%{x|%Y-%m-%d %H:%M:%S.%L}<br>"
                "frequency=%{y:.4f} MHz<br>Stokes I=%{z:.4g} dB<extra></extra>"
            ),
        )
    )
    time_indices = _sample_indices(len(window.time_utc), target=56)
    frequency_indices = _sample_indices(frequencies.size, target=56)
    grid_x: list[datetime] = []
    grid_y: list[float] = []
    for frequency_index in frequency_indices:
        for time_index in time_indices:
            grid_x.append(window.time_utc[time_index])
            grid_y.append(float(frequencies[frequency_index]))
    figure.add_trace(
        go.Scattergl(
            x=grid_x,
            y=grid_y,
            mode="markers",
            marker={"size": 5, "opacity": 0.01, "color": "white"},
            hoverinfo="skip",
            showlegend=False,
            name="Frequency selection grid",
        )
    )
    if band is not None:
        figure.add_hrect(
            y0=band.low_mhz,
            y1=band.high_mhz,
            line={"color": ROI_COLOR, "width": 2},
            fillcolor="rgba(0, 212, 255, 0.16)",
        )
    figure.update_layout(
        title="DART dynamic spectrum — drag a horizontal frequency band",
        xaxis_title="Time (UTC)",
        yaxis_title="Frequency (MHz)",
        dragmode="select",
        height=560,
        margin={"l": 70, "r": 30, "t": 60, "b": 55},
    )
    return figure


def build_source_map_selection_figure(
    image_png: bytes,
    metadata: Mapping[str, Any],
    *,
    roi: RadioRoi | None = None,
    roi_mode: str = "box",
):
    """Build a Plotly ROI selector from one Source Map artifact panel."""

    import plotly.graph_objects as go

    panel = _single_panel(metadata)
    with Image.open(io.BytesIO(image_png)) as source:
        image = source.convert("RGBA")
        width, height = image.size
        left, top, right, bottom = [float(value) for value in panel["bbox_normalized"]]
        crop_box = (
            max(0, int(round(left * width))),
            max(0, int(round(top * height))),
            min(width, int(round(right * width))),
            min(height, int(round(bottom * height))),
        )
        crop = image.crop(crop_box)
        buffer = io.BytesIO()
        crop.save(buffer, format="PNG")
    image_uri = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode(
        "ascii"
    )
    x0, x1 = (float(value) for value in panel["xlim_arcsec"])
    y0, y1 = (float(value) for value in panel["ylim_arcsec"])
    figure = go.Figure()
    figure.add_layout_image(
        source=image_uri,
        xref="x",
        yref="y",
        x=x0,
        y=y1,
        sizex=x1 - x0,
        sizey=y1 - y0,
        sizing="stretch",
        layer="below",
    )
    xs = np.linspace(x0, x1, 80)
    ys = np.linspace(y0, y1, 80)
    grid_x, grid_y = np.meshgrid(xs, ys)
    figure.add_trace(
        go.Scattergl(
            x=grid_x.ravel(),
            y=grid_y.ravel(),
            mode="markers",
            marker={"size": 4, "opacity": 0.01, "color": "white"},
            hoverinfo="skip",
            showlegend=False,
            name="ROI selection grid",
        )
    )
    if roi is not None:
        vertices = list(roi.vertices_arcsec)
        closed = [*vertices, vertices[0]]
        figure.add_trace(
            go.Scatter(
                x=[point[0] for point in closed],
                y=[point[1] for point in closed],
                mode="lines",
                line={"color": ROI_COLOR, "width": 3},
                name=roi.label or "Confirmed ROI",
            )
        )
    figure.update_layout(
        title="Source Map ROI selection",
        xaxis_title="HPLN / arcsec",
        yaxis_title="HPLT / arcsec",
        dragmode="lasso" if str(roi_mode).lower() == "lasso" else "select",
        height=650,
        margin={"l": 70, "r": 30, "t": 60, "b": 60},
    )
    figure.update_xaxes(range=[x0, x1])
    figure.update_yaxes(range=[y0, y1], scaleanchor="x", scaleratio=1)
    return figure


def annotate_source_map_png(
    image_png: bytes,
    metadata: Mapping[str, Any],
    roi: RadioRoi,
    *,
    color: str = ROI_COLOR,
) -> bytes:
    """Draw a confirmed HPLN/HPLT ROI on the exact Source Map PNG bytes."""

    panel = _single_panel(metadata)
    panel_id = str(panel["id"])
    with Image.open(io.BytesIO(image_png)) as source:
        image = source.convert("RGBA")
    points = [
        data_to_image_pixel(metadata, panel_id, float(x), float(y))
        for x, y in roi.vertices_arcsec
    ]
    if len(points) < 3:
        raise ValueError("Confirmed ROI must contain at least three vertices")
    closed = [*points, points[0]]
    width = max(2, int(round(min(image.size) / 450.0 * 2.5)))
    draw = ImageDraw.Draw(image)
    draw.line(closed, fill=color, width=width, joint="curve")
    label = str(roi.label or "ROI").strip() or "ROI"
    anchor_x, anchor_y = points[0]
    font = ImageFont.load_default()
    box = draw.textbbox((anchor_x, anchor_y), label, font=font, stroke_width=1)
    pad = max(2, width)
    draw.rectangle(
        (box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad),
        fill=(0, 0, 0, 190),
    )
    draw.text(
        (anchor_x, anchor_y),
        label,
        fill=color,
        font=font,
        stroke_width=1,
        stroke_fill="black",
    )
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def build_composite_figure(
    annotated_map_png: bytes,
    radio_df: pd.DataFrame,
    dart_result: DartNarrowbandResult,
    *,
    roi: RadioRoi,
    map_time: datetime | str,
    map_frequency_mhz: float,
    polarization: str,
    time_start: datetime | str,
    time_end: datetime | str,
):
    """Create the publication-style three-row composite with shared UTC axes."""

    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    import matplotlib.dates as mdates

    start = _utc_datetime(time_start)
    end = _utc_datetime(time_end)
    marker = _utc_datetime(map_time)
    if start >= end:
        raise ValueError("Shared time range must have positive duration")
    if not start <= marker <= end:
        raise ValueError("Selected Source Map time is outside the shared radio range")
    frequency = float(map_frequency_mhz)
    if not math.isfinite(frequency):
        raise ValueError("Source Map frequency must be finite")
    radio_plot = _radio_plot_frame(radio_df, frequency)
    if not dart_result.curves:
        raise ValueError("DART narrowband extraction returned no curve")
    dart_curve = dart_result.curves[0]
    dart_times = [_utc_datetime(value) for value in dart_result.time_utc]
    dart_values = np.asarray(dart_curve.stokes_i_db, dtype=float)
    if len(dart_times) != dart_values.size:
        raise ValueError("DART narrowband values do not match the UTC axis")
    finite_dart = np.isfinite(dart_values)
    if not finite_dart.any():
        raise ValueError("DART narrowband curve contains no finite samples")

    with Image.open(io.BytesIO(annotated_map_png)) as source:
        map_image = np.asarray(source.convert("RGBA"))
    aspect = map_image.shape[0] / max(1, map_image.shape[1])
    map_ratio = min(2.5, max(1.45, aspect * 2.25))
    figure = Figure(figsize=(12.0, 11.2 + 2.0 * aspect), dpi=160, facecolor="white")
    FigureCanvasAgg(figure)
    grid = figure.add_gridspec(
        3,
        1,
        height_ratios=[map_ratio, 1.0, 1.0],
        hspace=0.08,
        left=0.10,
        right=0.97,
        top=0.98,
        bottom=0.08,
    )
    map_axis = figure.add_subplot(grid[0])
    radio_axis = figure.add_subplot(grid[1])
    dart_axis = figure.add_subplot(grid[2], sharex=radio_axis)
    map_axis.imshow(map_image)
    map_axis.set_axis_off()

    for label, group in radio_plot.groupby("polarization", sort=True, dropna=False):
        ordered = group.sort_values("obs_time_dt")
        radio_axis.plot(
            ordered["obs_time_dt"],
            ordered["raw_sum"],
            linewidth=1.0,
            marker=".",
            markersize=2.8,
            label=str(label or polarization),
        )
    radio_axis.set_title(
        f"Confirmed ROI integrated intensity | {frequency:g} MHz | {polarization}",
        fontsize=11,
        loc="left",
    )
    radio_axis.set_ylabel(_radio_axis_label(radio_plot))
    if radio_plot["polarization"].nunique(dropna=False) > 1:
        radio_axis.legend(loc="best", frameon=False, fontsize=8)

    dart_axis.plot(
        np.asarray(dart_times, dtype=object)[finite_dart],
        dart_values[finite_dart],
        color="#2563eb",
        linewidth=1.0,
    )
    dart_axis.set_title(
        "DART narrowband Stokes I intensity | "
        f"{dart_curve.requested_frequency_range_mhz[0]:g}-"
        f"{dart_curve.requested_frequency_range_mhz[1]:g} MHz",
        fontsize=11,
        loc="left",
    )
    dart_axis.set_ylabel("Stokes I intensity (dB)")
    dart_axis.set_xlabel("Time (UTC)")

    for axis in (radio_axis, dart_axis):
        axis.axvline(
            marker,
            color=MAP_TIME_COLOR,
            linewidth=0.9,
            alpha=0.95,
            zorder=4,
        )
        axis.grid(alpha=0.25, linestyle=":", linewidth=0.65)
        axis.set_xlim(start, end)
    radio_axis.tick_params(axis="x", which="both", labelbottom=False)
    locator = mdates.AutoDateLocator(minticks=4, maxticks=9)
    dart_axis.xaxis.set_major_locator(locator)
    dart_axis.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator, tz=UTC))
    figure.align_ylabels([radio_axis, dart_axis])
    return figure


def render_composite_png(*args: Any, dpi: int = 160, **kwargs: Any) -> bytes:
    """Render the three-row composite into PNG bytes."""

    figure = build_composite_figure(*args, **kwargs)
    output = io.BytesIO()
    figure.savefig(output, format="png", dpi=int(dpi), facecolor="white")
    figure.clear()
    return output.getvalue()


def build_composite_artifacts(
    source_map_png: bytes,
    source_map_metadata: Mapping[str, Any],
    radio_df: pd.DataFrame,
    dart_result: DartNarrowbandResult,
    *,
    roi: RadioRoi,
    map_time: datetime | str,
    map_frequency_mhz: float,
    polarization: str,
    time_start: datetime | str,
    time_end: datetime | str,
    request_signature: str,
    source_context: Mapping[str, Any] | None = None,
    generated_at: datetime | None = None,
    dpi: int = 160,
) -> CompositeArtifactBundle:
    """Build PNG, CSV, ROI, metadata, and ZIP products in memory."""

    generated = _utc_datetime(generated_at or datetime.now(UTC))
    marker = _utc_datetime(map_time)
    annotated = annotate_source_map_png(source_map_png, source_map_metadata, roi)
    composite_png = render_composite_png(
        annotated,
        radio_df,
        dart_result,
        roi=roi,
        map_time=marker,
        map_frequency_mhz=map_frequency_mhz,
        polarization=polarization,
        time_start=time_start,
        time_end=time_end,
        dpi=dpi,
    )
    image_name = build_scientific_image_filename(
        sequence=1,
        start_time=marker,
        instrument="radio-dart",
        channel=f"{float(map_frequency_mhz):g}mhz",
        polarization=polarization,
        product="radio-composite",
        qualifiers=(roi.roi_id,),
        generated_at=generated,
        extension=".png",
    )
    stem = Path(image_name).stem
    filenames = {
        "composite_png": image_name,
        "radio_csv": f"{stem}_radio-roi.csv",
        "dart_csv": f"{stem}_dart-narrowband.csv",
        "roi_json": f"{stem}_roi.json",
        "metadata_json": f"{stem}_metadata.json",
    }
    dart_frame = _dart_curve_frame(dart_result)
    public_source_map_metadata = {
        key: value
        for key, value in source_map_metadata.items()
        if not str(key).startswith("_")
    }
    metadata = {
        "schema_version": COMPOSITE_SCHEMA_VERSION,
        "generated_at_utc": generated.isoformat(),
        "request_signature": str(request_signature),
        "map": {
            "observation_time_utc": marker.isoformat(),
            "frequency_mhz": float(map_frequency_mhz),
            "polarization": str(polarization),
            "source_map": _json_safe(public_source_map_metadata),
        },
        "roi": roi.to_json_dict(),
        "radio_curve": {
            "metric": "raw_sum",
            "time_start_utc": _utc_datetime(time_start).isoformat(),
            "time_end_utc": _utc_datetime(time_end).isoformat(),
            "rows": int(len(radio_df)),
        },
        "dart_curve": {
            "representation": "source Stokes I dB intensity",
            "rows": int(len(dart_frame)),
            "curves": [
                {
                    "center_frequency_mhz": float(curve.center_frequency_mhz),
                    "requested_frequency_range_mhz": list(
                        curve.requested_frequency_range_mhz
                    ),
                    "sampled_frequency_range_mhz": list(
                        curve.sampled_frequency_range_mhz
                    ),
                    "channel_count": int(curve.channel_count),
                }
                for curve in dart_result.curves
            ],
        },
        "source": _json_safe(dict(source_context or {})),
        "artifacts": dict(filenames),
    }
    files = {
        "composite_png": composite_png,
        "radio_csv": radio_df.to_csv(index=False).encode("utf-8-sig"),
        "dart_csv": dart_frame.to_csv(index=False).encode("utf-8-sig"),
        "roi_json": (json.dumps(roi.to_json_dict(), indent=2) + "\n").encode("utf-8"),
        "metadata_json": (
            json.dumps(metadata, indent=2, ensure_ascii=True) + "\n"
        ).encode("utf-8"),
    }
    zip_output = io.BytesIO()
    with zipfile.ZipFile(
        zip_output, mode="w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for key, payload in files.items():
            archive.writestr(filenames[key], payload)
    return CompositeArtifactBundle(
        files=files,
        filenames=filenames,
        zip_bytes=zip_output.getvalue(),
        zip_filename=f"{stem}.zip",
        metadata=metadata,
    )


def save_composite_bundle(
    bundle: CompositeArtifactBundle,
    output_directory: str | Path,
) -> Path:
    """Write a bundle into a new directory without overwriting prior products."""

    output = Path(output_directory).expanduser().resolve(strict=False)
    output.mkdir(parents=True, exist_ok=True)
    stem = Path(bundle.zip_filename).stem
    destination = output / stem
    suffix = 2
    while destination.exists():
        destination = output / f"{stem}_{suffix:03d}"
        suffix += 1
    destination.mkdir(parents=False, exist_ok=False)
    for key, payload in bundle.files.items():
        (destination / bundle.filenames[key]).write_bytes(payload)
    (destination / bundle.zip_filename).write_bytes(bundle.zip_bytes)
    return destination


def _radio_plot_frame(df: pd.DataFrame, frequency_mhz: float) -> pd.DataFrame:
    data = df.copy()
    data["obs_time_dt"] = pd.to_datetime(
        data.get("obs_time"), errors="coerce", utc=True
    )
    data["raw_sum"] = pd.to_numeric(data.get("raw_sum"), errors="coerce")
    frequencies = pd.to_numeric(data.get("freq_mhz"), errors="coerce")
    quality = (
        data.get("quality_flag", pd.Series("ok", index=data.index))
        .astype(str)
        .str.lower()
        .eq("ok")
    )
    tolerance = max(1e-6, abs(float(frequency_mhz)) * 1e-5)
    valid = (
        quality
        & data["obs_time_dt"].notna()
        & np.isfinite(data["raw_sum"].to_numpy(dtype=float, na_value=np.nan))
        & np.isfinite(frequencies.to_numpy(dtype=float, na_value=np.nan))
        & (np.abs(frequencies - float(frequency_mhz)) <= tolerance)
    )
    result = data.loc[valid].copy()
    if result.empty:
        raise ValueError("Radio ROI analysis contains no valid raw_sum samples")
    if "polarization" not in result:
        result["polarization"] = ""
    return result


def _radio_axis_label(df: pd.DataFrame) -> str:
    units = []
    if "bunit" in df:
        units = sorted(
            {str(value).strip() for value in df["bunit"].dropna() if str(value).strip()}
        )
    if len(units) == 1:
        return f"ROI raw_sum ({units[0]} × pixel)"
    return "ROI raw_sum (native unit × pixel)"


def _dart_curve_frame(result: DartNarrowbandResult) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for curve in result.curves:
        for timestamp, value in zip(result.time_utc, curve.stokes_i_db, strict=True):
            rows.append(
                {
                    "time_utc": _utc_datetime(timestamp).isoformat(),
                    "stokes_i_db": float(value),
                    "center_frequency_mhz": float(curve.center_frequency_mhz),
                    "bandwidth_mhz": float(curve.bandwidth_mhz),
                    "requested_low_mhz": float(curve.requested_frequency_range_mhz[0]),
                    "requested_high_mhz": float(curve.requested_frequency_range_mhz[1]),
                    "sampled_low_mhz": float(curve.sampled_frequency_range_mhz[0]),
                    "sampled_high_mhz": float(curve.sampled_frequency_range_mhz[1]),
                    "channel_count": int(curve.channel_count),
                }
            )
    return pd.DataFrame(rows)


def _single_panel(metadata: Mapping[str, Any]) -> Mapping[str, Any]:
    panels = metadata.get("panels")
    if not isinstance(panels, list) or len(panels) != 1:
        raise ValueError("Composite Source Map must contain exactly one radio panel")
    return panels[0]


def _sample_indices(size: int, *, target: int) -> np.ndarray:
    if size <= 0:
        raise ValueError("Selection axis must contain at least one sample")
    count = min(int(size), int(target))
    return np.unique(np.linspace(0, size - 1, count).round().astype(int))


def _utc_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            raise ValueError("UTC datetime value must not be blank")
        normalized = text[:-1] + "+00:00" if text.upper().endswith("Z") else text
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(f"Invalid UTC datetime: {value!r}") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _event_get(value: Any, key: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(key)
    return getattr(value, key, None)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=_json_default))


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return _utc_datetime(value).isoformat()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"Object is not JSON serializable: {type(value).__name__}")


__all__ = [
    "COMPOSITE_SCHEMA_VERSION",
    "CompositeArtifactBundle",
    "FrequencyBand",
    "annotate_source_map_png",
    "build_composite_artifacts",
    "build_composite_figure",
    "build_dart_selection_figure",
    "build_request_signature",
    "build_source_map_selection_figure",
    "frequency_band_from_selection",
    "render_composite_png",
    "save_composite_bundle",
    "select_dart_time_overlap",
]
