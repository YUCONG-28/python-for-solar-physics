"""
SDO/AIA EUV FITS processor.

This script creates exposure-normalized AIA single-band PNGs and multi-band
mosaics from wavelength subdirectories such as:

    D:\\solar_physics_project\\2024\\20240110\\SDO\\AIA\\94
    D:\\solar_physics_project\\2024\\20240110\\SDO\\AIA\\171

CLI examples:

    python sdo_aia_euv_processor.py --root D:\\solar_physics_project --year 2024 --date 20240110 --mode single --waves 94 131 171 193 211 304 335 1600

    python sdo_aia_euv_processor.py --root D:\\solar_physics_project --year 2024 --date 20240110 --mode mosaic --waves 94 131 171 193 211 304 335 1600

    python sdo_aia_euv_processor.py --root D:\\solar_physics_project --year 2025 --date 20250803 --mode single --waves 171 193 --roi -700 -100 -100 400

Mosaic layout examples:

    python sdo_aia_euv_processor.py --mode mosaic --waves 94 131 171 193 211 304 335 1600 --mosaic-ncols 3 --mosaic-seamless --mosaic-show-outer-axes

    python sdo_aia_euv_processor.py --mode mosaic --waves 94 131 171 193 211 304 335 1600 --mosaic-ncols 4 --mosaic-seamless --mosaic-show-outer-axes

    python sdo_aia_euv_processor.py --mode mosaic --waves 94 131 171 193 211 304 335 1600 --mosaic-ncols 4 --mosaic-seamless --no-mosaic-outer-axes

    python sdo_aia_euv_processor.py --mode mosaic --waves 94 131 171 193 211 304 --mosaic-ncols 3 --mosaic-seamless --mosaic-show-outer-axes --no-mosaic-save-tight

    python sdo_aia_euv_processor.py --mode mosaic --waves 94 131 171 193 211 304 335 1600 --mosaic-ncols 4 --mosaic-seamless --mosaic-show-outer-axes --no-mosaic-save-tight

    python sdo_aia_euv_processor.py --mode mosaic --waves 94 131 171 193 211 304 --mosaic-ncols 3 --mosaic-seamless --no-mosaic-outer-axes --mosaic-left 0 --mosaic-right 1 --mosaic-bottom 0 --mosaic-top 1 --no-mosaic-save-tight

    python sdo_aia_euv_processor.py --mode mosaic --waves 94 131 171 193 211 304 --mosaic-ncols 3 --mosaic-max-workers 1 --mosaic-max-slots 5

Test mode examples:

    python sdo_aia_euv_processor.py --mode test --test-file D:\\solar_physics_project\\2024\\20240110\\SDO\\AIA\\171\\your_file.fits --roi -700 -100 -100 400

    python sdo_aia_euv_processor.py --mode test --root D:\\solar_physics_project --year 2024 --date 20240110 --test-wave 171 --test-index 99 --roi -700 -100 -100 400

    python sdo_aia_euv_processor.py --mode test --root D:\\solar_physics_project --year 2024 --date 20240110 --test-wave 193 --test-index 49 --colorbar

    python sdo_aia_euv_processor.py --mode test --root D:\\solar_physics_project --year 2024 --date 20240110 --test-wave 94 --test-index 99 --vmax 1200

Difference image examples:

    # Original-image mosaic only, with global outer axis labels to avoid WCS tick overlap.
    python sdo_aia_euv_processor.py --mode mosaic --waves 94 131 171 193 211 304 --draw-original --no-draw-difference --mosaic-ncols 3 --mosaic-global-outer-axes

    # Difference-only mosaic using each band's AIA colormap and user-defined limits.
    python sdo_aia_euv_processor.py --mode mosaic --waves 94 131 171 193 211 304 --no-draw-original --draw-difference --diff-waves 94 131 171 193 211 304 --mosaic-difference-inline --difference-method running --difference-cmap-mode band --difference-norm-mode fixed --difference-vmin -200 --difference-vmax 200 --mosaic-ncols 3 --mosaic-global-outer-axes

    # Original panels plus selected inline difference panels in the same mosaic.
    python sdo_aia_euv_processor.py --mode mosaic --waves 94 131 171 193 211 304 --draw-original --draw-difference --diff-waves 94 171 304 --mosaic-difference-inline --difference-method running --difference-cmap-mode band --difference-norm-mode auto --mosaic-ncols 3 --mosaic-global-outer-axes

    # Single-band difference images only.
    python sdo_aia_euv_processor.py --mode single --waves 171 193 --no-draw-original --draw-difference --diff-waves 171 193 --difference-method running --difference-cmap-mode band --difference-norm-mode fixed --difference-vmin -200 --difference-vmax 200

    # Single-band original images only.
    python sdo_aia_euv_processor.py --mode single --waves 171 193 --draw-original --no-draw-difference

    # Single-band original images plus running differences.
    python sdo_aia_euv_processor.py --mode single --waves 171 193 --draw-original --draw-difference --diff-waves 171 193 --difference-method running

    # Single-band difference images only.
    python sdo_aia_euv_processor.py --mode single --waves 171 193 --no-draw-original --draw-difference --diff-waves 171 193 --difference-method running

    # Single-band difference with user-defined limits.
    python sdo_aia_euv_processor.py --mode single --waves 193 --no-draw-original --draw-difference --diff-waves 193 --difference-method base --difference-vmin -200 --difference-vmax 200 --difference-cmap-mode band

    # Mosaic with AIA 94 original plus AIA 94 difference.
    python sdo_aia_euv_processor.py --mode mosaic --waves 94 --draw-original --draw-difference --diff-waves 94 --mosaic-difference-inline --mosaic-ncols 2

    # Mosaic difference panels only.
    python sdo_aia_euv_processor.py --mode mosaic --waves 94 131 171 193 --no-draw-original --draw-difference --diff-waves 94 131 171 193 --mosaic-difference-inline --mosaic-ncols 4

    # Mosaic originals plus selected difference panels.
    python sdo_aia_euv_processor.py --mode mosaic --waves 94 131 171 193 --draw-original --draw-difference --diff-waves 94 171 --mosaic-difference-inline --mosaic-ncols 3

    # Difference-only mosaic with per-band symmetric limits and forced AIA band colormaps.
    python sdo_aia_euv_processor.py --mode mosaic --waves 94 131 171 193 211 304 --no-draw-original --draw-difference --diff-waves 94 131 171 193 211 304 --mosaic-difference-inline --difference-method running --difference-cmap-mode band --difference-vlim-by-wave 94:80 131:120 171:200 193:250 211:220 304:300 --mosaic-ncols 3 --mosaic-global-outer-axes

    # Difference-only mosaic with per-band asymmetric limits and forced AIA band colormaps.
    python sdo_aia_euv_processor.py --mode mosaic --waves 94 131 171 193 211 304 --no-draw-original --draw-difference --diff-waves 94 131 171 193 211 304 --mosaic-difference-inline --difference-method running --difference-cmap-mode band --difference-vmin-by-wave 94:-60 131:-100 171:-180 193:-220 211:-200 304:-280 --difference-vmax-by-wave 94:90 131:150 171:240 193:300 211:260 304:360 --mosaic-ncols 3 --mosaic-global-outer-axes

    # Single-band differences with per-band symmetric limits.
    python sdo_aia_euv_processor.py --mode single --waves 171 193 304 --no-draw-original --draw-difference --diff-waves 171 193 304 --difference-method running --difference-cmap-mode band --difference-vlim-by-wave 171:200 193:250 304:300

    # Mosaic difference images only; saved to multi_band_difference.
    python sdo_aia_euv_processor.py --mode mosaic --waves 94 131 171 193 211 304 --no-draw-original --draw-difference --diff-waves 94 131 171 193 211 304 --difference-output-mode mosaic --difference-method running --difference-cmap-mode band --difference-vlim-by-wave 94:7 131:7 171:34 193:49 211:22 304:9 --mosaic-ncols 3 --mosaic-global-outer-axes

    # Mosaic originals plus selected difference panels; saved to multi_band_original_plus_difference.
    python sdo_aia_euv_processor.py --mode mosaic --waves 94 131 171 193 211 304 --draw-original --draw-difference --diff-waves 94 171 193 304 --difference-output-mode mosaic --difference-method running --difference-cmap-mode band --mosaic-ncols 3 --mosaic-global-outer-axes

    # Mosaic difference images plus per-band single difference outputs.
    python sdo_aia_euv_processor.py --mode mosaic --waves 94 131 171 193 211 304 --no-draw-original --draw-difference --diff-waves 94 131 171 193 211 304 --difference-output-mode both --difference-method running --difference-cmap-mode band --mosaic-ncols 3 --mosaic-global-outer-axes

    # Recommended running-difference mosaic, no derotation for short-cadence AIA.
    python sdo_aia_euv_processor.py --mode mosaic --waves 94 131 171 193 211 304 --no-draw-original --draw-difference --diff-waves 94 131 171 193 211 304 --difference-output-mode mosaic --difference-method running --no-difference-derotate --difference-cmap-mode band --difference-vlim-by-wave 94:7 131:7 171:34 193:49 211:22 304:9 --mosaic-ncols 3 --mosaic-global-outer-axes

    # Base-difference mosaic, skipping the base reference frame by default.
    python sdo_aia_euv_processor.py --mode mosaic --waves 94 131 171 193 211 304 --no-draw-original --draw-difference --diff-waves 94 131 171 193 211 304 --difference-output-mode mosaic --difference-method base --difference-base-index 0 --no-difference-derotate --difference-cmap-mode band --mosaic-ncols 3 --mosaic-global-outer-axes

    # Long-duration derotated base difference; full-map reproject is applied before ROI cutout.
    python sdo_aia_euv_processor.py --mode mosaic --waves 171 193 --no-draw-original --draw-difference --diff-waves 171 193 --difference-output-mode mosaic --difference-method base --difference-base-index 0 --difference-derotate --difference-cmap-mode diverging --difference-vmin -200 --difference-vmax 200 --mosaic-ncols 2 --mosaic-global-outer-axes

    # Auto-scaled running-difference mosaic using percentile(abs(diff_data)).
    python sdo_aia_euv_processor.py --mode mosaic --waves 94 131 171 193 211 304 --no-draw-original --draw-difference --diff-waves 94 131 171 193 211 304 --difference-output-mode mosaic --difference-method running --difference-cmap-mode diverging --difference-norm-mode auto --difference-percentile 99.5 --no-difference-derotate --mosaic-ncols 3 --mosaic-global-outer-axes

Outputs:
- Single-band PNGs are saved beside the source FITS files in each band's
  ``plot`` subdirectory by default.
- Multi-band mosaics are saved in ``<data_path>\\multi_band`` by default.

Code test-mode example:

    cfg = AIAConfig(
        use_test_mode=True,
        test_wave=171,
        test_index=99,
        roi_bounds=(-700, -100, -100, 400),
        show_grid=True,
        show_limb=False,
        show_colorbar=True,
    )
    process_aia_fits(cfg)
"""

import argparse
import gc
import math
import multiprocessing
import re
import time
import warnings
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

import astropy.units as u
import matplotlib
import matplotlib.colors as mcolors
import matplotlib.patheffects as mpath_effects
import numpy as np
import sunpy.map
from astropy.coordinates import SkyCoord
from sunpy.coordinates import propagate_with_solar_surface
from tqdm import tqdm

from solar_toolkit.path_config import apply_config_to_object

from .aia_io import parse_timestr as _shared_parse_timestr

# ==============================================================================
# Configuration
# ==============================================================================
# AIA_CONFIG 控制颜色映射和 LogNorm 显示范围；vmin/vmax 是曝光归一化后的 DN/s。
# 图像过曝可增大 vmax，细节太暗可减小 vmax。
AIA_CONFIG: dict = {
    94: {"cmap": "sdoaia94", "vmin": 0.6, "vmax": 420},
    131: {"cmap": "sdoaia131", "vmin": 0.9, "vmax": 810},
    171: {"cmap": "sdoaia171", "vmin": 16.0, "vmax": 2800},
    193: {"cmap": "sdoaia193", "vmin": 49.0, "vmax": 4200},
    211: {"cmap": "sdoaia211", "vmin": 22.0, "vmax": 2800},
    304: {"cmap": "sdoaia304", "vmin": 1.2, "vmax": 1400},
    335: {"cmap": "sdoaia335", "vmin": 0.5, "vmax": 700},
    1600: {"cmap": "sdoaia1600", "vmin": 5.0, "vmax": 3500},
}

# Original AIA EUV images use LogNorm because the intensity range is large.
# Difference images contain signed values, so they must use a linear Normalize
# with symmetric vmin/vmax around zero. SunPy examples often show AIA 193
# differences with about +/-200, but practical science plots should adjust the
# range by event, ROI, and wavelength. The default below is therefore an auto
# symmetric percentile of abs(diff_data), with DIFF_CONFIG as a fallback or
# explicit config mode. Historical fixed values such as +/-777 or +/-888 are
# intentionally not the default because they can hide weak structure or saturate
# strong events.
DIFF_CONFIG: dict = {
    94: {"cmap": "RdBu_r", "vlim": 120.0},
    131: {"cmap": "RdBu_r", "vlim": 200.0},
    171: {"cmap": "RdBu_r", "vlim": 250.0},
    193: {"cmap": "RdBu_r", "vlim": 250.0},
    211: {"cmap": "RdBu_r", "vlim": 220.0},
    304: {"cmap": "RdBu_r", "vlim": 300.0},
    335: {"cmap": "RdBu_r", "vlim": 120.0},
    1600: {"cmap": "RdBu_r", "vlim": 600.0},
}


def _normalize_wave_float_dict(value, name: str) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        normalized = {}
        for k, v in value.items():
            wave = int(k)
            normalized[wave] = float(v)
        return normalized
    if isinstance(value, (list, tuple)):
        normalized = {}
        for item in value:
            if isinstance(item, str):
                if ":" not in item:
                    raise ValueError(
                        f"{name} item must use WAVE:VALUE format, got {item!r}"
                    )
                wave_str, val_str = item.split(":", 1)
                normalized[int(wave_str)] = float(val_str)
            else:
                raise ValueError(f"{name} must be dict or list of WAVE:VALUE strings.")
        return normalized
    raise ValueError(f"{name} must be dict, list, tuple, or None.")


@dataclass
class AIAConfig:
    # ===== 用户最常修改区域 =====
    root_dir: str = r"<PROJECT_ROOT>"
    year: str = "2026"
    date: str = "20260326"

    # mode 可选 single / mosaic / test；use_test_mode=True 时优先只预览一张图。
    mode: str = "mosaic"
    use_test_mode: bool = False

    # test_file 优先级最高；为空时从 data_path/test_wave 中按时间排序选第 test_index 个文件。
    # Python 从 0 开始计数；若想选肉眼看到的第 100 个文件，可设置 test_index=99。
    test_file: str | None = None
    test_wave: int = 131
    test_index: int = 99

    data_path: str | None = None
    output_dir: str | None = None
    single_band_output_subdir: str = "plot"
    mosaic_output_subdir: str = "multi_band"
    mosaic_difference_output_subdir: str = "multi_band_difference"
    mosaic_original_plus_difference_output_subdir: str = (
        "multi_band_original_plus_difference"
    )

    start_idx: int = 0
    end_idx: int | None = None

    # ROI 单位 arcsec，Helioprojective 坐标，格式 (xmin, xmax, ymin, ymax)。
    # test 模式最适合用来调 ROI。
    roi_bounds: tuple[float, float, float, float] = (-1100, -800, -550, -200)

    # 默认 None 表示使用 AIA_CONFIG；仅临时调图时手动覆盖。
    user_vmin: float | None = None
    user_vmax: float | None = None
    user_cmap: str | None = None

    base_fig_width: float = 8.0
    dpi: int = 300
    show_limb: bool = False
    show_grid: bool = True
    show_colorbar: bool = False

    # test 模式会自动设置 save_image=False、show_image=True。
    save_image: bool = True
    show_image: bool = False
    use_band_subdirs: bool = True
    max_workers: int | None = None

    draw_original: bool = False
    multi_band_composite: bool = False
    multi_band_wavelengths: tuple[int, ...] | None = (
        94,
        131,
        171,
        193,
        211,
        304,
    )
    multi_band_merge_axes: bool = True
    multi_band_also_save_single: bool = False

    # mosaic 每行多少张子图；None 表示自动接近方形布局，例如 3 表示每行 3 张。
    mosaic_ncols: int | None = 3
    # mosaic 子图之间是否无缝拼接；True 时强制 wspace/hspace=0。
    mosaic_seamless: bool = True
    # 是否只在拼图外边缘显示坐标轴刻度与标签。
    mosaic_show_outer_axes: bool = True
    # 外边缘坐标字体大小。
    mosaic_ticklabel_fontsize: int = 7
    mosaic_axislabel_fontsize: int = 9
    # 内部子图通常隐藏坐标，避免无缝拼接时坐标重叠。
    mosaic_hide_inner_axes: bool = True
    # 不够填满网格时是否隐藏最后的空白 panel。
    mosaic_hide_empty_panels: bool = True
    # 使用手动 axes 布局，避免 GridSpec/WCSAxes 装饰撑开子图间距。
    mosaic_manual_layout: bool = True
    # 只给整张 mosaic 外侧留边，panel 之间不留空隙。
    mosaic_left: float = 0.055
    mosaic_right: float = 0.995
    mosaic_bottom: float = 0.055
    mosaic_top: float = 0.935
    mosaic_top_no_title: float = 0.995
    mosaic_title_y: float = 0.975
    # mosaic 默认不使用 tight bbox，避免重新引入白边。
    mosaic_save_tight: bool = False
    mosaic_pad_inches: float = 0.0
    # 默认不拉伸图像；仅展示用途可强制填满 axes。
    mosaic_force_fill_axes: bool = False
    # 打印 figure/panel 宽高比，排查 mosaic 内部白边。
    mosaic_debug_layout: bool = False
    # 减少外边缘坐标数量，避免相邻 panel 的 tick label 重叠。
    mosaic_reduce_tick_overlap: bool = True
    mosaic_max_ticks_per_axis: int = 3
    mosaic_hide_boundary_ticklabels: bool = True
    mosaic_x_tick_strategy: str = "all_bottom"
    mosaic_y_tick_strategy: str = "all_left"
    # 只保留整张图一次 X/Y axis label，避免边缘 panel 重复写标签。
    mosaic_outer_axislabel_once: bool = True
    # 兜底模式：隐藏所有 panel tick 数字，只在整张图外侧加坐标轴名称。
    mosaic_global_outer_axes: bool = True
    # panel 左下角波段/时间文字位置。
    mosaic_panel_label_x: float = 0.02
    mosaic_panel_label_y: float = 0.035
    mosaic_panel_label_y_last_row: float = 0.08
    # mosaic 单任务会同时打开多波段 FITS，默认限制 worker 降低内存压力。
    mosaic_max_workers: int | None = 12
    mosaic_max_slots: int | None = None
    mosaic_difference_inline: bool = True

    # ===== Difference image options =====
    draw_difference: bool = True
    difference_method: str = "running"
    difference_output_mode: str = "auto"
    difference_wavelengths: tuple[int, ...] | None = (
        94,
        131,
        171,
        193,
        211,
        304,
    )
    difference_base_index: int | None = None
    difference_output_subdir: str = "difference"
    difference_norm_mode: str = "auto"
    difference_percentile: float = 99.5
    difference_vmin: float | None = None
    difference_vmax: float | None = None
    difference_cmap: str = "RdBu_r"
    difference_cmap_mode: str = "diverging"
    warn_band_difference_cmap: bool = False
    difference_save_reference: bool = False
    difference_show_colorbar: bool = False
    difference_derotate: bool = False
    difference_vmin_by_wave: dict = field(default_factory=dict)
    difference_vmax_by_wave: dict = field(default_factory=dict)
    difference_vlim_by_wave: dict = field(default_factory=dict)

    multi_band_wspace: float = 0.06
    multi_band_hspace: float = 0.06
    figure_pad_inches: float = 0.15
    figure_suptitle_fontsize: float = 34
    single_map_title_fontsize: float = 13

    def __post_init__(self):
        apply_config_to_object(self, "sdo_aia_euv_processor")
        self.difference_vmin_by_wave = _normalize_wave_float_dict(
            self.difference_vmin_by_wave, "difference_vmin_by_wave"
        )
        self.difference_vmax_by_wave = _normalize_wave_float_dict(
            self.difference_vmax_by_wave, "difference_vmax_by_wave"
        )
        self.difference_vlim_by_wave = _normalize_wave_float_dict(
            self.difference_vlim_by_wave, "difference_vlim_by_wave"
        )
        if self.mode not in ("single", "mosaic", "test"):
            raise ValueError(f"Invalid mode: {self.mode}")
        if self.data_path is None:
            self.data_path = str(
                Path(self.root_dir) / self.year / self.date / "SDO" / "AIA"
            )
        else:
            self.data_path = str(Path(self.data_path))
        if self.test_file is not None:
            self.test_file = str(Path(self.test_file))
        if self.output_dir is None:
            self.output_dir = self.data_path
        if self.multi_band_wavelengths is not None:
            self.multi_band_wavelengths = tuple(
                int(w) for w in self.multi_band_wavelengths
            )
        if self.difference_method not in ("base", "running"):
            raise ValueError(f"Invalid difference_method: {self.difference_method}")
        if self.difference_output_mode not in ("auto", "mosaic", "single", "both"):
            raise ValueError(
                f"Invalid difference_output_mode: {self.difference_output_mode}"
            )
        if self.difference_norm_mode not in ("auto", "fixed", "config"):
            raise ValueError(
                f"Invalid difference_norm_mode: {self.difference_norm_mode}"
            )
        if self.difference_cmap_mode not in ("band", "diverging", "custom"):
            raise ValueError(
                f"Invalid difference_cmap_mode: {self.difference_cmap_mode}"
            )
        if self.difference_wavelengths is not None:
            self.difference_wavelengths = tuple(
                int(w) for w in self.difference_wavelengths
            )
        if not self.draw_original and not self.draw_difference:
            raise ValueError(
                "Nothing to draw: at least one of draw_original or "
                "draw_difference must be True."
            )
        if self.draw_difference and self.difference_percentile <= 0:
            raise ValueError("difference_percentile must be positive.")


def _configure_matplotlib_backend(mode: str) -> None:
    if mode in ("single", "mosaic"):
        matplotlib.use("Agg", force=True)
    # test 模式不强制 Agg，尽量使用系统或 IDE 的交互后端。


@dataclass
class PanelData:
    cutout_map: sunpy.map.GenericMap
    wave_val: int
    iso_time: str
    date_ymd: str
    cmap: str
    norm: mcolors.Normalize
    panel_kind: str = "original"
    panel_label: str | None = None
    is_difference: bool = False


# ==============================================================================
# Path / IO Utilities
# ==============================================================================
def _parse_timestr(file_path: Path) -> str:
    """Extract a stable time string such as 2025-01-24T033001Z."""
    return _shared_parse_timestr(file_path)


def _resolve_files(input_path: Path, start_idx: int, end_idx: int | None) -> list:
    if input_path.is_file():
        file_list = [input_path]
    elif input_path.is_dir():
        file_list = sorted(input_path.rglob("*.fits"), key=lambda p: _parse_timestr(p))
    else:
        raise ValueError(f"Invalid path: {input_path}")

    total = len(file_list)
    if total == 0:
        raise ValueError(f"No FITS files found under: {input_path}")

    end = total if end_idx is None else min(end_idx, total)
    selected = file_list[start_idx:end]
    print(
        f"Found {total} files total, selected {len(selected)} for processing "
        f"(indices: {start_idx} ~ {end - 1})"
    )
    return selected


def _discover_wavelength_dirs(data_path: Path) -> tuple[int, ...]:
    if not data_path.is_dir():
        raise ValueError(f"AIA data directory does not exist: {data_path}")
    found = [
        int(p.name) for p in data_path.iterdir() if p.is_dir() and p.name.isdigit()
    ]
    if not found:
        raise ValueError(
            f"No numeric wavelength subdirectories found under {data_path}."
        )
    return tuple(sorted(found))


def _sorted_fits_for_band(
    data_path: Path, wave: int, use_band_subdirs: bool
) -> list[Path]:
    band_dir = (data_path / str(wave)) if use_band_subdirs else data_path
    if not band_dir.is_dir():
        raise ValueError(f"Missing AIA band directory for {wave} Å: {band_dir}")
    files = sorted(band_dir.rglob("*.fits"), key=lambda p: _parse_timestr(p))
    if not files:
        raise ValueError(f"No FITS files found in band directory: {band_dir}")
    return files


def _slice_band_files(
    files: list[Path], start_idx: int, end_idx: int | None
) -> list[Path]:
    total = len(files)
    end = total if end_idx is None else min(end_idx, total)
    return files[start_idx:end]


def _resolve_single_files(cfg: AIAConfig) -> list[Path]:
    data_path = Path(cfg.data_path)
    waves = cfg.multi_band_wavelengths

    if data_path.is_file():
        return _resolve_files(data_path, cfg.start_idx, cfg.end_idx)
    if not cfg.use_band_subdirs or waves is None:
        return _resolve_files(data_path, cfg.start_idx, cfg.end_idx)

    selected_files: list[Path] = []
    for wave in waves:
        files = _sorted_fits_for_band(data_path, wave, cfg.use_band_subdirs)
        sliced = _slice_band_files(files, cfg.start_idx, cfg.end_idx)
        if not sliced:
            raise ValueError(
                f"Band {wave} has no FITS files in index range "
                f"[{cfg.start_idx}, {cfg.end_idx})"
            )
        selected_files.extend(sliced)
        print(f"Band {wave}: selected {len(sliced)} / {len(files)} files")
    return selected_files


def _resolve_test_file(cfg: AIAConfig) -> Path:
    if cfg.test_file:
        test_path = Path(cfg.test_file)
        if not test_path.is_file():
            raise ValueError(f"Test file does not exist: {test_path}")
        print("Test mode selected file:")
        print("Test wave: from FITS header")
        print("Test index: direct file")
        print(f"File path: {test_path}")
        return test_path

    band_dir = Path(cfg.data_path) / str(cfg.test_wave)
    if not band_dir.is_dir():
        raise ValueError(f"Test band directory does not exist: {band_dir}")

    files = sorted(band_dir.glob("*.fits"), key=lambda p: _parse_timestr(p))
    if not files:
        raise ValueError(f"No FITS files found in test band directory: {band_dir}")

    if cfg.test_index < 0 or cfg.test_index >= len(files):
        raise ValueError(
            f"test_index={cfg.test_index} is out of range. Available index "
            f"range: 0 ~ {len(files) - 1}."
        )

    test_path = files[cfg.test_index]
    print("Test mode selected file:")
    print(f"Test wave: {cfg.test_wave}")
    print(f"Test index: {cfg.test_index}")
    print(f"File path: {test_path}")
    return test_path


def _build_multi_band_slots(
    cfg: AIAConfig, wavelengths: tuple[int, ...]
) -> list[tuple[Path, ...]]:
    data_path = Path(cfg.data_path)
    per_band: list[list[Path]] = []

    for wave in wavelengths:
        all_files = _sorted_fits_for_band(data_path, wave, cfg.use_band_subdirs)
        sliced = _slice_band_files(all_files, cfg.start_idx, cfg.end_idx)
        if not sliced:
            raise ValueError(
                f"Band {wave} has no FITS files in index range "
                f"[{cfg.start_idx}, {cfg.end_idx})"
            )
        per_band.append(sliced)

    slot_count = min(len(files) for files in per_band)
    if any(len(files) != slot_count for files in per_band):
        print(
            "Note: Available file counts differ across bands; using shortest "
            f"length {slot_count} after time sorting."
        )

    return [tuple(band[i] for band in per_band) for i in range(slot_count)]


# ==============================================================================
# Plotting Core
# ==============================================================================
def _resolve_display_params(
    current_map: sunpy.map.GenericMap,
    user_cmap: str | None,
    user_vmin: float | None,
    user_vmax: float | None,
) -> tuple[str, mcolors.Normalize]:
    wave_val = int(current_map.wavelength.value)
    config = AIA_CONFIG.get(wave_val)
    sunpy_norm = current_map.plot_settings["norm"]
    sunpy_cmap = current_map.plot_settings["cmap"]

    if config is None:
        warnings.warn(
            f"AIA wavelength {wave_val} Å is not in AIA_CONFIG; using SunPy "
            "default plot_settings unless CLI overrides are provided.",
            RuntimeWarning,
            stacklevel=2,
        )
        final_cmap = user_cmap or sunpy_cmap
        final_vmin = user_vmin if user_vmin is not None else sunpy_norm.vmin
        final_vmax = user_vmax if user_vmax is not None else sunpy_norm.vmax
    else:
        final_cmap = user_cmap or config["cmap"]
        final_vmin = user_vmin if user_vmin is not None else config["vmin"]
        final_vmax = user_vmax if user_vmax is not None else config["vmax"]

    if not (final_vmin and final_vmax and final_vmin > 0 and final_vmax > final_vmin):
        warnings.warn(
            f"Invalid LogNorm limits for AIA {wave_val} Å; falling back to "
            "vmin=1.0, vmax=10000.0.",
            RuntimeWarning,
            stacklevel=2,
        )
        final_vmin, final_vmax = 1.0, 1e4

    return final_cmap, mcolors.LogNorm(vmin=final_vmin, vmax=final_vmax)


def _diff_config_vlim(wave_val: int) -> float:
    config = DIFF_CONFIG.get(wave_val, {})
    vlim = float(config.get("vlim", 200.0))
    return vlim if np.isfinite(vlim) and vlim > 0 else 200.0


def _resolve_fixed_difference_limits_for_wave(
    wave_val: int,
    cfg: AIAConfig,
) -> tuple[float, float] | None:
    vmin_by_wave = cfg.difference_vmin_by_wave or {}
    vmax_by_wave = cfg.difference_vmax_by_wave or {}
    vlim_by_wave = cfg.difference_vlim_by_wave or {}

    has_vmin = wave_val in vmin_by_wave
    has_vmax = wave_val in vmax_by_wave
    has_vlim = wave_val in vlim_by_wave

    if has_vmin or has_vmax:
        if has_vmin and has_vmax:
            return float(vmin_by_wave[wave_val]), float(vmax_by_wave[wave_val])
        if has_vmin:
            vlim = abs(float(vmin_by_wave[wave_val]))
            return -vlim, vlim
        vlim = abs(float(vmax_by_wave[wave_val]))
        return -vlim, vlim

    if has_vlim:
        vlim = abs(float(vlim_by_wave[wave_val]))
        return -vlim, vlim

    if cfg.difference_vmin is not None or cfg.difference_vmax is not None:
        if cfg.difference_vmin is not None and cfg.difference_vmax is not None:
            return float(cfg.difference_vmin), float(cfg.difference_vmax)
        if cfg.difference_vmin is not None:
            vlim = abs(float(cfg.difference_vmin))
            return -vlim, vlim
        vlim = abs(float(cfg.difference_vmax))
        return -vlim, vlim

    if cfg.difference_norm_mode == "fixed":
        raise ValueError(
            "difference_norm_mode='fixed' requires per-band limits, "
            "difference_vlim_by_wave, or global difference_vmin/difference_vmax."
        )

    return None


def _resolve_difference_params(
    diff_data: np.ndarray,
    wave_val: int,
    cfg: AIAConfig,
) -> tuple[str, mcolors.Normalize]:
    diff_config = DIFF_CONFIG.get(wave_val, {})
    if cfg.difference_cmap_mode == "band":
        band_config = AIA_CONFIG.get(wave_val)
        if band_config is None:
            raise ValueError(
                f"AIA {wave_val}: missing AIA_CONFIG entry; cannot force "
                "band colormap."
            )
        if cfg.warn_band_difference_cmap:
            warnings.warn(
                "difference_cmap_mode='band' uses the AIA sequential band colormap. "
                "For signed difference maps, difference_cmap_mode='diverging' with "
                "RdBu_r is often clearer for positive/negative contrast.",
                RuntimeWarning,
                stacklevel=2,
            )
        cmap = band_config["cmap"]
    elif cfg.difference_cmap_mode == "diverging":
        cmap = diff_config.get("cmap") or "RdBu_r"
    elif cfg.difference_cmap_mode == "custom":
        if not cfg.difference_cmap:
            raise ValueError("difference_cmap_mode='custom' requires difference_cmap.")
        cmap = cfg.difference_cmap
    else:
        raise ValueError(f"Invalid difference_cmap_mode: {cfg.difference_cmap_mode}")

    def _difference_norm(vmin: float, vmax: float) -> mcolors.Normalize:
        if not vmin < vmax:
            raise ValueError("difference_vmin must be smaller than difference_vmax.")
        if vmin < 0 < vmax:
            return mcolors.TwoSlopeNorm(vmin=vmin, vcenter=0.0, vmax=vmax)
        warnings.warn(
            "Difference limits do not span zero; using linear Normalize "
            "instead of TwoSlopeNorm.",
            RuntimeWarning,
            stacklevel=2,
        )
        return mcolors.Normalize(vmin=vmin, vmax=vmax)

    fixed_limits = _resolve_fixed_difference_limits_for_wave(wave_val, cfg)
    if fixed_limits is not None:
        vmin, vmax = fixed_limits
        return cmap, _difference_norm(vmin, vmax)

    if cfg.difference_norm_mode == "config":
        vlim = _diff_config_vlim(wave_val)
        return cmap, _difference_norm(-vlim, vlim)

    finite = np.asarray(diff_data[np.isfinite(diff_data)])
    if finite.size:
        abs_finite = np.abs(finite)
        vlim = float(np.nanpercentile(abs_finite, cfg.difference_percentile))
    else:
        vlim = np.nan
    if not np.isfinite(vlim) or vlim <= 0:
        vlim = _diff_config_vlim(wave_val)
    if cfg.mosaic_debug_layout:
        print(
            f"AIA {wave_val} auto difference limits: "
            f"percentile={cfg.difference_percentile}, "
            f"vmin={-vlim:.3g}, vmax={vlim:.3g}"
        )
    return cmap, _difference_norm(-vlim, vlim)


def _load_exposure_normalized_map(path: Path) -> sunpy.map.GenericMap:
    current_map = sunpy.map.Map(path)
    exp_time = current_map.exposure_time.to_value(u.s)
    if exp_time <= 0:
        raise ValueError(f"{path.name}: abnormal exposure time ({exp_time}s)")

    normalized_data = current_map.data / exp_time
    meta = current_map.meta.copy()
    meta["bunit"] = "DN / s"
    return sunpy.map.Map(normalized_data, meta)


def _cutout_roi(
    aia_map: sunpy.map.GenericMap,
    cfg: AIAConfig,
) -> sunpy.map.GenericMap:
    tx1, tx2, ty1, ty2 = cfg.roi_bounds
    frame = aia_map.coordinate_frame
    bl = SkyCoord(Tx=tx1 * u.arcsec, Ty=ty1 * u.arcsec, frame=frame)
    tr = SkyCoord(Tx=tx2 * u.arcsec, Ty=ty2 * u.arcsec, frame=frame)
    return aia_map.submap(bl, top_right=tr)


def _load_normalized_cutout(
    path: Path,
    cfg: AIAConfig,
) -> sunpy.map.GenericMap:
    full_map = _load_exposure_normalized_map(path)
    return _cutout_roi(full_map, cfg)


def _make_difference_map(
    current_map: sunpy.map.GenericMap,
    reference_map: sunpy.map.GenericMap | None,
    cfg: AIAConfig,
    wave: int | None = None,
) -> sunpy.map.GenericMap:
    meta = current_map.meta.copy()

    if reference_map is None:
        diff_quantity = current_map.quantity - current_map.quantity
    else:
        if reference_map.data.shape != current_map.data.shape:
            raise ValueError(
                f"shape mismatch current={current_map.data.shape}, "
                f"reference={reference_map.data.shape}"
            )
        diff_quantity = current_map.quantity - reference_map.quantity

    meta["bunit"] = diff_quantity.unit.to_string()
    diff_data = diff_quantity.value
    nan_fraction = np.count_nonzero(~np.isfinite(diff_data)) / diff_data.size
    if nan_fraction > 0.05:
        warnings.warn(
            f"Difference map contains {nan_fraction:.1%} NaN pixels. "
            "If this occurs in running difference, set difference_derotate=False; "
            "if using derotation, reproject full map before ROI cutout.",
            RuntimeWarning,
            stacklevel=2,
        )

    if cfg.mosaic_debug_layout:
        finite = diff_data[np.isfinite(diff_data)]
        if finite.size:
            wave_label = f"AIA {wave}" if wave is not None else "AIA"
            print(
                f"{wave_label} diff stats: "
                f"min={np.nanmin(diff_data):.3g}, "
                f"max={np.nanmax(diff_data):.3g}, "
                f"p1={np.nanpercentile(finite, 1):.3g}, "
                f"p99={np.nanpercentile(finite, 99):.3g}, "
                f"nan_fraction={nan_fraction:.3%}"
            )

    diff_data = np.nan_to_num(diff_data, nan=0.0, posinf=0.0, neginf=0.0)
    return sunpy.map.Map(diff_data, meta)


def _load_difference_map_from_paths(
    current_path: Path,
    reference_path: Path | None,
    wave: int,
    cfg: AIAConfig,
) -> sunpy.map.GenericMap:
    current_full = None
    reference_full = None
    reference_aligned_full = None

    try:
        current_full = _load_exposure_normalized_map(current_path)

        wave_val = int(current_full.wavelength.value)
        if wave_val != wave:
            raise ValueError(
                f"{current_path.name}: FITS wavelength {wave_val} does not "
                f"match expected band {wave}"
            )

        current_cutout = _cutout_roi(current_full, cfg)

        if reference_path is None:
            reference_cutout = None
        else:
            reference_full = _load_exposure_normalized_map(reference_path)
            ref_wave = int(reference_full.wavelength.value)
            if ref_wave != wave:
                raise ValueError(
                    f"{reference_path.name}: FITS wavelength {ref_wave} does "
                    f"not match expected band {wave}"
                )

            if cfg.difference_derotate:
                # Reproject the full map first. Reprojecting an already-cut ROI
                # can discard pixels that should rotate into the current ROI.
                with propagate_with_solar_surface():
                    reference_aligned_full = reference_full.reproject_to(
                        current_full.wcs
                    )
                reference_cutout = _cutout_roi(reference_aligned_full, cfg)
            else:
                reference_cutout = _cutout_roi(reference_full, cfg)

        return _make_difference_map(
            current_cutout,
            reference_cutout,
            cfg,
            wave=wave,
        )

    finally:
        del current_full, reference_full, reference_aligned_full
        gc.collect()


def _plot_difference_map(
    diff_map: sunpy.map.GenericMap,
    wave_val: int,
    title: str,
    save_path: Path,
    cfg: AIAConfig,
    prev_or_base_label: str | None = None,
) -> None:
    import matplotlib.pyplot as plt

    tx1, tx2, ty1, ty2 = cfg.roi_bounds
    dx = abs(tx2 - tx1)
    dy = abs(ty2 - ty1)
    aspect_ratio = dy / dx if dx != 0 else 1.0
    fig_width = cfg.base_fig_width
    fig_height = fig_width * aspect_ratio
    cmap, norm = _resolve_difference_params(diff_map.data, wave_val, cfg)

    fig = plt.figure(figsize=(fig_width, fig_height), facecolor="white")
    try:
        ax = fig.add_subplot(projection=diff_map)
        ax.set_facecolor("white")
        im = diff_map.plot(axes=ax, cmap=cmap, norm=norm, annotate=False)

        if cfg.show_limb:
            diff_map.draw_limb(axes=ax, color="black", linewidth=0.8, alpha=0.6)

        if cfg.show_grid:
            overlay = diff_map.draw_grid(
                axes=ax,
                color="black",
                linewidth=0.3,
                alpha=0.3,
                linestyle="--",
                annotate=False,
            )
            _silence_heliographic_overlay(overlay)
            _purge_stonyhurst_text_artists(ax)

        if cfg.difference_show_colorbar or cfg.show_colorbar:
            cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, extend="both")
            cbar.set_label("Difference intensity (DN/s)", fontsize=10)
            cbar.ax.tick_params(labelsize=9)

        lon, lat = ax.coords
        lon.set_axislabel("Helioprojective Longitude (Solar-X)", fontsize=10)
        lat.set_axislabel("Helioprojective Latitude (Solar-Y)", fontsize=10)
        lon.set_ticks(direction="in")
        lat.set_ticks(direction="in")
        lon.set_ticks_position("tb")
        lat.set_ticks_position("lr")

        if prev_or_base_label:
            title = f"{title}\n{prev_or_base_label}"
        ax.set_title(title, fontsize=cfg.single_map_title_fontsize, pad=22)
        fig.subplots_adjust(left=0.13, right=0.95, top=0.90, bottom=0.11)

        if cfg.save_image:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(
                save_path,
                dpi=cfg.dpi,
                bbox_inches="tight",
                facecolor="white",
                pad_inches=cfg.figure_pad_inches,
            )

        if cfg.show_image:
            plt.show()

    finally:
        plt.close(fig)
        gc.collect()


def _layout_grid(n: int) -> tuple[int, int]:
    if n <= 0:
        return 1, 1
    ncol = max(1, math.ceil(math.sqrt(n)))
    nrow = max(1, math.ceil(n / ncol))
    return nrow, ncol


def _auto_mosaic_ncols(n: int) -> int:
    if n <= 0:
        return 1
    if n == 3:
        return 3
    if n == 4:
        return 2
    if n == 5:
        return 3
    if n == 6:
        return 3
    if n == 7:
        return 4
    if n == 8:
        return 4
    return math.ceil(math.sqrt(n))


def _layout_mosaic_grid(n: int, mosaic_ncols: int | None = None) -> tuple[int, int]:
    if n <= 0:
        return 1, 1
    if mosaic_ncols is not None:
        if mosaic_ncols <= 0:
            raise ValueError("mosaic_ncols must be a positive integer or None.")
        ncol = min(mosaic_ncols, n)
        nrow = math.ceil(n / ncol)
        return nrow, ncol
    ncol = _auto_mosaic_ncols(n)
    nrow = math.ceil(n / ncol)
    return nrow, ncol


def _compute_mosaic_axes_rects(
    nrow: int,
    ncol: int,
    cfg: AIAConfig,
    has_title: bool,
) -> list[tuple[float, float, float, float]]:
    if cfg.mosaic_show_outer_axes:
        left = cfg.mosaic_left
        bottom = cfg.mosaic_bottom
    else:
        left = cfg.mosaic_left
        bottom = cfg.mosaic_bottom

    right = cfg.mosaic_right
    top = cfg.mosaic_top if has_title else cfg.mosaic_top_no_title

    usable_w = right - left
    usable_h = top - bottom
    if usable_w <= 0 or usable_h <= 0:
        raise ValueError(
            "Invalid mosaic margins: usable width/height must be positive."
        )

    panel_w = usable_w / ncol
    panel_h = usable_h / nrow
    rects: list[tuple[float, float, float, float]] = []
    for idx in range(nrow * ncol):
        row, col = divmod(idx, ncol)
        x0 = left + col * panel_w
        y0 = top - (row + 1) * panel_h
        rects.append((x0, y0, panel_w, panel_h))
    return rects


def _compute_mosaic_figure_size(
    nrow: int,
    ncol: int,
    aspect_ratio: float,
    cfg: AIAConfig,
    has_title: bool,
) -> tuple[float, float]:
    fig_width = cfg.base_fig_width * ncol

    left = cfg.mosaic_left
    right = cfg.mosaic_right
    bottom = cfg.mosaic_bottom
    top = cfg.mosaic_top if has_title else cfg.mosaic_top_no_title

    usable_w = right - left
    usable_h = top - bottom
    if usable_w <= 0 or usable_h <= 0:
        raise ValueError(
            "Invalid mosaic margins: usable width/height must be positive."
        )

    fig_height = fig_width * aspect_ratio * (nrow / ncol) * (usable_w / usable_h)
    if fig_height <= 0:
        raise ValueError("Computed mosaic figure height must be positive.")

    return fig_width, max(fig_height, 2.0)


def _debug_mosaic_layout(
    nrow: int,
    ncol: int,
    fig_width: float,
    fig_height: float,
    aspect_ratio: float,
    cfg: AIAConfig,
    has_title: bool,
) -> None:
    if not cfg.mosaic_debug_layout:
        return

    left = cfg.mosaic_left
    right = cfg.mosaic_right
    bottom = cfg.mosaic_bottom
    top = cfg.mosaic_top if has_title else cfg.mosaic_top_no_title
    usable_w = right - left
    usable_h = top - bottom
    physical_panel_w = fig_width * usable_w / ncol
    physical_panel_h = fig_height * usable_h / nrow
    physical_panel_aspect = physical_panel_h / physical_panel_w

    print("Mosaic layout debug:")
    print(f"nrow={nrow}, ncol={ncol}")
    print(f"fig_width={fig_width:.3f}, fig_height={fig_height:.3f}")
    print(f"roi_aspect={aspect_ratio:.6f}")
    print(f"usable_w={usable_w:.6f}, usable_h={usable_h:.6f}")
    print(f"physical_panel_w={physical_panel_w:.6f}")
    print(f"physical_panel_h={physical_panel_h:.6f}")
    print(f"physical_panel_aspect={physical_panel_aspect:.6f}")


def _finalize_panel_aspect(ax, aspect_ratio: float, cfg: AIAConfig) -> None:
    if cfg.mosaic_force_fill_axes:
        try:
            ax.set_aspect("auto")
        except Exception:
            pass
        return

    try:
        ax.set_box_aspect(aspect_ratio)
    except Exception:
        pass
    try:
        ax.set_aspect("equal", adjustable="box", anchor="C")
    except Exception:
        pass


def _obs_time_isot_label(aia_map: sunpy.map.GenericMap, fallback_path: Path) -> str:
    try:
        return str(aia_map.date.isot)
    except Exception:
        time_str = _parse_timestr(fallback_path).strip()
        return time_str[:-1] if time_str.endswith("Z") else time_str


def _obs_date_ymd(
    aia_map: sunpy.map.GenericMap, fallback_path: Path | None = None
) -> str:
    try:
        dt = aia_map.date.to_datetime()
        return f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d}"
    except Exception:
        if fallback_path is not None:
            match = re.search(r"\d{4}-\d{2}-\d{2}", _parse_timestr(fallback_path))
            if match:
                return match.group(0)
        return ""


def _hide_wcs_frame_for_seamless(ax) -> None:
    lon, lat = ax.coords
    lon.set_ticks_visible(False)
    lat.set_ticks_visible(False)
    lon.set_ticklabel_visible(False)
    lat.set_ticklabel_visible(False)
    lon.set_axislabel("")
    lat.set_axislabel("")
    ax.set_frame_on(False)


def _configure_mosaic_axes(
    ax, row: int, col: int, nrow: int, ncol: int, cfg: AIAConfig
) -> None:
    if cfg.mosaic_global_outer_axes or not cfg.mosaic_show_outer_axes:
        _hide_wcs_frame_for_seamless(ax)
        return

    lon, lat = ax.coords
    is_last_row = row == nrow - 1
    is_first_col = col == 0

    try:
        lon.set_ticks(direction="in")
        lat.set_ticks(direction="in")
        lon.set_ticks_position("b")
        lon.set_ticklabel_position("b")
        lat.set_ticks_position("l")
        lat.set_ticklabel_position("l")
        lon.set_ticklabel(
            size=cfg.mosaic_ticklabel_fontsize,
            exclude_overlapping=True,
        )
        lat.set_ticklabel(
            size=cfg.mosaic_ticklabel_fontsize,
            exclude_overlapping=True,
        )
    except (TypeError, AttributeError):
        try:
            lon.set_ticklabel(size=cfg.mosaic_ticklabel_fontsize)
            lat.set_ticklabel(size=cfg.mosaic_ticklabel_fontsize)
        except (TypeError, AttributeError):
            pass

    if cfg.mosaic_x_tick_strategy == "all_bottom":
        show_lon = is_last_row
    elif cfg.mosaic_x_tick_strategy == "first_bottom_only":
        show_lon = is_last_row and col == 0
    elif cfg.mosaic_x_tick_strategy == "alternating_bottom":
        show_lon = is_last_row and (col % 2 == 0)
    else:
        raise ValueError("Invalid mosaic_x_tick_strategy")

    if cfg.mosaic_y_tick_strategy == "all_left":
        show_lat = is_first_col
    elif cfg.mosaic_y_tick_strategy == "first_left_only":
        show_lat = is_first_col and row == nrow - 1
    elif cfg.mosaic_y_tick_strategy == "alternating_left":
        show_lat = is_first_col and (row % 2 == 0)
    else:
        raise ValueError("Invalid mosaic_y_tick_strategy")

    if not cfg.mosaic_hide_inner_axes:
        show_lon = show_lon or is_last_row
        show_lat = show_lat or is_first_col

    lon.set_ticks_visible(show_lon)
    lon.set_ticklabel_visible(show_lon)
    lat.set_ticks_visible(show_lat)
    lat.set_ticklabel_visible(show_lat)

    if cfg.mosaic_reduce_tick_overlap:
        try:
            if show_lon:
                lon.set_ticks(number=cfg.mosaic_max_ticks_per_axis)
            if show_lat:
                lat.set_ticks(number=cfg.mosaic_max_ticks_per_axis)
        except Exception:
            pass

    lon.set_axislabel("")
    lat.set_axislabel("")

    ax.set_frame_on(True)


def _suppress_mosaic_boundary_ticklabels(
    ax, row: int, col: int, nrow: int, ncol: int, cfg: AIAConfig
) -> None:
    if not cfg.mosaic_hide_boundary_ticklabels:
        return

    # WCSAxes tick labels are version-dependent; rely on safer tick-count and
    # exclude-overlap controls, and only attempt best-effort private cleanup.
    try:
        lon, lat = ax.coords
        if row == nrow - 1 and col not in (0, ncol - 1):
            lon.set_ticklabel(exclude_overlapping=True)
        if col == 0 and row not in (0, nrow - 1):
            lat.set_ticklabel(exclude_overlapping=True)
    except Exception:
        pass


def _add_global_mosaic_axislabels(fig, cfg: AIAConfig) -> None:
    fig.text(
        0.5,
        0.015,
        "Helioprojective Longitude (Solar-X)",
        ha="center",
        va="center",
        fontsize=cfg.mosaic_axislabel_fontsize,
    )
    fig.text(
        0.015,
        0.5,
        "Helioprojective Latitude (Solar-Y)",
        ha="center",
        va="center",
        rotation="vertical",
        fontsize=cfg.mosaic_axislabel_fontsize,
    )


def _silence_heliographic_overlay(overlay) -> None:
    if overlay is None:
        return
    try:
        lon, lat = overlay[0], overlay[1]
        lon.set_axislabel("")
        lat.set_axislabel("")
        lon.set_ticklabel_visible(False)
        lat.set_ticklabel_visible(False)
        lon.set_ticks_visible(False)
        lat.set_ticks_visible(False)
    except (TypeError, KeyError, IndexError, AttributeError):
        pass


def _purge_stonyhurst_text_artists(ax) -> None:
    for text in ax.texts:
        label = text.get_text().lower()
        if "stonyhurst" in label or "carrington" in label:
            text.set_visible(False)


def _process_single_worker(file_path: Path, cfg: AIAConfig) -> tuple[bool, str]:
    current_map = None
    raw_cutout = None
    cutout_map = None
    fig = None
    plt = None

    try:
        if not cfg.show_image:
            matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt

        current_map = sunpy.map.Map(file_path)
        _unused_wave_val = int(current_map.wavelength.value)
        exp_time = current_map.exposure_time.to_value(u.s)

        if exp_time <= 0:
            return False, f"{file_path.name}: abnormal exposure time ({exp_time}s)"

        tx1, tx2, ty1, ty2 = cfg.roi_bounds
        dx = abs(tx2 - tx1)
        dy = abs(ty2 - ty1)
        aspect_ratio = dy / dx if dx != 0 else 1.0
        fig_width = cfg.base_fig_width
        fig_height = fig_width * aspect_ratio

        with propagate_with_solar_surface():
            frame = current_map.coordinate_frame
            bl = SkyCoord(Tx=tx1 * u.arcsec, Ty=ty1 * u.arcsec, frame=frame)
            tr = SkyCoord(Tx=tx2 * u.arcsec, Ty=ty2 * u.arcsec, frame=frame)
            raw_cutout = current_map.submap(bl, top_right=tr)

        normalized_data = raw_cutout.data / exp_time
        cutout_map = sunpy.map.Map(normalized_data, raw_cutout.meta)

        final_cmap, final_norm = _resolve_display_params(
            current_map, cfg.user_cmap, cfg.user_vmin, cfg.user_vmax
        )
        time_str = _parse_timestr(file_path)

        fig = plt.figure(figsize=(fig_width, fig_height), facecolor="white")
        ax = fig.add_subplot(projection=cutout_map)
        ax.set_facecolor("white")

        im = cutout_map.plot(axes=ax, cmap=final_cmap, norm=final_norm, annotate=False)

        if cfg.show_limb:
            current_map.draw_limb(axes=ax, color="black", linewidth=0.8, alpha=0.6)

        if cfg.show_grid:
            overlay = cutout_map.draw_grid(
                axes=ax,
                color="black",
                linewidth=0.3,
                alpha=0.3,
                linestyle="--",
                annotate=False,
            )
            _silence_heliographic_overlay(overlay)
            _purge_stonyhurst_text_artists(ax)

        if cfg.show_colorbar:
            cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
            cbar.set_label("Intensity (DN/s)", fontsize=10)
            cbar.ax.tick_params(labelsize=9)

        lon, lat = ax.coords
        lon.set_axislabel("Helioprojective Longitude (Solar-X)", fontsize=10)
        lat.set_axislabel("Helioprojective Latitude (Solar-Y)", fontsize=10)
        lon.set_ticks(direction="in")
        lat.set_ticks(direction="in")
        lon.set_ticks_position("tb")
        lat.set_ticks_position("lr")
        ax.set_title(f"{time_str}", fontsize=cfg.single_map_title_fontsize, pad=22)
        fig.subplots_adjust(left=0.13, right=0.95, top=0.93, bottom=0.11)

        if cfg.save_image:
            save_dir = file_path.parent / cfg.single_band_output_subdir
            save_dir.mkdir(parents=True, exist_ok=True)
            save_path = save_dir / f"{time_str}.png"
            fig.savefig(
                save_path,
                dpi=cfg.dpi,
                bbox_inches="tight",
                facecolor="white",
                pad_inches=cfg.figure_pad_inches,
            )

        if cfg.show_image:
            plt.show()

        return True, ""

    except Exception as exc:
        return False, f"{file_path.name} -> {exc}"

    finally:
        if fig is not None:
            plt.close(fig)
        del current_map, raw_cutout, cutout_map
        gc.collect()


def _load_aia_cutout_panel(path: Path, expected_wave: int, cfg: AIAConfig) -> PanelData:
    current_map = None
    raw_cutout = None
    normalized_data = None

    try:
        current_map = sunpy.map.Map(path)
        wave_val = int(current_map.wavelength.value)
        if wave_val != expected_wave:
            raise ValueError(
                f"{path.name}: FITS wavelength {wave_val} does not match "
                f"expected band {expected_wave}"
            )

        exp_time = current_map.exposure_time.to_value(u.s)
        if exp_time <= 0:
            raise ValueError(f"{path.name}: abnormal exposure time ({exp_time}s)")

        tx1, tx2, ty1, ty2 = cfg.roi_bounds
        with propagate_with_solar_surface():
            frame = current_map.coordinate_frame
            bl = SkyCoord(Tx=tx1 * u.arcsec, Ty=ty1 * u.arcsec, frame=frame)
            tr = SkyCoord(Tx=tx2 * u.arcsec, Ty=ty2 * u.arcsec, frame=frame)
            raw_cutout = current_map.submap(bl, top_right=tr)

        normalized_data = raw_cutout.data / exp_time
        cutout_map = sunpy.map.Map(normalized_data, raw_cutout.meta)
        final_cmap, final_norm = _resolve_display_params(
            current_map, cfg.user_cmap, cfg.user_vmin, cfg.user_vmax
        )

        return PanelData(
            cutout_map=cutout_map,
            wave_val=wave_val,
            iso_time=_obs_time_isot_label(current_map, path),
            date_ymd=_obs_date_ymd(current_map, path),
            cmap=final_cmap,
            norm=final_norm,
            panel_kind="original",
            panel_label=f"{_obs_time_isot_label(current_map, path)} AIA {wave_val} original",
            is_difference=False,
        )

    finally:
        del current_map, raw_cutout, normalized_data
        gc.collect()


def _load_difference_cutout_panel(
    current_path: Path,
    reference_path: Path | None,
    wave: int,
    cfg: AIAConfig,
    method_label: str,
) -> PanelData:
    diff_map = None

    try:
        diff_map = _load_difference_map_from_paths(
            current_path,
            reference_path,
            wave,
            cfg,
        )
        cmap, norm = _resolve_difference_params(diff_map.data, wave, cfg)
        current_time = _obs_time_isot_label(diff_map, current_path)
        if reference_path is None:
            if method_label == "base":
                relation = "reference frame, zero difference"
            else:
                relation = "reference frame, no previous frame"
        elif method_label == "running":
            relation = "current - previous"
        else:
            relation = "current - base"
        panel_label = f"{current_time} AIA {wave} {method_label} diff\n{relation}"

        return PanelData(
            cutout_map=diff_map,
            wave_val=wave,
            iso_time=current_time,
            date_ymd=_obs_date_ymd(diff_map, current_path),
            cmap=cmap,
            norm=norm,
            panel_kind="difference",
            panel_label=panel_label,
            is_difference=True,
        )

    except Exception as exc:
        reference_msg = str(reference_path) if reference_path is not None else "None"
        raise RuntimeError(
            f"AIA {wave} {method_label} difference failed; "
            f"current file={current_path}; reference/base file={reference_msg}; "
            f"{exc}"
        ) from exc

    finally:
        del diff_map
        gc.collect()


def _draw_aia_panel(fig, ax, panel: PanelData, cfg: AIAConfig):
    im = panel.cutout_map.plot(
        axes=ax,
        cmap=panel.cmap,
        norm=panel.norm,
        annotate=False,
    )

    if cfg.show_limb:
        panel.cutout_map.draw_limb(
            axes=ax,
            color="black",
            linewidth=0.8,
            alpha=0.6,
        )

    if cfg.show_grid:
        overlay = panel.cutout_map.draw_grid(
            axes=ax,
            color="black",
            linewidth=0.3,
            alpha=0.3,
            linestyle="--",
            annotate=False,
        )
        _silence_heliographic_overlay(overlay)
        _purge_stonyhurst_text_artists(ax)

    if cfg.show_colorbar:
        cbar_label = "Difference intensity (DN/s)" if panel.is_difference else "DN/s"
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02).set_label(
            cbar_label, fontsize=8
        )

    return im


def _add_panel_label(
    ax,
    iso_time: str,
    wave_val: int,
    row: int,
    nrow: int,
    cfg: AIAConfig,
    panel_label: str | None = None,
) -> None:
    label_y = (
        cfg.mosaic_panel_label_y_last_row
        if (
            (cfg.mosaic_show_outer_axes or cfg.mosaic_global_outer_axes)
            and row == nrow - 1
        )
        else cfg.mosaic_panel_label_y
    )
    ax.text(
        cfg.mosaic_panel_label_x,
        label_y,
        panel_label or f"{iso_time} AIA {wave_val}",
        transform=ax.transAxes,
        fontsize=11 if panel_label and "\n" in panel_label else 13,
        va="bottom",
        ha="left",
        color="white",
        path_effects=[
            mpath_effects.withStroke(
                linewidth=2.2,
                foreground="black",
                alpha=0.65,
            )
        ],
    )


def _save_mosaic_figure(fig, save_path: Path, cfg: AIAConfig) -> None:
    if cfg.mosaic_save_tight:
        bbox_inches = "tight"
        pad_inches = cfg.mosaic_pad_inches
    else:
        bbox_inches = None
        pad_inches = 0.0

    fig.savefig(
        save_path,
        dpi=cfg.dpi,
        bbox_inches=bbox_inches,
        facecolor="white",
        pad_inches=pad_inches,
    )


def _ordered_unique(values: Sequence[int]) -> tuple[int, ...]:
    seen = set()
    ordered: list[int] = []
    for value in values:
        int_value = int(value)
        if int_value not in seen:
            seen.add(int_value)
            ordered.append(int_value)
    return tuple(ordered)


def _mosaic_slot_wavelengths(cfg: AIAConfig) -> tuple[int, ...]:
    data_path = Path(cfg.data_path)
    original_waves = cfg.multi_band_wavelengths
    if original_waves is None:
        original_waves = _discover_wavelength_dirs(data_path)

    if cfg.mosaic_difference_inline and cfg.draw_difference:
        diff_waves = cfg.difference_wavelengths or original_waves
        if cfg.draw_original:
            return _ordered_unique(tuple(original_waves) + tuple(diff_waves))
        return _ordered_unique(diff_waves)

    return tuple(original_waves)


def _mosaic_save_prefix(cfg: AIAConfig) -> str:
    if cfg.mosaic_difference_inline and cfg.draw_difference:
        if cfg.draw_original:
            return "multi_original_plus_diff"
        return "multi_diff_only"
    return "multi"


def _mosaic_save_dir(cfg: AIAConfig) -> Path:
    data_path = Path(cfg.data_path)

    if cfg.draw_difference and cfg.mosaic_difference_inline and not cfg.draw_original:
        return data_path / cfg.mosaic_difference_output_subdir

    if cfg.draw_difference and cfg.mosaic_difference_inline and cfg.draw_original:
        return data_path / cfg.mosaic_original_plus_difference_output_subdir

    return data_path / cfg.mosaic_output_subdir


def _base_difference_reference_path(wave: int, cfg: AIAConfig) -> Path:
    files = _sorted_fits_for_band(Path(cfg.data_path), wave, cfg.use_band_subdirs)
    if cfg.difference_base_index is None:
        sliced_files = _slice_band_files(files, cfg.start_idx, cfg.end_idx)
        if not sliced_files:
            raise ValueError(f"AIA {wave}: no selected files for base difference.")
        return sliced_files[0]
    if cfg.difference_base_index < 0 or cfg.difference_base_index >= len(files):
        raise ValueError(
            f"AIA {wave}: difference_base_index={cfg.difference_base_index} "
            f"is out of range for {len(files)} files."
        )
    return files[cfg.difference_base_index]


def _process_multi_band_worker(
    slot_idx: int,
    paths: tuple[Path, ...],
    wavelengths: tuple[int, ...],
    cfg: AIAConfig,
    previous_paths: tuple[Path, ...] | None = None,
) -> tuple[bool, str]:
    fig = None
    panels: list[PanelData] = []
    plt = None

    try:
        if not cfg.show_image:
            matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt

        if len(paths) != len(wavelengths):
            return False, "Internal error: paths and wavelengths lengths differ."

        tx1, tx2, ty1, ty2 = cfg.roi_bounds
        dx = abs(tx2 - tx1)
        dy = abs(ty2 - ty1)
        aspect_ratio = dy / dx if dx != 0 else 1.0

        wave_to_current_path = dict(zip(wavelengths, paths, strict=False))
        wave_to_previous_path = (
            dict(zip(wavelengths, previous_paths, strict=False))
            if previous_paths is not None
            else {}
        )

        if cfg.draw_original:
            original_waves = cfg.multi_band_wavelengths or wavelengths
            for expected_wave in original_waves:
                path = wave_to_current_path.get(expected_wave)
                if path is None:
                    raise ValueError(
                        f"Missing current slot path for AIA {expected_wave}."
                    )
                try:
                    panels.append(_load_aia_cutout_panel(path, expected_wave, cfg))
                except Exception as exc:
                    raise RuntimeError(
                        f"wave={expected_wave}, slot_idx={slot_idx}, "
                        f"current file={path}, previous/base file=None: {exc}"
                    ) from exc

        if cfg.draw_difference and cfg.mosaic_difference_inline:
            diff_waves = (
                cfg.difference_wavelengths or cfg.multi_band_wavelengths or wavelengths
            )
            for wave in diff_waves:
                current_path = wave_to_current_path.get(wave)
                if current_path is None:
                    raise ValueError(f"Missing current slot path for AIA {wave}.")

                if cfg.difference_method == "base":
                    reference_path = _base_difference_reference_path(wave, cfg)
                    if (
                        current_path == reference_path
                        and not cfg.difference_save_reference
                    ):
                        continue
                    if current_path == reference_path:
                        reference_path = None
                else:
                    reference_path = wave_to_previous_path.get(wave)
                    if reference_path is None and not cfg.difference_save_reference:
                        if slot_idx == 0:
                            continue
                        raise ValueError(f"Missing previous slot path for AIA {wave}.")

                try:
                    panels.append(
                        _load_difference_cutout_panel(
                            current_path,
                            reference_path,
                            wave,
                            cfg,
                            cfg.difference_method,
                        )
                    )
                except Exception as exc:
                    reference_msg = (
                        str(reference_path) if reference_path is not None else "None"
                    )
                    raise RuntimeError(
                        f"wave={wave}, slot_idx={slot_idx}, "
                        f"current file={current_path}, "
                        f"previous/base file={reference_msg}: {exc}"
                    ) from exc

        if not panels:
            return (
                True,
                f"multi-band slot {slot_idx}: no panels selected; skipped.",
            )

        n_panels = len(panels)
        nrow, ncol = _layout_mosaic_grid(n_panels, cfg.mosaic_ncols)
        wspace = 0.0 if cfg.mosaic_seamless else cfg.multi_band_wspace
        hspace = 0.0 if cfg.mosaic_seamless else cfg.multi_band_hspace
        date_ymd = panels[0].date_ymd if panels else ""
        fig_width, fig_height = _compute_mosaic_figure_size(
            nrow=nrow,
            ncol=ncol,
            aspect_ratio=aspect_ratio,
            cfg=cfg,
            has_title=bool(date_ymd),
        )
        _debug_mosaic_layout(
            nrow=nrow,
            ncol=ncol,
            fig_width=fig_width,
            fig_height=fig_height,
            aspect_ratio=aspect_ratio,
            cfg=cfg,
            has_title=bool(date_ymd),
        )

        fig = plt.figure(figsize=(fig_width, fig_height), facecolor="white")

        if date_ymd:
            fig.suptitle(
                date_ymd,
                fontsize=cfg.figure_suptitle_fontsize,
                y=cfg.mosaic_title_y,
                fontweight="medium",
            )

        rects = None
        gs = None
        if cfg.mosaic_manual_layout:
            rects = _compute_mosaic_axes_rects(
                nrow,
                ncol,
                cfg,
                has_title=bool(date_ymd),
            )
        else:
            gs = fig.add_gridspec(
                nrow,
                ncol,
                figure=fig,
                wspace=wspace,
                hspace=hspace,
            )

        for idx in range(n_panels):
            row, col = divmod(idx, ncol)
            panel = panels[idx]
            if cfg.mosaic_manual_layout:
                ax = fig.add_axes(rects[idx], projection=panel.cutout_map)
            else:
                ax = fig.add_subplot(gs[row, col], projection=panel.cutout_map)
            ax.set_facecolor("white")
            _draw_aia_panel(fig, ax, panel, cfg)
            _finalize_panel_aspect(ax, aspect_ratio, cfg)

            if cfg.mosaic_global_outer_axes:
                _hide_wcs_frame_for_seamless(ax)
            elif cfg.mosaic_show_outer_axes:
                _configure_mosaic_axes(ax, row, col, nrow, ncol, cfg)
                _suppress_mosaic_boundary_ticklabels(ax, row, col, nrow, ncol, cfg)
            else:
                _hide_wcs_frame_for_seamless(ax)

            _add_panel_label(
                ax,
                panel.iso_time,
                panel.wave_val,
                row,
                nrow,
                cfg,
                panel.panel_label,
            )

        for idx in range(n_panels, nrow * ncol):
            row, col = divmod(idx, ncol)
            if not cfg.mosaic_hide_empty_panels:
                if cfg.mosaic_manual_layout:
                    ax_empty = fig.add_axes(rects[idx])
                else:
                    ax_empty = fig.add_subplot(gs[row, col])
                ax_empty.set_xticks([])
                ax_empty.set_yticks([])
                ax_empty.set_facecolor("white")

        if cfg.mosaic_global_outer_axes or (
            cfg.mosaic_show_outer_axes and cfg.mosaic_outer_axislabel_once
        ):
            _add_global_mosaic_axislabels(fig, cfg)

        if not cfg.mosaic_manual_layout:
            if cfg.mosaic_show_outer_axes:
                left, bottom = cfg.mosaic_left, cfg.mosaic_bottom
            else:
                left, bottom = cfg.mosaic_left, cfg.mosaic_bottom
            top = cfg.mosaic_top if date_ymd else cfg.mosaic_top_no_title
            fig.subplots_adjust(
                left=left,
                right=cfg.mosaic_right,
                bottom=bottom,
                top=top,
                wspace=wspace,
                hspace=hspace,
            )

        if cfg.save_image:
            save_dir = _mosaic_save_dir(cfg)
            save_dir.mkdir(parents=True, exist_ok=True)
            first_time = _parse_timestr(paths[0])
            prefix = _mosaic_save_prefix(cfg)
            save_path = save_dir / f"{prefix}_{slot_idx + 1:04d}_{first_time}.png"
            _save_mosaic_figure(fig, save_path, cfg)

        if cfg.show_image:
            plt.show()

        return True, ""

    except Exception as exc:
        return False, f"multi-band slot {slot_idx} -> {exc}"

    finally:
        if fig is not None:
            plt.close(fig)
        del panels
        gc.collect()


def _difference_save_dir(data_path: Path, wave: int, cfg: AIAConfig) -> Path:
    method_dir = f"{cfg.difference_method}_difference"
    if cfg.use_band_subdirs:
        return data_path / str(wave) / cfg.difference_output_subdir / method_dir
    return data_path / cfg.difference_output_subdir / str(wave) / method_dir


# Difference image meaning:
# base difference: I_diff(t) = I(t) - I(t_base). It highlights enhancement,
# dimming, EUV waves, jets, and accumulated evolution relative to a reference
# frame, but is more sensitive to solar rotation and long-term background drift.
# running difference: I_diff(t) = I(t) - I(t - delta_t). It highlights
# short-timescale motion, fronts, and fast propagating structures, but adjacent
# positive/negative edges represent the rate of change rather than an absolute
# brightness enhancement.
def _process_difference_band_worker(
    wave: int,
    cfg: AIAConfig,
) -> tuple[bool, str]:
    if not cfg.show_image:
        matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    data_path = Path(cfg.data_path)
    success_count = 0
    error_messages: list[str] = []

    try:
        files = _sorted_fits_for_band(data_path, wave, cfg.use_band_subdirs)
        sliced_files = _slice_band_files(files, cfg.start_idx, cfg.end_idx)
        if len(sliced_files) < 2:
            return (
                False,
                f"AIA {wave}: Difference processing requires at least 2 FITS "
                f"files; found {len(sliced_files)} in selected range.",
            )

        save_dir = _difference_save_dir(data_path, wave, cfg)

        if cfg.difference_method == "base":
            if cfg.difference_base_index is None:
                base_path = sliced_files[0]
            else:
                if cfg.difference_base_index < 0 or cfg.difference_base_index >= len(
                    files
                ):
                    return (
                        False,
                        f"AIA {wave}: difference_base_index={cfg.difference_base_index} "
                        f"is out of range for {len(files)} files.",
                    )
                base_path = files[cfg.difference_base_index]

            base_time = _parse_timestr(base_path)

            for current_file in sliced_files:
                if current_file == base_path and not cfg.difference_save_reference:
                    continue
                diff_map = None
                try:
                    reference_path = None if current_file == base_path else base_path
                    diff_map = _load_difference_map_from_paths(
                        current_file,
                        reference_path,
                        wave,
                        cfg,
                    )
                    current_time = _parse_timestr(current_file)
                    save_path = save_dir / f"{current_time}_base_diff.png"
                    label = (
                        "reference frame, zero difference"
                        if reference_path is None
                        else f"{current_time} - base {base_time}"
                    )
                    _plot_difference_map(
                        diff_map,
                        wave,
                        f"{current_time} AIA {wave} base difference",
                        save_path,
                        cfg,
                        prev_or_base_label=label,
                    )
                    success_count += 1
                except Exception as exc:
                    error_messages.append(
                        f"wave={wave}, current file={current_file}, "
                        f"previous/base file={base_path}: {exc}"
                    )
                    plt.close("all")
                finally:
                    del diff_map
                    gc.collect()

        else:
            if cfg.difference_save_reference:
                diff_map = None
                try:
                    diff_map = _load_difference_map_from_paths(
                        sliced_files[0],
                        None,
                        wave,
                        cfg,
                    )
                    first_time = _parse_timestr(sliced_files[0])
                    save_path = save_dir / f"{first_time}_running_diff.png"
                    _plot_difference_map(
                        diff_map,
                        wave,
                        f"{first_time} AIA {wave} running difference",
                        save_path,
                        cfg,
                        prev_or_base_label="reference frame, no previous frame",
                    )
                    success_count += 1
                except Exception as exc:
                    error_messages.append(
                        f"wave={wave}, current file={sliced_files[0]}, "
                        f"previous/base file=None: {exc}"
                    )
                    plt.close("all")
                finally:
                    del diff_map
                    gc.collect()

            for i in range(1, len(sliced_files)):
                prev_file = sliced_files[i - 1]
                current_file = sliced_files[i]
                diff_map = None
                try:
                    diff_map = _load_difference_map_from_paths(
                        current_file,
                        prev_file,
                        wave,
                        cfg,
                    )
                    current_time = _parse_timestr(current_file)
                    prev_time = _parse_timestr(prev_file)
                    save_path = save_dir / f"{current_time}_running_diff.png"
                    _plot_difference_map(
                        diff_map,
                        wave,
                        f"{current_time} AIA {wave} running difference",
                        save_path,
                        cfg,
                        prev_or_base_label=f"{current_time} - {prev_time}",
                    )
                    success_count += 1
                except Exception as exc:
                    error_messages.append(
                        f"wave={wave}, current file={current_file}, "
                        f"previous/base file={prev_file}: {exc}"
                    )
                    plt.close("all")
                finally:
                    del diff_map
                    gc.collect()

    except Exception as exc:
        plt.close("all")
        gc.collect()
        return False, f"AIA {wave}: {exc}"

    if success_count == 0:
        detail = "; ".join(error_messages[:3])
        return False, f"AIA {wave}: no difference frames saved. {detail}"

    if error_messages:
        return (
            True,
            f"AIA {wave}: saved {success_count} difference frames; "
            f"skipped {len(error_messages)} frames. First error: {error_messages[0]}",
        )
    return True, f"AIA {wave}: saved {success_count} difference frames."


# ==============================================================================
# Batch Processing
# ==============================================================================
def _worker_count(cfg: AIAConfig) -> int:
    return cfg.max_workers or max(1, multiprocessing.cpu_count() - 1)


def _mosaic_worker_count(cfg: AIAConfig) -> int:
    if cfg.max_workers is not None:
        return cfg.max_workers
    if cfg.mosaic_max_workers is not None:
        return max(1, cfg.mosaic_max_workers)
    return max(1, min(2, multiprocessing.cpu_count() - 1))


def _run_single_batch(cfg: AIAConfig) -> None:
    selected_files = _resolve_single_files(cfg)
    if not selected_files:
        raise ValueError("No FITS files selected for single-band processing.")

    start_time = time.time()
    success_count = 0
    error_count = 0
    workers = _worker_count(cfg)

    print(f"Single-band mode: {len(selected_files)} files")
    print(f"Starting multiprocessing, allocated cores: {workers} ...")

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_process_single_worker, file_path, cfg): file_path
            for file_path in selected_files
        }
        for future in tqdm(
            as_completed(futures),
            total=len(selected_files),
            desc="Processing",
            unit="file",
        ):
            success, msg = future.result()
            if success:
                success_count += 1
            else:
                error_count += 1
                tqdm.write(f"\n  [Failed] {msg}")

    elapsed = time.time() - start_time
    print(
        f"\nSingle-band processing completed! Success: {success_count}, "
        f"Failed: {error_count}, Total time: {elapsed:.2f} seconds"
    )


def _run_mosaic_batch(cfg: AIAConfig) -> None:
    if not cfg.use_band_subdirs:
        raise ValueError(
            "Multi-band mosaic requires wavelength subdirectories "
            "(use_band_subdirs=True)."
        )

    waves = _mosaic_slot_wavelengths(cfg)

    slots = _build_multi_band_slots(cfg, waves)
    if not slots:
        raise ValueError("No time slots selected for multi-band mosaic processing.")
    if cfg.mosaic_max_slots is not None:
        slots = slots[: cfg.mosaic_max_slots]
        print(f"Limiting mosaic slots to first {len(slots)} for memory-safe preview.")

    start_time = time.time()
    success_count = 0
    error_count = 0
    workers = _mosaic_worker_count(cfg)

    print(f"Multi-band mosaic mode: slot wavelengths {waves}")
    if cfg.mosaic_difference_inline:
        print("Mosaic inline difference panels: enabled")
    print(
        f"Total {len(slots)} time slots; each slot contains {len(waves)} "
        "time-sorted band files."
    )
    print(f"Mosaic memory-safe workers: {workers}")

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _process_multi_band_worker,
                idx,
                slots[idx],
                waves,
                cfg,
                slots[idx - 1] if idx > 0 else None,
            ): idx
            for idx in range(len(slots))
        }
        for future in tqdm(
            as_completed(futures), total=len(slots), desc="Multi-band", unit="slot"
        ):
            success, msg = future.result()
            if success:
                success_count += 1
            else:
                error_count += 1
                tqdm.write(f"\n  [Failed] {msg}")

    elapsed = time.time() - start_time
    print(
        f"\nMulti-band mosaic completed! Success: {success_count}, "
        f"Failed: {error_count}, Total time: {elapsed:.2f} seconds"
    )

    if cfg.multi_band_also_save_single and cfg.draw_original:
        print("\n--- Exporting single-band images as requested ---")
        _run_single_batch(cfg)


def _run_difference_batch(cfg: AIAConfig) -> None:
    if not cfg.draw_difference:
        return

    data_path = Path(cfg.data_path)
    if cfg.difference_wavelengths is not None:
        waves = cfg.difference_wavelengths
    elif cfg.multi_band_wavelengths is not None:
        waves = cfg.multi_band_wavelengths
    else:
        waves = _discover_wavelength_dirs(data_path)

    if not waves:
        raise ValueError("No wavelengths selected for difference processing.")

    workers = cfg.max_workers or min(
        len(waves), max(1, multiprocessing.cpu_count() - 1)
    )
    print("\n--- Difference mode enabled ---")
    print(f"Difference method: {cfg.difference_method}")
    print(f"Difference wavelengths: {waves}")
    print(f"Difference norm mode: {cfg.difference_norm_mode}")
    if cfg.difference_norm_mode == "fixed":
        print(
            "Difference fixed limits: "
            f"vmin={cfg.difference_vmin}, vmax={cfg.difference_vmax}"
        )
    else:
        print(f"Difference percentile: {cfg.difference_percentile}")
    print(f"Difference workers: {workers}")

    start_time = time.time()
    success_count = 0
    error_count = 0

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_process_difference_band_worker, wave, cfg): wave
            for wave in waves
        }
        for future in tqdm(
            as_completed(futures), total=len(futures), desc="Difference", unit="band"
        ):
            success, msg = future.result()
            if success:
                success_count += 1
                if msg:
                    tqdm.write(f"  [OK] {msg}")
            else:
                error_count += 1
                tqdm.write(f"\n  [Failed] {msg}")

    elapsed = time.time() - start_time
    print(
        f"\nDifference processing completed! Success bands: {success_count}, "
        f"Failed bands: {error_count}, Total time: {elapsed:.2f} seconds"
    )


def _run_test_mode(cfg: AIAConfig) -> None:
    test_path = _resolve_test_file(cfg)

    cfg.save_image = False
    cfg.show_image = True
    cfg.multi_band_composite = False
    cfg.max_workers = 1

    print("Test mode: previewing one AIA FITS file only.")
    print("No image will be saved.")
    print(f"Selected file: {test_path}")
    print(f"ROI: {cfg.roi_bounds}")
    print(
        "Display override: "
        f"cmap={cfg.user_cmap}, vmin={cfg.user_vmin}, vmax={cfg.user_vmax}"
    )
    print(
        f"Grid={cfg.show_grid}, Limb={cfg.show_limb}, " f"Colorbar={cfg.show_colorbar}"
    )

    success, msg = _process_single_worker(test_path, cfg)
    if not success:
        raise RuntimeError(msg)


def _actual_mode(cfg: AIAConfig) -> str:
    if cfg.use_test_mode or cfg.mode == "test":
        return "test"
    if cfg.mode == "mosaic" or cfg.multi_band_composite:
        return "mosaic"
    return "single"


def process_aia_fits(cfg: AIAConfig):
    actual_mode = _actual_mode(cfg)
    _configure_matplotlib_backend(actual_mode)
    if not cfg.draw_original and not cfg.draw_difference:
        raise ValueError(
            "Nothing to draw: at least one of draw_original or "
            "draw_difference must be True."
        )

    if actual_mode == "test":
        _run_test_mode(cfg)
        if cfg.draw_difference:
            print(
                "Test mode: draw_difference=True detected; full difference batch skipped."
            )
        return

    if actual_mode == "single":
        if cfg.draw_original:
            _run_single_batch(cfg)
        if cfg.draw_difference:
            _run_difference_batch(cfg)
        return

    if actual_mode == "mosaic":
        output_mode = cfg.difference_output_mode
        if output_mode == "auto":
            output_mode = "mosaic" if cfg.draw_difference else "mosaic"

        if cfg.draw_difference and output_mode in ("mosaic", "both"):
            cfg.mosaic_difference_inline = True
            _run_mosaic_batch(cfg)

        elif not cfg.draw_difference and cfg.draw_original:
            _run_mosaic_batch(cfg)

        if cfg.draw_difference and output_mode in ("single", "both"):
            _run_difference_batch(cfg)

        return


# ==============================================================================
# CLI
# ==============================================================================
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Process exposure-normalized SDO/AIA EUV FITS files."
    )
    parser.add_argument("--root", dest="root_dir", default=None)
    parser.add_argument("--year", default=None)
    parser.add_argument("--date", default=None)
    parser.add_argument("--data-path", default=None)
    parser.add_argument("--mode", choices=("single", "mosaic", "test"), default=None)
    parser.add_argument("--test-file", default=None)
    parser.add_argument("--test-wave", type=int, default=None)
    parser.add_argument("--test-index", type=int, default=None)
    parser.add_argument("--use-test-mode", action="store_true")
    parser.add_argument(
        "--waves",
        nargs="+",
        type=int,
        default=None,
        help="AIA wavelengths to process, e.g. 94 131 171 193 211 304 335 1600.",
    )
    parser.add_argument("--start", dest="start_idx", type=int, default=None)
    parser.add_argument("--end", dest="end_idx", type=int, default=None)
    parser.add_argument(
        "--roi",
        nargs=4,
        type=float,
        metavar=("XMIN", "XMAX", "YMIN", "YMAX"),
        default=None,
    )
    parser.add_argument("--dpi", type=int, default=None)
    parser.add_argument("--workers", dest="max_workers", type=int, default=None)
    parser.add_argument("--mosaic-ncols", type=int, default=None)
    parser.add_argument("--mosaic-manual-layout", action="store_true", default=None)
    parser.add_argument(
        "--no-mosaic-manual-layout",
        dest="mosaic_manual_layout",
        action="store_false",
        default=None,
    )
    parser.add_argument("--mosaic-seamless", action="store_true", default=None)
    parser.add_argument(
        "--no-mosaic-seamless",
        dest="mosaic_seamless",
        action="store_false",
        default=None,
    )
    parser.add_argument(
        "--mosaic-show-outer-axes",
        action="store_true",
        default=None,
    )
    parser.add_argument(
        "--no-mosaic-outer-axes",
        dest="mosaic_show_outer_axes",
        action="store_false",
        default=None,
    )
    parser.add_argument("--mosaic-ticklabel-fontsize", type=int, default=None)
    parser.add_argument("--mosaic-axislabel-fontsize", type=int, default=None)
    parser.add_argument("--mosaic-save-tight", action="store_true", default=None)
    parser.add_argument(
        "--no-mosaic-save-tight",
        dest="mosaic_save_tight",
        action="store_false",
        default=None,
    )
    parser.add_argument("--mosaic-max-workers", type=int, default=None)
    parser.add_argument("--mosaic-max-slots", type=int, default=None)
    parser.add_argument("--mosaic-difference-output-subdir", default=None)
    parser.add_argument(
        "--mosaic-original-plus-difference-output-subdir",
        default=None,
    )
    parser.add_argument("--mosaic-left", type=float, default=None)
    parser.add_argument("--mosaic-right", type=float, default=None)
    parser.add_argument("--mosaic-bottom", type=float, default=None)
    parser.add_argument("--mosaic-top", type=float, default=None)
    parser.add_argument(
        "--mosaic-force-fill-axes",
        action="store_true",
        default=None,
    )
    parser.add_argument(
        "--no-mosaic-force-fill-axes",
        dest="mosaic_force_fill_axes",
        action="store_false",
        default=None,
    )
    parser.add_argument("--mosaic-debug-layout", action="store_true", default=None)
    parser.add_argument(
        "--mosaic-reduce-tick-overlap",
        action="store_true",
        default=None,
    )
    parser.add_argument(
        "--no-mosaic-reduce-tick-overlap",
        dest="mosaic_reduce_tick_overlap",
        action="store_false",
        default=None,
    )
    parser.add_argument("--mosaic-max-ticks-per-axis", type=int, default=None)
    parser.add_argument(
        "--mosaic-hide-boundary-ticklabels",
        action="store_true",
        default=None,
    )
    parser.add_argument(
        "--no-mosaic-hide-boundary-ticklabels",
        dest="mosaic_hide_boundary_ticklabels",
        action="store_false",
        default=None,
    )
    parser.add_argument(
        "--mosaic-x-tick-strategy",
        choices=("all_bottom", "first_bottom_only", "alternating_bottom"),
        default=None,
    )
    parser.add_argument(
        "--mosaic-y-tick-strategy",
        choices=("all_left", "first_left_only", "alternating_left"),
        default=None,
    )
    parser.add_argument(
        "--mosaic-outer-axislabel-once",
        action="store_true",
        default=None,
    )
    parser.add_argument(
        "--no-mosaic-outer-axislabel-once",
        dest="mosaic_outer_axislabel_once",
        action="store_false",
        default=None,
    )
    parser.add_argument("--mosaic-global-outer-axes", action="store_true", default=None)
    parser.add_argument(
        "--no-mosaic-global-outer-axes",
        dest="mosaic_global_outer_axes",
        action="store_false",
        default=None,
    )
    parser.add_argument("--draw-original", action="store_true", default=None)
    parser.add_argument(
        "--no-draw-original",
        dest="draw_original",
        action="store_false",
        default=None,
    )
    parser.add_argument(
        "--mosaic-difference-inline",
        action="store_true",
        default=None,
    )
    parser.add_argument(
        "--no-mosaic-difference-inline",
        dest="mosaic_difference_inline",
        action="store_false",
        default=None,
    )

    parser.add_argument("--draw-difference", action="store_true", default=None)
    parser.add_argument(
        "--no-draw-difference",
        dest="draw_difference",
        action="store_false",
        default=None,
    )
    parser.add_argument(
        "--difference-method",
        choices=("base", "running"),
        default=None,
    )
    parser.add_argument(
        "--difference-output-mode",
        choices=("auto", "mosaic", "single", "both"),
        default=None,
        help=(
            "Difference output target. auto: single mode saves per-band "
            "differences, mosaic mode saves mosaic differences; mosaic: save "
            "stitched mosaic; single: save per-band difference images; both: "
            "save both."
        ),
    )
    parser.add_argument(
        "--diff-waves",
        "--difference-wavelengths",
        dest="difference_wavelengths",
        nargs="+",
        type=int,
        default=None,
        help="Wavelengths for difference images only, e.g. --diff-waves 171 193 304.",
    )
    parser.add_argument(
        "--diff-base-index",
        dest="difference_base_index",
        type=int,
        default=None,
    )
    parser.add_argument(
        "--difference-norm-mode",
        choices=("auto", "fixed", "config"),
        default=None,
    )
    parser.add_argument("--difference-percentile", type=float, default=None)
    parser.add_argument("--difference-vmin", type=float, default=None)
    parser.add_argument("--difference-vmax", type=float, default=None)
    parser.add_argument(
        "--difference-vmin-by-wave",
        nargs="*",
        default=None,
        metavar="WAVE:VMIN",
        help="Per-band difference vmin, e.g. 94:-80 131:-120 171:-200.",
    )
    parser.add_argument(
        "--difference-vmax-by-wave",
        nargs="*",
        default=None,
        metavar="WAVE:VMAX",
        help="Per-band difference vmax, e.g. 94:80 131:120 171:200.",
    )
    parser.add_argument(
        "--difference-vlim-by-wave",
        nargs="*",
        default=None,
        metavar="WAVE:VLIM",
        help="Per-band symmetric difference range, e.g. 94:80 131:120 171:200.",
    )
    parser.add_argument("--difference-cmap", default=None)
    parser.add_argument(
        "--difference-cmap-mode",
        choices=("band", "diverging", "custom"),
        default=None,
    )
    parser.add_argument(
        "--warn-band-difference-cmap",
        action="store_true",
        default=None,
        help=(
            "Print a warning when difference_cmap_mode='band'. By default "
            "this warning is disabled because the user may intentionally force "
            "each AIA difference panel to use its corresponding band colormap."
        ),
    )
    parser.add_argument(
        "--difference-save-reference",
        action="store_true",
        default=None,
    )
    parser.add_argument(
        "--no-difference-save-reference",
        dest="difference_save_reference",
        action="store_false",
        default=None,
    )
    parser.add_argument(
        "--difference-colorbar",
        dest="difference_show_colorbar",
        action="store_true",
        default=None,
    )
    parser.add_argument(
        "--no-difference-colorbar",
        dest="difference_show_colorbar",
        action="store_false",
        default=None,
    )
    parser.add_argument(
        "--difference-derotate",
        dest="difference_derotate",
        action="store_true",
        default=None,
    )
    parser.add_argument(
        "--no-difference-derotate",
        dest="difference_derotate",
        action="store_false",
        default=None,
    )

    grid_group = parser.add_mutually_exclusive_group()
    grid_group.add_argument("--show-grid", dest="show_grid", action="store_true")
    grid_group.add_argument("--no-grid", dest="show_grid", action="store_false")
    parser.set_defaults(show_grid=None)

    parser.add_argument("--show-limb", action="store_true", default=None)
    parser.add_argument(
        "--colorbar", dest="show_colorbar", action="store_true", default=None
    )
    parser.add_argument(
        "--also-save-single",
        dest="multi_band_also_save_single",
        action="store_true",
        default=None,
    )
    parser.add_argument("--vmin", dest="user_vmin", type=float, default=None)
    parser.add_argument("--vmax", dest="user_vmax", type=float, default=None)
    parser.add_argument("--cmap", dest="user_cmap", default=None)
    return parser


def _set_if_provided(kwargs: dict, name: str, value) -> None:
    if value is not None:
        kwargs[name] = value


def config_from_args(args: argparse.Namespace) -> AIAConfig:
    cfg = AIAConfig()
    provided = {}
    for name in (
        "root_dir",
        "year",
        "date",
        "mode",
        "test_wave",
        "test_index",
        "start_idx",
        "end_idx",
        "dpi",
        "max_workers",
        "mosaic_ncols",
        "mosaic_manual_layout",
        "mosaic_seamless",
        "mosaic_show_outer_axes",
        "mosaic_ticklabel_fontsize",
        "mosaic_axislabel_fontsize",
        "mosaic_save_tight",
        "mosaic_max_workers",
        "mosaic_max_slots",
        "mosaic_difference_output_subdir",
        "mosaic_original_plus_difference_output_subdir",
        "mosaic_left",
        "mosaic_right",
        "mosaic_bottom",
        "mosaic_top",
        "mosaic_force_fill_axes",
        "mosaic_debug_layout",
        "mosaic_reduce_tick_overlap",
        "mosaic_max_ticks_per_axis",
        "mosaic_hide_boundary_ticklabels",
        "mosaic_x_tick_strategy",
        "mosaic_y_tick_strategy",
        "mosaic_outer_axislabel_once",
        "mosaic_global_outer_axes",
        "draw_original",
        "mosaic_difference_inline",
        "draw_difference",
        "difference_method",
        "difference_output_mode",
        "difference_base_index",
        "difference_norm_mode",
        "difference_percentile",
        "difference_vmin",
        "difference_vmax",
        "difference_vmin_by_wave",
        "difference_vmax_by_wave",
        "difference_vlim_by_wave",
        "difference_cmap",
        "difference_cmap_mode",
        "warn_band_difference_cmap",
        "difference_save_reference",
        "difference_show_colorbar",
        "difference_derotate",
        "show_grid",
        "show_limb",
        "user_vmin",
        "user_vmax",
        "user_cmap",
    ):
        _set_if_provided(provided, name, getattr(args, name))

    for name, value in provided.items():
        setattr(cfg, name, value)

    cfg.difference_vmin_by_wave = _normalize_wave_float_dict(
        cfg.difference_vmin_by_wave, "difference_vmin_by_wave"
    )
    cfg.difference_vmax_by_wave = _normalize_wave_float_dict(
        cfg.difference_vmax_by_wave, "difference_vmax_by_wave"
    )
    cfg.difference_vlim_by_wave = _normalize_wave_float_dict(
        cfg.difference_vlim_by_wave, "difference_vlim_by_wave"
    )

    if args.roi is not None:
        cfg.roi_bounds = tuple(args.roi)
    if args.waves is not None:
        cfg.multi_band_wavelengths = tuple(args.waves)
    else:
        cfg.multi_band_wavelengths = None
    if args.difference_wavelengths is not None:
        cfg.difference_wavelengths = tuple(args.difference_wavelengths)
    elif args.waves is not None:
        cfg.difference_wavelengths = tuple(args.waves)
    if args.use_test_mode:
        cfg.use_test_mode = True
    if args.test_file is not None:
        cfg.test_file = str(Path(args.test_file))

    if args.data_path is not None:
        cfg.data_path = str(Path(args.data_path))
    elif any(getattr(args, name) is not None for name in ("root_dir", "year", "date")):
        cfg.data_path = str(Path(cfg.root_dir) / cfg.year / cfg.date / "SDO" / "AIA")
    cfg.output_dir = cfg.data_path

    if cfg.mode == "test":
        cfg.use_test_mode = True
    if cfg.mode == "mosaic":
        cfg.multi_band_composite = True
    elif cfg.mode in ("single", "test"):
        cfg.multi_band_composite = False
    if args.show_colorbar is not None:
        cfg.show_colorbar = args.show_colorbar
    if args.multi_band_also_save_single is not None:
        cfg.multi_band_also_save_single = args.multi_band_also_save_single

    if args.difference_norm_mode is None and (
        args.difference_vmin is not None or args.difference_vmax is not None
    ):
        cfg.difference_norm_mode = "fixed"

    if cfg.difference_method not in ("base", "running"):
        raise ValueError(f"Invalid difference_method: {cfg.difference_method}")
    if cfg.difference_output_mode not in ("auto", "mosaic", "single", "both"):
        raise ValueError(
            f"Invalid difference_output_mode: {cfg.difference_output_mode}"
        )
    if cfg.difference_norm_mode not in ("auto", "fixed", "config"):
        raise ValueError(f"Invalid difference_norm_mode: {cfg.difference_norm_mode}")
    if cfg.difference_cmap_mode not in ("band", "diverging", "custom"):
        raise ValueError(f"Invalid difference_cmap_mode: {cfg.difference_cmap_mode}")
    if cfg.difference_wavelengths is not None:
        cfg.difference_wavelengths = tuple(int(w) for w in cfg.difference_wavelengths)
    if not cfg.draw_original and not cfg.draw_difference:
        raise ValueError(
            "Nothing to draw: at least one of draw_original or "
            "draw_difference must be True."
        )
    if cfg.mosaic_difference_inline and not cfg.draw_difference:
        warnings.warn(
            "mosaic_difference_inline=True but draw_difference=False; no "
            "difference panels will be added.",
            RuntimeWarning,
            stacklevel=2,
        )
    if cfg.draw_difference and cfg.difference_percentile <= 0:
        raise ValueError("difference_percentile must be positive.")

    return cfg


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    cli_mode = "test" if args.use_test_mode or args.mode == "test" else args.mode
    if cli_mode is not None:
        _configure_matplotlib_backend(cli_mode)

    cfg = config_from_args(args)
    actual_mode = _actual_mode(cfg)
    if cli_mode is None:
        _configure_matplotlib_backend(actual_mode)

    print("--- Starting SDO/AIA EUV FITS processing ---")
    print(f"Data path: {cfg.data_path}")
    print(f"Mode: {actual_mode}")
    print(f"Wavelengths: {cfg.multi_band_wavelengths}")
    process_aia_fits(cfg)


if __name__ == "__main__":
    main()
