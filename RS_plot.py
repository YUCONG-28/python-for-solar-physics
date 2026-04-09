# -*- coding: utf-8 -*-
"""
Created on Sun Nov 23 00:19:30 2025
@author: Severus

修改说明：
1. 添加多波段合成模式，类似 AIA.py
2. 支持单波段模式和多波段模式切换
3. 重构文件处理逻辑
"""

import os
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
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
    # 注意：这里需要根据偏振方向选择正确的子目录
    "data_dir": r"<PROJECT_ROOT>\2025\20250124\RS_0447-0450\149MHz\RR",
    
    # 文件范围 (仅在批量模式下生效)
    "start_idx": 13,          # 起始索引（含）
    "end_idx":   17,          # 结束索引（不含）
    
    # ---------- 多波段模式配置 ----------
    # 波段根目录（包含各频率子目录）
    "multi_band_root": r"<PROJECT_ROOT>\2025\20250124\RS_0447-0450",
    
    # 要合成的波段列表（MHz）
    "multi_band_freqs": [149, 173, 237, 327],  # 示例：四个波段
    
    # 各波段子目录命名模式，{freq} 会被替换为波段频率，{polar} 会被替换为偏振方向
    "band_dir_pattern": "{freq}MHz/{polar}",
    
    # 多波段输出子目录名（自动包含偏振信息）
    "multi_band_output_subdir": "multi_band_{polar}",
    
    # 多波段画布布局
    "multi_band_layout": "auto",  # "auto" 自动布局，或指定 (nrow, ncol)
    
    # ---------- 输出配置 ----------
    # 图片输出目录（留空或 None 则自动在单文件/数据文件所在目录下创建 "plot" 子文件夹）
    "output_dir": r'<PROJECT_ROOT>\2025\20250124\DEM\0457_10\RS',
    
    # 多波段模式下是否同时保存单波段图像
    "multi_band_also_save_single": False,
    
    # ---------- 色彩范围 ----------
    "use_fixed_cbar": False,   # True: 固定范围；False: 每帧自动调整
    "fixed_vmin":     None,    # 固定模式最小值（None → 自动统计全局最小）
    "fixed_vmax":     None,    # 固定模式最大值（None → 自动统计全局最大）
    
    # ---------- 图像呈现范围 ----------
    "use_custom_lim": True,           # True: 使用下方自定义范围；False: 使用 scale_factor 自动范围
    "custom_xlim":    (-1150, 1150),   # 自定义 X 轴显示范围 (xmin, xmax)，单位：角秒 (ArcSec)
    "custom_ylim":    (-1150, 1150),   # 自定义 Y 轴显示范围 (ymin, ymax)，单位：角秒 (ArcSec)
    
    # ---------- 图像外观 ----------
    "fig_size":       (18, 16),    # 单波段画布尺寸（英寸）
    "multi_band_fig_size": (24, 20),  # 多波段画布尺寸（英寸）
    "dpi":            100,         # 输出分辨率
    "cmap":           "gist_heat", # 色表，可改为 "inferno"/"hot"/"jet" 等
    "scale_factor":   3.5,         # 显示范围 = rsun_obs × scale_factor (仅在 use_custom_lim=False 时有效)
    
    # ---------- 注记样式 ----------
    "title_fontsize":      24,
    "label_fontsize":      28,
    "tick_fontsize":       22,
    "legend_fontsize":     18,
    "annotation_fontsize": 20,
    
    # ---------- 并行 ----------
    "max_workers": None,  # 并行工作进程数；None → 自动使用全部 CPU 核心
    
    # ---------- 输出 ----------
    "show_plot": False,   # True: 屏幕弹窗（单进程调试用）；False: 仅保存文件
    "save_plot": True,    # True: 保存 PNG；False: 不保存
}
# ============================================================


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

    data = np.squeeze(data)   # 去除冗余维度，确保二维
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


def compute_global_range(file_list: list, fixed_vmin=None, fixed_vmax=None):
    """
    遍历所有文件统计全局 [vmin, vmax]。
    fixed_vmin / fixed_vmax 不为 None 时直接使用给定值，跳过统计。
    """
    if fixed_vmin is not None and fixed_vmax is not None:
        return fixed_vmin, fixed_vmax

    mins, maxs = [], []
    for fp in tqdm(file_list, desc="计算全局色彩范围", unit="文件"):
        try:
            data, _ = read_fits(fp)
            mins.append(np.nanmin(data))
            maxs.append(np.nanmax(data))
        except Exception as e:
            warnings.warn(f"跳过文件 {fp}：{e}")

    gmin = fixed_vmin if fixed_vmin is not None else float(np.nanmin(mins))
    gmax = fixed_vmax if fixed_vmax is not None else float(np.nanmax(maxs))
    print(f"全局色彩范围：[{gmin:.3e}, {gmax:.3e}]")
    return gmin, gmax


def get_time_from_header(header):
    """从 FITS 头文件提取观测时间"""
    date_obs = header.get("DATE-OBS", "Unknown")
    # 尝试提取更精确的时间
    if "TIME-OBS" in header:
        time_obs = header["TIME-OBS"]
        return f"{date_obs} {time_obs}"
    return date_obs


def get_freq_from_header(header):
    """从 FITS 头文件提取频率"""
    freq = header.get("FREQ", None)
    if freq is None:
        freq = header.get("FREQUENCY", None)
    return freq


def get_polar_from_header(header):
    """从 FITS 头文件提取偏振信息"""
    polar = str(header.get("POLAR", "StokesI")).strip()
    return polar


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
    
    total = len(all_files)
    end = total if end_idx is None else min(end_idx, total)
    selected = all_files[start_idx:end]
    
    if not selected:
        raise ValueError(f"索引范围 [{start_idx}, {end}) 内没有文件")
    
    return selected


def _build_multi_band_slots(cfg: dict) -> list:
    """构建多波段合成的时间槽（每个槽包含同一时间各波段的文件）"""
    root = cfg["multi_band_root"]
    freqs = cfg["multi_band_freqs"]
    pattern = cfg["band_dir_pattern"]
    polarization = cfg["polarization"]  # 获取偏振方向
    start_idx = cfg.get("start_idx", 0)
    end_idx = cfg.get("end_idx", None)
    
    # 收集各波段的文件列表
    per_band = []
    for freq in freqs:
        # 使用格式化字符串替换频率和偏振
        band_dir = os.path.join(root, pattern.format(freq=freq, polar=polarization))
        files = _sorted_fits_for_band(band_dir, start_idx, end_idx)
        per_band.append(files)
    
    # 检查各波段文件数量
    lengths = [len(files) for files in per_band]
    if len(set(lengths)) > 1:
        min_len = min(lengths)
        print(f"警告：各波段文件数量不一致，使用最小数量 {min_len}")
        # 截断到最小数量
        per_band = [files[:min_len] for files in per_band]
    
    # 构建时间槽：每个槽包含同一索引的各波段文件
    num_slots = len(per_band[0])
    slots = []
    for i in range(num_slots):
        slot = [band_files[i] for band_files in per_band]
        slots.append(slot)
    
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
# 核心绘图函数（在子进程中执行）
# ──────────────────────────────────────────────────────────────

def plot_single_band(file_path: str, output_dir: str, cfg: dict,
                    vmin=None, vmax=None) -> str:
    """
    处理并绘制单个波段 FITS 文件，保存为 PNG。
    """
    # 子进程重新设置后端（不继承主进程状态）
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    import matplotlib.patches as patches

    # 1. 读取数据
    img_data, header = read_fits(file_path)

    # 2. 计算坐标 extent
    extent = calc_extent(header, img_data.shape)

    # 3. 从头文件提取元信息
    rsun_obs = header.get("RSUN_OBS", 960.0)       # 太阳半径（角秒）
    freq     = get_freq_from_header(header) or "Unknown"
    polar    = get_polar_from_header(header)
    time_str = get_time_from_header(header)

    file_name = os.path.basename(file_path)
    title = f"{file_name}   {freq} MHz  {polar}   {time_str}"

    # 4. 建图
    fig, ax = plt.subplots(figsize=cfg["fig_size"])

    # 4a. 绘制 2D 图像
    im_kwargs = dict(
        extent=extent,
        origin="upper",
        cmap=cfg["cmap"],
        aspect="equal",
    )
    if vmin is not None:
        im_kwargs["vmin"] = vmin
    if vmax is not None:
        im_kwargs["vmax"] = vmax

    im = ax.imshow(img_data, **im_kwargs)

    # 4b. Colorbar
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=cfg["tick_fontsize"] - 4)

    # 4c. 标题 & 坐标轴标签
    ax.set_title(title, fontsize=cfg["title_fontsize"], fontweight="bold", pad=20)
    ax.set_xlabel("x (arcsec)", fontsize=cfg["label_fontsize"])
    ax.set_ylabel("y (arcsec)", fontsize=cfg["label_fontsize"])
    ax.tick_params(axis="both", which="major", labelsize=cfg["tick_fontsize"])

    # 4d. 太阳轮廓圆
    solar_limb = patches.Circle(
        (0, 0), radius=rsun_obs,
        edgecolor="white", facecolor="none",
        linewidth=3, linestyle="-",
    )
    ax.add_patch(solar_limb)

    # 4e. 太阳赤道线 & 中央子午线
    half = rsun_obs
    ax.add_line(plt.Line2D([-half, half], [0, 0],
                           color="cyan", lw=1.5, linestyle="--", alpha=0.8))
    ax.add_line(plt.Line2D([0, 0], [-half, half],
                           color="cyan", lw=1.5, linestyle="--", alpha=0.8))

    # 4f. 方向标注（N / E）
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

    # 4g. 显示范围、背景网格、图例
    if cfg.get("use_custom_lim", False):
        ax.set_xlim(cfg["custom_xlim"])
        ax.set_ylim(cfg["custom_ylim"])
    else:
        sf = cfg["scale_factor"]
        ax.set_xlim(-rsun_obs * sf, rsun_obs * sf)
        ax.set_ylim(-rsun_obs * sf, rsun_obs * sf)
        
    ax.grid(True, alpha=0.3, linestyle=":", color="gray")

    legend_elements = [
        Line2D([0], [0], color="white", lw=3,
               label=f'Solar Limb (R={rsun_obs:.0f}")'),
        Line2D([0], [0], color="cyan", lw=1.5, linestyle="--",
               label="Solar Grid"),
    ]
    ax.legend(handles=legend_elements, loc="upper right",
              fontsize=cfg["legend_fontsize"])

    # 5. 保存 / 显示
    plt.tight_layout()
    
    # 创建输出目录（波段子目录）
    band_output_dir = os.path.join(output_dir, f"{int(freq)}MHz" if isinstance(freq, (int, float)) else "unknown")
    os.makedirs(band_output_dir, exist_ok=True)
    
    output_path = os.path.join(band_output_dir, f"{os.path.splitext(file_name)[0]}.png")

    if cfg["save_plot"]:
        plt.savefig(output_path, dpi=cfg["dpi"], bbox_inches="tight")

    # show_plot 仅在主进程交互模式下有效
    if cfg["show_plot"] and cfg.get("_interactive", False):
        plt.show()

    plt.close(fig)   # 及时释放内存
    return output_path


def plot_multi_band_slot(slot_idx: int, slot_files: list, output_dir: str, 
                        cfg: dict, vmin=None, vmax=None) -> str:
    """
    处理并绘制多波段合成图像（一个时间槽的所有波段）。
    """
    # 子进程重新设置后端
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches

    # 1. 读取所有波段数据
    all_data = []
    all_headers = []
    all_extents = []
    band_info = []  # (freq, polar, time_str)
    
    for file_path in slot_files:
        img_data, header = read_fits(file_path)
        all_data.append(img_data)
        all_headers.append(header)
        all_extents.append(calc_extent(header, img_data.shape))
        
        # 收集波段信息
        freq = get_freq_from_header(header) or "Unknown"
        polar = get_polar_from_header(header)
        time_str = get_time_from_header(header)
        band_info.append((freq, polar, time_str))
    
    # 2. 确定布局
    n_bands = len(slot_files)
    if cfg["multi_band_layout"] == "auto":
        nrow, ncol = _layout_grid(n_bands)
    else:
        nrow, ncol = cfg["multi_band_layout"]
    
    # 3. 创建画布
    fig, axes = plt.subplots(nrow, ncol, figsize=cfg["multi_band_fig_size"])
    axes = axes.flatten() if hasattr(axes, 'flatten') else [axes]
    
    # 4. 绘制每个波段的子图
    for idx in range(n_bands):
        ax = axes[idx]
        img_data = all_data[idx]
        extent = all_extents[idx]
        freq, polar, time_str = band_info[idx]
        
        # 绘制图像
        im_kwargs = dict(
            extent=extent,
            origin="upper",
            cmap=cfg["cmap"],
            aspect="equal",
        )
        if vmin is not None:
            im_kwargs["vmin"] = vmin
        if vmax is not None:
            im_kwargs["vmax"] = vmax
            
        im = ax.imshow(img_data, **im_kwargs)
        
        # 太阳轮廓圆
        rsun_obs = all_headers[idx].get("RSUN_OBS", 960.0)
        solar_limb = patches.Circle(
            (0, 0), radius=rsun_obs,
            edgecolor="white", facecolor="none",
            linewidth=2, linestyle="-",
        )
        ax.add_patch(solar_limb)
        
        # 设置显示范围
        if cfg.get("use_custom_lim", False):
            ax.set_xlim(cfg["custom_xlim"])
            ax.set_ylim(cfg["custom_ylim"])
        else:
            sf = cfg["scale_factor"]
            ax.set_xlim(-rsun_obs * sf, rsun_obs * sf)
            ax.set_ylim(-rsun_obs * sf, rsun_obs * sf)
        
        # 子图标题
        title = f"{freq} MHz  {polar}"
        ax.set_title(title, fontsize=cfg["title_fontsize"] - 4, fontweight="bold")
        
        # 只在第一行和第一列显示坐标轴标签
        if idx % ncol == 0:  # 第一列
            ax.set_ylabel("y (arcsec)", fontsize=cfg["label_fontsize"] - 4)
        if idx >= (nrow - 1) * ncol:  # 最后一行
            ax.set_xlabel("x (arcsec)", fontsize=cfg["label_fontsize"] - 4)
        
        ax.tick_params(axis="both", which="major", labelsize=cfg["tick_fontsize"] - 6)
        
        # 添加 colorbar
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
        cbar.ax.tick_params(labelsize=cfg["tick_fontsize"] - 8)
    
    # 5. 隐藏多余的子图
    for idx in range(n_bands, len(axes)):
        axes[idx].axis('off')
    
    # 6. 添加主标题（使用第一个文件的时间）
    main_time = band_info[0][2] if band_info else "Unknown"
    fig.suptitle(f"Multi-band Radio Synthesis - {main_time}", 
                 fontsize=cfg["title_fontsize"] + 4, fontweight="bold", y=0.98)
    
    # 7. 调整布局并保存
    plt.tight_layout(rect=[0, 0, 1, 0.96])  # 为标题留出空间
    
    # 创建多波段输出目录（包含偏振信息）
    polarization = cfg.get("polarization", "RR")
    subdir_template = cfg.get("multi_band_output_subdir", "multi_band_{polar}")
    multi_output_subdir = subdir_template.format(polar=polarization)
    multi_output_dir = os.path.join(output_dir, multi_output_subdir)
    os.makedirs(multi_output_dir, exist_ok=True)
    
    output_path = os.path.join(multi_output_dir, f"multi_band_slot_{slot_idx:04d}.png")
    
    if cfg["save_plot"]:
        plt.savefig(output_path, dpi=cfg["dpi"], bbox_inches="tight")
    
    if cfg["show_plot"] and cfg.get("_interactive", False):
        plt.show()
    
    plt.close(fig)
    return output_path


# ──────────────────────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────────────────────

def main():
    cfg = CONFIG
    mode = cfg.get("mode", "single_band")
    
    # 1. 根据模式决定运行方式
    if mode == "multi_band":
        print("运行模式：多波段合成")
        # 构建多波段时间槽
        slots = _build_multi_band_slots(cfg)
        
        # 设置输出目录
        output_dir = cfg.get("output_dir") or os.path.join(cfg["multi_band_root"], "plot")
        os.makedirs(output_dir, exist_ok=True)
        print(f"输出目录：{output_dir}")
        
        # 多波段模式下，也可以选择是否保存单波段图像
        if cfg.get("multi_band_also_save_single", False):
            print("注意：multi_band_also_save_single=True，将同时保存单波段图像")
            # 这里可以添加单波段处理逻辑
        
    else:  # single_band 模式
        print("运行模式：单波段")
        # 单文件模式检查
        single_file = cfg.get("single_file_path")
        
        if single_file and os.path.isfile(single_file):
            # ★ 单文件模式 ★
            files = [single_file]
            output_dir = cfg.get("output_dir") or os.path.join(os.path.dirname(single_file), "plot")
            os.makedirs(output_dir, exist_ok=True)
            print(f"单文件模式，仅处理文件：{single_file}")
            print(f"输出目录：{output_dir}")
        else:
            # ★ 批量模式 ★
            if single_file: 
                print(f"[警告] 指定的单文件不存在或路径有误：{single_file}。将回退到批量处理模式。")
            
            # 根据偏振方向构建正确的数据目录
            polarization = cfg.get("polarization", "RR")
            # 注意：这里假设 data_dir 的父目录包含频率子目录
            data_dir = cfg["data_dir"]
            # 如果 data_dir 已经包含了偏振子目录，我们不需要修改
            # 否则，我们需要根据配置调整
            print(f"单波段模式，偏振方向：{polarization}")
                
            output_dir = cfg.get("output_dir") or os.path.join(data_dir, "plot")
            os.makedirs(output_dir, exist_ok=True)
            files = get_sorted_fits(data_dir, cfg["start_idx"], cfg["end_idx"])
            print(f"共选中 {len(files)} 个 FITS 文件，输出目录：{output_dir}")
    
    # 2. 根据 show_plot 决定运行模式
    if cfg["show_plot"]:
        for backend in ("TkAgg", "Qt5Agg", "MacOSX", "WXAgg"):
            try:
                matplotlib.use(backend)
                break
            except Exception:
                continue
        cfg = {**cfg, "_interactive": True}
        use_parallel = False
        print(f"show_plot=True：交互后端 {matplotlib.get_backend()}，单进程逐帧显示")
    else:
        matplotlib.use("Agg")
        cfg = {**cfg, "_interactive": False}
        use_parallel = True
    
    # 3. 若需固定色彩范围，先统计全局 vmin/vmax
    vmin = vmax = None
    if cfg["use_fixed_cbar"]:
        # 对于多波段模式，需要统计所有波段的所有文件
        if mode == "multi_band":
            # 收集所有文件
            all_files = []
            for slot in slots:
                all_files.extend(slot)
            vmin, vmax = compute_global_range(
                all_files, cfg["fixed_vmin"], cfg["fixed_vmax"]
            )
        else:
            vmin, vmax = compute_global_range(
                files, cfg["fixed_vmin"], cfg["fixed_vmax"]
            )
    
    # 4. 绘图（多进程批量 / 单进程交互）
    t0 = time.time()
    errors = []
    
    if mode == "multi_band":
        # 多波段模式处理
        if use_parallel and len(slots) > 1:
            max_workers = cfg["max_workers"]
            worker = partial(plot_multi_band_slot, output_dir=output_dir, cfg=cfg, vmin=vmin, vmax=vmax)
            
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(worker, i, slot): i for i, slot in enumerate(slots)}
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
            # 单进程处理
            for i, slot in enumerate(tqdm(slots, desc="多波段绘图进度", unit="槽")):
                try:
                    plot_multi_band_slot(i, slot, output_dir, cfg, vmin, vmax)
                except Exception as e:
                    errors.append((i, str(e)))
                    tqdm.write(f"[错误] 槽 {i}: {e}")
    else:
        # 单波段模式处理
        if use_parallel and len(files) > 1:
            max_workers = cfg["max_workers"]
            worker = partial(plot_single_band, output_dir=output_dir, cfg=cfg, vmin=vmin, vmax=vmax)
            
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
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
            # 单进程处理
            for fp in tqdm(files, desc="绘图进度", unit="文件"):
                try:
                    plot_single_band(fp, output_dir, cfg, vmin, vmax)
                except Exception as e:
                    errors.append((fp, str(e)))
                    tqdm.write(f"[错误] {os.path.basename(fp)}: {e}")
    
    # 5. 汇总
    elapsed = time.time() - t0
    total = len(slots) if mode == "multi_band" else len(files)
    ok = total - len(errors)
    print(f"\n完成！成功 {ok} / 共 {total} 个{'槽' if mode == 'multi_band' else '文件'}，耗时 {elapsed:.1f} 秒")
    if errors:
        print(f"失败{'槽' if mode == 'multi_band' else '文件'}（{len(errors)} 个）：")
        for item, msg in errors:
            if mode == "multi_band":
                print(f"  槽 {item}: {msg}")
            else:
                print(f"  {os.path.basename(item)}: {msg}")


if __name__ == "__main__":
    # Windows 多进程必须在此保护块内启动 main()
    main()
