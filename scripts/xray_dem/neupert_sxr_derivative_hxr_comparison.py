# 模块用途: 比较 GOES SXR 导数与 HXR 辐射，用于 Neupert 效应时序分析。
# 主要输入: GOES 软 X 射线光变和硬 X 射线光变数据。
# 主要输出/运行说明: 输出 SXR 导数-HXR 对比图和相关时序诊断。
"""
Created on Tue Oct 21 23:20:37 2025

@author: Severus
"""

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from matplotlib.font_manager import FontProperties, findfont
from scipy.signal import savgol_filter

from solar_toolkit.path_config import load_script_config

# --------------------------
# 配置参数（可根据需求调整）
# --------------------------
PATH_CONFIG = load_script_config(
    "neupert_sxr_derivative_hxr_comparison",
    {"data_file_path": "<DATA_ROOT>/dn_xrsf-l2-flx1s_g16_d20240808_v2-2-0.nc"},
)
DATA_FILE_PATH = Path(PATH_CONFIG["data_file_path"])
START_TIME = "2024-08-08T19:00:00"
END_TIME = "2024-08-08T20:00:00"
SMOOTH_WINDOW = 22
SMOOTH_POLY_ORDER = 3
FIG_SIZE = (12, 16)
DPI = 300
SAVE_FIG = False
FIG_NAME = "SXR分析结果.png"
# 优先选择支持完整符号集的字体
FONT_CANDIDATES = [
    "Arial",
    "Times New Roman",
    "SimHei",
    "Microsoft YaHei",
    "DejaVu Sans",
]


# --------------------------
# 字体与格式工具
# --------------------------
def get_available_fonts(candidates):
    """筛选系统中可用的字体"""
    available = []
    for font in candidates:
        try:
            findfont(FontProperties(family=font))
            available.append(font)
        except Exception:
            continue
    return available if available else ["sans-serif"]


class CustomLogFormatter(mticker.LogFormatter):
    """自定义对数坐标格式化器，确保负号正确显示"""

    def __call__(self, x, pos=None):
        # 处理对数坐标下的标签格式化
        if x == 0:
            return ""

        # 计算指数
        exp = np.floor(np.log10(x))
        base = x / (10**exp)

        # 格式化显示，使用mathtext确保负号正确渲染
        if abs(base - 1.0) < 1e-6:
            return rf"$10^{{{exp}}}$"
        else:
            return rf"${base:.1f} \times 10^{{{exp}}}$"


# --------------------------
# 初始化配置
# --------------------------
def init_plt_settings():
    """初始化matplotlib配置，重点解决负号显示问题"""
    available_fonts = get_available_fonts(FONT_CANDIDATES)
    print(f"使用可用字体: {available_fonts}")

    # 核心设置：确保负号和数学符号正确显示
    plt.rcParams.update(
        {
            "font.family": available_fonts,
            "axes.unicode_minus": True,  # 关键：启用Unicode负号
            "mathtext.fontset": "dejavusans",  # 使用支持符号的数学字体
            "mathtext.default": "regular",
            "axes.formatter.use_mathtext": True,  # 对轴标签使用mathtext
            "axes.titlesize": 14,
            "axes.labelsize": 12,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
        }
    )


# --------------------------
# 数据处理函数
# --------------------------
def load_sxr_data(file_path, start_time, end_time):
    import xarray as xr

    if not file_path.exists():
        raise FileNotFoundError(f"数据文件不存在: {file_path}")

    try:
        with xr.open_dataset(file_path) as ds:
            ds = xr.decode_cf(ds)
            print("数据集信息:")
            print(ds.info())
    except Exception as e:
        raise RuntimeError(f"读取数据失败: {str(e)}") from e

    try:
        ds_subset = ds.sel(time=slice(start_time, end_time))
        if ds_subset.time.size == 0:
            raise ValueError(f"时间范围内没有数据: {start_time} 至 {end_time}")
        print(f"\n成功截取数据，共 {len(ds_subset.time)} 个数据点")
    except Exception as e:
        raise RuntimeError(f"截取时间范围失败: {str(e)}") from e

    return ds_subset


def smooth_flux_data(flux_data, window_length, polyorder):
    if window_length % 2 == 0:
        window_length += 1
        print(f"窗口大小调整为奇数: {window_length}")

    window_length = min(
        window_length, len(flux_data) if len(flux_data) % 2 == 1 else len(flux_data) - 1
    )
    polyorder = min(polyorder, window_length - 1)

    return savgol_filter(flux_data, window_length, polyorder)


def calculate_derivative(time_data, flux_data):
    time_seconds = time_data.astype("int64") / 1e9
    return np.gradient(flux_data, time_seconds)


# --------------------------
# 绘图函数
# --------------------------
def plot_flux_comparison(ax, time, raw_data, smooth_data, title, ylabel):
    title = title.replace("Å", "Angstrom")

    ax.semilogy(time, raw_data, label="原始数据", color="lightcoral", alpha=0.5)
    ax.semilogy(time, smooth_data, label="平滑后", color="red")
    ax.legend()
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.xaxis.set_minor_locator(mdates.MinuteLocator(interval=5))
    ax.xaxis.grid(True, which="minor", linestyle="--", color="gray", alpha=0.3)

    # 应用自定义格式化器解决负号问题
    ax.yaxis.set_major_formatter(CustomLogFormatter())


def plot_derivative(ax, time, derivative_data, title, ylabel):
    abs_derivative = np.abs(derivative_data)
    non_zero = abs_derivative[abs_derivative > 0]
    if len(non_zero) > 0:
        abs_derivative[abs_derivative == 0] = np.min(non_zero) * 0.1
    else:
        abs_derivative[abs_derivative == 0] = 1e-20

    ax.semilogy(time, abs_derivative, color="blue", label="导数绝对值")
    ax.legend()
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.xaxis.set_minor_locator(mdates.MinuteLocator(interval=5))
    ax.xaxis.grid(True, which="minor", linestyle="--", color="gray", alpha=0.3)

    # 应用自定义格式化器解决负号问题
    ax.yaxis.set_major_formatter(CustomLogFormatter())


def visualize_results(
    time, xrsa_raw, xrsa_smooth, xrsb_raw, xrsb_smooth, xrsa_deriv, xrsb_deriv
):
    fig, axes = plt.subplots(4, 1, figsize=FIG_SIZE, sharex=True)

    plot_flux_comparison(
        axes[0],
        time,
        xrsa_raw,
        xrsa_smooth,
        "GOES-16 太阳软X射线流量 (0.5-4 Angstrom)",
        "流量 (W/m²)",
    )

    plot_flux_comparison(
        axes[1],
        time,
        xrsb_raw,
        xrsb_smooth,
        "GOES-16 太阳软X射线流量 (1.0-8 Angstrom)",
        "流量 (W/m²)",
    )

    plot_derivative(
        axes[2],
        time,
        xrsa_deriv,
        "GOES-16 太阳软X射线流量导数 (0.5-4 Angstrom)",
        "流量 (W/(m²s)",
    )

    plot_derivative(
        axes[3],
        time,
        xrsb_deriv,
        "GOES-16 太阳软X射线流量导数 (1.0-8 Angstrom)",
        "流量 (W/(m²s)",
    )

    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    plt.xticks(rotation=45, ha="right")
    plt.xlabel("时间")
    plt.tight_layout()

    if SAVE_FIG:
        plt.savefig(FIG_NAME, dpi=DPI, bbox_inches="tight")
        print(f"图像已保存为: {FIG_NAME}")

    plt.show()


# --------------------------
# 主函数
# --------------------------
def main():
    try:
        init_plt_settings()
        ds_subset = load_sxr_data(DATA_FILE_PATH, START_TIME, END_TIME)

        time_subset = ds_subset["time"]
        xrsa_flux = np.clip(ds_subset["xrsa_flux"].values, 1e-12, None)
        xrsb_flux = np.clip(ds_subset["xrsb_flux"].values, 1e-12, None)

        xrsa_smoothed = smooth_flux_data(xrsa_flux, SMOOTH_WINDOW, SMOOTH_POLY_ORDER)
        xrsb_smoothed = smooth_flux_data(xrsb_flux, SMOOTH_WINDOW, SMOOTH_POLY_ORDER)

        xrsa_derivative = calculate_derivative(time_subset, xrsa_smoothed)
        xrsb_derivative = calculate_derivative(time_subset, xrsb_smoothed)

        visualize_results(
            time_subset,
            xrsa_flux,
            xrsa_smoothed,
            xrsb_flux,
            xrsb_smoothed,
            xrsa_derivative,
            xrsb_derivative,
        )

    except Exception as e:
        print(f"程序出错: {str(e)}")


if __name__ == "__main__":
    main()
