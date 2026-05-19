# 模块用途: 读取并绘制 GOES 软 X 射线 NetCDF 光变数据。
# 主要输入: GOES SXR NetCDF 产品。
# 主要输出/运行说明: 输出 SXR 光变曲线，用于耀斑等级和时间演化分析。
"""
Created on Tue Mar  4 09:21:34 2025

@author: 李
"""

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import xarray as xr

from solar_toolkit.path_config import load_script_config

plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示异常

if __name__ == "__main__":
    path_config = load_script_config(
        "goes_sxr_lightcurve_plot",
        {"file_path": "d:/Flare/dn_xrsf-l2-flx1s_g16_d20240808_v2-2-0.nc"},
    )
    file_path = Path(path_config["file_path"])
    ds = xr.open_dataset(file_path)
    print(ds)
    ds = xr.decode_cf(ds)
    condition = ds.time
    start_time = "2024-08-08T19:00:00"
    end_time = "2024-08-08T20:00:00"
    ds_subset = ds.sel(time=slice(start_time, end_time))
    time_subset = ds_subset["time"]
    xrsa_flux_subset = ds_subset["xrsa_flux"]
    xrsb_flux_subset = ds_subset["xrsb_flux"]

    plt.figure(figsize=(16, 8))
    plt.semilogy(time_subset, xrsa_flux_subset, label="0.5-4.0 A")
    plt.semilogy(time_subset, xrsb_flux_subset, label="1.0-8.0 A")
    plt.legend()

    plt.xlabel("Time (UTC)", fontsize=12, labelpad=10)
    plt.ylabel("Flux (W/m²)", fontsize=12, labelpad=10)
    plt.title(
        "GOES-16 Solar Soft X-ray Flux (0.5-4 Å)   2024-08-08",
        fontsize=14,
        fontweight="bold",
    )
    plt.grid(True, linestyle="--", alpha=0.5)
    ax = plt.gca()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=5))

    # 添加 x 轴每隔 1 分钟的小竖线
    ax.xaxis.set_minor_locator(mdates.MinuteLocator())
    ax.xaxis.grid(True, which="minor", linestyle="--", color="gray", alpha=0.5)

    plt.xticks(rotation=45, ha="right")
    title = "SXR"
    plt.savefig(f"{title}.png", dpi=300)

    plt.show()
