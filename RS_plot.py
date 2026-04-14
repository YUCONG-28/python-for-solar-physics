# -*- coding: utf-8 -*-
"""
Created on Sun Nov 23 00:19:30 2025
@author: Severus

RS_plot.py: Process solar radio spectrogram (FITS files) and generate single-band or multi-band composite images.
Supports two operation modes: single-band mode (process FITS files one by one) and multi-band mode (synthesize multiple bands at the same time).
Supports parallel processing, automatic memory safety detection, multiple color range modes, and generates images with solar limb, coordinate grid, and directional markers.


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
    "polarization": "LL",  # "RR" or "LL"

    # ---------- Single-band mode configuration ----------
    # Single-file mode: if you only want to plot a single file, fill in the full absolute path here
    "single_file_path": r'<PROJECT_ROOT>\2025\20250124\RS_0447-0450\149MHz\RR\149MHz_2025124_045710_093.fits',

    # Batch single-band mode: directory containing FITS files
    "data_dir": r"<PROJECT_ROOT>\2025\20250124\RS_0447-0450\149MHz\RR",

    # File range (only effective in batch mode)
    "start_idx": 1400,          # start index (inclusive)
    "end_idx":   1900,          # end index (exclusive)

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
    "multi_band_fig_size": (24, 20),
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

    per_band = []
    for freq in freqs:
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
# 核心绘图函数（在子进程中执行）
# ──────────────────────────────────────────────────────────────

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

    img_data, header = read_fits(file_path)
    extent           = calc_extent(header, img_data.shape)

    rsun_obs  = header.get("RSUN_OBS", 960.0)
    freq      = get_freq_from_header(header) or "Unknown"
    polar     = get_polar_from_header(header)
    time_str  = get_time_from_header(header)
    file_name = os.path.basename(file_path)
    # 将偏振缩写转换为可读名称
    if polar == "RR":
        polar_display = "Right Circular (RR)"
    elif polar == "LL":
        polar_display = "Left Circular (LL)"
    else:
        polar_display = polar
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
    cbar.ax.tick_params(labelsize=cfg["tick_fontsize"] - 4)

    ax.set_title(title, fontsize=cfg["title_fontsize"], fontweight="bold", pad=20)
    ax.set_xlabel("x (arcsec)", fontsize=cfg["label_fontsize"])
    ax.set_ylabel("y (arcsec)", fontsize=cfg["label_fontsize"])
    ax.tick_params(axis="both", which="major", labelsize=cfg["tick_fontsize"])

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

    for file_path in slot_files:
        img_data, header = read_fits(file_path)
        all_data.append(img_data)
        all_headers.append(header)
        all_extents.append(calc_extent(header, img_data.shape))
        band_info.append((
            get_freq_from_header(header) or "Unknown",
            get_polar_from_header(header),
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
    
    # 减少子图之间的间隙
    plt.subplots_adjust(wspace=0.05, hspace=0.05)
    
    # 将axes转换为二维数组以便索引
    if nrow == 1 and ncol == 1:
        axes = np.array([[axes]])
    elif nrow == 1:
        axes = axes.reshape(1, -1)
    elif ncol == 1:
        axes = axes.reshape(-1, 1)
    else:
        axes = axes.reshape(nrow, ncol)

    # 为每个波段计算对数数据的最大值和最小值
    band_vmins = []
    band_vmaxs = []
    
    for idx in range(n_bands):
        log_data = all_log_data[idx]
        valid_data = log_data[~np.isnan(log_data)]
        if len(valid_data) > 0:
            # 使用数据的分位数避免极端值影响
            q1 = np.percentile(valid_data, 1)
            q99 = np.percentile(valid_data, 99)
            band_vmins.append(q1)
            band_vmaxs.append(q99)
        else:
            band_vmins.append(0)
            band_vmaxs.append(1)
    
    # 计算整体对数范围（可选，用于保持颜色条一致性）
    all_valid = np.concatenate([d[~np.isnan(d)] for d in all_log_data if len(d[~np.isnan(d)]) > 0])
    if len(all_valid) > 0:
        global_q1 = np.percentile(all_valid, 1)
        global_q99 = np.percentile(all_valid, 99)
    else:
        global_q1, global_q99 = 0, 1

    for idx in range(n_bands):
        row = idx // ncol
        col = idx % ncol
        ax = axes[row, col]
        
        freq, polar, _ = band_info[idx]
        rsun_obs = all_headers[idx].get("RSUN_OBS", 960.0)
        
        # 使用对数化数据
        log_data = all_log_data[idx]
        
        im_kwargs = dict(extent=all_extents[idx], origin="upper",
                         cmap=cfg["cmap"], aspect="equal")
        
        # 为每个波段设置独立的对数颜色范围
        if cfg.get("use_per_band_colormap", True):
            # 使用每个波段自己的范围
            vmin_band, vmax_band = band_vmins[idx], band_vmaxs[idx]
        else:
            # 使用全局范围
            vmin_band, vmax_band = global_q1, global_q99
            
        im_kwargs["vmin"] = vmin_band
        im_kwargs["vmax"] = vmax_band

        im = ax.imshow(log_data, **im_kwargs)

        ax.add_patch(patches.Circle(
            (0, 0), radius=rsun_obs,
            edgecolor="white", facecolor="none", linewidth=2,
        ))

        if cfg.get("use_custom_lim", False):
            ax.set_xlim(cfg["custom_xlim"])
            ax.set_ylim(cfg["custom_ylim"])
        else:
            sf = cfg["scale_factor"]
            ax.set_xlim(-rsun_obs * sf, rsun_obs * sf)
            ax.set_ylim(-rsun_obs * sf, rsun_obs * sf)

        # 将偏振缩写转换为可读名称
        if polar == "RR":
            polar_display = "Right Circular (RR)"
        elif polar == "LL":
            polar_display = "Left Circular (LL)"
        else:
            polar_display = polar
            
        # 添加波段频率和偏振信息
        ax.set_title(f"{freq} MHz  {polar_display}",
                     fontsize=cfg["title_fontsize"] - 4, fontweight="bold")

        # 坐标轴标签设置：只在最左边一列显示Y轴，最下面一行显示X轴
        if col == 0:  # 最左边一列
            ax.set_ylabel("y (arcsec)", fontsize=cfg["label_fontsize"] - 4)
        else:
            ax.set_ylabel("")
            ax.tick_params(axis='y', which='both', left=False, labelleft=False)
            
        if row == nrow - 1:  # 最下面一行
            ax.set_xlabel("x (arcsec)", fontsize=cfg["label_fontsize"] - 4)
        else:
            ax.set_xlabel("")
            ax.tick_params(axis='x', which='both', bottom=False, labelbottom=False)

        # 调整刻度标签大小
        ax.tick_params(axis="both", which="major",
                       labelsize=cfg["tick_fontsize"] - 6)

        # 为每个子图添加颜色条
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
        cbar.ax.tick_params(labelsize=cfg["tick_fontsize"] - 8)
        cbar.set_label('log10(Intensity)', fontsize=cfg["tick_fontsize"] - 8)

    # 隐藏多余的子图
    for idx in range(n_bands, nrow * ncol):
        row = idx // ncol
        col = idx % ncol
        axes[row, col].axis("off")

    main_time = band_info[0][2] if band_info else "Unknown"
    polarization = cfg.get("polarization", "RR")
    # 将偏振缩写转换为可读名称
    if polarization == "RR":
        polar_display = "Right Circular"
    elif polarization == "LL":
        polar_display = "Left Circular"
    else:
        polar_display = polarization
        
    # 添加总标题
    fig.suptitle(f"Multi-band Radio Synthesis ({polar_display}) - {main_time}",
                 fontsize=cfg["title_fontsize"] + 4, fontweight="bold", y=0.98)

    # 进一步调整布局
    plt.tight_layout(rect=[0, 0, 1, 0.96])

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
            polarization = cfg.get("polarization", "RR")
            data_dir     = cfg["data_dir"]
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
        if fixed_vmin is None or fixed_vmax is None:
            print("Warning: color_range_mode='fixed' but fixed_vmin/vmax not set, fallback to auto mode")
        else:
            print(f"Color range mode: fixed values [{fixed_vmin:.3e}, {fixed_vmax:.3e}]")
            vmin, vmax = fixed_vmin, fixed_vmax

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
