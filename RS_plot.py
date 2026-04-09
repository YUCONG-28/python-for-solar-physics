# -*- coding: utf-8 -*-
"""

Created on Sun Nov 23 00:19:30 2025
@author: Severus

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
#   ★ 全部可调参数集中于此，无需深入代码即可修改 ★
# ============================================================
CONFIG = {
    # ---------- 运行模式 ----------
    # "single_band": 单波段模式 (类似原版)
    # "multi_band": 多波段合成模式 (类似 AIA.py)
    "mode": "multi_band",  # "single_band" 或 "multi_band"

    # ---------- 偏振方向配置 ----------
    # "RR": 右旋圆偏振
    # "LL": 左旋圆偏振
    "polarization": "RR",  # "RR" 或 "LL"

    # ---------- 单波段模式配置 ----------
    # 单文件模式：如果只想画单个文件，请在此填写文件的完整绝对路径
    "single_file_path": r'<PROJECT_ROOT>\2025\20250124\RS_0447-0450\149MHz\RR\149MHz_2025124_045710_093.fits',

    # 单波段批量模式：FITS 文件所在目录
    "data_dir": r"<PROJECT_ROOT>\2025\20250124\RS_0447-0450\149MHz\RR",

    # 文件范围 (仅在批量模式下生效)
    "start_idx": 1,          # 起始索引（含）
    "end_idx":   None,          # 结束索引（不含）

    # ---------- 多波段模式配置 ----------
    "multi_band_root": r"<PROJECT_ROOT>\2025\20250503\20250503UT071600-072600",
    "multi_band_freqs": [149, 164, 190, 238, 285, 324],
    "band_dir_pattern": "{freq}MHz/{polar}",
    "multi_band_output_subdir": "multi_band_{polar}",
    "multi_band_layout": "auto",

    # ---------- 输出配置 ----------
    "output_dir": r'<PROJECT_ROOT>\2025\20250503\RS_multi_band',
    "multi_band_also_save_single": False,

    # ---------- 色彩范围 ----------
    # "auto": 每帧自动调整
    # "global": 固定为全局最大最小值
    # "fixed": 固定为 fixed_vmin / fixed_vmax
    "color_range_mode": "global",
    "fixed_vmin": None,
    "fixed_vmax": None,

    # ---------- 图像呈现范围 ----------
    "use_custom_lim": True,
    "custom_xlim":    (-1150, 1150),
    "custom_ylim":    (-1150, 1150),

    # ---------- 图像外观 ----------
    "fig_size":            (18, 16),
    "multi_band_fig_size": (24, 20),
    "dpi":                 300,
    "cmap":                "gist_heat",
    "scale_factor":        3.5,

    # ---------- 注记样式 ----------
    "title_fontsize":      24,
    "label_fontsize":      28,
    "tick_fontsize":       22,
    "legend_fontsize":     18,
    "annotation_fontsize": 20,

    # ---------- 并行 ----------
    # max_workers: 并行工作进程数
    #   None  → 程序自动根据【可用内存 / 单帧估算内存】计算安全上限
    #   整数  → 强制指定（如设为 4 则最多使用 4 个核心）
    #   注意：设置过大可能导致内存不足崩溃，建议先用 None 自动推算
    "max_workers": 8,

    # memory_per_worker_mb: 每个 worker 预估占用内存（MB）
    #   用于自动推算安全 max_workers，可根据实际 FITS 文件大小调整
    #   None → 自动从文件大小估算（×20 倍余量）
    "memory_per_worker_mb": None,

    # ---------- 输出 ----------
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
    根据可用物理内存和每个 worker 的预估内存开销，
    计算安全的并行进程数。

    Parameters
    ----------
    file_list            : 待处理文件列表（用于估算单帧内存）
    requested            : 用户在 CONFIG 中指定的 max_workers（None=自动）
    memory_per_worker_mb : 每个 worker 预估内存（MB）；None=自动估算

    Returns
    -------
    安全的 worker 数（至少为 1）
    """
    try:
        import psutil
        available_mb = psutil.virtual_memory().available / (1024 ** 2)
    except ImportError:
        warnings.warn(
            "未找到 psutil，无法自动估算内存安全值；建议执行 `pip install psutil`。"
            "本次使用保守值 max_workers=2。"
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

    # 保留 20% 可用内存作为系统缓冲
    usable_mb = available_mb * 0.80
    mem_safe  = max(1, int(usable_mb / memory_per_worker_mb))
    cpu_count = os.cpu_count() or 1

    if requested is not None:
        if requested > mem_safe:
            warnings.warn(
                f"[内存警告] 您设置了 max_workers={requested}，"
                f"但根据可用内存 {available_mb:.0f} MB 和单 worker 估算 "
                f"{memory_per_worker_mb:.0f} MB，安全上限约为 {mem_safe}。"
                f"已自动调整为 {mem_safe}，请在 CONFIG['max_workers'] 中修改。"
            )
            return mem_safe
        return requested

    auto = min(cpu_count, mem_safe)
    print(
        f"[自动推算] 可用内存 {available_mb:.0f} MB，"
        f"单 worker 估算 {memory_per_worker_mb:.0f} MB，"
        f"CPU 核心数 {cpu_count}  →  max_workers = {auto}"
    )
    return auto


# ──────────────────────────────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────────────────────────────

def get_sorted_fits(data_dir: str, start: int, end: int) -> list:
    """返回排序后、截取范围内的 FITS 文件路径列表。"""
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
    读取 FITS 文件，返回 (img_data 2D ndarray, header)。
    优先使用 ImageHDU（hdul[1]），否则使用主 HDU（hdul[0]）。
    memmap=True 加速大文件顺序读取，.copy() 确保关闭 hdul 后数据仍有效。
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
    从 FITS 头文件计算像素坐标 extent（角秒），格式为 imshow 要求的
    [x_min, x_max, y_max, y_min]。
    若头文件缺少 WCS 关键字则返回默认值 [-1500, 1500, 1500, -1500]。
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
        warnings.warn("头文件缺少 WCS 坐标关键字，使用默认 extent [-1500,1500]")
        return [-1500, 1500, 1500, -1500]


def _global_range_one(fp: str):
    """
    读取单个文件，返回 (nanmin, nanmax)。
    供并行调用，独立捕获异常。
    """
    try:
        data, _ = read_fits(fp)
        return float(np.nanmin(data)), float(np.nanmax(data))
    except Exception as e:
        warnings.warn(f"跳过文件 {fp}：{e}")
        return None


def compute_global_range(file_list: list, fixed_vmin=None, fixed_vmax=None,
                          max_workers: int = 4):
    """
    并行遍历所有文件统计全局 [vmin, vmax]。
    fixed_vmin / fixed_vmax 不为 None 时直接返回，跳过统计。

    【优化】改用 ThreadPoolExecutor：
      - 读 FITS + nanmin/nanmax 属于 I/O + NumPy 计算混合，
        线程池可并行 I/O，NumPy 释放 GIL 后计算也可并行，
        且不产生进程 fork 开销，内存占用更低。
    """
    if fixed_vmin is not None and fixed_vmax is not None:
        return fixed_vmin, fixed_vmax

    mins, maxs = [], []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_global_range_one, fp): fp for fp in file_list}
        with tqdm(total=len(file_list), desc="计算全局色彩范围", unit="文件") as pbar:
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    mins.append(result[0])
                    maxs.append(result[1])
                pbar.update(1)

    gmin = fixed_vmin if fixed_vmin is not None else float(np.nanmin(mins))
    gmax = fixed_vmax if fixed_vmax is not None else float(np.nanmax(maxs))
    print(f"全局色彩范围：[{gmin:.3e}, {gmax:.3e}]")
    return gmin, gmax


def get_time_from_header(header):
    """从 FITS 头文件提取观测时间"""
    date_obs = header.get("DATE-OBS", "Unknown")
    if "TIME-OBS" in header:
        return f"{date_obs} {header['TIME-OBS']}"
    return date_obs


def get_freq_from_header(header):
    """从 FITS 头文件提取频率"""
    return header.get("FREQ", header.get("FREQUENCY", None))


def get_polar_from_header(header):
    """从 FITS 头文件提取偏振信息"""
    return str(header.get("POLAR", "StokesI")).strip()


def _sorted_fits_for_band(band_dir: str, start_idx: int, end_idx) -> list:
    """获取指定波段目录中排序后的 FITS 文件列表"""
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
    构建多波段合成的时间槽（每个槽包含同一时间各波段的文件）。

    【优化】内层时间槽构建改用 zip(*per_band)，
    省去嵌套 for 循环，速度略快且代码更简洁。
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
        print(f"警告：各波段文件数量不一致，使用最小数量 {min_len}")
        per_band = [f[:min_len] for f in per_band]

    # ★ 优化：zip 直接转置二维列表，替代双层 for 循环
    slots = [list(band_files) for band_files in zip(*per_band)]

    print(f"构建了 {len(slots)} 个时间槽，每个槽包含 {len(freqs)} 个波段")
    print(f"偏振方向：{polarization}")
    return slots


def _layout_grid(n: int):
    """自动计算子图布局"""
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
    在主进程中预先创建所有单波段输出子目录，
    避免多个子进程并发调用 os.makedirs 竞争文件系统。
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
    """预先创建多波段输出子目录，返回目录路径。"""
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
    处理并绘制单个波段 FITS 文件，保存为 PNG。

    【优化】输出目录已由主进程预创建，此处直接拼接路径，
    不再调用 os.makedirs。
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
    title     = f"{file_name}   {freq} MHz  {polar}   {time_str}"

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
    处理并绘制多波段合成图像（一个时间槽的所有波段）。

    【优化】输出目录已由主进程预创建，此处直接拼接路径。
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches

    all_data    = []
    all_headers = []
    all_extents = []
    band_info   = []

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

    n_bands = len(slot_files)
    if cfg["multi_band_layout"] == "auto":
        nrow, ncol = _layout_grid(n_bands)
    else:
        nrow, ncol = cfg["multi_band_layout"]

    fig, axes = plt.subplots(nrow, ncol, figsize=cfg["multi_band_fig_size"])
    axes = axes.flatten() if hasattr(axes, "flatten") else [axes]

    for idx in range(n_bands):
        ax       = axes[idx]
        freq, polar, _ = band_info[idx]
        rsun_obs = all_headers[idx].get("RSUN_OBS", 960.0)

        im_kwargs = dict(extent=all_extents[idx], origin="upper",
                         cmap=cfg["cmap"], aspect="equal")
        if vmin is not None:
            im_kwargs["vmin"] = vmin
        if vmax is not None:
            im_kwargs["vmax"] = vmax

        im = ax.imshow(all_data[idx], **im_kwargs)

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

        ax.set_title(f"{freq} MHz  {polar}",
                     fontsize=cfg["title_fontsize"] - 4, fontweight="bold")

        if idx % ncol == 0:
            ax.set_ylabel("y (arcsec)", fontsize=cfg["label_fontsize"] - 4)
        if idx >= (nrow - 1) * ncol:
            ax.set_xlabel("x (arcsec)", fontsize=cfg["label_fontsize"] - 4)

        ax.tick_params(axis="both", which="major",
                       labelsize=cfg["tick_fontsize"] - 6)

        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
        cbar.ax.tick_params(labelsize=cfg["tick_fontsize"] - 8)

    for idx in range(n_bands, len(axes)):
        axes[idx].axis("off")

    main_time = band_info[0][2] if band_info else "Unknown"
    fig.suptitle(f"Multi-band Radio Synthesis - {main_time}",
                 fontsize=cfg["title_fontsize"] + 4, fontweight="bold", y=0.98)

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
    """向后兼容：将旧的 use_fixed_cbar 配置迁移到新的 color_range_mode"""
    if "use_fixed_cbar" in cfg:
        use_fixed_cbar = cfg.pop("use_fixed_cbar")
        if use_fixed_cbar:
            if cfg.get("fixed_vmin") is not None or cfg.get("fixed_vmax") is not None:
                cfg["color_range_mode"] = "fixed"
            else:
                cfg["color_range_mode"] = "global"
        else:
            cfg["color_range_mode"] = "auto"
        print(f"已迁移旧配置：use_fixed_cbar={use_fixed_cbar} -> "
              f"color_range_mode={cfg['color_range_mode']}")
    return cfg


def main():
    cfg  = CONFIG
    cfg  = _migrate_config(cfg)
    mode = cfg.get("mode", "single_band")

    # ── 1. 根据模式决定文件列表 / 时间槽 ──────────────────────
    if mode == "multi_band":
        print("运行模式：多波段合成")
        slots      = _build_multi_band_slots(cfg)
        output_dir = cfg.get("output_dir") or os.path.join(cfg["multi_band_root"], "plot")
        os.makedirs(output_dir, exist_ok=True)
        print(f"输出目录：{output_dir}")

        if cfg.get("multi_band_also_save_single", False):
            print("注意：multi_band_also_save_single=True，将同时保存单波段图像")

    else:
        print("运行模式：单波段")
        single_file = cfg.get("single_file_path")

        if single_file and os.path.isfile(single_file):
            files      = [single_file]
            output_dir = cfg.get("output_dir") or os.path.join(
                os.path.dirname(single_file), "plot")
            os.makedirs(output_dir, exist_ok=True)
            print(f"单文件模式，仅处理文件：{single_file}")
        else:
            if single_file:
                print(f"[警告] 指定的单文件不存在：{single_file}。回退到批量处理模式。")
            polarization = cfg.get("polarization", "RR")
            data_dir     = cfg["data_dir"]
            print(f"单波段模式，偏振方向：{polarization}")
            output_dir = cfg.get("output_dir") or os.path.join(data_dir, "plot")
            os.makedirs(output_dir, exist_ok=True)
            files = get_sorted_fits(data_dir, cfg["start_idx"], cfg["end_idx"])
            print(f"共选中 {len(files)} 个 FITS 文件，输出目录：{output_dir}")

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
        print(f"show_plot=True：交互后端 {matplotlib.get_backend()}，单进程逐帧显示")
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
        print("色彩范围模式：每帧自动调整")

    elif color_range_mode == "global":
        print("色彩范围模式：固定为全局最大最小值")
        all_files = [fp for slot in slots for fp in slot] \
                    if mode == "multi_band" else files
        # ★ 并行统计，复用 safe_workers
        vmin, vmax = compute_global_range(
            all_files, None, None, max_workers=safe_workers)

    elif color_range_mode == "fixed":
        fixed_vmin = cfg.get("fixed_vmin")
        fixed_vmax = cfg.get("fixed_vmax")
        if fixed_vmin is None or fixed_vmax is None:
            print("警告：color_range_mode='fixed' 但未设置 fixed_vmin/vmax，回退到自动模式")
        else:
            print(f"色彩范围模式：固定值 [{fixed_vmin:.3e}, {fixed_vmax:.3e}]")
            vmin, vmax = fixed_vmin, fixed_vmax

    else:
        print(f"警告：未知模式 '{color_range_mode}'，使用自动调整模式")

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
                with tqdm(total=len(slots), desc="多波段绘图进度", unit="槽") as pbar:
                    for future in as_completed(futures):
                        slot_idx = futures[future]
                        try:
                            future.result()
                        except Exception as e:
                            errors.append((slot_idx, str(e)))
                            tqdm.write(f"[错误] 槽 {slot_idx}: {e}")
                        finally:
                            pbar.update(1)
        else:
            for i, slot in enumerate(tqdm(slots, desc="多波段绘图进度", unit="槽")):
                try:
                    plot_multi_band_slot(i, slot, output_dir, cfg, vmin, vmax)
                except Exception as e:
                    errors.append((i, str(e)))
                    tqdm.write(f"[错误] 槽 {i}: {e}")

    else:
        if use_parallel and len(files) > 1:
            worker = partial(plot_single_band,
                             output_dir=output_dir, cfg=cfg, vmin=vmin, vmax=vmax)
            with ProcessPoolExecutor(max_workers=safe_workers) as executor:
                futures = {executor.submit(worker, fp): fp for fp in files}
                with tqdm(total=len(files), desc="绘图进度", unit="文件") as pbar:
                    for future in as_completed(futures):
                        fp = futures[future]
                        try:
                            future.result()
                        except Exception as e:
                            errors.append((fp, str(e)))
                            tqdm.write(f"[错误] {os.path.basename(fp)}: {e}")
                        finally:
                            pbar.update(1)
        else:
            for fp in tqdm(files, desc="绘图进度", unit="文件"):
                try:
                    plot_single_band(fp, output_dir, cfg, vmin, vmax)
                except Exception as e:
                    errors.append((fp, str(e)))
                    tqdm.write(f"[错误] {os.path.basename(fp)}: {e}")

    # ── 7. 汇总 ─────────────────────────────────────────────────
    elapsed = time.time() - t0
    total   = len(slots) if mode == "multi_band" else len(files)
    ok      = total - len(errors)
    label   = "槽" if mode == "multi_band" else "文件"
    print(f"\n完成！成功 {ok} / 共 {total} 个{label}，耗时 {elapsed:.1f} 秒")
    if errors:
        print(f"失败{label}（{len(errors)} 个）：")
        for item, msg in errors:
            name = item if mode == "multi_band" else os.path.basename(item)
            print(f"  {name}: {msg}")


if __name__ == "__main__":
    # Windows 多进程必须在此保护块内启动 main()
    main()