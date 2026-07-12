"""Radio FITS ROI light-curve extraction and product writers."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from astropy.io import fits
from matplotlib.path import Path as MplPath

from .centers import (
    POL_LCP,
    POL_RCP,
    POL_SUM,
    POL_UNKNOWN,
    RadioImage,
    filter_radio_images,
    infer_pol_from_stokes_axis,
    infer_polarization,
    iter_radio_images,
    normalize_pol_text,
    parse_datetime_value,
    parse_frequency_mhz,
    parse_observation_time,
    select_radio_files,
)
from .coordinates import normalize_roi_bounds_arcsec

__all__ = [
    "DEFAULT_PAIR_TOLERANCE_SEC",
    "PRODUCT_FILENAMES",
    "ROI_SCHEMA_VERSION",
    "RadioRoi",
    "build_parser",
    "build_radio_roi_artifacts",
    "build_radio_roi_mask",
    "extract_radio_roi_lightcurve",
    "index_radio_roi_images",
    "main",
    "measure_radio_roi",
    "radio_roi_from_json",
    "run_radio_roi_lightcurve",
    "write_radio_roi_products",
]

ROI_SCHEMA_VERSION = 1
DEFAULT_PAIR_TOLERANCE_SEC = 0.5
PRODUCT_FILENAMES = {
    "csv": "radio_roi_statistics.csv",
    "json": "radio_roi_selection.json",
    "reference_png": "radio_roi_reference.png",
    "lightcurve_png": "radio_roi_lightcurve.png",
}
_ANGULAR_UNITS = {
    "arcsec",
    "arcsecs",
    "arcsecond",
    "arcseconds",
    "asec",
    "deg",
    "degree",
    "degrees",
    "arcmin",
    "arcminute",
    "arcminutes",
    "amin",
    "rad",
    "radian",
    "radians",
}
_SPATIAL_CTYPE_MARKERS = (("HPLN", "SOLX"), ("HPLT", "SOLY"))
_WCS_KEYS = (
    "CTYPE1",
    "CTYPE2",
    "CUNIT1",
    "CUNIT2",
    "CRPIX1",
    "CRPIX2",
    "CRVAL1",
    "CRVAL2",
    "CDELT1",
    "CDELT2",
    "PC1_1",
    "PC1_2",
    "PC2_1",
    "PC2_2",
    "CD1_1",
    "CD1_2",
    "CD2_1",
    "CD2_2",
)
_GRID_CACHE: dict[tuple[Any, ...], tuple[np.ndarray, np.ndarray]] = {}
_GRID_CACHE_MAX_ITEMS = 32


@dataclass(frozen=True)
class _RadioImageMeta:
    path: Path
    hdu_index: int
    image_index: int
    image_shape: tuple[int, int]
    header: fits.Header
    pol: str
    freq_mhz: float
    obs_time: datetime | None
    source_label: str = "main"


@dataclass(frozen=True)
class RadioRoi:
    """A user-selected radio ROI stored in HPLN/HPLT arcsec coordinates."""

    kind: str
    vertices_arcsec: tuple[tuple[float, float], ...]
    label: str = ""

    @classmethod
    def from_box(
        cls,
        left: float,
        bottom: float,
        right: float,
        top: float,
        *,
        label: str = "",
    ) -> RadioRoi:
        """Build a rectangular ROI from HPLN/HPLT arcsec bounds."""

        bounds = normalize_roi_bounds_arcsec(
            {
                "roi_bounds_arcsec": {
                    "left": left,
                    "bottom": bottom,
                    "right": right,
                    "top": top,
                }
            }
        )
        return cls(
            kind="box",
            vertices_arcsec=(
                (bounds["left"], bounds["bottom"]),
                (bounds["right"], bounds["bottom"]),
                (bounds["right"], bounds["top"]),
                (bounds["left"], bounds["top"]),
            ),
            label=label,
        )

    @classmethod
    def from_polygon(
        cls,
        vertices: list[tuple[float, float]] | tuple[tuple[float, float], ...],
        *,
        label: str = "",
    ) -> RadioRoi:
        """Build a lasso-style polygon ROI from HPLN/HPLT arcsec vertices."""

        normalized = tuple(_normalize_vertices(vertices))
        if len(normalized) < 3:
            raise ValueError("polygon ROI requires at least three vertices")
        bounds = _bounds_from_vertices(normalized)
        if bounds["left"] >= bounds["right"] or bounds["bottom"] >= bounds["top"]:
            raise ValueError("polygon ROI is degenerate")
        return cls(kind="polygon", vertices_arcsec=normalized, label=label)

    @property
    def bounds_arcsec(self) -> dict[str, float]:
        """Return normalized ROI bounds as left/bottom/right/top arcsec."""

        return _bounds_from_vertices(self.vertices_arcsec)

    @property
    def roi_id(self) -> str:
        """Return a stable short ID for this ROI geometry."""

        payload = {
            "kind": self.kind,
            "vertices_arcsec": [
                [round(float(x), 6), round(float(y), 6)]
                for x, y in self.vertices_arcsec
            ],
        }
        digest = hashlib.sha1(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return f"roi-{digest[:12]}"

    def to_json_dict(self) -> dict[str, Any]:
        """Serialize the ROI geometry for reproducible extraction."""

        return {
            "schema_version": ROI_SCHEMA_VERSION,
            "roi_id": self.roi_id,
            "kind": self.kind,
            "label": self.label,
            "coordinate_system": "HPLN/HPLT arcsec",
            "bounds_arcsec": self.bounds_arcsec,
            "vertices_arcsec": [
                {"x": float(x), "y": float(y)} for x, y in self.vertices_arcsec
            ],
        }


def radio_roi_from_json(source: str | Path | dict[str, Any]) -> RadioRoi:
    """Load a ``RadioRoi`` from a saved JSON path or dictionary."""

    if isinstance(source, (str, Path)):
        payload = json.loads(Path(source).read_text(encoding="utf-8"))
    else:
        payload = dict(source)
    roi_payload = payload.get("roi", payload)
    kind = str(roi_payload.get("kind", "box")).lower()
    label = str(roi_payload.get("label", ""))
    vertices_payload = roi_payload.get("vertices_arcsec")
    if vertices_payload:
        vertices = [
            (
                float(item["x"]) if isinstance(item, dict) else float(item[0]),
                float(item["y"]) if isinstance(item, dict) else float(item[1]),
            )
            for item in vertices_payload
        ]
    else:
        bounds = roi_payload.get("bounds_arcsec", roi_payload)
        vertices = [
            (float(bounds["left"]), float(bounds["bottom"])),
            (float(bounds["right"]), float(bounds["bottom"])),
            (float(bounds["right"]), float(bounds["top"])),
            (float(bounds["left"]), float(bounds["top"])),
        ]
    if kind == "polygon":
        return RadioRoi.from_polygon(vertices, label=label)
    bounds = _bounds_from_vertices(vertices)
    return RadioRoi.from_box(
        bounds["left"], bounds["bottom"], bounds["right"], bounds["top"], label=label
    )


def build_radio_roi_mask(
    header: fits.Header,
    shape: tuple[int, int],
    roi: RadioRoi,
) -> np.ndarray:
    """Return a boolean mask for ``roi`` over a radio FITS image plane."""

    _validate_spatial_wcs(header)
    if len(shape) != 2:
        raise ValueError("radio ROI masking requires a 2D image shape")
    ny, nx = int(shape[0]), int(shape[1])
    if ny <= 0 or nx <= 0:
        raise ValueError("radio ROI masking requires a positive 2D image shape")
    x_arcsec, y_arcsec = _pixel_center_grid_hpc_arcsec(header, (ny, nx))
    if roi.kind == "box":
        bounds = roi.bounds_arcsec
        return (
            (x_arcsec >= bounds["left"])
            & (x_arcsec <= bounds["right"])
            & (y_arcsec >= bounds["bottom"])
            & (y_arcsec <= bounds["top"])
        )
    if roi.kind == "polygon":
        vertices = np.asarray(roi.vertices_arcsec, dtype=float)
        points = np.column_stack([x_arcsec.ravel(), y_arcsec.ravel()])
        return MplPath(vertices).contains_points(points, radius=1e-12).reshape((ny, nx))
    raise ValueError(f"unsupported ROI kind: {roi.kind!r}")


def measure_radio_roi(
    image: np.ndarray,
    header: fits.Header,
    roi: RadioRoi,
) -> dict[str, Any]:
    """Measure raw intensity statistics inside a radio ROI."""

    arr = np.asarray(image, dtype=float)
    if arr.ndim != 2:
        return _empty_measurement(
            "invalid_image", f"expected 2D image, got {arr.ndim}D"
        )
    try:
        mask = build_radio_roi_mask(header, arr.shape, roi)
    except Exception as exc:  # noqa: BLE001 - row-level quality is the contract.
        return _empty_measurement("invalid_wcs", str(exc))

    roi_pixel_count = int(mask.sum())
    if roi_pixel_count <= 0:
        return _empty_measurement("empty_roi", "ROI does not intersect this image WCS")
    finite_mask = mask & np.isfinite(arr)
    valid_count = int(finite_mask.sum())
    if valid_count <= 0:
        return {
            "roi_pixel_count": roi_pixel_count,
            "valid_pixel_count": 0,
            "coverage_fraction": 0.0,
            "raw_sum": math.nan,
            "raw_mean": math.nan,
            "raw_peak": math.nan,
            "quality_flag": "empty_roi",
            "quality_detail": "ROI contains no finite pixels",
        }
    values = arr[finite_mask]
    return {
        "roi_pixel_count": roi_pixel_count,
        "valid_pixel_count": valid_count,
        "coverage_fraction": float(valid_count) / float(roi_pixel_count),
        "raw_sum": float(np.sum(values)),
        "raw_mean": float(np.mean(values)),
        "raw_peak": float(np.max(values)),
        "quality_flag": "ok",
        "quality_detail": "",
    }


def index_radio_roi_images(
    radio_dir: str | Path,
    *,
    pattern: str = "*.fits",
    recursive: bool = True,
    freqs: list[float] | tuple[float, ...] | None = None,
    time_start: str | datetime | None = None,
    time_end: str | datetime | None = None,
    default_pol: str = POL_SUM,
) -> list[RadioImage]:
    """Read matching radio image headers/planes for ROI preview or extraction."""

    folder = Path(radio_dir).expanduser().resolve()
    if not folder.exists():
        raise FileNotFoundError(f"Radio data folder does not exist: {folder}")
    files = select_radio_files(
        folder,
        pattern=pattern,
        recursive=recursive,
        freqs=freqs,
        time_start=time_start,
        time_end=time_end,
    )
    images: list[RadioImage] = []
    for path in files:
        images.extend(iter_radio_images(path, default_pol=default_pol))
    return filter_radio_images(
        images,
        freqs=freqs,
        time_start=time_start,
        time_end=time_end,
    )


def extract_radio_roi_lightcurve(
    radio_dir: str | Path,
    roi: RadioRoi,
    *,
    pattern: str = "*.fits",
    recursive: bool = True,
    files: list[str | Path] | tuple[str | Path, ...] | None = None,
    freqs: list[float] | tuple[float, ...] | None = None,
    polarization: str = POL_SUM,
    time_start: str | datetime | None = None,
    time_end: str | datetime | None = None,
    default_pol: str = POL_SUM,
    pair_time_tolerance_sec: float = DEFAULT_PAIR_TOLERANCE_SEC,
) -> pd.DataFrame:
    """Extract raw ROI statistics from spatial radio FITS files."""

    file_paths = _resolve_radio_files(
        radio_dir,
        pattern=pattern,
        recursive=recursive,
        files=files,
        freqs=freqs,
        time_start=time_start,
        time_end=time_end,
    )
    metas = _index_radio_image_metadata(file_paths, default_pol=default_pol)
    metas = _filter_radio_image_metadata(
        metas,
        freqs=freqs,
        time_start=time_start,
        time_end=time_end,
    )
    mode = _normalize_polarization_mode(polarization)
    selected = _select_metadata_for_mode(metas, mode)
    skipped_pair_rows: list[dict[str, Any]] = []
    paired_rows: list[dict[str, Any]] = []
    if mode in {POL_SUM, "all"}:
        paired, skipped = _make_paired_sum_metadata(
            metas,
            tolerance_sec=pair_time_tolerance_sec,
        )
        skipped_pair_rows.extend(
            _quality_row_for_meta(
                meta,
                roi=roi,
                quality_flag=flag,
                quality_detail=detail,
                polarization=POL_SUM,
                paired_filepath=paired_path,
            )
            for meta, flag, detail, paired_path in skipped
        )
        paired_rows.extend(
            _row_from_paired_metadata(left, right, roi, default_pol=default_pol)
            for left, right in paired
        )

    rows = [_row_from_metadata(item, roi, default_pol=default_pol) for item in selected]
    rows.extend(paired_rows)
    rows.extend(skipped_pair_rows)
    if not rows:
        raise RuntimeError("No radio ROI rows were extracted.")
    df = pd.DataFrame(rows)
    df = df.sort_values(
        ["freq_mhz", "polarization", "obs_time", "filepath"],
        kind="mergesort",
        na_position="last",
    ).reset_index(drop=True)
    return df


def write_radio_roi_products(
    df: pd.DataFrame,
    roi: RadioRoi,
    output_dir: str | Path,
    *,
    reference_image: RadioImage | None = None,
    reference_images: list[RadioImage] | tuple[RadioImage, ...] | None = None,
    display_config: dict[str, Any] | None = None,
    run_metadata: dict[str, Any] | None = None,
    metric: str = "raw_sum",
    selected_products: list[str] | tuple[str, ...] | set[str] | None = None,
    unique_run: bool = True,
) -> dict[str, Path]:
    """Write selected ROI CSV, JSON, reference PNG, and light-curve PNG products."""

    product_keys = _normalize_selected_products(selected_products)
    target_dir = _unique_output_dir(Path(output_dir).expanduser(), unique=unique_run)
    artifacts = build_radio_roi_artifacts(
        df,
        roi,
        reference_image=reference_image,
        reference_images=reference_images,
        display_config=display_config,
        run_metadata=run_metadata,
        metric=metric,
        selected_products=product_keys,
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    products: dict[str, Path] = {"output_dir": target_dir}
    for key, payload in artifacts.items():
        path = target_dir / PRODUCT_FILENAMES[key]
        path.write_bytes(payload)
        products[key] = path
    return products


def build_radio_roi_artifacts(
    df: pd.DataFrame,
    roi: RadioRoi,
    *,
    reference_image: RadioImage | None = None,
    reference_images: list[RadioImage] | tuple[RadioImage, ...] | None = None,
    display_config: dict[str, Any] | None = None,
    run_metadata: dict[str, Any] | None = None,
    metric: str = "raw_sum",
    selected_products: list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, bytes]:
    """Build selected radio ROI export products as in-memory bytes."""

    product_keys = _normalize_selected_products(selected_products)
    artifacts: dict[str, bytes] = {}
    if "csv" in product_keys:
        artifacts["csv"] = df.to_csv(index=False).encode("utf-8-sig")
    if "json" in product_keys:
        selection = {
            "schema_version": ROI_SCHEMA_VERSION,
            "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "roi": roi.to_json_dict(),
            "settings": _json_safe(run_metadata or {}),
            "outputs": {
                key: PRODUCT_FILENAMES[key]
                for key in product_keys
                if key in PRODUCT_FILENAMES
            },
        }
        artifacts["json"] = json.dumps(
            selection,
            indent=2,
            ensure_ascii=False,
        ).encode("utf-8")
    with tempfile.TemporaryDirectory(prefix="radio_roi_artifacts_") as tmp:
        tmp_dir = Path(tmp)
        if "reference_png" in product_keys:
            path = tmp_dir / PRODUCT_FILENAMES["reference_png"]
            refs = list(reference_images or [])
            if not refs:
                refs = [reference_image or _load_reference_from_rows(df)]
            _plot_reference_images(refs, roi, path, display_config=display_config)
            artifacts["reference_png"] = path.read_bytes()
        if "lightcurve_png" in product_keys:
            path = tmp_dir / PRODUCT_FILENAMES["lightcurve_png"]
            _plot_radio_roi_lightcurve(df, path, metric=metric)
            artifacts["lightcurve_png"] = path.read_bytes()
    return artifacts


def build_parser() -> argparse.ArgumentParser:
    """Build the non-interactive ROI extraction parser."""

    parser = argparse.ArgumentParser(
        description="Extract raw radio FITS ROI light curves from HPLN/HPLT selections."
    )
    parser.add_argument(
        "--radio-dir", required=True, help="Folder containing radio FITS files."
    )
    parser.add_argument("--out-dir", default="radio_roi_lightcurve_outputs")
    parser.add_argument(
        "--pattern", default="*.fits", help="FITS filename glob pattern."
    )
    parser.add_argument("--recursive", action="store_true", default=True)
    parser.add_argument("--no-recursive", dest="recursive", action="store_false")
    parser.add_argument("--freqs", help="Comma-separated frequencies in MHz.")
    parser.add_argument(
        "--polarization",
        default=POL_SUM,
        choices=[POL_SUM, POL_LCP, POL_RCP, "all"],
        help="Polarization to measure; L+R pairs LCP/RCP where needed.",
    )
    parser.add_argument("--time-start", help="Inclusive observation-time start.")
    parser.add_argument("--time-end", help="Inclusive observation-time end.")
    parser.add_argument(
        "--pair-time-tolerance-sec", type=float, default=DEFAULT_PAIR_TOLERANCE_SEC
    )
    roi_group = parser.add_mutually_exclusive_group(required=True)
    roi_group.add_argument(
        "--roi-bounds",
        help="Box bounds as left,bottom,right,top in HPLN/HPLT arcsec.",
    )
    roi_group.add_argument("--roi-json", help="Saved ROI JSON file.")
    parser.add_argument(
        "--metric",
        default="raw_sum",
        choices=["raw_sum", "raw_mean", "raw_peak"],
        help="Metric used in the default PNG curve.",
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Write directly into --out-dir."
    )
    return parser


def run_radio_roi_lightcurve(argv: list[str] | None = None) -> dict[str, Path]:
    """Run ROI light-curve extraction and write products."""

    args = build_parser().parse_args(argv)
    roi = (
        radio_roi_from_json(args.roi_json)
        if args.roi_json
        else _parse_roi_bounds(args.roi_bounds)
    )
    freqs = _parse_float_csv(args.freqs)
    df = extract_radio_roi_lightcurve(
        args.radio_dir,
        roi,
        pattern=args.pattern,
        recursive=bool(args.recursive),
        freqs=freqs,
        polarization=args.polarization,
        time_start=args.time_start,
        time_end=args.time_end,
        pair_time_tolerance_sec=float(args.pair_time_tolerance_sec),
    )
    reference = _first_ok_image(
        args.radio_dir,
        pattern=args.pattern,
        recursive=bool(args.recursive),
        freqs=freqs,
        time_start=args.time_start,
        time_end=args.time_end,
    )
    return write_radio_roi_products(
        df,
        roi,
        args.out_dir,
        reference_image=reference,
        run_metadata={
            "radio_dir": str(Path(args.radio_dir).expanduser()),
            "pattern": args.pattern,
            "recursive": bool(args.recursive),
            "freqs": freqs,
            "polarization": args.polarization,
            "time_start": args.time_start or "",
            "time_end": args.time_end or "",
            "pair_time_tolerance_sec": float(args.pair_time_tolerance_sec),
            "metric": args.metric,
        },
        metric=args.metric,
        unique_run=not bool(args.overwrite),
    )


def main(argv: list[str] | None = None) -> int:
    """Run the command-line ROI light-curve workflow."""

    products = run_radio_roi_lightcurve(argv)
    print("[Radio ROI Light Curve] outputs:")
    print(f"  Output directory: {products['output_dir']}")
    print(f"  Statistics CSV: {products['csv']}")
    print(f"  ROI JSON: {products['json']}")
    print(f"  Reference PNG: {products['reference_png']}")
    print(f"  Light curve PNG: {products['lightcurve_png']}")
    return 0


def _resolve_radio_files(
    radio_dir: str | Path,
    *,
    pattern: str,
    recursive: bool,
    files: list[str | Path] | tuple[str | Path, ...] | None,
    freqs: list[float] | tuple[float, ...] | None,
    time_start: str | datetime | None,
    time_end: str | datetime | None,
) -> list[Path]:
    folder = Path(radio_dir).expanduser().resolve()
    if files is None:
        if not folder.exists():
            raise FileNotFoundError(f"Radio data folder does not exist: {folder}")
        selected = select_radio_files(
            folder,
            pattern=pattern,
            recursive=recursive,
            freqs=freqs,
            time_start=time_start,
            time_end=time_end,
        )
    else:
        selected = []
        for value in files:
            path = Path(value).expanduser()
            if not path.is_absolute():
                path = folder / path
            selected.append(path.resolve())
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in selected:
        if path in seen:
            continue
        seen.add(path)
        if not path.exists():
            raise FileNotFoundError(f"Selected radio FITS file does not exist: {path}")
        if not path.is_file():
            raise FileNotFoundError(f"Selected radio FITS path is not a file: {path}")
        unique.append(path)
    if not unique:
        raise FileNotFoundError(f"No FITS files found under {folder} matching filters.")
    return unique


def _index_radio_image_metadata(
    files: list[Path],
    *,
    default_pol: str,
) -> list[_RadioImageMeta]:
    metas: list[_RadioImageMeta] = []
    for path in files:
        metas.extend(_iter_radio_image_metadata(path, default_pol=default_pol))
    return metas


def _iter_radio_image_metadata(
    path: Path, *, default_pol: str
) -> list[_RadioImageMeta]:
    metas: list[_RadioImageMeta] = []
    image_index = 0
    try:
        with fits.open(path, memmap=True, ignore_missing_end=True) as hdul:
            for hdu_index, hdu in enumerate(hdul):
                if not getattr(hdu, "is_image", False):
                    continue
                header = hdu.header.copy()
                shape = _hdu_numpy_shape(hdu, header)
                if not shape:
                    continue
                for image_shape, pol in _iter_hdu_metadata_planes(
                    path,
                    header,
                    shape,
                    default_pol=default_pol,
                ):
                    metas.append(
                        _RadioImageMeta(
                            path=path,
                            hdu_index=hdu_index,
                            image_index=image_index,
                            image_shape=image_shape,
                            header=header,
                            pol=pol,
                            freq_mhz=parse_frequency_mhz(path, header),
                            obs_time=parse_observation_time(path, header),
                        )
                    )
                    image_index += 1
    except Exception as exc:  # noqa: BLE001 - preserve row-level behavior.
        warnings.warn(f"Failed to read radio FITS metadata {path}: {exc}", stacklevel=2)
    return metas


def _hdu_numpy_shape(hdu: Any, header: fits.Header) -> tuple[int, ...]:
    shape = getattr(hdu, "shape", None)
    if shape:
        return tuple(int(item) for item in shape)
    naxis = int(header.get("NAXIS", 0) or 0)
    if naxis <= 0:
        return ()
    dims = [int(header.get(f"NAXIS{axis}", 0) or 0) for axis in range(1, naxis + 1)]
    if any(dim <= 0 for dim in dims):
        return ()
    return tuple(reversed(dims))


def _iter_hdu_metadata_planes(
    path: Path,
    header: fits.Header,
    arr_shape: tuple[int, ...],
    *,
    default_pol: str,
) -> list[tuple[tuple[int, int], str]]:
    if len(arr_shape) < 2:
        return []
    if len(arr_shape) == 2:
        return [
            (
                tuple(arr_shape),
                infer_polarization(path, header, default_pol=default_pol),
            )
        ]

    squeezed_shape = tuple(dim for dim in arr_shape if dim != 1)
    if len(squeezed_shape) == 2:
        return [
            (
                tuple(squeezed_shape),
                infer_polarization(path, header, default_pol=default_pol),
            )
        ]

    naxis = int(header.get("NAXIS", len(arr_shape)) or len(arr_shape))
    stokes_fits_axis = None
    for axis in range(1, naxis + 1):
        ctype = str(header.get(f"CTYPE{axis}", "")).upper()
        if "STOKES" in ctype or "POL" in ctype:
            stokes_fits_axis = axis
            break
    if stokes_fits_axis is not None:
        py_axis = len(arr_shape) - stokes_fits_axis
        if 0 <= py_axis < len(arr_shape):
            planes: list[tuple[tuple[int, int], str]] = []
            for index in range(arr_shape[py_axis]):
                pol = infer_pol_from_stokes_axis(header, index, stokes_fits_axis)
                if pol == POL_UNKNOWN:
                    pol = infer_polarization(path, header, default_pol=default_pol)
                planes.append((tuple(arr_shape[-2:]), pol))
            return planes

    candidate_axes = [
        axis for axis, size in enumerate(squeezed_shape[:-2]) if size <= 4
    ]
    if candidate_axes:
        pol = infer_polarization(path, header, default_pol=default_pol)
        return [
            (tuple(squeezed_shape[-2:]), pol)
            for _ in range(squeezed_shape[candidate_axes[-1]])
        ]

    pol = infer_polarization(path, header, default_pol=default_pol)
    return [(tuple(squeezed_shape[-2:]), pol)]


def _filter_radio_image_metadata(
    metas: list[_RadioImageMeta],
    *,
    freqs: list[float] | tuple[float, ...] | None,
    time_start: str | datetime | None,
    time_end: str | datetime | None,
) -> list[_RadioImageMeta]:
    freq_set = {float(freq) for freq in freqs or []}
    start = _parse_optional_datetime(time_start, "time_start")
    end = _parse_optional_datetime(time_end, "time_end")
    filtered: list[_RadioImageMeta] = []
    for item in metas:
        if freq_set and not _frequency_in_set(item.freq_mhz, freq_set):
            continue
        if start is not None and (item.obs_time is None or item.obs_time < start):
            continue
        if end is not None and (item.obs_time is None or item.obs_time > end):
            continue
        filtered.append(item)
    return filtered


def _select_metadata_for_mode(
    metas: list[_RadioImageMeta],
    mode: str,
) -> list[_RadioImageMeta]:
    if mode == "all":
        return list(metas)
    return [item for item in metas if item.pol == mode]


def _normalize_vertices(vertices) -> list[tuple[float, float]]:
    normalized = []
    for item in vertices:
        if len(item) != 2:
            raise ValueError("ROI vertices must be x/y pairs")
        x, y = float(item[0]), float(item[1])
        if not (np.isfinite(x) and np.isfinite(y)):
            raise ValueError("ROI vertices must be finite")
        normalized.append((x, y))
    return normalized


def _bounds_from_vertices(vertices) -> dict[str, float]:
    arr = np.asarray(vertices, dtype=float)
    if arr.ndim != 2 or arr.shape[1] != 2 or arr.size == 0:
        raise ValueError("ROI vertices must be a non-empty sequence of x/y pairs")
    if not np.isfinite(arr).all():
        raise ValueError("ROI vertices must be finite")
    return {
        "left": float(np.min(arr[:, 0])),
        "bottom": float(np.min(arr[:, 1])),
        "right": float(np.max(arr[:, 0])),
        "top": float(np.max(arr[:, 1])),
    }


def _validate_spatial_wcs(header: fits.Header) -> None:
    ctype1 = str(header.get("CTYPE1", "")).upper()
    ctype2 = str(header.get("CTYPE2", "")).upper()
    if not ctype1 or not ctype2:
        raise ValueError("missing CTYPE1/CTYPE2 spatial WCS")
    if not any(marker in ctype1 for marker in _SPATIAL_CTYPE_MARKERS[0]):
        raise ValueError(f"non-HPLN spatial axis CTYPE1={ctype1!r}")
    if not any(marker in ctype2 for marker in _SPATIAL_CTYPE_MARKERS[1]):
        raise ValueError(f"non-HPLT spatial axis CTYPE2={ctype2!r}")
    unit1 = str(header.get("CUNIT1", "arcsec")).strip().lower()
    unit2 = str(header.get("CUNIT2", "arcsec")).strip().lower()
    if unit1 not in _ANGULAR_UNITS or unit2 not in _ANGULAR_UNITS:
        raise ValueError(f"non-angular WCS units CUNIT1={unit1!r}, CUNIT2={unit2!r}")
    required = {"CRPIX1", "CRPIX2", "CRVAL1", "CRVAL2"}
    missing = sorted(key for key in required if key not in header)
    has_cd = all(key in header for key in ("CD1_1", "CD1_2", "CD2_1", "CD2_2"))
    if not has_cd:
        missing.extend(key for key in ("CDELT1", "CDELT2") if key not in header)
    if missing:
        raise ValueError(f"missing spatial WCS keywords: {missing}")


def _pixel_center_grid_hpc_arcsec(
    header: fits.Header, shape: tuple[int, int]
) -> tuple[np.ndarray, np.ndarray]:
    key = _wcs_signature(header, shape)
    cached = _GRID_CACHE.get(key)
    if cached is not None:
        return cached

    y_pix, x_pix = np.indices(shape, dtype=float)
    x_arcsec, y_arcsec = _pixel_coordinates_hpc_arcsec(header, x_pix, y_pix)
    if len(_GRID_CACHE) >= _GRID_CACHE_MAX_ITEMS:
        _GRID_CACHE.pop(next(iter(_GRID_CACHE)))
    _GRID_CACHE[key] = (x_arcsec, y_arcsec)
    return x_arcsec, y_arcsec


def _pixel_coordinates_hpc_arcsec(
    header: fits.Header,
    x_pix: np.ndarray,
    y_pix: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    x_values = np.asarray(x_pix, dtype=float)
    y_values = np.asarray(y_pix, dtype=float)
    if x_values.shape != y_values.shape:
        raise ValueError("x/y pixel coordinate arrays must have identical shapes")
    crpix1 = float(header.get("CRPIX1", 1.0))
    crpix2 = float(header.get("CRPIX2", 1.0))
    crval1 = float(header.get("CRVAL1", 0.0))
    crval2 = float(header.get("CRVAL2", 0.0))
    cdelt1 = float(header.get("CDELT1", 1.0))
    cdelt2 = float(header.get("CDELT2", 1.0))
    dx = x_values + 1.0 - crpix1
    dy = y_values + 1.0 - crpix2

    if all(key_name in header for key_name in ("CD1_1", "CD1_2", "CD2_1", "CD2_2")):
        wx = float(header["CD1_1"]) * dx + float(header["CD1_2"]) * dy
        wy = float(header["CD2_1"]) * dx + float(header["CD2_2"]) * dy
    else:
        pc11 = float(header.get("PC1_1", 1.0))
        pc12 = float(header.get("PC1_2", 0.0))
        pc21 = float(header.get("PC2_1", 0.0))
        pc22 = float(header.get("PC2_2", 1.0))
        if not any(
            key_name in header for key_name in ("PC1_1", "PC1_2", "PC2_1", "PC2_2")
        ):
            theta = math.radians(float(header.get("CROTA2", 0.0)))
            pc11, pc12 = math.cos(theta), -math.sin(theta)
            pc21, pc22 = math.sin(theta), math.cos(theta)
        x_int = cdelt1 * dx
        y_int = cdelt2 * dy
        wx = pc11 * x_int + pc12 * y_int
        wy = pc21 * x_int + pc22 * y_int

    x_arcsec = _to_arcsec_array(crval1 + wx, str(header.get("CUNIT1", "arcsec")))
    y_arcsec = _to_arcsec_array(crval2 + wy, str(header.get("CUNIT2", "arcsec")))
    return x_arcsec, y_arcsec


def _to_arcsec_array(values: np.ndarray, unit: str) -> np.ndarray:
    unit_norm = (unit or "arcsec").strip().lower()
    arr = np.asarray(values, dtype=float)
    if unit_norm in {"arcsec", "arcsecs", "arcsecond", "arcseconds", "asec"}:
        return arr
    if unit_norm in {"deg", "degree", "degrees"}:
        return arr * 3600.0
    if unit_norm in {"arcmin", "arcminute", "arcminutes", "amin"}:
        return arr * 60.0
    if unit_norm in {"rad", "radian", "radians"}:
        return np.degrees(arr) * 3600.0
    return arr


def _empty_measurement(flag: str, detail: str) -> dict[str, Any]:
    return {
        "roi_pixel_count": 0,
        "valid_pixel_count": 0,
        "coverage_fraction": math.nan,
        "raw_sum": math.nan,
        "raw_mean": math.nan,
        "raw_peak": math.nan,
        "quality_flag": flag,
        "quality_detail": detail,
    }


def _normalize_polarization_mode(value: str) -> str:
    if str(value).lower() == "all":
        return "all"
    pol = normalize_pol_text(value)
    if pol == POL_UNKNOWN:
        raise ValueError(f"Unsupported polarization mode: {value!r}")
    return pol


def _select_images_for_mode(images: list[RadioImage], mode: str) -> list[RadioImage]:
    if mode == "all":
        return list(images)
    return [item for item in images if item.pol == mode]


def _row_from_metadata(
    meta: _RadioImageMeta,
    roi: RadioRoi,
    *,
    default_pol: str,
) -> dict[str, Any]:
    item = _load_image_for_meta(meta, default_pol=default_pol)
    if item is None:
        return _quality_row_for_meta(
            meta,
            roi=roi,
            quality_flag="invalid_image",
            quality_detail="selected image plane could not be loaded",
        )
    return _row_from_radio_image(item, roi)


def _row_from_paired_metadata(
    left: _RadioImageMeta,
    right: _RadioImageMeta,
    roi: RadioRoi,
    *,
    default_pol: str,
) -> dict[str, Any]:
    left_item = _load_image_for_meta(left, default_pol=default_pol)
    right_item = _load_image_for_meta(right, default_pol=default_pol)
    if left_item is None:
        return _quality_row_for_meta(
            left,
            roi=roi,
            quality_flag="invalid_image",
            quality_detail="selected LCP image plane could not be loaded",
            polarization=POL_SUM,
            paired_filepath=str(right.path),
        )
    if right_item is None:
        return _quality_row_for_meta(
            left,
            roi=roi,
            quality_flag="invalid_image",
            quality_detail="selected RCP image plane could not be loaded",
            polarization=POL_SUM,
            paired_filepath=str(right.path),
        )
    detail = _pair_incompatibility(left_item, right_item)
    if detail:
        return _quality_row_for_meta(
            left,
            roi=roi,
            quality_flag="mismatched_pair",
            quality_detail=detail,
            polarization=POL_SUM,
            paired_filepath=str(right.path),
        )
    header = left_item.header.copy()
    header["POLAR"] = POL_SUM
    header["ROIPAIR"] = str(right_item.path)
    midpoint = left_item.obs_time
    if left_item.obs_time is not None and right_item.obs_time is not None:
        midpoint = left_item.obs_time + (right_item.obs_time - left_item.obs_time) / 2
    paired = RadioImage(
        path=left_item.path,
        hdu_index=left_item.hdu_index,
        image=np.asarray(left_item.image, dtype=float)
        + np.asarray(right_item.image, dtype=float),
        header=header,
        pol=POL_SUM,
        freq_mhz=left_item.freq_mhz,
        obs_time=midpoint,
        source_label="paired_L_plus_R",
    )
    return _row_from_radio_image(paired, roi)


def _load_image_for_meta(
    meta: _RadioImageMeta,
    *,
    default_pol: str,
) -> RadioImage | None:
    for index, item in enumerate(iter_radio_images(meta.path, default_pol=default_pol)):
        if index == meta.image_index:
            return item
    return None


def _row_from_radio_image(item: RadioImage, roi: RadioRoi) -> dict[str, Any]:
    measurement = measure_radio_roi(item.image, item.header, roi)
    row = _base_row(
        roi,
        obs_time=item.obs_time,
        freq_mhz=item.freq_mhz,
        polarization=item.pol,
        bunit=str(item.header.get("BUNIT", "")),
        filepath=str(item.path),
        paired_filepath=(
            str(item.header.get("ROIPAIR", "")) if item.header.get("ROIPAIR") else ""
        ),
        hdu_index=item.hdu_index,
    )
    row.update(measurement)
    return row


def _quality_row_for_item(
    item: RadioImage,
    *,
    roi: RadioRoi,
    quality_flag: str,
    quality_detail: str,
    polarization: str | None = None,
    paired_filepath: str = "",
) -> dict[str, Any]:
    row = _base_row(
        roi,
        obs_time=item.obs_time,
        freq_mhz=item.freq_mhz,
        polarization=polarization or item.pol,
        bunit=str(item.header.get("BUNIT", "")),
        filepath=str(item.path),
        paired_filepath=paired_filepath,
        hdu_index=item.hdu_index,
    )
    row.update(_empty_measurement(quality_flag, quality_detail))
    return row


def _quality_row_for_meta(
    meta: _RadioImageMeta,
    *,
    roi: RadioRoi,
    quality_flag: str,
    quality_detail: str,
    polarization: str | None = None,
    paired_filepath: str = "",
) -> dict[str, Any]:
    row = _base_row(
        roi,
        obs_time=meta.obs_time,
        freq_mhz=meta.freq_mhz,
        polarization=polarization or meta.pol,
        bunit=str(meta.header.get("BUNIT", "")),
        filepath=str(meta.path),
        paired_filepath=paired_filepath,
        hdu_index=meta.hdu_index,
    )
    row.update(_empty_measurement(quality_flag, quality_detail))
    return row


def _base_row(
    roi: RadioRoi,
    *,
    obs_time: datetime | None,
    freq_mhz: float,
    polarization: str,
    bunit: str,
    filepath: str,
    paired_filepath: str,
    hdu_index: int,
) -> dict[str, Any]:
    bounds = roi.bounds_arcsec
    return {
        "obs_time": obs_time.isoformat(timespec="milliseconds") if obs_time else "",
        "time_unix": (
            obs_time.replace(tzinfo=timezone.utc).timestamp() if obs_time else math.nan
        ),
        "freq_mhz": float(freq_mhz) if np.isfinite(freq_mhz) else math.nan,
        "polarization": polarization,
        "bunit": bunit,
        "roi_id": roi.roi_id,
        "roi_kind": roi.kind,
        "roi_left_arcsec": bounds["left"],
        "roi_right_arcsec": bounds["right"],
        "roi_bottom_arcsec": bounds["bottom"],
        "roi_top_arcsec": bounds["top"],
        "filepath": filepath,
        "paired_filepath": paired_filepath,
        "hdu_index": int(hdu_index),
    }


def _make_paired_sum_images(
    images: list[RadioImage], *, tolerance_sec: float
) -> tuple[list[RadioImage], list[tuple[RadioImage, str, str, str]]]:
    left_items = [
        item
        for item in images
        if item.pol == POL_LCP
        and item.obs_time is not None
        and np.isfinite(item.freq_mhz)
    ]
    right_items = [
        item
        for item in images
        if item.pol == POL_RCP
        and item.obs_time is not None
        and np.isfinite(item.freq_mhz)
    ]
    paired: list[RadioImage] = []
    skipped: list[tuple[RadioImage, str, str, str]] = []
    used_right: set[int] = set()
    for left in left_items:
        candidate_index = None
        candidate_dt = None
        for index, right in enumerate(right_items):
            if index in used_right or not _same_frequency(
                left.freq_mhz, right.freq_mhz
            ):
                continue
            dt = abs((left.obs_time - right.obs_time).total_seconds())
            if dt <= tolerance_sec and (candidate_dt is None or dt < candidate_dt):
                candidate_index = index
                candidate_dt = dt
        if candidate_index is None:
            skipped.append(
                (
                    left,
                    "unmatched_pair",
                    f"no RCP image within {float(tolerance_sec):g} seconds",
                    "",
                )
            )
            continue
        right = right_items[candidate_index]
        detail = _pair_incompatibility(left, right)
        if detail:
            skipped.append((left, "mismatched_pair", detail, str(right.path)))
            continue
        used_right.add(candidate_index)
        header = left.header.copy()
        header["POLAR"] = POL_SUM
        header["ROIPAIR"] = str(right.path)
        midpoint = left.obs_time + (right.obs_time - left.obs_time) / 2
        paired.append(
            RadioImage(
                path=left.path,
                hdu_index=left.hdu_index,
                image=np.asarray(left.image, dtype=float)
                + np.asarray(right.image, dtype=float),
                header=header,
                pol=POL_SUM,
                freq_mhz=left.freq_mhz,
                obs_time=midpoint,
                source_label="paired_L_plus_R",
            )
        )
    for index, right in enumerate(right_items):
        if index not in used_right:
            skipped.append(
                (
                    right,
                    "unmatched_pair",
                    f"no LCP image within {float(tolerance_sec):g} seconds",
                    "",
                )
            )
    return paired, skipped


def _make_paired_sum_metadata(
    metas: list[_RadioImageMeta], *, tolerance_sec: float
) -> tuple[
    list[tuple[_RadioImageMeta, _RadioImageMeta]],
    list[tuple[_RadioImageMeta, str, str, str]],
]:
    left_items = [
        item
        for item in metas
        if item.pol == POL_LCP
        and item.obs_time is not None
        and np.isfinite(item.freq_mhz)
    ]
    right_items = [
        item
        for item in metas
        if item.pol == POL_RCP
        and item.obs_time is not None
        and np.isfinite(item.freq_mhz)
    ]
    paired: list[tuple[_RadioImageMeta, _RadioImageMeta]] = []
    skipped: list[tuple[_RadioImageMeta, str, str, str]] = []
    used_right: set[int] = set()
    for left in left_items:
        candidate_index = None
        candidate_dt = None
        for index, right in enumerate(right_items):
            if index in used_right or not _same_frequency(
                left.freq_mhz, right.freq_mhz
            ):
                continue
            dt = abs((left.obs_time - right.obs_time).total_seconds())
            if dt <= tolerance_sec and (candidate_dt is None or dt < candidate_dt):
                candidate_index = index
                candidate_dt = dt
        if candidate_index is None:
            skipped.append(
                (
                    left,
                    "unmatched_pair",
                    f"no RCP image within {float(tolerance_sec):g} seconds",
                    "",
                )
            )
            continue
        right = right_items[candidate_index]
        detail = _metadata_pair_incompatibility(left, right)
        if detail:
            skipped.append((left, "mismatched_pair", detail, str(right.path)))
            continue
        used_right.add(candidate_index)
        paired.append((left, right))
    for index, right in enumerate(right_items):
        if index not in used_right:
            skipped.append(
                (
                    right,
                    "unmatched_pair",
                    f"no LCP image within {float(tolerance_sec):g} seconds",
                    "",
                )
            )
    return paired, skipped


def _metadata_pair_incompatibility(
    left: _RadioImageMeta, right: _RadioImageMeta
) -> str:
    if left.image_shape != right.image_shape:
        return f"shape mismatch: {left.image_shape} vs {right.image_shape}"
    left_bunit = str(left.header.get("BUNIT", "")).strip().casefold()
    right_bunit = str(right.header.get("BUNIT", "")).strip().casefold()
    if left_bunit != right_bunit:
        return f"BUNIT mismatch: {left.header.get('BUNIT', '')!r} vs {right.header.get('BUNIT', '')!r}"
    if _wcs_signature(left.header, left.image_shape) != _wcs_signature(
        right.header, right.image_shape
    ):
        return "spatial WCS mismatch"
    return ""


def _pair_incompatibility(left: RadioImage, right: RadioImage) -> str:
    if left.image.shape != right.image.shape:
        return f"shape mismatch: {left.image.shape} vs {right.image.shape}"
    left_bunit = str(left.header.get("BUNIT", "")).strip().casefold()
    right_bunit = str(right.header.get("BUNIT", "")).strip().casefold()
    if left_bunit != right_bunit:
        return f"BUNIT mismatch: {left.header.get('BUNIT', '')!r} vs {right.header.get('BUNIT', '')!r}"
    if _wcs_signature(left.header, left.image.shape) != _wcs_signature(
        right.header, right.image.shape
    ):
        return "spatial WCS mismatch"
    return ""


def _wcs_signature(header: fits.Header, shape: tuple[int, int]) -> tuple[Any, ...]:
    values: list[Any] = [tuple(shape)]
    for key in _WCS_KEYS:
        value = header.get(key, None)
        if isinstance(value, float):
            value = round(float(value), 12)
        values.append((key, value))
    return tuple(values)


def _same_frequency(left_mhz: float, right_mhz: float) -> bool:
    if not (np.isfinite(left_mhz) and np.isfinite(right_mhz)):
        return False
    tolerance = max(1e-6, 1e-5 * abs(float(left_mhz)))
    return abs(float(left_mhz) - float(right_mhz)) <= tolerance


def _unique_output_dir(base: Path, *, unique: bool) -> Path:
    if not unique:
        return base
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = base / f"radio_roi_lightcurve_{stamp}"
    if not candidate.exists():
        return candidate
    for index in range(2, 1000):
        numbered = base / f"radio_roi_lightcurve_{stamp}_{index:03d}"
        if not numbered.exists():
            return numbered
    raise RuntimeError(f"Could not allocate a unique output directory under {base}")


def _plot_radio_roi_lightcurve(df: pd.DataFrame, path: Path, *, metric: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=180)
    data = df.copy()
    data["obs_time_dt"] = pd.to_datetime(data.get("obs_time"), errors="coerce")
    data[metric] = pd.to_numeric(data.get(metric), errors="coerce")
    ok = data["quality_flag"].astype(str).str.lower().eq("ok")
    data = data.loc[ok & data["obs_time_dt"].notna() & data[metric].notna()]
    if data.empty:
        ax.text(
            0.5,
            0.5,
            "No valid ROI samples",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
    else:
        for (freq, pol), group in data.groupby(
            ["freq_mhz", "polarization"], dropna=False
        ):
            label = f"{freq:g} MHz {pol}" if np.isfinite(freq) else str(pol)
            ordered = group.sort_values("obs_time_dt")
            ax.plot(
                ordered["obs_time_dt"],
                ordered[metric],
                marker="o",
                linewidth=1.2,
                markersize=3,
                label=label,
            )
        ax.legend(fontsize=7, loc="best")
    unit = _metric_unit_label(data, metric)
    ax.set_title("Radio ROI light curve")
    ax.set_xlabel("Observation time")
    ax.set_ylabel(f"{metric} ({unit})" if unit else metric)
    ax.grid(True, linestyle=":", alpha=0.35)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _metric_unit_label(df: pd.DataFrame, metric: str) -> str:
    bunit = ""
    if "bunit" in df.columns and not df.empty:
        units = [
            str(item).strip()
            for item in df["bunit"].dropna().unique()
            if str(item).strip()
        ]
        bunit = units[0] if units else ""
    if metric == "raw_sum":
        return f"{bunit} pixel".strip()
    return bunit


def _plot_reference_images(
    items: list[RadioImage | None],
    roi: RadioRoi,
    path: Path,
    *,
    display_config: dict[str, Any] | None = None,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    refs = items or [None]
    column_count = min(3, max(1, len(refs)))
    row_count = int(math.ceil(len(refs) / column_count))
    fig, axes = plt.subplots(
        row_count,
        column_count,
        figsize=(5.2 * column_count, 4.8 * row_count),
        dpi=180,
        squeeze=False,
    )
    for ax in axes.ravel()[len(refs) :]:
        ax.set_axis_off()
    for ax, item in zip(axes.ravel(), refs, strict=False):
        if item is None:
            ax.text(
                0.5,
                0.5,
                "No reference image",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.set_axis_off()
            continue
        arr = np.asarray(item.image, dtype=float)
        try:
            x_arcsec, y_arcsec = _pixel_center_grid_hpc_arcsec(item.header, arr.shape)
            extent = (
                float(np.nanmin(x_arcsec)),
                float(np.nanmax(x_arcsec)),
                float(np.nanmin(y_arcsec)),
                float(np.nanmax(y_arcsec)),
            )
            display_arr = _reference_display_array(arr, display_config)
            zmin, zmax = _reference_display_limits(item, display_arr, display_config)
            cmap = _matplotlib_cmap(plt, display_config)
            image = ax.imshow(
                display_arr,
                origin="lower",
                extent=extent,
                cmap=cmap,
                aspect="auto",
                vmin=zmin,
                vmax=zmax,
            )
            ax.set_xlabel("HPLN / arcsec")
            ax.set_ylabel("HPLT / arcsec")
            _apply_reference_fov(ax, display_config)
            _add_reference_roi_patch(ax, roi)
        except Exception:
            warnings.warn(
                "Reference image WCS is invalid; plotting in pixel coordinates.",
                stacklevel=2,
            )
            display_arr = _reference_display_array(arr, display_config)
            zmin, zmax = _reference_display_limits(item, display_arr, display_config)
            image = ax.imshow(
                display_arr,
                origin="lower",
                cmap=_matplotlib_cmap(plt, display_config),
                aspect="auto",
                vmin=zmin,
                vmax=zmax,
            )
            ax.set_xlabel("x pixel")
            ax.set_ylabel("y pixel")
        fig.colorbar(
            image, ax=ax, label=_reference_colorbar_label(item, display_config)
        )
        ax.set_title(_reference_plot_title(item))
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_reference_image(item: RadioImage | None, roi: RadioRoi, path: Path) -> None:
    _plot_reference_images([item], roi, path)


def _reference_display_array(
    arr: np.ndarray, display_config: dict[str, Any] | None
) -> np.ndarray:
    config = display_config or {}
    values = np.asarray(arr, dtype=float)
    transform = str(config.get("transform", "linear")).strip().lower()
    if transform in {"log10", "log10 positive", "log"}:
        return np.where(values > 0.0, np.log10(values), np.nan)
    return values


def _reference_display_limits(
    item: RadioImage,
    display_arr: np.ndarray,
    display_config: dict[str, Any] | None,
) -> tuple[float, float]:
    config = display_config or {}
    freq_key = _display_frequency_key(item.freq_mhz)
    for key in ("limits_by_frequency", "per_frequency_limits"):
        limits = config.get(key, {})
        if isinstance(limits, dict) and freq_key in limits:
            return _clean_display_limits(limits[freq_key])
    shared = config.get("shared_limits")
    if shared is not None:
        return _clean_display_limits(shared)

    finite = display_arr[np.isfinite(display_arr)]
    if not finite.size:
        return 0.0, 1.0
    mode = str(config.get("range_mode", "auto")).strip().lower()
    if mode.startswith("manual"):
        raw_min = config.get("manual_min")
        raw_max = config.get("manual_max")
        if raw_min not in (None, "") and raw_max not in (None, ""):
            return _clean_display_limits(
                [
                    _transform_display_limit(float(raw_min), config),
                    _transform_display_limit(float(raw_max), config),
                ]
            )
    low = float(config.get("low_percentile", 1.0))
    high = float(config.get("high_percentile", 99.7))
    return _clean_display_limits(np.nanpercentile(finite, [low, high]))


def _clean_display_limits(values: Any) -> tuple[float, float]:
    zmin, zmax = [float(item) for item in list(values)[:2]]
    if not np.isfinite(zmin) or not np.isfinite(zmax):
        return 0.0, 1.0
    if zmin > zmax:
        zmin, zmax = zmax, zmin
    if zmin == zmax:
        pad = abs(zmin) * 0.01 or 1.0
        zmin -= pad
        zmax += pad
    return zmin, zmax


def _transform_display_limit(value: float, display_config: dict[str, Any]) -> float:
    transform = str(display_config.get("transform", "linear")).strip().lower()
    if transform in {"log10", "log10 positive", "log"}:
        return math.log10(value) if value > 0.0 else math.nan
    return value


def _matplotlib_cmap(plt: Any, display_config: dict[str, Any] | None) -> Any:
    config = display_config or {}
    cmap_name = str(config.get("colormap", "viridis")).strip() or "viridis"
    try:
        cmap = plt.get_cmap(cmap_name).copy()
    except ValueError:
        cmap = plt.get_cmap(cmap_name.lower()).copy()
    bad_color = str(config.get("bad_color", "")).strip()
    if bad_color:
        cmap.set_bad(bad_color)
    return cmap


def _apply_reference_fov(ax: Any, display_config: dict[str, Any] | None) -> None:
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
    ax.set_xlim(min(left, right), max(left, right))
    ax.set_ylim(min(bottom, top), max(bottom, top))


def _add_reference_roi_patch(ax: Any, roi: RadioRoi) -> None:
    from matplotlib.patches import Polygon, Rectangle

    bounds = roi.bounds_arcsec
    if roi.kind == "box":
        patch = Rectangle(
            (bounds["left"], bounds["bottom"]),
            bounds["right"] - bounds["left"],
            bounds["top"] - bounds["bottom"],
            fill=False,
            edgecolor="white",
            linewidth=1.5,
        )
    else:
        patch = Polygon(
            roi.vertices_arcsec,
            closed=True,
            fill=False,
            edgecolor="white",
            linewidth=1.5,
        )
    ax.add_patch(patch)


def _reference_colorbar_label(
    item: RadioImage, display_config: dict[str, Any] | None
) -> str:
    bunit = str(item.header.get("BUNIT", "")).strip() or "raw intensity"
    transform = str((display_config or {}).get("transform", "linear")).strip().lower()
    if transform in {"log10", "log10 positive", "log"}:
        return f"log10({bunit})"
    return bunit


def _reference_plot_title(item: RadioImage) -> str:
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


def _display_frequency_key(freq_mhz: float) -> str:
    if not np.isfinite(freq_mhz):
        return "nan"
    return f"{float(freq_mhz):.6g}"


def _load_reference_from_rows(df: pd.DataFrame) -> RadioImage | None:
    if "filepath" not in df.columns:
        return None
    ok = (
        df[df.get("quality_flag", "").astype(str).str.lower().eq("ok")]
        if "quality_flag" in df.columns
        else df
    )
    for value in ok["filepath"].dropna():
        path = Path(str(value))
        if not path.exists():
            continue
        for item in iter_radio_images(path):
            return item
    return None


def _first_ok_image(
    radio_dir: str | Path,
    *,
    pattern: str,
    recursive: bool,
    freqs: list[float],
    time_start: str | datetime | None,
    time_end: str | datetime | None,
) -> RadioImage | None:
    files = _resolve_radio_files(
        radio_dir,
        pattern=pattern,
        recursive=recursive,
        files=None,
        freqs=freqs,
        time_start=time_start,
        time_end=time_end,
    )
    for path in files:
        for item in iter_radio_images(path):
            return item
    return None


def _parse_roi_bounds(raw: str) -> RadioRoi:
    parts = [float(item.strip()) for item in str(raw).split(",") if item.strip()]
    if len(parts) != 4:
        raise ValueError("--roi-bounds must contain left,bottom,right,top")
    return RadioRoi.from_box(parts[0], parts[1], parts[2], parts[3])


def _parse_float_csv(raw: str | None) -> list[float]:
    if not raw:
        return []
    return [float(item.strip()) for item in raw.split(",") if item.strip()]


def _parse_optional_datetime(
    value: str | datetime | None, label: str
) -> datetime | None:
    if value in (None, ""):
        return None
    parsed = parse_datetime_value(value)
    if parsed is None:
        raise ValueError(f"Invalid {label}: {value}")
    return parsed


def _frequency_in_set(value: float, freq_set: set[float]) -> bool:
    if not np.isfinite(value):
        return False
    return any(_same_frequency(float(value), freq) for freq in freq_set)


def _normalize_selected_products(
    selected_products: list[str] | tuple[str, ...] | set[str] | None,
) -> tuple[str, ...]:
    if selected_products is None:
        return tuple(PRODUCT_FILENAMES)
    requested = [str(item) for item in selected_products]
    if not requested:
        raise ValueError("At least one export product must be selected.")
    unknown = sorted(set(requested) - set(PRODUCT_FILENAMES))
    if unknown:
        raise ValueError(f"Unknown export products: {unknown}")
    ordered = tuple(key for key in PRODUCT_FILENAMES if key in set(requested))
    if not ordered:
        raise ValueError("At least one export product must be selected.")
    return ordered


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    return value


if __name__ == "__main__":
    raise SystemExit(main())
