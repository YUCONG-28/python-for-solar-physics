# -*- coding: utf-8 -*-
# 模块用途: 探索 SXR 到 HXR 对比中的时间误差和相关性参数。
# 主要输入: SXR/HXR 光变数据和待扫描参数。
# 主要输出/运行说明: 输出 Neupert 效应参数调试和误差分析结果。
"""
Created on Tue Oct 21 23:20:37 2025

@author: Severus
"""

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from scipy.signal import savgol_filter  # 导入平滑处理所需库

plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示异常

# 字体配置（确保中文显示正常）
plt.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示问题

if __name__ == "__main__":
    file_path = "<DATA_ROOT>/dn_xrsf-l2-flx1s_g16_d20240808_v2-2-0.nc"
    ds = xr.open_dataset(file_path)
    print(ds)
    ds = xr.decode_cf(ds)
    start_time = "2024-08-08T19:00:00"
    end_time = "2024-08-08T20:00:00"
    ds_subset = ds.sel(time=slice(start_time, end_time))
    time_subset = ds_subset["time"]
    xrsa_flux_subset = ds_subset["xrsa_flux"].values  # 转为numpy数组便于处理
    xrsb_flux_subset = ds_subset["xrsb_flux"].values

    # 数据平滑参数（可调整）
    # window_length: 平滑窗口大小，必须为奇数，值越大平滑效果越强（但可能丢失细节）
    # polyorder: 多项式拟合阶数，通常取2或3，值越小平滑效果越强
    window_length = 22  # 平滑窗口大小（关键参数）
    polyorder = 3  # 多项式阶数（关键参数）

    # 对原始数据进行平滑处理
    xrsa_smoothed = savgol_filter(xrsa_flux_subset, window_length, polyorder)
    xrsb_smoothed = savgol_filter(xrsb_flux_subset, window_length, polyorder)

    time_seconds = time_subset.astype("datetime64[s]").astype(float)

    # 计算时间间隔（秒）
    time_diff = np.diff(time_seconds)
    # 使用平滑后的数据计算导数
    xrsa_flux_derivative = np.diff(xrsa_smoothed) / time_diff
    xrsb_flux_derivative = np.diff(xrsb_smoothed) / time_diff

    # 创建4行1列的子图，共享x轴
    fig, ([ax1, ax3], [ax2, ax4]) = plt.subplots(2, 2, figsize=(32, 16), sharex=True)

    # 第一个子图：0.5-4.0 A原始流量
    ax1.semilogy(time_subset, xrsa_flux_subset, label="0.5-4.0 A", color="red")
    ax1.legend()
    ax1.set_ylabel("Flux (W/m²)", fontsize=12, labelpad=10)
    ax1.set_title(
        "GOES-16 Solar Soft X-ray Flux (0.5-4 Å)   2024-08-08",
        fontsize=14,
        fontweight="bold",
    )
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.xaxis.set_minor_locator(mdates.MinuteLocator())
    ax1.xaxis.grid(True, which="minor", linestyle="--", color="gray", alpha=0.5)

    # 第二个子图：1.0-8.0 A原始流量
    ax2.semilogy(time_subset, xrsb_flux_subset, label="1.0-8.0 A", color="green")
    ax2.legend()
    ax2.set_ylabel("Flux (W/m²)", fontsize=12, labelpad=10)
    ax2.set_title(
        "GOES-16 Solar Soft X-ray Flux (1.0-8 Å)   2024-08-08",
        fontsize=14,
        fontweight="bold",
    )
    ax2.grid(True, linestyle="--", alpha=0.5)
    ax2.xaxis.set_minor_locator(mdates.MinuteLocator())
    ax2.xaxis.grid(True, which="minor", linestyle="--", color="gray", alpha=0.5)

    # 第三个子图：0.5-4.0 A原始流量与平滑后流量对比
    ax3.semilogy(
        time_subset, xrsa_flux_subset, label="原始数据", color="lightcoral", alpha=0.5
    )
    ax3.semilogy(time_subset, xrsa_smoothed, label="平滑后", color="red")
    ax3.legend()
    ax3.set_ylabel("Flux (W/m²)", fontsize=12, labelpad=10)
    ax3.set_title(
        "GOES-16 Solar Soft X-ray Flux (0.5-4 Å))", fontsize=14, fontweight="bold"
    )
    ax3.grid(True, linestyle="--", alpha=0.5)
    ax3.xaxis.set_minor_locator(mdates.MinuteLocator())
    ax3.xaxis.grid(True, which="minor", linestyle="--", color="gray", alpha=0.5)

    # 第四个子图：1.0-8.0 A原始流量与平滑后流量对比
    ax4.semilogy(
        time_subset, xrsb_flux_subset, label="原始数据", color="lightgreen", alpha=0.5
    )
    ax4.semilogy(time_subset, xrsb_smoothed, label="平滑后", color="green")
    ax4.legend()
    ax4.set_ylabel("Flux (W/m²)", fontsize=12, labelpad=10)
    ax4.set_title(
        "GOES-16 Solar Soft X-ray Flux (1.0-8 Å))", fontsize=14, fontweight="bold"
    )
    ax4.grid(True, linestyle="--", alpha=0.5)
    ax4.xaxis.set_minor_locator(mdates.MinuteLocator())
    ax4.xaxis.grid(True, which="minor", linestyle="--", color="gray", alpha=0.5)

    plt.xticks(rotation=45, ha="right")

    plt.tight_layout()

    # plt.savefig('SXR to HXR 2.png', dpi=300)

    plt.show()
