"""Structured, non-interactive DEM/radio overlay adapter.

The historical :mod:`dem_radio_source_overlay` module remains the canonical
implementation of the FITS/Tb loading, radio time matching, and plotting
science.  This module provides the explicit file and output contract needed by
the Radio Workspace without changing that compatibility entry point.
"""

from __future__ import annotations

import argparse
import json
import threading
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "DemRadioOverlayRequest",
    "DemRadioOverlayResult",
    "build_parser",
    "main",
    "render_dem_radio_overlay",
]


_CONFIG_LOCK = threading.Lock()
_OUTPUT_IMAGE = "dem_radio_overlay.png"
_OUTPUT_METADATA = "dem_radio_overlay_metadata.json"


@dataclass(frozen=True)
class DemRadioOverlayRequest:
    """Validated inputs for one DEM brightness-temperature/radio overlay."""

    aia_fits: Path
    tb_data: Path
    output_dir: Path
    radio_file: Path | None = None
    radio_dir: Path | None = None
    radio_pattern: str = "*.fits"
    time_match_level: str = "minute"
    tb_pixel_size: float = 3.0
    tb_xmin: float = -1150.0
    tb_xmax: float = 1150.0
    tb_ymin: float = -1150.0
    tb_ymax: float = 1150.0
    display_mode: str = "custom"
    display_xmin: float = -1600.0
    display_xmax: float = 1600.0
    display_ymin: float = -1600.0
    display_ymax: float = 1600.0
    percentile_low: float = 1.0
    percentile_high: float = 99.0
    radio_smooth_sigma: float = 1.5
    dpi: int = 300

    def __post_init__(self) -> None:
        object.__setattr__(self, "aia_fits", _input_file(self.aia_fits, "AIA FITS"))
        object.__setattr__(self, "tb_data", _input_file(self.tb_data, "Tb data"))
        object.__setattr__(
            self, "output_dir", Path(self.output_dir).expanduser().resolve(strict=False)
        )
        if self.radio_file is not None:
            object.__setattr__(
                self, "radio_file", _input_file(self.radio_file, "radio FITS")
            )
        if self.radio_dir is not None:
            object.__setattr__(
                self, "radio_dir", _input_dir(self.radio_dir, "radio directory")
            )
        if self.radio_file is None and self.radio_dir is None:
            raise ValueError("Either radio_file or radio_dir is required")
        _validate_pattern(self.radio_pattern)
        if self.time_match_level not in {"minute", "hour", "any"}:
            raise ValueError("time_match_level must be minute, hour, or any")
        if self.display_mode not in {"full", "solar_disk", "custom"}:
            raise ValueError("display_mode must be full, solar_disk, or custom")
        if self.tb_pixel_size <= 0:
            raise ValueError("tb_pixel_size must be positive")
        if not self.tb_xmin < self.tb_xmax or not self.tb_ymin < self.tb_ymax:
            raise ValueError("Tb coordinate minima must be smaller than maxima")
        if not self.display_xmin < self.display_xmax:
            raise ValueError("display_xmin must be smaller than display_xmax")
        if not self.display_ymin < self.display_ymax:
            raise ValueError("display_ymin must be smaller than display_ymax")
        if not 0 <= self.percentile_low < self.percentile_high <= 100:
            raise ValueError("percentiles must satisfy 0 <= low < high <= 100")
        if self.radio_smooth_sigma < 0:
            raise ValueError("radio_smooth_sigma cannot be negative")
        if self.dpi <= 0:
            raise ValueError("dpi must be positive")


@dataclass(frozen=True)
class DemRadioOverlayResult:
    """Files and matching metadata produced by the adapter."""

    image_path: Path
    metadata_path: Path
    radio_file: Path
    aia_time: str
    radio_time: str
    time_difference_seconds: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_path": str(self.image_path),
            "metadata_path": str(self.metadata_path),
            "radio_file": str(self.radio_file),
            "aia_time": self.aia_time,
            "radio_time": self.radio_time,
            "time_difference_seconds": self.time_difference_seconds,
        }


def _input_file(value: str | Path, label: str) -> Path:
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError(f"{label} must be a file: {path}")
    return path


def _input_dir(value: str | Path, label: str) -> Path:
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_dir():
        raise ValueError(f"{label} must be a directory: {path}")
    return path


def _validate_pattern(pattern: str) -> None:
    value = str(pattern).strip()
    if not value:
        raise ValueError("radio_pattern cannot be empty")
    if (
        Path(value).is_absolute()
        or ".." in value
        or "/" in value
        or "\\" in value
        or ":" in value
    ):
        raise ValueError("radio_pattern must be a filename pattern without directories")


def _radio_selection(request: DemRadioOverlayRequest, workflow, aia_map):
    if request.radio_file is not None:
        radio_time = workflow.get_radio_time(str(request.radio_file))
        return request.radio_file, radio_time, None

    assert request.radio_dir is not None
    files = sorted(
        path.resolve(strict=True)
        for path in request.radio_dir.glob(request.radio_pattern)
        if not path.is_symlink() and path.is_file()
    )
    if not files:
        raise FileNotFoundError(
            f"No radio FITS files match {request.radio_pattern!r} in "
            f"{request.radio_dir}"
        )
    selected, radio_time, difference = workflow.find_matching_radio(
        [str(path) for path in files], aia_map.obs_dt
    )
    return Path(selected).resolve(strict=True), radio_time, difference


def _workflow_config(request: DemRadioOverlayRequest, workflow) -> dict[str, Any]:
    config = deepcopy(workflow._DEFAULT_CONFIG)
    config.update(
        {
            "aia_fits_path": str(request.aia_fits),
            "tb_data_path": str(request.tb_data),
            "overlay_radio": True,
            "radio_sources_dir": str(request.radio_dir or request.radio_file.parent),
            "radio_sources_pattern": request.radio_pattern,
            "time_match_level": request.time_match_level,
            "tb_pixel_size": request.tb_pixel_size,
            "tb_xmin": request.tb_xmin,
            "tb_xmax": request.tb_xmax,
            "tb_ymin": request.tb_ymin,
            "tb_ymax": request.tb_ymax,
            "display_mode": request.display_mode,
            "display_x_range": (request.display_xmin, request.display_xmax),
            "display_y_range": (request.display_ymin, request.display_ymax),
            "percentile_low": request.percentile_low,
            "percentile_high": request.percentile_high,
            "radio_smooth_sigma": request.radio_smooth_sigma,
            "dpi": request.dpi,
            "save_figure": True,
            "output_filename": str(request.output_dir / _OUTPUT_IMAGE),
        }
    )
    return config


def render_dem_radio_overlay(
    request: DemRadioOverlayRequest,
) -> DemRadioOverlayResult:
    """Render one overlay through the canonical DEM/radio workflow functions."""

    import matplotlib

    matplotlib.use("Agg", force=True)
    from matplotlib import pyplot as plt

    from . import dem_radio_source_overlay as workflow

    request.output_dir.mkdir(parents=True, exist_ok=True)
    image_path = request.output_dir / _OUTPUT_IMAGE
    metadata_path = request.output_dir / _OUTPUT_METADATA
    figure = None

    # Canonical helpers currently read their historical module-level CONFIG.
    # The lock and exact restoration keep this adapter deterministic and avoid
    # changing the public compatibility entry point.
    with _CONFIG_LOCK:
        previous_config = workflow.CONFIG
        workflow.CONFIG = _workflow_config(request, workflow)
        try:
            aia_map = workflow.SolarMap(str(request.aia_fits))
            tb_values = workflow.load_tb(str(request.tb_data))
            if tb_values.ndim != 2:
                raise ValueError(
                    f"Tb data must be two-dimensional, got {tb_values.shape}"
                )

            radio_path, radio_time, difference = _radio_selection(
                request, workflow, aia_map
            )
            radio_values, radio_extent = workflow.load_radio(str(radio_path))
            if radio_values.ndim != 2:
                raise ValueError(
                    f"Radio FITS data must be two-dimensional, got {radio_values.shape}"
                )

            figure, _ = workflow.plot_tb(
                tb_values,
                aia_map,
                radio_data=radio_values,
                radio_extent=radio_extent,
                radio_time=radio_time,
            )
            figure.savefig(image_path, dpi=request.dpi, bbox_inches="tight")
            metadata = {
                "schema_version": 1,
                "image": image_path.name,
                "aia_file": request.aia_fits.name,
                "tb_file": request.tb_data.name,
                "radio_file": radio_path.name,
                "aia_time": aia_map.obs_time,
                "radio_time": radio_time,
                "time_difference_seconds": difference,
                "tb_shape": list(tb_values.shape),
                "radio_shape": list(radio_values.shape),
                "time_match_level": request.time_match_level,
            }
            metadata_path.write_text(
                json.dumps(metadata, indent=2, ensure_ascii=True) + "\n",
                encoding="utf-8",
            )
        finally:
            if figure is not None:
                plt.close(figure)
            workflow.CONFIG = previous_config

    return DemRadioOverlayResult(
        image_path=image_path,
        metadata_path=metadata_path,
        radio_file=radio_path,
        aia_time=aia_map.obs_time,
        radio_time=radio_time,
        time_difference_seconds=difference,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Render a non-interactive DEM brightness-temperature/radio overlay."
        )
    )
    parser.add_argument("--aia-fits", type=Path, required=True)
    parser.add_argument("--tb-data", type=Path, required=True)
    parser.add_argument(
        "--radio-file",
        type=Path,
        help="Use this explicit radio FITS image (takes precedence over --radio-dir).",
    )
    parser.add_argument(
        "--radio-dir",
        type=Path,
        help="Select the closest radio FITS image from this directory.",
    )
    parser.add_argument("--radio-pattern", default="*.fits")
    parser.add_argument(
        "--time-match-level", choices=("minute", "hour", "any"), default="minute"
    )
    parser.add_argument("--tb-pixel-size", type=float, default=3.0)
    parser.add_argument("--tb-xmin", type=float, default=-1150.0)
    parser.add_argument("--tb-xmax", type=float, default=1150.0)
    parser.add_argument("--tb-ymin", type=float, default=-1150.0)
    parser.add_argument("--tb-ymax", type=float, default=1150.0)
    parser.add_argument(
        "--display-mode", choices=("full", "solar_disk", "custom"), default="custom"
    )
    parser.add_argument("--display-xmin", type=float, default=-1600.0)
    parser.add_argument("--display-xmax", type=float, default=1600.0)
    parser.add_argument("--display-ymin", type=float, default=-1600.0)
    parser.add_argument("--display-ymax", type=float, default=1600.0)
    parser.add_argument("--percentile-low", type=float, default=1.0)
    parser.add_argument("--percentile-high", type=float, default=99.0)
    parser.add_argument("--radio-smooth-sigma", type=float, default=1.5)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    request = DemRadioOverlayRequest(
        aia_fits=args.aia_fits,
        tb_data=args.tb_data,
        output_dir=args.output_dir,
        radio_file=args.radio_file,
        radio_dir=args.radio_dir,
        radio_pattern=args.radio_pattern,
        time_match_level=args.time_match_level,
        tb_pixel_size=args.tb_pixel_size,
        tb_xmin=args.tb_xmin,
        tb_xmax=args.tb_xmax,
        tb_ymin=args.tb_ymin,
        tb_ymax=args.tb_ymax,
        display_mode=args.display_mode,
        display_xmin=args.display_xmin,
        display_xmax=args.display_xmax,
        display_ymin=args.display_ymin,
        display_ymax=args.display_ymax,
        percentile_low=args.percentile_low,
        percentile_high=args.percentile_high,
        radio_smooth_sigma=args.radio_smooth_sigma,
        dpi=args.dpi,
    )
    result = render_dem_radio_overlay(request)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
