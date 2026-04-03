# -*- coding: utf-8 -*-
"""
Created on Sun Nov 23 00:19:30 2025
@author: Severus

"""

import os
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial

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
    # ---------- 单文件模式 (新增) ----------
    # 如果只想画单个文件，请在此填写文件的完整绝对路径（例如 r"D:\path\to\file.fits"）。
    # 若此项不为空或 None，程序将只画这一个文件，并自动忽略下方的 data_dir 和 start/end_idx。
    "single_file_path": r'D:\spike_topping_type_III\2025\20250124\RS_0447-0450\149MHz\RR\149MHz_2025124_045710_093.fits',  

    # ---------- 路径 ----------
    # FITS 文件所在目录 (仅在批量模式下生效)
    "data_dir": r"D:\spike_topping_type_III\2025\20250124\RS_0447-0450\149MHz\RR",

    # 图片输出目录（留空或 None 则自动在单文件/数据文件所在目录下创建 "plot" 子文件夹）
    "output_dir": r'D:\spike_topping_type_III\2025\20250124\DEM\0457_10\RS',

    # ---------- 文件范围 (仅在批量模式下生效) ----------
    "start_idx": 13,          # 起始索引（含）
    "end_idx":   17,          # 结束索引（不含）

    # ---------- 色彩范围 ----------
    "use_fixed_cbar": False,   # True: 固定范围；False: 每帧自动调整
    "fixed_vmin":     None,    # 固定模式最小值（None → 自动统计全局最小）
    "fixed_vmax":     None,    # 固定模式最大值（None → 自动统计全局最大）

    # ---------- 图像呈现范围 ----------
    "use_custom_lim": True,           # True: 使用下方自定义范围；False: 使用 scale_factor 自动范围
    "custom_xlim":    (-1150, 1150),   # 自定义 X 轴显示范围 (xmin, xmax)，单位：角秒 (ArcSec)
    "custom_ylim":    (-1150, 1150),   # 自定义 Y 轴显示范围 (ymin, ymax)，单位：角秒 (ArcSec)

    # ---------- 图像外观 ----------
    "fig_size":       (18, 16),    # 画布尺寸（英寸）
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
    # 并行工作进程数；None → 自动使用全部 CPU 核心
    # 若内存紧张可手动设为 2 或 4
    "max_workers": None,

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


# ──────────────────────────────────────────────────────────────
# 核心绘图函数（在子进程中执行）
# ──────────────────────────────────────────────────────────────

def plot_one(file_path: str, output_dir: str, cfg: dict,
             vmin=None, vmax=None) -> str:
    """
    处理并绘制单个 FITS 文件，保存为 PNG。
    参数：
        file_path  : FITS 文件路径
        output_dir : 输出目录
        cfg        : CONFIG 字典（含内部标志 _interactive）
        vmin/vmax  : 色彩范围（None → 每帧自动）
    返回：输出 PNG 路径
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

    # 3. 从头文件提取元信息（带默认值，避免 KeyError）
    rsun_obs = header.get("RSUN_OBS", 960.0)       # 太阳半径（角秒）
    freq     = header.get("FREQ",     149.0)        # 观测频率（MHz）
    polar    = str(header.get("POLAR", "StokesI")).strip()
    date_obs = header.get("DATE-OBS", "Unknown")

    file_name = os.path.basename(file_path)
    title = f"{file_name}   {freq} MHz  {polar}   {date_obs}"

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

    # 4e. 太阳赤道线 & 中央子午线（虚线，方便辨认方向）
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
    output_path = os.path.join(output_dir, f"{os.path.splitext(file_name)[0]}.png")

    if cfg["save_plot"]:
        plt.savefig(output_path, dpi=cfg["dpi"], bbox_inches="tight")

    # show_plot 仅在主进程交互模式下有效（子进程 Agg 后端无法弹窗）
    if cfg["show_plot"] and cfg.get("_interactive", False):
        plt.show()

    plt.close(fig)   # 及时释放内存，多进程尤为重要
    return output_path


# ──────────────────────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────────────────────

def main():
    cfg = CONFIG

    # 1. 决定文件列表和输出目录
    single_file = cfg.get("single_file_path")
    
    if single_file and os.path.isfile(single_file):
        # ★ 单文件模式 ★
        files = [single_file]
        # 若输出目录为空，则在单文件所在目录下建 plot 文件夹
        output_dir = cfg.get("output_dir") or os.path.join(os.path.dirname(single_file), "plot")
        os.makedirs(output_dir, exist_ok=True)
        print(f"检测到单文件模式，仅处理文件：{single_file}")
        print(f"输出目录：{output_dir}")
    else:
        # ★ 批量模式 ★
        if single_file: 
            print(f"[警告] 指定的单文件不存在或路径有误：{single_file}。将回退到批量处理模式。")
            
        output_dir = cfg.get("output_dir") or os.path.join(cfg["data_dir"], "plot")
        os.makedirs(output_dir, exist_ok=True)
        files = get_sorted_fits(cfg["data_dir"], cfg["start_idx"], cfg["end_idx"])
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
        vmin, vmax = compute_global_range(
            files, cfg["fixed_vmin"], cfg["fixed_vmax"]
        )

    # 4. 绘图（多进程批量 / 单进程交互）
    t0 = time.time()
    worker = partial(plot_one, output_dir=output_dir, cfg=cfg, vmin=vmin, vmax=vmax)
    errors = []

    # 当仅有1个文件时，强制使用单进程，没有必要启用进程池
    if use_parallel and len(files) > 1:
        max_workers = cfg["max_workers"]   # None → os.cpu_count()
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
        for fp in tqdm(files, desc="绘图进度", unit="文件"):
            try:
                worker(fp)
            except Exception as e:
                errors.append((fp, str(e)))
                tqdm.write(f"[错误] {os.path.basename(fp)}: {e}")

    # 5. 汇总
    elapsed = time.time() - t0
    ok = len(files) - len(errors)
    print(f"\n完成！成功 {ok} / 共 {len(files)} 个文件，耗时 {elapsed:.1f} 秒")
    if errors:
        print(f"失败文件（{len(errors)} 个）：")
        for fp, msg in errors:
            print(f"  {os.path.basename(fp)}: {msg}")


if __name__ == "__main__":
    # Windows 多进程必须在此保护块内启动 main()
    main()