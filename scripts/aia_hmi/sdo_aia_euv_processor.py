# -*- coding: utf-8 -*-
# 模块用途: 处理 SDO/AIA EUV FITS 数据，生成单波段图像、多波段拼图和指定区域图像。
# 主要输入: AIA FITS 文件或按波段组织的 FITS 目录。
# 主要输出/运行说明: 输出 PNG 图像；批处理使用 Agg 后端和多进程以适配大批量科研绘图。
"""

Author: Severus
Created on: Sun Nov 23 00:19:30 2025

"""

"""
AIA FITS File Processing Module
================================
This module provides high-performance processing for AIA (Atmospheric Imaging Assembly)
solar observation FITS files. It supports both single-band and multi-band composite
visualization with configurable ROI, display parameters, and parallel processing.

Features:
- Single-band image processing with exposure time normalization
- Multi-band composite visualization (2×3 grid for six AIA wavelengths)
- Configurable region of interest (ROI) extraction
- Parallel processing using multiprocessing for speed
- Customizable display parameters (colormap, intensity range)
- White background for publication-ready figures
- Time-sorted file processing for chronological alignment
"""

import gc
import math
import multiprocessing
import re
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import matplotlib

matplotlib.use(
    "Agg"
)  # Force non-interactive backend for multiprocessing safety and memory leak prevention
import astropy.units as u
import matplotlib.colors as mcolors
import matplotlib.patheffects as mpath_effects
import matplotlib.pyplot as plt
import sunpy.map
from astropy.coordinates import SkyCoord
from sunpy.coordinates import propagate_with_solar_surface
from tqdm import tqdm

from solar_toolkit.path_config import apply_config_to_object

# ==============================================================================
# Global Configuration
# ==============================================================================
AIA_CONFIG: dict = {
    94: {"cmap": "sdoaia94", "vmin": 0.4, "vmax": 6666},
    131: {"cmap": "sdoaia131", "vmin": 0.7, "vmax": 6666},
    171: {"cmap": "sdoaia171", "vmin": 16, "vmax": 6666},
    193: {"cmap": "sdoaia193", "vmin": 42, "vmax": 6666},
    211: {"cmap": "sdoaia211", "vmin": 18, "vmax": 6666},
    304: {"cmap": "sdoaia304", "vmin": 0.9, "vmax": 2222},
}


@dataclass
class AIAConfig:
    data_path: str = r"D:\spike_topping_type_III\2025\20250503\AIA"
    output_dir: Optional[str] = None
    start_idx: int = 0
    end_idx: Optional[int] = None
    roi_bounds: Tuple[float, float, float, float] = (
        -700,
        -100,
        -100,
        400,
    )  # (xmin, xmax, ymin, ymax)
    user_vmin: Optional[float] = None
    user_vmax: Optional[float] = None
    user_cmap: Optional[str] = None

    # Base width for dynamic figure size (inches), height is automatically calculated proportionally
    base_fig_width: float = 8.0
    dpi: int = 300
    show_limb: bool = False  # If enabled, limb color will be changed to black
    show_grid: bool = True  # Enabled by default to match reference images
    show_colorbar: bool = False
    save_image: bool = True
    show_image: bool = False
    use_band_subdirs: bool = True

    max_workers: Optional[int] = None

    # Multi-band composite: False for original behavior (single image per file);
    # True aligns the k-th time-sorted file from each band directory onto the same canvas
    multi_band_composite: bool = True
    multi_band_wavelengths: Optional[Tuple[int, ...]] = (
        None  # Six-band reference layout: (94,131,171,193,211,304)
    )
    # corresponds to 2×3 grid: top row 94–131–171, bottom row 193–211–304;
    # None means sorting by numeric subdirectory names (usually this order)
    multi_band_output_subdir: str = "multi_band"
    multi_band_merge_axes: bool = (
        True  # Kept for backward compatibility; mosaic mode uses seamless stitching with only band/time labels
    )
    # Only effective when multi_band_composite=True: whether to also export single-band PNGs for each FITS file after mosaic creation
    multi_band_also_save_single: bool = False
    # Spacing between subplots in mosaic (matplotlib relative to subplot width/height, typically 0.03–0.1 for visible gaps)
    multi_band_wspace: float = 0.06
    multi_band_hspace: float = 0.06
    # Absolute padding around canvas when saving (inches); used for both single and mosaic images
    figure_pad_inches: float = 0.15
    # Main title (date YYYY-MM-DD) font size; used for both single and mosaic images
    figure_suptitle_fontsize: float = 34
    # Time title font size at the top of subplot in single-map mode (below main title)
    single_map_title_fontsize: float = 13

    def __post_init__(self):
        apply_config_to_object(self, "sdo_aia_euv_processor")
        if self.multi_band_wavelengths is not None:
            self.multi_band_wavelengths = tuple(self.multi_band_wavelengths)
        if self.output_dir is None:
            self.output_dir = self.data_path
        if self.multi_band_composite and self.multi_band_wavelengths is None:
            self.multi_band_wavelengths = (94, 131, 171, 193, 211, 304)


# ==============================================================================
# Internal Utility Functions
# ==============================================================================
def _resolve_files(input_path: Path, start_idx: int, end_idx: Optional[int]) -> list:
    if input_path.is_file():
        file_list = [input_path]
    elif input_path.is_dir():
        # Sort by time string (not path string) in ascending order to ensure output sequence matches observation time in single-map mode
        file_list = sorted(input_path.rglob("*.fits"), key=lambda p: _parse_timestr(p))
    else:
        raise ValueError(f"Invalid path: {input_path}")

    total = len(file_list)
    if total == 0:
        raise ValueError("No FITS files found in data directory or its subdirectories!")

    end = total if end_idx is None else min(end_idx, total)
    selected = file_list[start_idx:end]
    print(
        f"Found {total} files total, selected {len(selected)} for processing (indices: {start_idx} ~ {end - 1})"
    )
    return selected


def _parse_timestr(file_path: Path) -> str:
    """Precisely extract time string in format like 2025-01-24T033001Z"""
    # Try regex matching standard ISO time format
    match = re.search(r"\d{4}-\d{2}-\d{2}T\d{6}Z", file_path.name)
    if match:
        return match.group(0)

    # Fallback approach
    parts = file_path.name.split(".")
    for part in parts:
        if "T" in part and "Z" in part:
            return part
    return file_path.stem


def _resolve_display_params(
    current_map: sunpy.map.GenericMap,
    user_cmap: Optional[str],
    user_vmin: Optional[float],
    user_vmax: Optional[float],
) -> Tuple[str, mcolors.Normalize]:
    wave_val = int(current_map.wavelength.value)
    config = AIA_CONFIG.get(wave_val, {})
    sunpy_norm = current_map.plot_settings["norm"]
    sunpy_cmap = current_map.plot_settings["cmap"]

    final_cmap = user_cmap or config.get("cmap", sunpy_cmap)
    final_vmin = (
        user_vmin if user_vmin is not None else config.get("vmin", sunpy_norm.vmin)
    )
    final_vmax = (
        user_vmax if user_vmax is not None else config.get("vmax", sunpy_norm.vmax)
    )

    if not (final_vmin and final_vmax and final_vmin > 0 and final_vmax > final_vmin):
        final_vmin, final_vmax = 1.0, 1e4

    return final_cmap, mcolors.LogNorm(vmin=final_vmin, vmax=final_vmax)


def _layout_grid(n: int) -> Tuple[int, int]:
    if n <= 0:
        return 1, 1
    ncol = max(1, math.ceil(math.sqrt(n)))
    nrow = max(1, math.ceil(n / ncol))
    return nrow, ncol


def _layout_mosaic_grid(n: int) -> Tuple[int, int]:
    """Matches common SDO six-band mosaic layout: 2 rows × 3 columns; other counts use approximate square grid."""
    if n == 6:
        return 2, 3
    return _layout_grid(n)


def _discover_wavelength_dirs(data_path: Path) -> Tuple[int, ...]:
    found: List[int] = []
    digit_dirs = [p for p in data_path.iterdir() if p.is_dir() and p.name.isdigit()]
    for p in sorted(digit_dirs, key=lambda x: int(x.name)):
        found.append(int(p.name))
    if not found:
        raise ValueError(
            f"No numeric wavelength subdirectories found under {data_path}; "
            f"please set multi_band_wavelengths or check use_band_subdirs / path."
        )
    return tuple(found)


def _sorted_fits_for_band(
    data_path: Path, wave: int, use_band_subdirs: bool
) -> List[Path]:
    band_dir = (data_path / str(wave)) if use_band_subdirs else data_path
    if not band_dir.is_dir():
        raise ValueError(f"Band directory does not exist: {band_dir}")
    files = sorted(band_dir.rglob("*.fits"), key=lambda p: _parse_timestr(p))
    return files


def _slice_band_files(
    files: List[Path], start_idx: int, end_idx: Optional[int]
) -> List[Path]:
    total = len(files)
    if total == 0:
        return []
    end = total if end_idx is None else min(end_idx, total)
    return files[start_idx:end]


def _build_multi_band_slots(
    cfg: AIAConfig, wavelengths: Tuple[int, ...]
) -> List[Tuple[Path, ...]]:
    data_path = Path(cfg.data_path)
    per_band: List[List[Path]] = []
    for w in wavelengths:
        all_f = _sorted_fits_for_band(data_path, w, cfg.use_band_subdirs)
        # Double safety: sort the complete list again by time string before slicing,
        # ensuring files from each band are strictly ordered by observation time regardless of filesystem order.
        all_f = sorted(all_f, key=lambda p: _parse_timestr(p))
        sliced = _slice_band_files(all_f, cfg.start_idx, cfg.end_idx)
        if not sliced:
            raise ValueError(
                f"Band {w} has no FITS files in index range [{cfg.start_idx}, {cfg.end_idx})"
            )
        # Sort again after slicing to prevent potential disorder from start_idx/end_idx (defensive programming)
        sliced = sorted(sliced, key=lambda p: _parse_timestr(p))
        per_band.append(sliced)
    m = min(len(x) for x in per_band)
    if any(len(x) != m for x in per_band):
        print(
            f"Note: Available file counts differ across bands; using shortest length {m} frames after time sorting "
            f"(the k-th frame from each band will be aligned on the same canvas)."
        )
    # Construct slots: slot[i] = (i-th time file from band0, i-th time file from band1, ...)
    # From the 1st mosaic to the m-th mosaic, files from each band progress from earliest to latest observation time.
    return [tuple(band[i] for band in per_band) for i in range(m)]


def _obs_time_isot_label(aia_map: sunpy.map.GenericMap, fallback_path: Path) -> str:
    """Matches reference images: ISO time + optional milliseconds, e.g., 2025-04-28T02:48:11.121."""
    try:
        return str(aia_map.date.isot)
    except Exception:
        s = _parse_timestr(fallback_path).strip()
        return s[:-1] if s.endswith("Z") else s


def _hide_wcs_frame_for_seamless(ax) -> None:
    """Remove coordinate ticks and axis labels for seamless subplot boundaries, facilitating multi-band pixel-aligned mosaics."""
    lon, lat = ax.coords
    lon.set_ticks_visible(False)
    lat.set_ticks_visible(False)
    lon.set_ticklabel_visible(False)
    lat.set_ticklabel_visible(False)
    lon.set_axislabel("")
    lat.set_axislabel("")
    ax.set_frame_on(False)


def _silence_heliographic_overlay(overlay) -> None:
    """Remove Stonyhurst/Carrington axis labels and ticks produced by draw_grid (keep grid lines)."""
    if overlay is None:
        return
    try:
        o0, o1 = overlay[0], overlay[1]
        o0.set_axislabel("")
        o1.set_axislabel("")
        o0.set_ticklabel_visible(False)
        o1.set_ticklabel_visible(False)
        o0.set_ticks_visible(False)
        o1.set_ticks_visible(False)
    except (TypeError, KeyError, IndexError, AttributeError):
        pass


def _purge_stonyhurst_text_artists(ax) -> None:
    """Hide text objects accidentally left on the plot containing 'Stonyhurst' or 'Carrington' labels."""
    for txt in ax.texts:
        t = txt.get_text().lower()
        if "stonyhurst" in t or "carrington" in t:
            txt.set_visible(False)


def _obs_date_ymd(
    aia_map: sunpy.map.GenericMap, fallback_path: Optional[Path] = None
) -> str:
    """For main title: observation date from FITS/image, only year-month-day YYYY-MM-DD."""
    try:
        dt = aia_map.date.to_datetime()
        return f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d}"
    except Exception:
        if fallback_path is not None:
            s = _parse_timestr(fallback_path)
            m = re.search(r"\d{4}-\d{2}-\d{2}", s)
            if m:
                return m.group(0)
        return ""


# ==============================================================================
# Single File Processing Core Function
# ==============================================================================
def _process_single_worker(file_path: Path, cfg: AIAConfig) -> Tuple[bool, str]:
    current_map = None
    raw_cutout = None
    cutout_map = None
    fig = None

    try:
        current_map = sunpy.map.Map(file_path)
        wave_val = int(current_map.wavelength.value)
        exp_time = current_map.exposure_time.to_value(u.s)

        if exp_time <= 0:
            return False, f"{file_path.name}: Abnormal exposure time ({exp_time}s)"

        # 1. Coordinate and crop boundary parsing
        tx1, tx2, ty1, ty2 = cfg.roi_bounds
        roi_bl_tx, roi_bl_ty = tx1 * u.arcsec, ty1 * u.arcsec
        roi_tr_tx, roi_tr_ty = tx2 * u.arcsec, ty2 * u.arcsec

        # 2. Calculate adaptive figsize (height based on physical aspect ratio)
        dx = abs(tx2 - tx1)
        dy = abs(ty2 - ty1)
        aspect_ratio = dy / dx if dx != 0 else 1.0
        fig_width = cfg.base_fig_width
        fig_height = fig_width * aspect_ratio

        # 3. Crop processing
        with propagate_with_solar_surface():
            frame = current_map.coordinate_frame
            bl = SkyCoord(Tx=roi_bl_tx, Ty=roi_bl_ty, frame=frame)
            tr = SkyCoord(Tx=roi_tr_tx, Ty=roi_tr_ty, frame=frame)
            raw_cutout = current_map.submap(bl, top_right=tr)

        normalized_data = raw_cutout.data / exp_time
        cutout_map = sunpy.map.Map(normalized_data, raw_cutout.meta)

        final_cmap, final_norm = _resolve_display_params(
            current_map, cfg.user_cmap, cfg.user_vmin, cfg.user_vmax
        )
        time_str = _parse_timestr(file_path)

        # 4. Plot setup (core modification: set background to white)
        # Explicitly set figure facecolor to white
        fig = plt.figure(figsize=(fig_width, fig_height), facecolor="white")
        ax = fig.add_subplot(projection=cutout_map)
        # Set axes facecolor (inside plot area) to white
        ax.set_facecolor("white")

        im = cutout_map.plot(axes=ax, cmap=final_cmap, norm=final_norm, annotate=False)

        if cfg.show_limb:
            # With white background, change limb color to black
            current_map.draw_limb(axes=ax, color="black", linewidth=0.8, alpha=0.6)

        if cfg.show_grid:
            # annotate=False: do not draw Stonyhurst grid axis labels/ticks; then forcibly clear overlay text
            hg_ov = cutout_map.draw_grid(
                axes=ax,
                color="black",
                linewidth=0.3,
                alpha=0.3,
                linestyle="--",
                annotate=False,
            )
            _silence_heliographic_overlay(hg_ov)
            _purge_stonyhurst_text_artists(ax)

        if cfg.show_colorbar:
            cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
            cbar.set_label("Intensity (DN/s)", fontsize=10)
            cbar.ax.tick_params(labelsize=9)

        # 5. UI fine-tuning (match reference image layout)
        lon, lat = ax.coords
        lon.set_axislabel("Helioprojective Longitude (Solar-X)", fontsize=10)
        lat.set_axislabel("Helioprojective Latitude (Solar-Y)", fontsize=10)

        # Ticks and labels (already black by default, clear on white background)

        # Ticks inward, displayed on all four sides
        lon.set_ticks(direction="in")
        lat.set_ticks(direction="in")
        lon.set_ticks_position("tb")
        lat.set_ticks_position("lr")

        # Set title to time only (font size slightly smaller than main title)
        ax.set_title(f"{time_str}", fontsize=cfg.single_map_title_fontsize, pad=22)

        # Single-band mode: no main title (date), only keep subtitle (specific time)
        # Adjust subplot position to leave enough space for axis labels and ticks
        fig.subplots_adjust(left=0.13, right=0.95, top=0.93, bottom=0.11)

        # 6. Save image (filename uses time string directly)
        if cfg.save_image and cfg.output_dir:
            save_dir = (
                Path(cfg.output_dir) / str(wave_val)
                if cfg.use_band_subdirs
                else Path(cfg.output_dir)
            )
            save_dir.mkdir(parents=True, exist_ok=True)
            # Output name: time_string.png (change to .jpg here if needed)
            save_path = save_dir / f"{time_str}.png"
            fig.savefig(
                save_path,
                dpi=cfg.dpi,
                bbox_inches="tight",
                facecolor="white",
                pad_inches=cfg.figure_pad_inches,
            )

        return True, ""

    except Exception as e:
        return False, f"{file_path.name} -> {str(e)}"

    finally:
        if fig is not None:
            plt.close(fig)
        del current_map, raw_cutout, cutout_map
        gc.collect()


def _process_multi_band_worker(
    slot_idx: int,
    paths: Tuple[Path, ...],
    wavelengths: Tuple[int, ...],
    cfg: AIAConfig,
) -> Tuple[bool, str]:
    fig = None
    cutout_maps = []
    current_maps = []
    panel_meta: List[Tuple[str, int, str, mcolors.Normalize]] = []

    try:
        if len(paths) != len(wavelengths):
            return False, "内部错误: paths 与 wavelengths 长度不一致"

        tx1, tx2, ty1, ty2 = cfg.roi_bounds
        roi_bl_tx, roi_bl_ty = tx1 * u.arcsec, ty1 * u.arcsec
        roi_tr_tx, roi_tr_ty = tx2 * u.arcsec, ty2 * u.arcsec
        dx = abs(tx2 - tx1)
        dy = abs(ty2 - ty1)
        aspect_ratio = dy / dx if dx != 0 else 1.0

        for path, expect_w in zip(paths, wavelengths):
            current_map = sunpy.map.Map(path)
            wave_val = int(current_map.wavelength.value)
            if wave_val != expect_w:
                return False, f"{path.name}: 波长 {wave_val} 与期望波段 {expect_w} 不符"
            exp_time = current_map.exposure_time.to_value(u.s)
            if exp_time <= 0:
                return False, f"{path.name}: 曝光时间异常 ({exp_time}s)"
            with propagate_with_solar_surface():
                frame = current_map.coordinate_frame
                bl = SkyCoord(Tx=roi_bl_tx, Ty=roi_bl_ty, frame=frame)
                tr = SkyCoord(Tx=roi_tr_tx, Ty=roi_tr_ty, frame=frame)
                raw_cutout = current_map.submap(bl, top_right=tr)
            normalized_data = raw_cutout.data / exp_time
            cutout_map = sunpy.map.Map(normalized_data, raw_cutout.meta)
            final_cmap, final_norm = _resolve_display_params(
                current_map, cfg.user_cmap, cfg.user_vmin, cfg.user_vmax
            )
            iso_t = _obs_time_isot_label(current_map, path)
            cutout_maps.append(cutout_map)
            current_maps.append(current_map)
            panel_meta.append((final_cmap, wave_val, iso_t, final_norm))

        n = len(cutout_maps)
        nrow, ncol = _layout_mosaic_grid(n)
        fig_width = cfg.base_fig_width * ncol
        panel_w = fig_width / ncol
        fig_height = panel_w * aspect_ratio * nrow

        fig = plt.figure(figsize=(fig_width, fig_height), facecolor="white")
        gs = fig.add_gridspec(
            nrow,
            ncol,
            figure=fig,
            wspace=cfg.multi_band_wspace,
            hspace=cfg.multi_band_hspace,
        )
        for idx in range(n):
            row, col = divmod(idx, ncol)
            ax = fig.add_subplot(gs[row, col], projection=cutout_maps[idx])
            ax.set_facecolor("white")
            cmap, wave_val, iso_t, norm = panel_meta[idx]
            im = cutout_maps[idx].plot(axes=ax, cmap=cmap, norm=norm, annotate=False)
            if cfg.show_limb:
                current_maps[idx].draw_limb(
                    axes=ax, color="black", linewidth=0.8, alpha=0.6
                )
            if cfg.show_grid:
                hg_ov = cutout_maps[idx].draw_grid(
                    axes=ax,
                    color="black",
                    linewidth=0.3,
                    alpha=0.3,
                    linestyle="--",
                    annotate=False,
                )
                _silence_heliographic_overlay(hg_ov)
                _purge_stonyhurst_text_artists(ax)
            if cfg.show_colorbar:
                fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02).set_label(
                    "DN/s", fontsize=8
                )
            _hide_wcs_frame_for_seamless(ax)
            ax.text(
                0.02,
                0.03,
                f"{iso_t} AIA {wave_val}",
                transform=ax.transAxes,
                fontsize=13,
                va="bottom",
                ha="left",
                color="white",
                path_effects=[
                    mpath_effects.withStroke(
                        linewidth=2.2, foreground="black", alpha=0.65
                    )
                ],
            )

        for j in range(n, nrow * ncol):
            er, ec = divmod(j, ncol)
            ax_empty = fig.add_subplot(gs[er, ec])
            ax_empty.set_visible(False)

        slot_label = f"{slot_idx + 1:04d}"
        date_ymd = _obs_date_ymd(current_maps[0], paths[0])

        # 多波段模式：添加主标题（日期）
        if date_ymd:
            fig.suptitle(
                date_ymd,
                fontsize=cfg.figure_suptitle_fontsize,
                y=0.97,  # 调整主标题垂直位置
                fontweight="medium",
            )

        # 根据是否有主标题调整子图位置
        if date_ymd:
            # 有主标题：顶部留出标题高度，底部和两侧留出适当空间
            fig.subplots_adjust(
                left=0.04,
                right=0.96,
                top=0.89,  # 为标题留出空间
                bottom=0.04,
            )
        else:
            # 无主标题：均匀分布
            fig.subplots_adjust(
                left=0.04,
                right=0.96,
                top=0.95,
                bottom=0.04,
            )

        if cfg.save_image and cfg.output_dir:
            save_dir = Path(cfg.output_dir) / cfg.multi_band_output_subdir
            save_dir.mkdir(parents=True, exist_ok=True)
            save_path = save_dir / f"multi_{slot_label}.png"
            fig.savefig(
                save_path,
                dpi=cfg.dpi,
                bbox_inches="tight",
                facecolor="white",
                pad_inches=cfg.figure_pad_inches,
            )

        return True, ""

    except Exception as e:
        return False, f"multi-band slot {slot_idx} -> {str(e)}"

    finally:
        if fig is not None:
            plt.close(fig)
        del cutout_maps, current_maps
        gc.collect()


# ==============================================================================
# Batch Processing Entry Point
# ==============================================================================
def process_aia_fits(cfg: AIAConfig):
    if cfg.multi_band_composite:
        if not cfg.use_band_subdirs:
            raise ValueError(
                "Multi-band mosaic requires data organized in wavelength subdirectories (use_band_subdirs=True)."
            )
        waves = cfg.multi_band_wavelengths
        if waves is None:
            waves = _discover_wavelength_dirs(Path(cfg.data_path))
        print(f"Multi-band mosaic mode: wavelengths {waves}")
        slots = _build_multi_band_slots(cfg, waves)
        print(
            f"Total {len(slots)} time slots (each slot contains {len(waves)} bands on the same canvas)"
        )

        start_time = time.time()
        success_cnt = 0
        error_cnt = 0
        workers = cfg.max_workers or max(1, multiprocessing.cpu_count() - 1)
        print(f"Starting multiprocessing for mosaics, allocated cores: {workers} ...")

        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_process_multi_band_worker, i, slots[i], waves, cfg): i
                for i in range(len(slots))
            }
            for future in tqdm(
                as_completed(futures), total=len(slots), desc="Multi-band", unit="slot"
            ):
                success, msg = future.result()
                if success:
                    success_cnt += 1
                else:
                    error_cnt += 1
                    tqdm.write(f"\n  [Failed] {msg}")

        elapsed = time.time() - start_time
        print(
            f"\nMulti-band mosaic completed! Success: {success_cnt}, Failed: {error_cnt}, Total time: {elapsed:.2f} seconds"
        )
        if not cfg.multi_band_also_save_single:
            return
        print(
            "\n--- Continuing to export single-band images (multi_band_also_save_single=True) ---"
        )

    input_path = Path(cfg.data_path)
    selected_files = _resolve_files(input_path, cfg.start_idx, cfg.end_idx)

    start_time = time.time()
    success_cnt = 0
    error_cnt = 0

    workers = cfg.max_workers or max(1, multiprocessing.cpu_count() - 1)
    print(f"Starting multiprocessing, allocated cores: {workers} ...")

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_process_single_worker, f, cfg): f for f in selected_files
        }

        for future in tqdm(
            as_completed(futures),
            total=len(selected_files),
            desc="Processing",
            unit="file",
        ):
            success, msg = future.result()
            if success:
                success_cnt += 1
            else:
                error_cnt += 1
                tqdm.write(f"\n  [Failed] {msg}")

    elapsed = time.time() - start_time
    print(
        f"\nProcessing completed! Success: {success_cnt}, Failed: {error_cnt}, Total time: {elapsed:.2f} seconds"
    )


if __name__ == "__main__":
    # Default: single file per image (same as original)
    cfg = AIAConfig(show_image=False, show_grid=True)
    # Multi-band on same canvas: multi_band_composite=True; if also want single-band PNGs: multi_band_also_save_single=True
    print(
        "--- Starting high-speed batch processing of AIA data (white background version) ---"
    )
    process_aia_fits(cfg)
