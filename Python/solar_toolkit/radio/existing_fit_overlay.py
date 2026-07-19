"""Static context overlays from persisted center and Gaussian tables.

This service consumes existing table products only.  It deliberately does not
fit radio images or run another upstream workflow.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = [
    "ExistingFitOverlayRequest",
    "ExistingFitOverlayResult",
    "render_existing_fit_overlay",
]


_OUTPUT_IMAGE = "existing_fit_overlay.png"
_OUTPUT_METADATA = "existing_fit_overlay_metadata.json"
_THEMES = frozenset({"auto", "light", "dark"})


@dataclass(frozen=True)
class ExistingFitOverlayRequest:
    """Validated inputs for one persisted-table context overlay."""

    output_dir: Path
    center_csv: Path | None = None
    gaussian_csv: Path | None = None
    aia_fits: Path | None = None
    width: int = 1200
    height: int = 900
    marker_size: int = 10
    theme: str = "light"
    draw_lines: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "output_dir",
            Path(self.output_dir).expanduser().resolve(strict=False),
        )
        for field_name, label, suffixes in (
            ("center_csv", "center CSV", {".csv"}),
            ("gaussian_csv", "Gaussian CSV", {".csv"}),
            ("aia_fits", "AIA FITS", {".fits", ".fit", ".fts"}),
        ):
            value = getattr(self, field_name)
            if value is None:
                continue
            path = Path(value).expanduser().resolve(strict=True)
            if not path.is_file():
                raise ValueError(f"{label} must be a file: {path}")
            if path.suffix.casefold() not in suffixes:
                expected = ", ".join(sorted(suffixes))
                raise ValueError(f"{label} must use one of: {expected}")
            object.__setattr__(self, field_name, path)
        if self.center_csv is None and self.gaussian_csv is None:
            raise ValueError("Provide center_csv, gaussian_csv, or both.")
        if int(self.width) < 320 or int(self.height) < 240:
            raise ValueError("width and height must be at least 320 x 240 pixels")
        if int(self.marker_size) <= 0:
            raise ValueError("marker_size must be greater than zero")
        theme = str(self.theme).strip().lower()
        if theme not in _THEMES:
            raise ValueError("theme must be auto, light, or dark")
        object.__setattr__(self, "theme", theme)


@dataclass(frozen=True)
class ExistingFitOverlayResult:
    """Static image and metadata emitted by the service."""

    image_path: Path
    metadata_path: Path
    rendered_rows: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_path": str(self.image_path),
            "suggested_filename": self.image_path.name,
            "metadata_path": str(self.metadata_path),
            "rendered_rows": int(self.rendered_rows),
        }


def render_existing_fit_overlay(
    request: ExistingFitOverlayRequest,
) -> ExistingFitOverlayResult:
    """Render existing center/Gaussian rows, optionally over one AIA FITS file."""

    import pandas as pd

    from solar_toolkit.aia.background import read_aia_background
    from solar_toolkit.visualization.radio_source_overlay import (
        render_radio_source_overlay_png,
    )

    from ._image_naming import build_radio_image_filename
    from .trajectory import load_centers_table

    frames: list[pd.DataFrame] = []
    row_counts = {"center_table": 0, "gaussian_table": 0}
    for table_role, table_path in (
        ("center_table", request.center_csv),
        ("gaussian_table", request.gaussian_csv),
    ):
        if table_path is None:
            continue
        frame = load_centers_table(table_path)
        frame["input_table"] = table_role
        row_counts[table_role] = int(len(frame))
        frames.append(frame)
    centers = pd.concat(frames, ignore_index=True, sort=False)
    if centers.empty:
        raise ValueError("No valid center or Gaussian rows are available to overlay.")

    background = (
        read_aia_background(
            request.aia_fits, max_pixels=max(request.width, request.height)
        )
        if request.aia_fits is not None
        else None
    )
    output_dir = request.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    image_path = output_dir / build_radio_image_filename(
        centers,
        sequence=1,
        product="source_map_overlay",
        generated_at=datetime.now(timezone.utc),
    )
    metadata_path = output_dir / _OUTPUT_METADATA
    display_time = pd.to_datetime(centers["obs_time"], errors="coerce").max()
    render_radio_source_overlay_png(
        centers,
        image_path,
        frame_time=display_time,
        aia_background=background,
        width=int(request.width),
        height=int(request.height),
        theme_mode=request.theme,
        draw_lines=bool(request.draw_lines),
        marker_size=int(request.marker_size),
        title_prefix="Existing radio center/Gaussian overlay",
    )

    metadata = {
        "schema_version": 1,
        "fitting_performed": False,
        "inputs": {
            "center_table": str(request.center_csv) if request.center_csv else None,
            "gaussian_table": (
                str(request.gaussian_csv) if request.gaussian_csv else None
            ),
            "aia_fits": str(request.aia_fits) if request.aia_fits else None,
        },
        "artifacts": {
            "overlay_image": str(image_path),
            "overlay_metadata": str(metadata_path),
        },
        "row_counts": {**row_counts, "rendered": int(len(centers))},
        "frequencies_mhz": _sorted_floats(centers["freq_mhz"]),
        "polarizations": sorted(
            {str(value) for value in centers["polarization"].dropna().tolist()}
        ),
        "center_methods": sorted(
            {str(value) for value in centers["center_method"].dropna().tolist()}
        ),
        "time_range": {
            "start": _iso_or_none(centers["obs_time"].min()),
            "end": _iso_or_none(centers["obs_time"].max()),
        },
        "aia_background": _background_metadata(background),
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return ExistingFitOverlayResult(
        image_path=image_path,
        metadata_path=metadata_path,
        rendered_rows=len(centers),
    )


def _sorted_floats(values) -> list[float]:
    return sorted({float(value) for value in values.dropna().tolist()})


def _iso_or_none(value) -> str | None:
    try:
        if value is None or bool(value != value):
            return None
        return value.isoformat()
    except (AttributeError, TypeError, ValueError):
        return str(value) if value not in (None, "") else None


def _background_metadata(background) -> dict[str, Any] | None:
    if background is None:
        return None
    return {
        "path": str(background.path),
        "label": str(background.label),
        "wavelength": str(background.wavelength),
        "obs_time": _iso_or_none(background.obs_time),
        "shape": [int(value) for value in background.z.shape],
        "x_range_arcsec": [
            float(background.x_arcsec.min()),
            float(background.x_arcsec.max()),
        ],
        "y_range_arcsec": [
            float(background.y_arcsec.min()),
            float(background.y_arcsec.max()),
        ],
    }
