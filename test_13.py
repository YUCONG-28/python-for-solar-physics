# -*- coding: utf-8 -*-
"""
Created on Sun May 18 22:38:21 2025

@author: 李
"""

import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示异常

if __name__ == "__main__":
    file_path = 'd:/Flare/dn_xrsf-l2-flx1s_g16_d20240808_v2-2-0.nc'
    ds = xr.open_dataset(file_path)
    print(ds)
    ds = xr.decode_cf(ds)
    condition = (ds.time)
    start_time = "2024-08-08T19:00:00"
    end_time = "2024-08-08T20:00:00"
    ds_subset = ds.sel(time=slice(start_time, end_time))
    time_subset = ds_subset["time"]
    xrsa_flux_subset = ds_subset["xrsa_flux"]
    xrsb_flux_subset = ds_subset["xrsb_flux"]

    # 将时间转换为秒，以便进行求导计算
    time_seconds = time_subset.astype('datetime64[s]').astype(float)

    # 计算导数
    xrsa_flux_derivative = np.gradient(xrsa_flux_subset, time_seconds)
    xrsb_flux_derivative = np.gradient(xrsb_flux_subset, time_seconds)

    # 处理导数中的负值，将其替换为附近两个正值的平均值
    def replace_negatives_with_avg(arr):
        new_arr = arr.copy()
        for i in range(1, len(arr) - 1):
            if arr[i] < 0:
                left_positive = None
                right_positive = None
                # 寻找左边第一个正值
                for j in range(i - 1, -1, -1):
                    if arr[j] >= 0:
                        left_positive = arr[j]
                        break
                # 寻找右边第一个正值
                for j in range(i + 1, len(arr)):
                    if arr[j] >= 0:
                        right_positive = arr[j]
                        break
                if left_positive is not None and right_positive is not None:
                    new_arr[i] = (left_positive + right_positive) / 2
        return new_arr

    xrsa_flux_derivative = replace_negatives_with_avg(xrsa_flux_derivative)
    xrsb_flux_derivative = replace_negatives_with_avg(xrsb_flux_derivative)

    # 每5个数据点取一个进行绘图
    indices = slice(0, len(time_subset), 1)
    time_subset_downsampled = time_subset[indices]
    xrsa_flux_subset_downsampled = xrsa_flux_subset[indices]
    xrsb_flux_subset_downsampled = xrsb_flux_subset[indices]
    xrsa_flux_derivative_downsampled = xrsa_flux_derivative[indices]
    xrsb_flux_derivative_downsampled = xrsb_flux_derivative[indices]

    plt.figure(figsize=(16, 8))
    # 绘制散点图
    # plt.scatter(time_subset_downsampled, xrsa_flux_subset_downsampled, label='0.5-4.0 A', s=20)
    # plt.scatter(time_subset_downsampled, xrsb_flux_subset_downsampled, label='1.0-8.0 A', s=20)

    # 绘制导数散点图
    #plt.plot(time_subset_downsampled, xrsa_flux_derivative_downsampled, label='Derivative of 0.5-4.0 A')
    plt.plot(time_subset_downsampled, xrsb_flux_derivative_downsampled, label='Derivative of 1.0-8.0 A')

    plt.legend()

    plt.xlabel("Time (UTC)", fontsize=12, labelpad=10)
    plt.ylabel("Flux (W/m²) / Derivative", fontsize=12, labelpad=10)
    plt.title("GOES-16 Solar Soft X-ray Flux (0.5-4 Å)   2024-08-08", fontsize=14, fontweight="bold")
    plt.grid(True, linestyle="--", alpha=0.5)
    ax = plt.gca()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=5))

    # 添加 x 轴每隔 1 分钟的小竖线
    ax.xaxis.set_minor_locator(mdates.MinuteLocator())
    ax.xaxis.grid(True, which='minor', linestyle='--', color='gray', alpha=0.5)

    plt.xticks(rotation=45, ha="right")
    title = "SXR"
    # plt.savefig(f'{title}.png', dpi=300)

    plt.show()