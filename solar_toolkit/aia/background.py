"""AIA FITS background helpers for radio-source trajectory views.

English: Scan AIA FITS folders, choose the closest image to a radio frame, and
read a lightweight helioprojective background grid for Plotly overlays.

中文：扫描 AIA FITS 文件夹，为射电帧匹配最近的 AIA 图像，并读取轻量级
日面角秒背景网格用于轨迹前端叠加。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from astropy.io import fits

from solar_toolkit.radio.centers import (
    FITS_SUFFIXES,
    parse_datetime_value,
    parse_time_from_filename,
    pixel_to_hpc_arcsec,
)


@dataclass
class AiaBackground:
    """Downsampled AIA image plus 1D HPLN/HPLT axes for Plotly heatmaps."""

    path: str
    z: np.ndarray
    x_arcsec: np.ndarray
    y_arcsec: np.ndarray
    label: str
    obs_time: pd.Timestamp | None
    wavelength: str


@dataclass
class NearestAIA:
    """Result of matching a radio frame time to an AIA table."""

    status: str
    path: str | None = None
    obs_time: pd.Timestamp | None = None
    delta_seconds: float | None = None
    reason: str = ""


def scan_aia_folder(
    aia_dir: str | Path,
    *,
    pattern: str = "*.fits",
    recursive: bool = False,
) -> pd.DataFrame:
    """Scan an AIA FITS folder and return ``path``, ``obs_time``, ``wavelength``."""

    folder = Path(aia_dir).expanduser()
    columns = ["path", "obs_time", "wavelength"]
    if not str(aia_dir).strip() or not folder.exists():
        return pd.DataFrame(columns=columns)

    files = folder.rglob(pattern) if recursive else folder.glob(pattern)
    rows: list[dict[str, object]] = []
    for path in sorted(files):
        if not path.is_file() or path.suffix.lower() not in FITS_SUFFIXES:
            continue
        obs_time = None
        wavelength = ""
        try:
            with fits.open(path, memmap=False, ignore_missing_end=True) as hdul:
                for hdu in hdul:
                    header = hdu.header
                    if header is None:
                        continue
                    obs_time = _header_time(header)
                    wavelength = str(header.get("WAVELNTH", wavelength or ""))
                    if obs_time is not None:
                        break
        except Exception:
            obs_time = None
        if obs_time is None:
            obs_time = parse_time_from_filename(path)
        if obs_time is None:
            continue
        rows.append(
            {
                "path": str(path),
                "obs_time": pd.Timestamp(obs_time),
                "wavelength": wavelength,
            }
        )
    return pd.DataFrame(rows, columns=columns).sort_values("obs_time").reset_index(drop=True)


def _header_time(header: fits.Header) -> pd.Timestamp | None:
    for key in ("DATE-OBS", "DATE_OBS", "T_OBS", "DATE"):
        parsed = parse_datetime_value(header.get(key))
        if parsed is not None:
            return pd.Timestamp(parsed)
    return None


def find_nearest_aia(
    aia_table: pd.DataFrame,
    frame_time,
    *,
    max_dt_seconds: float = 3600.0,
) -> NearestAIA:
    """Find the AIA row closest to ``frame_time`` within a maximum time gap."""

    if aia_table is None or aia_table.empty:
        return NearestAIA(status="no_files", reason="AIA table is empty.")
    if "obs_time" not in aia_table.columns or "path" not in aia_table.columns:
        return NearestAIA(status="invalid_table", reason="AIA table lacks path/obs_time.")
    target = pd.Timestamp(frame_time)
    times = pd.to_datetime(aia_table["obs_time"], errors="coerce")
    valid = times.notna()
    if not valid.any():
        return NearestAIA(status="invalid_table", reason="AIA table has no valid times.")
    diffs = (times[valid] - target).abs().dt.total_seconds()
    best_index = diffs.idxmin()
    best_delta = float(diffs.loc[best_index])
    row = aia_table.loc[best_index]
    if best_delta > float(max_dt_seconds):
        return NearestAIA(
            status="too_far",
            path=str(row["path"]),
            obs_time=pd.Timestamp(row["obs_time"]),
            delta_seconds=best_delta,
            reason="Nearest AIA file exceeds max_dt_seconds.",
        )
    return NearestAIA(
        status="matched",
        path=str(row["path"]),
        obs_time=pd.Timestamp(row["obs_time"]),
        delta_seconds=best_delta,
    )


def read_aia_background(
    path: str | Path,
    *,
    max_pixels: int = 1024,
    percentile_limits: tuple[float, float] = (1.0, 99.7),
    log_scale: bool = True,
    wcs_mode: str = "header",
) -> AiaBackground:
    """Read a downsampled AIA image for Plotly background display.

    ``wcs_mode="header"`` uses a fast linear FITS-header grid. ``"sunpy"``
    validates that SunPy can read the file before using the same regular grid,
    because Plotly heatmaps need 1D axes for efficient playback.
    """

    resolved = Path(path).expanduser()
    mode = str(wcs_mode or "header").lower()
    if mode not in {"header", "sunpy"}:
        raise ValueError("wcs_mode must be 'header' or 'sunpy'")
    if mode == "sunpy":
        _validate_sunpy_map_readable(resolved)

    image, header = _read_first_image_hdu(resolved)
    image = np.where(np.isfinite(image), image, np.nan)
    ny, nx = image.shape
    step = max(1, int(math.ceil(max(ny, nx) / max(1, int(max_pixels)))))
    z = image[::step, ::step].astype(float)
    z = _scale_background(z, percentile_limits=percentile_limits, log_scale=log_scale)

    y_pix = np.arange(0, ny, step)
    x_pix = np.arange(0, nx, step)
    x_arcsec = np.array(
        [pixel_to_hpc_arcsec(header, float(x), 0.0)[0] for x in x_pix],
        dtype=float,
    )
    y_arcsec = np.array(
        [pixel_to_hpc_arcsec(header, 0.0, float(y))[1] for y in y_pix],
        dtype=float,
    )
    obs_time = _header_time(header) or (
        pd.Timestamp(parse_time_from_filename(resolved))
        if parse_time_from_filename(resolved) is not None
        else None
    )
    wavelength = str(header.get("WAVELNTH", ""))
    label = resolved.name
    if obs_time is not None:
        label += f" | {pd.Timestamp(obs_time).isoformat()}"
    if wavelength:
        label += f" | {wavelength} A"
    return AiaBackground(
        path=str(resolved),
        z=z,
        x_arcsec=x_arcsec,
        y_arcsec=y_arcsec,
        label=label,
        obs_time=pd.Timestamp(obs_time) if obs_time is not None else None,
        wavelength=wavelength,
    )


def _validate_sunpy_map_readable(path: Path) -> None:
    try:
        import sunpy.map
    except Exception as exc:  # pragma: no cover - depends on optional runtime pieces.
        raise ImportError("SunPy WCS mode requires sunpy.map.") from exc
    sunpy.map.Map(path)


def _read_first_image_hdu(path: Path) -> tuple[np.ndarray, fits.Header]:
    with fits.open(path, memmap=False, ignore_missing_end=True) as hdul:
        for hdu in hdul:
            if hdu.data is None:
                continue
            data = np.asarray(hdu.data)
            if data.dtype.fields is not None:
                continue
            data = np.squeeze(data)
            while data.ndim > 2:
                data = data[0]
            if data.ndim == 2:
                return data.astype(float), hdu.header
    raise ValueError(f"No 2D image found in AIA FITS file: {path}")


def _scale_background(
    z: np.ndarray,
    *,
    percentile_limits: tuple[float, float],
    log_scale: bool,
) -> np.ndarray:
    finite = np.isfinite(z)
    if not np.any(finite):
        return np.zeros_like(z, dtype=float)
    low, high = percentile_limits
    lo = float(np.nanpercentile(z[finite], low))
    hi = float(np.nanpercentile(z[finite], high))
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        lo = float(np.nanmin(z[finite]))
        hi = float(np.nanmax(z[finite]))
    scaled = np.clip(z, lo, hi)
    if log_scale:
        scaled = np.log10(scaled - lo + 1.0)
    return scaled


def load_nearest_background(
    aia_table: pd.DataFrame,
    frame_time,
    *,
    max_dt_seconds: float = 3600.0,
    max_pixels: int = 1024,
    percentile_limits: tuple[float, float] = (1.0, 99.7),
    log_scale: bool = True,
    wcs_mode: str = "header",
) -> tuple[AiaBackground | None, NearestAIA]:
    """Find and read the closest AIA background, returning status either way."""

    nearest = find_nearest_aia(
        aia_table,
        frame_time,
        max_dt_seconds=max_dt_seconds,
    )
    if nearest.status != "matched" or nearest.path is None:
        return None, nearest
    return (
        read_aia_background(
            nearest.path,
            max_pixels=max_pixels,
            percentile_limits=percentile_limits,
            log_scale=log_scale,
            wcs_mode=wcs_mode,
        ),
        nearest,
    )
