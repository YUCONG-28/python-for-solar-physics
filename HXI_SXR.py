# -*- coding: utf-8 -*-
# 模块用途: 对比 ASO-S/HXI 硬 X 射线与 GOES SXR 时间演化。
# 主要输入: HXI 光变数据和 GOES 软 X 射线数据。
# 主要输出/运行说明: 输出多能段光变对比图，辅助耀斑能量释放分析。
"""
Created on Sun Mar  9 20:39:21 2025

@author: 21129
"""

from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from astropy.io import fits

if __name__ == "__main__":
    file_path = Path("D:/Flare/hxi_qld_levq1_20240808_19_hly_v03.fits")

    hdul = fits.open(file_path)

    plt.figure(figsize=(25, 16))

    ax1 = plt.gca()
    h1 = hdul[1].data
    h2 = hdul[2].data
    h3 = hdul[3].data
    CTS = h3["CTS_THINTHICK"]
    C0 = CTS[:, 0]
    C1 = CTS[:, 1]
    C2 = CTS[:, 2]
    C3 = CTS[:, 3]
    base_time = datetime(2018, 12, 31, 16, 00, 00)
    utc_times = [base_time + timedelta(seconds=t) for t in h1.TIME]
    nptimes = [np.datetime64(t) for t in utc_times]
    plt.sca(ax1)
    plt.semilogy(utc_times, C0, label="HXI 10-20 keV")
    plt.semilogy(utc_times, C1, label="HXI 20-50 keV")
    plt.semilogy(utc_times, C2, label="HXI 50-100 keV")
    plt.semilogy(utc_times, C3, label="HXI 100-300 keV")
    plt.ylabel("Counts s\u207B\u00B9 detector\u207B\u00B9", fontsize=22, labelpad=12)
    plt.legend(loc="upper left", ncol=1, fontsize=18)

    # ax2 = ax1.twinx()
    # file_path = 'd:/Flare/dn_xrsf-l2-flx1s_g16_d20240808_v2-2-0.nc'
    # ds = xr.open_dataset(file_path)
    # time = ds["time"].values
    # xrsa_flux = ds["xrsa_flux"].values
    # xrsb_flux = ds["xrsb_flux"].values
    # dtype = "datetime64[ns]"
    # x = [datetime.utcfromtimestamp(t.astype("datetime64[ns]").astype("int64") / 1e9) for t in time]
    # start_time = datetime(2024, 8, 8, 19,00,00)
    # end_time = datetime(2024, 8, 8, 20,00,00)
    # plt.sca(ax2)
    # plt.xlim(start_time, end_time)
    # plt.semilogy(time,xrsa_flux,label = '0.5-4.0 A',color = 'pink')
    # plt.semilogy(time,xrsb_flux,label = '1.0-8.0 A',color = 'purple')
    # plt.legend(loc='upper right', ncol = 1,fontsize=18)
    # plt.ylabel("flux",fontsize = 22, labelpad = 12,rotation = 270)

    # 添加 x 轴每隔 1 分钟的小竖线
    ax1.xaxis.set_minor_locator(mdates.MinuteLocator())
    ax1.xaxis.grid(True, which="minor", linestyle="--", color="gray", alpha=0.5)

    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    plt.gcf().autofmt_xdate()
    plt.xlabel("time", fontsize=22, labelpad=12)
    title = "Soft X-ray Flux & HXI lightcurve"
    plt.title("Soft X-ray Flux & HXI lightcurve", fontsize=22, fontweight="bold")

    # 保存图片
    # plt.savefig('HXR.png', dpi=300)

    plt.show()
