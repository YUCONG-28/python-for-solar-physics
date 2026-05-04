# -*- coding: utf-8 -*-
# 模块用途: 绘制 AIA 图像、GOES SXR 光变和 HXR 光变组成的三面板耀斑诊断图。
# 主要输入: AIA 图像、GOES 软 X 射线数据和硬 X 射线光变数据。
# 主要输出/运行说明: 输出综合时空诊断图，用于事件论文配图或快速检查。
"""
Created on Mon Oct 13 16:33:00 2025

@author: Severus
"""

import argparse
import csv
import fnmatch  # 用于文件名匹配
import math
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import xarray as xr
from astropy.io import fits
from scipy.signal import savgol_filter

from solar_toolkit.path_config import load_script_config

# 字体配置（确保中文显示正常）
plt.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示问题


def load_sxr_data(file_path, start_time, end_time):
    """加载并处理SXR数据"""
    ds = xr.open_dataset(file_path)
    ds = xr.decode_cf(ds)
    ds_subset = ds.sel(time=slice(start_time, end_time))

    # 提取数据
    time_subset = ds_subset["time"].values
    xrsa_flux = ds_subset["xrsa_flux"].values
    xrsb_flux = ds_subset["xrsb_flux"].values

    # 数据平滑
    window_length = 22
    polyorder = 3
    xrsa_smoothed = savgol_filter(xrsa_flux, window_length, polyorder)
    xrsb_smoothed = savgol_filter(xrsb_flux, window_length, polyorder)

    # 计算导数
    time_seconds = ds_subset["time"].astype("datetime64[s]").astype(float)
    time_diff = np.diff(time_seconds)
    xrsa_deriv = np.diff(xrsa_smoothed) / time_diff
    xrsb_deriv = np.diff(xrsb_smoothed) / time_diff

    # 转换时间格式
    times = [
        datetime.utcfromtimestamp(t.astype("datetime64[ns]").astype("int64") / 1e9)
        for t in time_subset
    ]

    return {
        "times": times,
        "xrsa": {"raw": xrsa_flux, "smoothed": xrsa_smoothed, "deriv": xrsa_deriv},
        "xrsb": {"raw": xrsb_flux, "smoothed": xrsb_smoothed, "deriv": xrsb_deriv},
        "time_subset": time_subset,
    }


def load_hxi_data(file_path, start_time, end_time):
    """加载并处理HXI数据"""
    hdul = fits.open(file_path)

    h1 = hdul[1].data
    h3 = hdul[3].data
    CTS = h3["CTS_THINTHICK"]

    # 提取不同能量范围的数据
    data = {
        "10-20 keV": CTS[:, 0],
        "20-50 keV": CTS[:, 1],
        "50-100 keV": CTS[:, 2],
        "100-300 keV": CTS[:, 3],
    }

    # 转换时间格式
    base_time = datetime(2018, 12, 31, 16, 00, 00)
    utc_times = [base_time + timedelta(seconds=t) for t in h1.TIME]

    # 时间范围筛选
    mask = [(t >= start_time) and (t <= end_time) for t in utc_times]
    filtered_times = [t for t, m in zip(utc_times, mask) if m]

    filtered_data = {}
    for key, values in data.items():
        filtered_data[key] = values[mask]

    return {"times": filtered_times, "data": filtered_data}


def load_aia_data(dir_path, file_pattern, start_time, end_time):
    """加载并处理AIA数据，按文件名模式选取文件"""
    data_dir = Path(dir_path)

    # 获取文件夹中所有匹配模式的CSV文件并按名称排序
    all_files = sorted(
        [
            f
            for f in data_dir.iterdir()
            if f.suffix == ".csv" and fnmatch.fnmatch(f.name, file_pattern)
        ]
    )

    if not all_files:
        print(
            f"警告：文件夹 '{dir_path}' 中没有找到匹配模式 '{file_pattern}' 的CSV文件"
        )
        return []

    print(f"已选择AIA文件（匹配模式：{file_pattern}）：{[f.name for f in all_files]}")

    all_aia_data = []
    for file_path in all_files:
        time_list, flux_list = [], []

        try:
            with file_path.open("r", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader)  # 跳过表头
                for row in reader:
                    if len(row) != 2:
                        continue
                    dt = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
                    # 时间范围筛选
                    if start_time <= dt <= end_time:
                        flux = float(row[1])
                        if flux > 0:  # 对数坐标需要正值
                            time_list.append(dt)
                            flux_list.append(flux)
            if time_list and flux_list:
                all_aia_data.append(
                    {"times": time_list, "flux": flux_list, "label": file_path.name}
                )
                print(
                    f"成功加载 {file_path.name}，共 {len(time_list)} 条有效数据（在指定时间范围内）"
                )
        except Exception as e:
            print(f"加载 {file_path.name} 失败: {str(e)}，已跳过")

    return all_aia_data


def plot_combined_data(
    sxr_data, hxi_data, aia_data_list, start_time, end_time, vline_times
):
    """将所有数据绘制到同一图表，支持多条竖线"""
    fig, ax1 = plt.subplots(figsize=(18, 12))

    # 设置X轴范围为用户指定的时间范围
    ax1.set_xlim(start_time, end_time)

    # 绘制竖线，使用明显的细线样式
    line_styles = ["--", "--"]  # 支持不同样式区分多条线
    for i, vtime in enumerate(vline_times):
        ax1.axvline(
            x=vtime,
            color="black",
            linestyle=line_styles[i % len(line_styles)],
            linewidth=1.5,
            alpha=0.8,
            label=f'时间点{i+1}: {vtime.strftime("%H:%M:%S")}',
        )

    # 1. 绘制SXR数据 (ax1)
    ax1.semilogy(
        sxr_data["times"],
        sxr_data["xrsa"]["smoothed"],
        label="SXR 0.5-4.0 Å (平滑)",
        color="red",
    )
    ax1.semilogy(
        sxr_data["times"],
        sxr_data["xrsb"]["smoothed"],
        label="SXR 1.0-8.0 Å (平滑)",
        color="green",
    )
    ax1.set_ylabel("SXR 流量 (W/m²)", fontsize=12, labelpad=10)
    ax1.tick_params(axis="y", labelcolor="black")
    ax1.legend(loc="upper left", fontsize=10)

    # 2. 创建第二个Y轴用于HXI数据
    ax2 = ax1.twinx()
    colors = ["darkred", "darkgreen", "blue", "purple"]
    for i, (energy, counts) in enumerate(hxi_data["data"].items()):
        ax2.semilogy(
            hxi_data["times"],
            counts,
            label=f"HXI {energy}",
            color=colors[i],
            linestyle="--",
        )
    ax2.set_ylabel("HXI 计数率 (counts/s/detector)", fontsize=12, labelpad=10)
    ax2.tick_params(axis="y", labelcolor="black")
    ax2.legend(loc="upper right", fontsize=10)

    # 3. 创建第三个Y轴用于SXR导数数据
    ax3 = ax1.twinx()
    # 将第三个Y轴定位到右侧更远处
    ax3.spines["right"].set_position(("outward", 60))
    ax3.plot(
        sxr_data["times"][1:],
        sxr_data["xrsa"]["deriv"],
        label="SXR 0.5-4.0 Å 导数",
        color="pink",
        linestyle="-.",
    )
    ax3.plot(
        sxr_data["times"][1:],
        sxr_data["xrsb"]["deriv"],
        label="SXR 1.0-8.0 Å 导数",
        color="lightgreen",
        linestyle="-.",
    )
    ax3.set_ylabel("SXR 流量导数 (W/m²/s)", fontsize=12, labelpad=10)
    ax3.tick_params(axis="y", labelcolor="black")
    ax3.set_ylim(-0.25e-15, 0.25e-15)
    ax3.legend(loc="lower left", fontsize=10)

    # 4. 创建第四个Y轴用于AIA数据
    if aia_data_list:
        ax4 = ax1.twinx()
        ax4.spines["right"].set_position(("outward", 120))
        line_styles = ["-", "--", "-.", ":"]

        for i, aia_data in enumerate(aia_data_list):
            ls = line_styles[i % len(line_styles)]
            ax4.semilogy(
                aia_data["times"],
                aia_data["flux"],
                label=aia_data["label"],
                linestyle=ls,
                alpha=0.7,
            )

        ax4.set_ylabel("AIA 流量", fontsize=12, labelpad=10)
        ax4.tick_params(axis="y", labelcolor="black")
        ax4.legend(loc="lower right", fontsize=10)

    # 配置X轴
    ax1.set_xlabel("时间 (UTC)", fontsize=12, labelpad=10)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    ax1.xaxis.set_major_locator(
        mdates.MinuteLocator(interval=5)
    )  # 可根据时间范围调整间隔
    ax1.xaxis.set_minor_locator(mdates.MinuteLocator())
    ax1.xaxis.grid(True, which="both", linestyle="--", alpha=0.5)
    plt.xticks(rotation=45, ha="right")

    # 设置标题，包含时间范围信息
    plt.title(
        f'SXR-HXR-AIA ({start_time.strftime("%Y-%m-%d %H:%M")}至{end_time.strftime("%H:%M")})',
        fontsize=16,
        fontweight="bold",
    )

    # 调整布局
    plt.tight_layout()

    return fig


def main():
    path_config = load_script_config(
        "flare_aia_sxr_hxr_summary_plot",
        {
            "sxr": "d:/Flare/dn_xrsf-l2-flx1s_g16_d20240808_v2-2-0.nc",
            "hxi": "D:/Flare/hxi_qld_levq1_20240808_19_hly_v03.fits",
            "aia_dir": "D:/Flare/JSOCdata/All/Flux_data/",
        },
    )
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="太阳X射线流量与HXI数据综合可视化")
    parser.add_argument(
        "--sxr",
        type=str,
        default=path_config["sxr"],
        help="SXR数据文件路径",
    )
    parser.add_argument(
        "--hxi",
        type=str,
        default=path_config["hxi"],
        help="HXI数据文件路径",
    )
    parser.add_argument(
        "--aia-dir",
        type=str,
        default=path_config["aia_dir"],
        help="AIA数据文件夹路径",
    )
    parser.add_argument(
        "--aia-patterns",
        type=str,
        nargs="+",
        default=["aia_304.csv", "aia_1600.csv"],
        help='AIA文件匹配模式列表（支持通配符，如"aia_*.csv"）',
    )
    parser.add_argument(
        "--start-time",
        type=str,
        default="2024-08-08T19:00:00",
        help="起始时间（格式：YYYY-MM-DDTHH:MM:SS）",
    )
    parser.add_argument(
        "--end-time",
        type=str,
        default="2024-08-08T20:00:00",
        help="结束时间（格式：YYYY-MM-DDTHH:MM:SS）",
    )
    # 新增竖线时间参数，支持多个时间点
    parser.add_argument(
        "--vline-times",
        type=str,
        nargs="+",
        default=["2024-08-08T19:22:30", "2024-08-08T19:27:50"],
        help="竖线时间点列表（格式：YYYY-MM-DDTHH:MM:SS，可添加或减少）",
    )
    parser.add_argument(
        "--output", type=str, default="combined_plot.png", help="输出图像文件名"
    )
    args = parser.parse_args()

    # 转换时间字符串为datetime对象
    try:
        # 转换时间格式，支持T分隔或空格分隔
        start_time = datetime.fromisoformat(args.start_time.replace("T", " "))
        end_time = datetime.fromisoformat(args.end_time.replace("T", " "))
        # 转换竖线时间列表
        vline_times = [
            datetime.fromisoformat(t.replace("T", " ")) for t in args.vline_times
        ]
        print(
            f"将绘制 {start_time} 至 {end_time} 的数据，包含竖线时间点: {[t.strftime('%H:%M:%S') for t in vline_times]}"
        )
    except ValueError:
        print(
            "时间格式错误，请使用YYYY-MM-DDTHH:MM:SS格式（例如：2024-08-08T19:00:00）"
        )
        return

    # 加载各类数据，均传入时间范围参数
    print("加载SXR数据...")
    sxr_data = load_sxr_data(args.sxr, args.start_time, args.end_time)

    print("加载HXI数据...")
    hxi_data = load_hxi_data(args.hxi, start_time, end_time)

    print("加载AIA数据...")
    aia_data_list = []
    # 循环处理每个模式（因为aia_patterns是列表）
    for pattern in args.aia_patterns:
        aia_data = load_aia_data(args.aia_dir, pattern, start_time, end_time)
        aia_data_list.extend(aia_data)

    # 绘制综合图像，传入时间范围参数和竖线时间列表
    print("绘制综合图像...")
    fig = plot_combined_data(
        sxr_data, hxi_data, aia_data_list, start_time, end_time, vline_times
    )

    # 保存并显示图像
    # fig.savefig(args.output, dpi=300, bbox_inches='tight')
    print(f"图像已保存至：{args.output}")
    plt.show()


if __name__ == "__main__":
    main()
