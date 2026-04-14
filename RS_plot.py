# -*- coding: utf-8 -*-
"""
Created on Sun Nov 23 00:19:30 2025
@author: Severus

RS_plot.py: Process solar radio spectrogram (FITS files) and generate single-band or multi-band composite images.
Supports two operation modes: single-band mode (process FITS files one by one) and multi-band mode (synthesize multiple bands at the same time).
Supports parallel processing, automatic memory safety detection, multiple color range modes, and generates images with solar limb, coordinate grid, and directional markers.

新增功能: 左右旋数据加和（可配置加权平均）
"""

import os
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from functools import partial
import math

import matplotlib
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
from astropy.io import fits
from matplotlib.lines import Line2D
from tqdm import tqdm

# ============================================================
#   ★ All configurable parameters are centralized here, no need to dive into code to adjust ★
# ============================================================
CONFIG = {
    # ---------- Operation mode ----------
    # "single_band": single-band mode (similar to original)
    # "multi_band": multi-band synthesis mode (similar to AIA.py)
    "mode": "multi_band",  # "single_band" or "multi_band"

    # ---------- Polarization configuration ----------
    # "RR": right circular polarization
    # "LL": left circular polarization
    # "RR+LL": sum of right and left circular polarization
    "polarization": "RR",  # "RR", "LL", or "RR+LL"

    # ---------- 左右旋数据加和配置 ----------
    "combine_polarizations": False,  # 是否启用左右旋数据加和功能
    "rr_dir_suffix": "RR",           # 右旋数据目录后缀
    "ll_dir_suffix": "LL",           # 左旋数据目录后缀
    "weighted_average": False,       # 是否使用加权平均（True）或简单相加（False）
    "rr_weight": 0.5,                # 右旋权重（加权平均时使用）
    "ll_weight": 0.5,                # 左旋权重（加权平均时使用）
    "save_individual_pols": False,   # 是否同时保存单独的RR、LL图像
    "time_tolerance_seconds": 1.0,   # 时间对齐容差（秒）

    # ---------- Single-band mode configuration ----------
    # Single-file mode: if you only want to plot a single file, fill in the full absolute path here
    "single_file_path": r'<PROJECT_ROOT>\2025\20250124\RS_0447-0450\149MHz\RR\149MHz_2025124_045710_093.fits',

    # Batch single-band mode: directory containing FITS files
    "data_dir": r"<PROJECT_ROOT>\2025\20250124\RS_0447-0450\149MHz\RR",

    # File range (only effective in batch mode)
    "start_idx": 1580,          # start index (inclusive)
    "end_idx":   1700,          # end index (exclusive)

    # ---------- Multi-band mode configuration ----------
    "multi_band_root": r"<PROJECT_ROOT>\2025\20250124\RS_0447-0450",
    "multi_band_freqs": [149, 164, 190, 223, 238, 285, 300, 309, 324],
    "band_dir_pattern": "{freq}MHz/{polar}",
    "multi_band_output_subdir": "multi_band_{polar}",
    "multi_band_layout": "auto",

    # ---------- 多波段颜色范围 ----------
    # True: 每个波段使用独立的颜色范围
    # False: 所有波段使用统一的全局颜色范围
    "use_per_band_colormap": True,
    
    # ---------- 波段颜色范围计算方法 ----------
    # "percentile": 使用固定百分位数（5%-95%，范围太小时自动调整到1%-99%）
    # "fixed_percentile": 使用用户自定义的百分位数
    # "minmax": 使用最小最大值方法
    "per_band_range_method": "fixed_percentile",
    
    # 当使用fixed_percentile方法时的百分位数设置
    # 例如: [5, 95] 表示使用5%到95%的数据范围
    "per_band_percentiles": [99.9, 99.99],
    
    # 当数据范围太小时的最小对数范围阈值
    "min_log_range": 0.001,

    # ---------- 多波段子图间距配置 ----------
    "multi_band_wspace": 0.0,      # 子图之间的水平间距（0表示无间隙）
    "multi_band_hspace": 0.0,      # 子图之间的垂直间距（0表示无间隙）
    
    # ---------- 颜色条位置配置 ----------
    "colorbar_position": [0.75, 0.05, 0.22, 0.03],  # [x, y, width, height] 相对于子图内部

    # ---------- Output configuration ----------
    "output_dir": r'<PROJECT_ROOT>\2025\20250124\RS_multi_band',
    "multi_band_also_save_single": False,

    # ---------- Color range ----------
    # "auto": adjust per frame automatically
    # "global": fixed to global min/max values
    # "fixed": fixed to fixed_vmin / fixed_vmax
    "color_range_mode": "fixed",
    "fixed_vmin": 0,
    "fixed_vmax": 4*1e9,

    # ---------- Image display limits ----------
    "use_custom_lim": True,
    "custom_xlim":    (-1500, 1500),
    "custom_ylim":    (-1500, 1500),

    # ---------- Image appearance ----------
    "fig_size":            (18, 16),
    "multi_band_fig_size": (24, 24),
    "dpi":                 300,
    "cmap":                "jet",
    "scale_factor":        3.5,

    # ---------- Annotation styles ----------
    "title_fontsize":      24,
    "label_fontsize":      28,
    "tick_fontsize":       22,
    "legend_fontsize":     18,
    "annotation_fontsize": 20,

    # ---------- Parallel processing ----------
    # max_workers: number of parallel worker processes
    #   None  → program automatically calculates safe upper limit based on 【available memory / estimated per-frame memory】
    #   integer  → force specified (e.g., setting to 4 will use at most 4 cores)
    #   Note: setting too high may cause out-of-memory crashes, it is recommended to start with None for auto estimation
    "max_workers": None,

    # memory_per_worker_mb: estimated memory per worker (MB)
    #   used for automatic safe max_workers calculation, can be adjusted according to actual FITS file size
    #   None → automatically estimated from file size (×20 safety margin)
    "memory_per_worker_mb": None,

    # ---------- Output ----------
    "show_plot": False,
    "save_plot": True,
}
# ============================================================


# ──────────────────────────────────────────────────────────────
# 内存与核心数工具
# ──────────────────────────────────────────────────────────────

def _estimate_safe_workers(file_list: list, requested,
                            memory_per_worker_mb) -> int:
    """
    Estimate safe number of parallel worker processes based on available physical memory and estimated memory per worker.

    Parameters
    ----------
    file_list            : list of files to be processed (used to estimate memory per frame)
    requested            : max_workers specified by the user in CONFIG (None means auto)
    memory_per_worker_mb : estimated memory per worker (MB); None means auto estimation

    Returns
    -------
    safe number of workers (at least 1)
    """
    try:
        import psutil
        available_mb = psutil.virtual_memory().available / (1024 ** 2)
    except ImportError:
        warnings.warn(
            "psutil not found, cannot auto-estimate memory safety; please run `pip install psutil`. "
            "This run will use a conservative max_workers=2."
        )
        cpu_count = os.cpu_count() or 1
        return min(requested or 2, cpu_count)

    # 估算单帧占用内存
    if memory_per_worker_mb is None:
        if file_list:
            try:
                sample = file_list[:3]
                avg_bytes = sum(os.path.getsize(f) for f in sample) / len(sample)
                memory_per_worker_mb = avg_bytes * 20 / (1024 ** 2)
            except OSError:
                memory_per_worker_mb = 500.0
        else:
            memory_per_worker_mb = 500.0

    # Keep 20% available memory as system buffer
    usable_mb = available_mb * 0.80
    mem_safe  = max(1, int(usable_mb / memory_per_worker_mb))
    cpu_count = os.cpu_count() or 1

    if requested is not None:
        if requested > mem_safe:
            warnings.warn(
                f"[Memory warning] You set max_workers={requested}, "
                f"but according to available memory {available_mb:.0f} MB and per-worker estimate "
                f"{memory_per_worker_mb:.0f} MB, the safe upper limit is about {mem_safe}. "
                f"Automatically adjusted to {mem_safe}, please modify CONFIG['max_workers']."
            )
            return mem_safe
        return requested

    auto = min(cpu_count, mem_safe)
    print(
        f"[Auto estimation] Available memory {available_mb:.0f} MB, "
        f"per worker estimate {memory_per_worker_mb:.0f} MB, "
        f"CPU cores {cpu_count}  →  max_workers = {auto}"
    )
    return auto


# ──────────────────────────────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────────────────────────────

def get_sorted_fits(data_dir: str, start: int, end: int) -> list:
    """Return sorted list of FITS file paths within the specified range."""
    all_files = sorted(
        os.path.join(data_dir, f)
        for f in os.listdir(data_dir)
        if f.lower().endswith(".fits")
    )
    if not all_files:
        raise FileNotFoundError(f"目录 {data_dir} 中未找到 FITS 文件")
    selected = all_files[start:end]
    if not selected:
        raise ValueError(f"索引范围 [{start}, {end}) 内没有文件，请检查参数")
    return selected


def read_fits(file_path: str):
    """
    Read FITS file, return (img_data 2D ndarray, header).
    Prefer ImageHDU (hdul[1]), otherwise use primary HDU (hdul[0]).
    memmap=True speeds up sequential reading of large files, .copy() ensures data remains valid after hdul is closed.
    """
    with fits.open(file_path, memmap=True) as hdul:
        if len(hdul) > 1 and isinstance(hdul[1], fits.ImageHDU):
            data, header = hdul[1].data.copy(), hdul[1].header
        else:
            data, header = hdul[0].data.copy(), hdul[0].header

    data = np.squeeze(data)
    if data.ndim != 2:
        raise ValueError(f"数据维度异常：{data.ndim}D，需要 2D，文件：{file_path}")
    return data, header


def calc_extent(header, img_shape):
    """
    Calculate pixel coordinate extent (arcsec) from FITS header, in the format required by imshow:
    [x_min, x_max, y_max, y_min].
    If the header lacks WCS keywords, return default value [-1500, 1500, 1500, -1500].
    """
    try:
        crval1, crpix1, cdelt1 = header["CRVAL1"], header["CRPIX1"], header["CDELT1"]
        crval2, crpix2, cdelt2 = header["CRVAL2"], header["CRPIX2"], header["CDELT2"]
        x_min = crval1 + (1 - crpix1) * cdelt1
        x_max = crval1 + (img_shape[1] - crpix1) * cdelt1
        y_min = crval2 + (1 - crpix2) * cdelt2
        y_max = crval2 + (img_shape[0] - crpix2) * cdelt2
        return [x_min, x_max, y_max, y_min]
    except KeyError:
        warnings.warn("Header lacks WCS coordinate keywords, using default extent [-1500,1500]")
        return [-1500, 1500, 1500, -1500]


def _global_range_one(fp: str):
    """
    Read a single file, return (nanmin, nanmax).
    For parallel calls, exceptions are caught independently.
    """
    try:
        data, _ = read_fits(fp)
        return float(np.nanmin(data)), float(np.nanmax(data))
    except Exception as e:
        warnings.warn(f"Skipping file {fp}: {e}")
        return None


def compute_global_range(file_list: list, fixed_vmin=None, fixed_vmax=None,
                          max_workers: int = 4):
    """
    Traverse all files in parallel to compute global [vmin, vmax].
    When fixed_vmin / fixed_vmax are not None, return directly and skip statistics.

    【Optimization】Use ThreadPoolExecutor:
      - Reading FITS + nanmin/nanmax is a mix of I/O and NumPy computation,
        ThreadPool can parallelize I/O, NumPy releases GIL so computation can also be parallel,
        and it avoids process fork overhead, memory usage is lower.
    """
    if fixed_vmin is not None and fixed_vmax is not None:
        return fixed_vmin, fixed_vmax

    mins, maxs = [], []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_global_range_one, fp): fp for fp in file_list}
        with tqdm(total=len(file_list), desc="Computing global color range", unit="files") as pbar:
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    mins.append(result[0])
                    maxs.append(result[1])
                pbar.update(1)

    gmin = fixed_vmin if fixed_vmin is not None else float(np.nanmin(mins))
    gmax = fixed_vmax if fixed_vmax is not None else float(np.nanmax(maxs))
    print(f"Global color range: [{gmin:.3e}, {gmax:.3e}]")
    return gmin, gmax


def get_time_from_header(header):
    """Extract observation time from FITS header."""
    date_obs = header.get("DATE-OBS", "Unknown")
    if "TIME-OBS" in header:
        return f"{date_obs} {header['TIME-OBS']}"
    return date_obs


def get_freq_from_header(header):
    """Extract frequency from FITS header."""
    return header.get("FREQ", header.get("FREQUENCY", None))


def get_polar_from_header(header):
    """Extract polarization information from FITS header."""
    return str(header.get("POLAR", "StokesI")).strip()


def _sorted_fits_for_band(band_dir: str, start_idx: int, end_idx) -> list:
    """Get sorted list of FITS files in the specified band directory"""
    if not os.path.isdir(band_dir):
        raise ValueError(f"波段目录不存在：{band_dir}")

    all_files = sorted(
        os.path.join(band_dir, f)
        for f in os.listdir(band_dir)
        if f.lower().endswith(".fits")
    )
    if not all_files:
        raise ValueError(f"波段目录 {band_dir} 中未找到 FITS 文件")

    total    = len(all_files)
    end      = total if end_idx is None else min(end_idx, total)
    selected = all_files[start_idx:end]
    if not selected:
        raise ValueError(f"索引范围 [{start_idx}, {end}) 内没有文件")
    return selected


def _parse_time_from_filename(filename):
    """从文件名中解析时间信息，用于时间对齐检查"""
    # 示例文件名: 149MHz_2025124_045710_093.fits
    # 提取日期和时间部分
    import re
    pattern = r'_(\d+)_(\d+)'
    match = re.search(pattern, filename)
    if match:
        date_part = match.group(1)  # 2025124
        time_part = match.group(2)  # 045710
        return f"{date_part}_{time_part}"
    return None


def _check_time_alignment(rr_header, ll_header, rr_path, ll_path, tolerance_seconds=1.0):
    """检查RR和LL文件的时间对齐情况"""
    from astropy.time import Time
    
    # 尝试从header获取时间
    rr_time_str = get_time_from_header(rr_header)
    ll_time_str = get_time_from_header(ll_header)
    
    if rr_time_str == "Unknown" or ll_time_str == "Unknown":
        # 如果header中没有时间，尝试从文件名解析
        rr_time_key = _parse_time_from_filename(os.path.basename(rr_path))
        ll_time_key = _parse_time_from_filename(os.path.basename(ll_path))
        
        if rr_time_key and ll_time_key:
            return rr_time_key == ll_time_key
        else:
            # 无法检查时间，假设对齐
            return True
    
    try:
        # 尝试解析时间字符串
        rr_time = Time(rr_time_str, format='isot', scale='utc')
        ll_time = Time(ll_time_str, format='isot', scale='utc')
        
        # 计算时间差（秒）
        time_diff = abs((rr_time - ll_time).sec)
        
        if time_diff > tolerance_seconds:
            print(f"警告: RR和LL文件时间差 {time_diff:.2f} 秒超过容差 {tolerance_seconds} 秒")
            print(f"  RR文件: {rr_time_str}")
            print(f"  LL文件: {ll_time_str}")
            return False
        return True
    except Exception as e:
        # 解析失败，使用字符串比较
        print(f"时间解析失败: {e}，使用字符串比较")
        return rr_time_str == ll_time_str


def _build_multi_band_slots(cfg: dict) -> list:
    """
    Build multi-band synthesis time slots (each slot contains files of each band at the same time).

    【Optimization】Inner time slot construction changed to zip(*per_band),
    eliminating nested for loops, slightly faster and more concise code.
    """
    root         = cfg["multi_band_root"]
    freqs        = cfg["multi_band_freqs"]
    pattern      = cfg["band_dir_pattern"]
    polarization = cfg["polarization"]
    start_idx    = cfg.get("start_idx", 0)
    end_idx      = cfg.get("end_idx", None)
    
    # 检查是否启用左右旋数据加和
    combine_polarizations = cfg.get("combine_polarizations", False)
    time_tolerance = cfg.get("time_tolerance_seconds", 1.0)
    
    per_band = []
    for freq in freqs:
        if combine_polarizations and polarization == "RR+LL":
            # 左右旋数据加和模式：需要读取RR和LL两个目录的文件
            rr_dir = os.path.join(root, pattern.format(freq=freq, polar=cfg["rr_dir_suffix"]))
            ll_dir = os.path.join(root, pattern.format(freq=freq, polar=cfg["ll_dir_suffix"]))
            
            rr_files = _sorted_fits_for_band(rr_dir, start_idx, end_idx)
            ll_files = _sorted_fits_for_band(ll_dir, start_idx, end_idx)
            
            # 检查两个偏振的文件数量是否一致
            if len(rr_files) != len(ll_files):
                raise ValueError(f"频率 {freq}MHz: RR和LL文件数量不一致 (RR={len(rr_files)}, LL={len(ll_files)})")
            
            # 检查时间对齐
            misaligned_count = 0
            for rr_path, ll_path in zip(rr_files, ll_files):
                try:
                    rr_header = fits.getheader(rr_path)
                    ll_header = fits.getheader(ll_path)
                    if not _check_time_alignment(rr_header, ll_header, rr_path, ll_path, time_tolerance):
                        misaligned_count += 1
                except Exception as e:
                    print(f"检查时间对齐时出错: {e}")
            
            if misaligned_count > 0:
                print(f"频率 {freq}MHz: 发现 {misaligned_count} 个时间未对齐的文件对")
            
            # 将RR和LL文件路径组成元组，以便后续同时读取
            combined_files = [(rr, ll) for rr, ll in zip(rr_files, ll_files)]
            per_band.append(combined_files)
        else:
            # 普通模式：只读取指定偏振的文件
            band_dir = os.path.join(root, pattern.format(freq=freq, polar=polarization))
            files    = _sorted_fits_for_band(band_dir, start_idx, end_idx)
            per_band.append(files)

    lengths = [len(f) for f in per_band]
    if len(set(lengths)) > 1:
        min_len  = min(lengths)
        print(f"Warning: number of files per band inconsistent, using the minimum count {min_len}")
        per_band = [f[:min_len] for f in per_band]

    # ★ 优化：zip 直接转置二维列表，替代双层 for 循环
    slots = [list(band_files) for band_files in zip(*per_band)]

    print(f"Built {len(slots)} time slots, each slot contains {len(freqs)} bands")
    print(f"Polarization: {polarization}")
    if combine_polarizations and polarization == "RR+LL":
        print("Mode: RR + LL data combination")
        if cfg.get("weighted_average", False):
            print(f"Weighted average: RR weight={cfg['rr_weight']}, LL weight={cfg['ll_weight']}")
        else:
            print("Simple summation")
    return slots


def _layout_grid(n: int):
    """Automatically calculate subplot layout"""
    if n <= 0:
        return 1, 1
    ncol = max(1, math.ceil(math.sqrt(n)))
    nrow = max(1, math.ceil(n / ncol))
    return nrow, ncol


# ──────────────────────────────────────────────────────────────
# 输出目录预创建
# ──────────────────────────────────────────────────────────────

def _precreate_single_band_dirs(files: list, output_dir: str):
    """
    Pre-create all single-band output subdirectories in the main process,
    to avoid multiple subprocesses concurrently calling os.makedirs and competing for the file system.
    """
    for fp in files:
        try:
            with fits.open(fp, memmap=True) as hdul:
                hdr = hdul[1].header if (
                    len(hdul) > 1 and isinstance(hdul[1], fits.ImageHDU)
                ) else hdul[0].header
            freq = get_freq_from_header(hdr)
        except Exception:
            freq = None

        subdir = f"{int(freq)}MHz" if isinstance(freq, (int, float)) else "unknown"
        os.makedirs(os.path.join(output_dir, subdir), exist_ok=True)


def _precreate_multi_band_dir(output_dir: str, cfg: dict) -> str:
    """Pre-create multi-band output subdirectory, return directory path."""
    polarization        = cfg.get("polarization", "RR")
    subdir_template     = cfg.get("multi_band_output_subdir", "multi_band_{polar}")
    multi_output_subdir = subdir_template.format(polar=polarization)
    multi_output_dir    = os.path.join(output_dir, multi_output_subdir)
    os.makedirs(multi_output_dir, exist_ok=True)
    return multi_output_dir


# ──────────────────────────────────────────────────────────────
# 颜色范围计算辅助函数
# ──────────────────────────────────────────────────────────────

def _calculate_range(data: np.ndarray, cfg: dict, is_global: bool = False) -> tuple:
    """
    计算数据范围。
    
    参数:
    ----------
    data : np.ndarray
        输入数据（通常是对数化后的数据）
    cfg : dict
        配置字典
    is_global : bool
        是否为全局范围计算
    
    返回:
    -------
    tuple : (vmin, vmax)
    """
    method = cfg.get("per_band_range_method", "fixed_percentile")
    min_log_range = cfg.get("min_log_range", 0.5)
    
    if len(data) == 0:
        return 0, 1
    
    if method == "percentile":
        # 使用5%和95%分位数
        low = np.percentile(data, 5)
        high = np.percentile(data, 95)
        
        # 如果范围太小，使用1%和99%分位数
        if high - low < min_log_range:
            low = np.percentile(data, 1)
            high = np.percentile(data, 99)
            
    elif method == "fixed_percentile":
        # 使用用户自定义的百分位数
        percentiles = cfg.get("per_band_percentiles", [66, 95])
        if len(percentiles) == 2:
            low = np.percentile(data, percentiles[0])
            high = np.percentile(data, percentiles[1])
        else:
            # 如果配置错误，使用默认值
            low = np.percentile(data, 5)
            high = np.percentile(data, 95)
            
        # 如果范围太小，给出警告但保持用户设置
        if high - low < min_log_range:
            warnings.warn(f"颜色范围过小 ({high - low:.3f})，考虑调整百分位数设置。")
            
    elif method == "minmax":
        # 使用最小最大值方法
        low = np.min(data)
        high = np.max(data)
        
        # 如果范围太小，给出警告
        if high - low < min_log_range:
            warnings.warn(f"颜色范围过小 ({high - low:.3f})，考虑使用百分位数方法。")
    else:
        # 默认使用5%和95%分位数
        low = np.percentile(data, 5)
        high = np.percentile(data, 95)
        
        if high - low < min_log_range:
            low = np.percentile(data, 1)
            high = np.percentile(data, 99)
    
    return low, high


def _calculate_per_band_ranges(all_log_data: list, cfg: dict) -> tuple:
    """
    为每个波段计算合适的对数数据范围。
    
    参数:
    ----------
    all_log_data : list
        所有波段的对数数据列表
    cfg : dict
        配置字典
    
    返回:
    -------
    tuple : (band_vmins, band_vmaxs)
    """
    band_vmins = []
    band_vmaxs = []
    
    for idx, log_data in enumerate(all_log_data):
        valid_data = log_data[~np.isnan(log_data)]
        if len(valid_data) > 0:
            # 使用配置的方法计算范围
            vmin_band, vmax_band = _calculate_range(valid_data, cfg, is_global=False)
            band_vmins.append(vmin_band)
            band_vmaxs.append(vmax_band)
        else:
            # 如果没有有效数据，使用默认范围
            band_vmins.append(0)
            band_vmaxs.append(1)
    
    return band_vmins, band_vmaxs


# ──────────────────────────────────────────────────────────────
# 核心绘图函数（在子进程中执行）
# ──────────────────────────────────────────────────────────────

def _combine_polarization_data(rr_data, ll_data, cfg):
    """组合RR和LL数据（加权平均或简单相加）"""
    weighted = cfg.get("weighted_average", False)
    
    if weighted:
        rr_weight = cfg.get("rr_weight", 0.5)
        ll_weight = cfg.get("ll_weight", 0.5)
        combined_data = rr_data * rr_weight + ll_data * ll_weight
    else:
        combined_data = rr_data + ll_data
    
    return combined_data


def plot_single_band(file_path: str, output_dir: str, cfg: dict,
                     vmin=None, vmax=None) -> str:
    """
    Process and plot a single-band FITS file, save as PNG image.

    Note: Output directories have been pre-created by the main process, just concatenate paths here, no need to call os.makedirs.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    import matplotlib.patches as patches

    # 检查是否启用左右旋数据加和
    combine_polarizations = cfg.get("combine_polarizations", False)
    
    if combine_polarizations:
        # 获取对应的左旋/右旋文件路径
        base_dir = os.path.dirname(os.path.dirname(file_path))  # 获取频率目录
        file_name = os.path.basename(file_path)
        
        # 根据当前文件路径判断是RR还是LL
        if cfg["rr_dir_suffix"] in file_path:
            # 当前是RR文件，查找对应的LL文件
            rr_path = file_path
            ll_path = os.path.join(base_dir, cfg["ll_dir_suffix"], file_name)
            current_pol = "RR"
        elif cfg["ll_dir_suffix"] in file_path:
            # 当前是LL文件，查找对应的RR文件
            ll_path = file_path
            rr_path = os.path.join(base_dir, cfg["rr_dir_suffix"], file_name)
            current_pol = "LL"
        else:
            # 无法确定偏振，使用单个文件
            img_data, header = read_fits(file_path)
            rr_data, ll_data = None, None
            current_pol = get_polar_from_header(header)
    
    if combine_polarizations and 'rr_path' in locals() and 'll_path' in locals():
        # 读取两个偏振的数据并组合
        try:
            rr_data, rr_header = read_fits(rr_path)
            ll_data, ll_header = read_fits(ll_path)
            
            # 检查时间对齐
            time_tolerance = cfg.get("time_tolerance_seconds", 1.0)
            if not _check_time_alignment(rr_header, ll_header, rr_path, ll_path, time_tolerance):
                warnings.warn(f"RR和LL文件时间未对齐: {rr_path} vs {ll_path}")
            
            # 数据组合（加权平均或简单相加）
            img_data = _combine_polarization_data(rr_data, ll_data, cfg)
            header = rr_header  # 使用RR文件的头文件
            polar_display = "RR+LL"
            
            # 如果需要保存单独的偏振图像
            save_individual = cfg.get("save_individual_pols", False)
            if save_individual:
                # 保存单独的RR图像
                rr_polar_display = "RR"
                rr_out_path = _save_single_pol_image(rr_data, rr_header, output_dir, cfg, 
                                                     vmin, vmax, rr_polar_display, file_name)
                # 保存单独的LL图像
                ll_polar_display = "LL"
                ll_out_path = _save_single_pol_image(ll_data, ll_header, output_dir, cfg,
                                                     vmin, vmax, ll_polar_display, file_name)
            
        except FileNotFoundError as e:
            warnings.warn(f"无法找到对应的偏振文件: {e}，使用单个文件")
            if current_pol == "RR" and rr_data is not None:
                img_data, header = rr_data, rr_header
                polar_display = "RR"
            elif current_pol == "LL" and ll_data is not None:
                img_data, header = ll_data, ll_header
                polar_display = "LL"
            else:
                img_data, header = read_fits(file_path)
                polar_display = get_polar_from_header(header)
    else:
        polar_display = get_polar_from_header(header)
    
    extent           = calc_extent(header, img_data.shape)

    rsun_obs  = header.get("RSUN_OBS", 960.0)
    freq      = get_freq_from_header(header) or "Unknown"
    time_str  = get_time_from_header(header)
    file_name = os.path.basename(file_path)
    
    # 将偏振显示名称
    if polar_display == "RR":
        polar_display = "Right Circular (RR)"
    elif polar_display == "LL":
        polar_display = "Left Circular (LL)"
    elif polar_display == "RR+LL":
        if cfg.get("weighted_average", False):
            rr_weight = cfg.get("rr_weight", 0.5)
            ll_weight = cfg.get("ll_weight", 0.5)
            polar_display = f"RR+LL Combined (weighted: RR={rr_weight}, LL={ll_weight})"
        else:
            polar_display = "RR+LL Combined (sum)"
        
    title     = f"{file_name}   {freq} MHz  {polar_display}   {time_str}"

    fig, ax = plt.subplots(figsize=cfg["fig_size"])

    im_kwargs = dict(extent=extent, origin="upper",
                     cmap=cfg["cmap"], aspect="equal")
    if vmin is not None:
        im_kwargs["vmin"] = vmin
    if vmax is not None:
        im_kwargs["vmax"] = vmax

    im   = ax.imshow(img_data, **im_kwargs)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=cfg["tick_fontsize"] - 4, colors = 'y')

    ax.set_title(title, fontsize=cfg["title_fontsize"], fontweight="bold", pad=20)
    ax.set_xlabel("x (arcsec)", fontsize=cfg["label_fontsize"])
    ax.set_ylabel("y (arcsec)", fontsize=cfg["label_fontsize"])
    ax.tick_params(axis="both", which="major", labelsize=cfg["tick_fontsize"], colors = 'y')

    ax.add_patch(patches.Circle(
        (0, 0), radius=rsun_obs,
        edgecolor="white", facecolor="none", linewidth=3,
    ))

    half = rsun_obs
    ax.add_line(plt.Line2D([-half, half], [0, 0],
                            color="cyan", lw=1.5, linestyle="--", alpha=0.8))
    ax.add_line(plt.Line2D([0, 0], [-half, half],
                            color="cyan", lw=1.5, linestyle="--", alpha=0.8))

    offset_inner = rsun_obs + 50
    offset_text  = rsun_obs + 150
    arrow_props  = dict(arrowstyle="->", color="yellow", lw=2)
    fs = cfg["annotation_fontsize"]
    ax.annotate("N", xy=(0, offset_inner), xytext=(0, offset_text),
                ha="center", va="bottom", fontsize=fs, color="yellow",
                arrowprops=arrow_props)
    ax.annotate("E", xy=(offset_inner, 0), xytext=(offset_text, 0),
                ha="left", va="center", fontsize=fs, color="yellow",
                arrowprops=arrow_props)

    if cfg.get("use_custom_lim", False):
        ax.set_xlim(cfg["custom_xlim"])
        ax.set_ylim(cfg["custom_ylim"])
    else:
        sf = cfg["scale_factor"]
        ax.set_xlim(-rsun_obs * sf, rsun_obs * sf)
        ax.set_ylim(-rsun_obs * sf, rsun_obs * sf)

    ax.grid(True, alpha=0.3, linestyle=":", color="gray")
    ax.legend(handles=[
        Line2D([0], [0], color="white", lw=3,
               label=f'Solar Limb (R={rsun_obs:.0f}")'),
        Line2D([0], [0], color="cyan", lw=1.5, linestyle="--",
               label="Solar Grid"),
    ], loc="upper right", fontsize=cfg["legend_fontsize"])

    plt.tight_layout()

    # ★ 优化：输出目录已预创建，直接拼接路径
    subdir   = f"{int(freq)}MHz" if isinstance(freq, (int, float)) else "unknown"
    out_path = os.path.join(output_dir, subdir,
                            f"{os.path.splitext(file_name)[0]}.png")

    if cfg["save_plot"]:
        plt.savefig(out_path, dpi=cfg["dpi"], bbox_inches="tight")

    if cfg["show_plot"] and cfg.get("_interactive", False):
        plt.show()

    plt.close(fig)
    return out_path


def _save_single_pol_image(img_data, header, output_dir, cfg, vmin, vmax, polar_display, base_filename):
    """保存单独的偏振图像"""
    import matplotlib.pyplot as plt
    
    extent = calc_extent(header, img_data.shape)
    rsun_obs = header.get("RSUN_OBS", 960.0)
    freq = get_freq_from_header(header) or "Unknown"
    time_str = get_time_from_header(header)
    
    # 修改文件名以包含偏振信息
    filename_no_ext = os.path.splitext(base_filename)[0]
    new_filename = f"{filename_no_ext}_{polar_display}.png"
    
    # 创建子目录
    subdir = f"{int(freq)}MHz_{polar_display}" if isinstance(freq, (int, float)) else f"unknown_{polar_display}"
    pol_output_dir = os.path.join(output_dir, "individual_pols", subdir)
    os.makedirs(pol_output_dir, exist_ok=True)
    
    # 创建图像
    fig, ax = plt.subplots(figsize=cfg["fig_size"])
    
    im_kwargs = dict(extent=extent, origin="upper",
                     cmap=cfg["cmap"], aspect="equal")
    if vmin is not None:
        im_kwargs["vmin"] = vmin
    if vmax is not None:
        im_kwargs["vmax"] = vmax
    
    im = ax.imshow(img_data, **im_kwargs)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=cfg["tick_fontsize"] - 4, colors='y')
    
    title = f"{base_filename}   {freq} MHz  {polar_display}   {time_str}"
    ax.set_title(title, fontsize=cfg["title_fontsize"] - 4, fontweight="bold", pad=20)
    ax.set_xlabel("x (arcsec)", fontsize=cfg["label_fontsize"] - 4)
    ax.set_ylabel("y (arcsec)", fontsize=cfg["label_fontsize"] - 4)
    ax.tick_params(axis="both", which="major", labelsize=cfg["tick_fontsize"] - 4, colors='y')
    
    # 添加太阳轮廓
    ax.add_patch(patches.Circle(
        (0, 0), radius=rsun_obs,
        edgecolor="white", facecolor="none", linewidth=2,
    ))
    
    plt.tight_layout()
    out_path = os.path.join(pol_output_dir, new_filename)
    plt.savefig(out_path, dpi=cfg["dpi"] - 50, bbox_inches="tight")
    plt.close(fig)
    
    return out_path


def plot_multi_band_slot(slot_idx: int, slot_files: list, output_dir: str,
                         cfg: dict, vmin=None, vmax=None) -> str:
    """
    Process and plot multi-band composite image (all bands in one time slot).

    Note: Output directories have been pre-created by the main process, just concatenate paths here.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches

    all_data    = []
    all_headers = []
    all_extents = []
    band_info   = []
    
    # 存储每个波段的对数化数据
    all_log_data = []
    
    # 检查是否启用左右旋数据加和
    combine_polarizations = cfg.get("combine_polarizations", False)
    polarization = cfg.get("polarization", "RR")
    time_tolerance = cfg.get("time_tolerance_seconds", 1.0)
    
    # 如果需要保存单独的偏振图像，创建存储路径
    save_individual = cfg.get("save_individual_pols", False)
    individual_outputs = []

    for file_item in slot_files:
        if combine_polarizations and polarization == "RR+LL" and isinstance(file_item, tuple):
            # 左右旋数据加和模式：file_item是(RR文件路径, LL文件路径)的元组
            rr_path, ll_path = file_item
            
            # 读取两个偏振的数据
            rr_data, rr_header = read_fits(rr_path)
            ll_data, ll_header = read_fits(ll_path)
            
            # 检查时间对齐
            if not _check_time_alignment(rr_header, ll_header, rr_path, ll_path, time_tolerance):
                warnings.warn(f"RR和LL文件时间未对齐: {rr_path} vs {ll_path}")
            
            # 数据组合（加权平均或简单相加）
            img_data = _combine_polarization_data(rr_data, ll_data, cfg)
            header = rr_header  # 使用RR文件的头文件
            polar_display = "RR+LL"
            
            # 如果需要保存单独的偏振图像
            if save_individual:
                freq = get_freq_from_header(rr_header) or "Unknown"
                time_str = get_time_from_header(rr_header)
                base_filename = f"slot_{slot_idx:04d}_freq_{freq}MHz"
                
                # 保存RR图像
                rr_out = _save_single_pol_image(rr_data, rr_header, output_dir, cfg, 
                                                vmin, vmax, "RR", base_filename)
                # 保存LL图像
                ll_out = _save_single_pol_image(ll_data, ll_header, output_dir, cfg,
                                                vmin, vmax, "LL", base_filename)
                individual_outputs.extend([rr_out, ll_out])
            
        else:
            # 普通模式：file_item是单个文件路径
            img_data, header = read_fits(file_item)
            polar_display = get_polar_from_header(header)
        
        all_data.append(img_data)
        all_headers.append(header)
        all_extents.append(calc_extent(header, img_data.shape))
        band_info.append((
            get_freq_from_header(header) or "Unknown",
            polar_display,
            get_time_from_header(header),
        ))
        
        # 对数化处理：将数据转换为对数坐标，安全处理非正值
        mask = img_data > 0
        log_data = np.full_like(img_data, np.nan, dtype=np.float64)
        log_data[mask] = np.log10(img_data[mask])
        all_log_data.append(log_data)

    n_bands = len(slot_files)
    if cfg["multi_band_layout"] == "auto":
        nrow, ncol = _layout_grid(n_bands)
    else:
        nrow, ncol = cfg["multi_band_layout"]

    fig, axes = plt.subplots(nrow, ncol, figsize=cfg["multi_band_fig_size"])
    
    # 使用用户配置的子图间距
    wspace = cfg.get("multi_band_wspace", 0.0)
    hspace = cfg.get("multi_band_hspace", 0.0)
    plt.subplots_adjust(wspace=wspace, hspace=hspace, left=0.05, right=0.95, top=0.95, bottom=0.05)
    
    # 将axes转换为二维数组以便索引
    if nrow == 1 and ncol == 1:
        axes = np.array([[axes]])
    elif nrow == 1:
        axes = axes.reshape(1, -1)
    elif ncol == 1:
        axes = axes.reshape(-1, 1)
    else:
        axes = axes.reshape(nrow, ncol)

    # 为每个波段计算合适的对数数据范围
    band_vmins, band_vmaxs = _calculate_per_band_ranges(all_log_data, cfg)
    
    # 计算整体对数范围（用于统一颜色条时）
    all_valid = np.concatenate([d[~np.isnan(d)] for d in all_log_data if len(d[~np.isnan(d)]) > 0])
    if len(all_valid) > 0:
        global_low, global_high = _calculate_range(all_valid, cfg, is_global=True)
    else:
        global_low, global_high = 0, 1

    for idx in range(n_bands):
        row = idx // ncol
        col = idx % ncol
        ax = axes[row, col]
        
        freq, polar, _ = band_info[idx]
        rsun_obs = all_headers[idx].get("RSUN_OBS", 960.0)
        
        # 使用对数化数据
        log_data = all_log_data[idx]
        
        current_cmap = plt.get_cmap(cfg["cmap"]).copy()
        current_cmap.set_bad(color='#000080')
        
        im_kwargs = dict(extent=all_extents[idx], origin="upper",
                         cmap=current_cmap, aspect="equal")
        
        # 为每个波段设置合适的颜色范围
        if cfg.get("use_per_band_colormap", True):
            # 使用每个波段自己的合适范围
            vmin_band, vmax_band = band_vmins[idx], band_vmaxs[idx]
        else:
            # 使用全局范围
            vmin_band, vmax_band = global_low, global_high
            
        im_kwargs["vmin"] = vmin_band
        im_kwargs["vmax"] = vmax_band

        im = ax.imshow(log_data, **im_kwargs)

        ax.add_patch(patches.Circle(
            (0, 0), radius=rsun_obs,
            edgecolor="white", facecolor="none", linewidth=1.5,
        ))

        if cfg.get("use_custom_lim", False):
            ax.set_xlim(cfg["custom_xlim"])
            ax.set_ylim(cfg["custom_ylim"])
        else:
            sf = cfg["scale_factor"]
            ax.set_xlim(-rsun_obs * sf, rsun_obs * sf)
            ax.set_ylim(-rsun_obs * sf, rsun_obs * sf)

        # 在子图中标注频率（替代标题）
        freq_text = f"{freq} MHz"
        ax.text(0.02, 0.98, freq_text, transform=ax.transAxes,
                fontsize=cfg["title_fontsize"] - 6, fontweight="bold",
                color="white", verticalalignment="top",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.7, edgecolor="white"))

        # 坐标轴标签设置：只在最左边一列显示Y轴，最下面一行显示X轴
        if col == 0:  # 最左边一列
            ax.set_ylabel("y (arcsec)", fontsize=cfg["label_fontsize"] - 6)
        else:
            ax.set_ylabel("")
            ax.tick_params(axis='y', which='both', left=False, labelleft=False, colors = 'y')
            
        if row == nrow - 1:  # 最下面一行
            ax.set_xlabel("x (arcsec)", fontsize=cfg["label_fontsize"] - 6)
        else:
            ax.set_xlabel("")
            ax.tick_params(axis='x', which='both', bottom=False, labelbottom=False, colors = 'y')

        # 调整刻度标签大小
        ax.tick_params(axis="both", which="major",
                       labelsize=cfg["tick_fontsize"] - 8, colors = 'y')

        # 为每个子图添加嵌入式颜色条，使用用户配置的位置
        colorbar_pos = cfg.get("colorbar_position", [0.75, 0.05, 0.22, 0.03])
        
        # 确保颜色条完全在子图内部
        cax = ax.inset_axes(colorbar_pos)  # [x, y, width, height] 相对于子图内部
        cbar = fig.colorbar(im, cax=cax, orientation='horizontal')
        cbar.ax.tick_params(labelsize=cfg["tick_fontsize"] - 10, colors='y')
        # cbar.set_label('log10(I)', fontsize=cfg["tick_fontsize"] - 10, colors='y')
        cbar.ax.locator_params(nbins=3)

    # 隐藏多余的子图
    for idx in range(n_bands, nrow * ncol):
        row = idx // ncol
        col = idx % ncol
        axes[row, col].axis("off")

    main_time = band_info[0][2] if band_info else "Unknown"
    
    # 确定显示名称
    if combine_polarizations and polarization == "RR+LL":
        if cfg.get("weighted_average", False):
            rr_weight = cfg.get("rr_weight", 0.5)
            ll_weight = cfg.get("ll_weight", 0.5)
            polar_display = f"RR+LL Combined (weighted: RR={rr_weight}, LL={ll_weight})"
        else:
            polar_display = "RR+LL Combined (sum)"
    elif polarization == "RR":
        polar_display = "Right Circular"
    elif polarization == "LL":
        polar_display = "Left Circular"
    else:
        polar_display = polarization
        
    # 添加总标题
    fig.suptitle(f"Multi-band Radio Synthesis ({polar_display}) - {main_time}",
                 fontsize=cfg["title_fontsize"] + 2, fontweight="bold", y=0.98)

    # 进一步调整布局
    # plt.tight_layout(rect=[0, 0, 1, 0.96])

    # ★ 优化：输出目录已预创建，直接拼接文件名
    polarization        = cfg.get("polarization", "RR")
    subdir_template     = cfg.get("multi_band_output_subdir", "multi_band_{polar}")
    multi_output_subdir = subdir_template.format(polar=polarization)
    output_path         = os.path.join(output_dir, multi_output_subdir,
                                       f"multi_band_slot_{slot_idx:04d}.png")

    if cfg["save_plot"]:
        plt.savefig(output_path, dpi=cfg["dpi"], bbox_inches="tight")

    if cfg["show_plot"] and cfg.get("_interactive", False):
        plt.show()

    plt.close(fig)
    
    # 如果保存了单独的偏振图像，打印信息
    if save_individual and individual_outputs:
        print(f"Slot {slot_idx}: Saved {len(individual_outputs)} individual polarization images")
    
    return output_path


# ──────────────────────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────────────────────

def _migrate_config(cfg):
    """Backward compatibility: migrate old use_fixed_cbar configuration to new color_range_mode"""
    if "use_fixed_cbar" in cfg:
        use_fixed_cbar = cfg.pop("use_fixed_cbar")
        if use_fixed_cbar:
            if cfg.get("fixed_vmin") is not None or cfg.get("fixed_vmax") is not None:
                cfg["color_range_mode"] = "fixed"
            else:
                cfg["color_range_mode"] = "global"
        else:
            cfg["color_range_mode"] = "auto"
        print(f"Migrated old config: use_fixed_cbar={use_fixed_cbar} -> "
              f"color_range_mode={cfg['color_range_mode']}")
    return cfg


def main():
    """
    Main function: process single-band or multi-band radio data according to configuration mode, parallel plotting and saving results.
    """
    cfg  = CONFIG
    cfg  = _migrate_config(cfg)
    mode = cfg.get("mode", "single_band")
    
    # 检查左右旋数据加和配置
    combine_polarizations = cfg.get("combine_polarizations", False)
    polarization = cfg.get("polarization", "RR")
    
    if combine_polarizations and polarization != "RR+LL":
        print(f"Warning: combine_polarizations is True but polarization is '{polarization}'")
        print("Setting polarization to 'RR+LL' for combined mode")
        cfg["polarization"] = "RR+LL"
    
    if combine_polarizations:
        print("=" * 60)
        print("左右旋数据加和功能已启用")
        print(f"  RR目录后缀: {cfg['rr_dir_suffix']}")
        print(f"  LL目录后缀: {cfg['ll_dir_suffix']}")
        print(f"  时间对齐容差: {cfg.get('time_tolerance_seconds', 1.0)} 秒")
        
        if cfg.get("weighted_average", False):
            print(f"  组合方式: 加权平均 (RR权重={cfg.get('rr_weight', 0.5)}, LL权重={cfg.get('ll_weight', 0.5)})")
        else:
            print("  组合方式: 简单相加")
        
        if cfg.get("save_individual_pols", False):
            print("  同时保存单独的RR、LL图像: 是")
        else:
            print("  同时保存单独的RR、LL图像: 否")
        print("=" * 60)

    # ── 1. 根据模式决定文件列表 / 时间槽 ──────────────────────
    if mode == "multi_band":
        print("Operation mode: multi-band synthesis")
        slots      = _build_multi_band_slots(cfg)
        output_dir = cfg.get("output_dir") or os.path.join(cfg["multi_band_root"], "plot")
        os.makedirs(output_dir, exist_ok=True)
        print(f"Output directory: {output_dir}")

        if cfg.get("multi_band_also_save_single", False):
            print("Note: multi_band_also_save_single=True, will also save single-band images")

    else:
        print("Operation mode: single-band")
        single_file = cfg.get("single_file_path")

        if single_file and os.path.isfile(single_file):
            files      = [single_file]
            output_dir = cfg.get("output_dir") or os.path.join(
                os.path.dirname(single_file), "plot")
            os.makedirs(output_dir, exist_ok=True)
            print(f"Single-file mode, processing only: {single_file}")
        else:
            if single_file:
                print(f"[Warning] Specified single file does not exist: {single_file}. Falling back to batch processing mode.")
            
            # 根据是否启用左右旋数据加和来决定数据目录
            if combine_polarizations and polarization == "RR+LL":
                # 左右旋加和模式：需要从RR目录获取文件列表
                data_dir = cfg["data_dir"]
                # 检查是否是RR目录，如果不是则尝试转换为RR目录
                if cfg["rr_dir_suffix"] not in data_dir and cfg["ll_dir_suffix"] not in data_dir:
                    # 假设数据目录是频率目录，需要添加RR子目录
                    data_dir = os.path.join(data_dir, cfg["rr_dir_suffix"])
                elif cfg["ll_dir_suffix"] in data_dir:
                    # 如果是LL目录，转换为RR目录
                    data_dir = data_dir.replace(cfg["ll_dir_suffix"], cfg["rr_dir_suffix"])
                
                if not os.path.exists(data_dir):
                    raise FileNotFoundError(f"找不到RR数据目录: {data_dir}")
                    
                print(f"Single-band mode with RR+LL summation, using RR directory: {data_dir}")
            else:
                data_dir = cfg["data_dir"]
                print(f"Single-band mode, polarization: {polarization}")
                
            output_dir = cfg.get("output_dir") or os.path.join(data_dir, "plot")
            os.makedirs(output_dir, exist_ok=True)
            files = get_sorted_fits(data_dir, cfg["start_idx"], cfg["end_idx"])
            print(f"Selected {len(files)} FITS files, output directory: {output_dir}")

    # ── 2. 确定运行模式（交互 / 并行） ─────────────────────────
    if cfg["show_plot"]:
        for backend in ("TkAgg", "Qt5Agg", "MacOSX", "WXAgg"):
            try:
                matplotlib.use(backend)
                break
            except Exception:
                continue
        cfg          = {**cfg, "_interactive": True}
        use_parallel = False
        print(f"show_plot=True: interactive backend {matplotlib.get_backend()}, single‑process frame‑by‑frame display")
    else:
        matplotlib.use("Agg")
        cfg          = {**cfg, "_interactive": False}
        use_parallel = True

    # ── 3. 安全 max_workers ─────────────────────────────────────
    sample_files = (
        [slot[0] for slot in slots[:5]] if mode == "multi_band" else files[:5]
    )
    safe_workers = _estimate_safe_workers(
        file_list            = sample_files,
        requested            = cfg.get("max_workers"),
        memory_per_worker_mb = cfg.get("memory_per_worker_mb"),
    )

    # ── 4. 处理色彩范围 ─────────────────────────────────────────
    vmin = vmax = None
    color_range_mode = cfg.get("color_range_mode", "auto")

    if color_range_mode == "auto":
        print("Color range mode: auto adjust per frame")

    elif color_range_mode == "global":
        print("Color range mode: fixed to global min/max")
        all_files = [fp for slot in slots for fp in slot] \
                    if mode == "multi_band" else files
        # ★ parallel statistics, reuse safe_workers
        vmin, vmax = compute_global_range(
            all_files, None, None, max_workers=safe_workers)

    elif color_range_mode == "fixed":
        fixed_vmin = cfg.get("fixed_vmin")
        fixed_vmax = cfg.get("fixed_vmax")
        if fixed_vmin is not None or fixed_vmax is not None:
            print(f"Color range mode: fixed values [{fixed_vmin:.3e}, {fixed_vmax:.3e}]")
            vmin, vmax = fixed_vmin, fixed_vmax
        else:
            print("Warning: color_range_mode='fixed' but fixed_vmin/vmax not set, fallback to auto mode")

    else:
        print(f"Warning: unknown mode '{color_range_mode}', using auto‑adjust mode")

    # ── 5. 预创建输出子目录（主进程统一完成，子进程免 makedirs）──
    if mode == "multi_band":
        _precreate_multi_band_dir(output_dir, cfg)
    else:
        _precreate_single_band_dirs(files, output_dir)

    # ── 6. 绘图（多进程批量 / 单进程交互） ──────────────────────
    t0     = time.time()
    errors = []

    if mode == "multi_band":
        if use_parallel and len(slots) > 1:
            worker    = partial(plot_multi_band_slot,
                                output_dir=output_dir, cfg=cfg, vmin=vmin, vmax=vmax)
            with ProcessPoolExecutor(max_workers=safe_workers) as executor:
                futures = {
                    executor.submit(worker, i, slot): i
                    for i, slot in enumerate(slots)
                }
                with tqdm(total=len(slots), desc="Multi‑band plotting progress", unit="slots") as pbar:
                    for future in as_completed(futures):
                        slot_idx = futures[future]
                        try:
                            future.result()
                        except Exception as e:
                            errors.append((slot_idx, str(e)))
                            tqdm.write(f"[Error] slot {slot_idx}: {e}")
                        finally:
                            pbar.update(1)
        else:
            for i, slot in enumerate(tqdm(slots, desc="Multi‑band plotting progress", unit="slots")):
                try:
                    plot_multi_band_slot(i, slot, output_dir, cfg, vmin, vmax)
                except Exception as e:
                    errors.append((i, str(e)))
                    tqdm.write(f"[Error] slot {i}: {e}")

    else:
        if use_parallel and len(files) > 1:
            worker = partial(plot_single_band,
                             output_dir=output_dir, cfg=cfg, vmin=vmin, vmax=vmax)
            with ProcessPoolExecutor(max_workers=safe_workers) as executor:
                futures = {executor.submit(worker, fp): fp for fp in files}
                with tqdm(total=len(files), desc="Plotting progress", unit="files") as pbar:
                    for future in as_completed(futures):
                        fp = futures[future]
                        try:
                            future.result()
                        except Exception as e:
                            errors.append((fp, str(e)))
                            tqdm.write(f"[Error] {os.path.basename(fp)}: {e}")
                        finally:
                            pbar.update(1)
        else:
            for fp in tqdm(files, desc="Plotting progress", unit="files"):
                try:
                    plot_single_band(fp, output_dir, cfg, vmin, vmax)
                except Exception as e:
                    errors.append((fp, str(e)))
                    tqdm.write(f"[Error] {os.path.basename(fp)}: {e}")

    # ── 7. 汇总 ─────────────────────────────────────────────────
    elapsed = time.time() - t0
    total   = len(slots) if mode == "multi_band" else len(files)
    ok      = total - len(errors)
    label   = "slots" if mode == "multi_band" else "files"
    print(f"\nDone! Success {ok} / total {total} {label}, elapsed {elapsed:.1f} sec")
    if errors:
        print(f"Failed {label} ({len(errors)} items):")
        for item, msg in errors:
            name = item if mode == "multi_band" else os.path.basename(item)
            print(f"  {name}: {msg}")


if __name__ == "__main__":
    # On Windows, multiprocessing must start main() inside this guard block
    main()
