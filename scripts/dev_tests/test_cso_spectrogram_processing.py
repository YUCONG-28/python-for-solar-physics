# -*- coding: utf-8 -*-
# 模块用途: 测试 CSO 射电动态频谱处理和绘图行为。
# 主要输入: CSO 测试频谱数据。
# 主要输出/运行说明: 输出测试频谱图或控制台诊断信息。
"""
Created on Sun Nov 23 00:19:30 2025

@author: Severus
"""

import datetime
import time

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import rebin
from astropy.io import fits
from tqdm import tqdm

from solar_toolkit.path_config import load_script_config


# 计时装饰器，用于测量函数运行时间
def timing_decorator(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"{func.__name__} 运行时间: {end_time - start_time:.4f} 秒")
        return result

    return wrapper


class spectrogram:
    def __init__(
        self,
        data=None,
        time=None,
        freq=None,
        polar=None,
        dateobs=None,
        unit=None,
        obsdev=None,
        dt_base=None,
    ):
        for name, value, expected_type in [
            ("data", data, np.ndarray),
            ("time", time, np.ndarray),
            ("freq", freq, np.ndarray),
            ("polar", polar, str),
            ("dateobs", dateobs, str),
            ("unit", unit, str),
            ("obsdev", obsdev, str),
            ("dt_base", dt_base, datetime.datetime),
        ]:
            if value is not None and isinstance(value, expected_type):
                setattr(self, name, value)
            else:
                setattr(self, name, None)


@timing_decorator
def readcso_spectrofits(fn):
    hdu = None
    try:
        hdu = fits.open(fn)
        header = hdu[0].header
        data = hdu[0].data
        time = np.ravel(hdu[1].data["time"])
        freq = np.ravel(hdu[1].data["frequency"])
        dateobs = header.get("DATE-OBS") or header.get("DATE_OBS")
        datet0 = datetime.datetime.fromisoformat(dateobs[0:10])

        if time[0] < 0:
            datexx = datetime.datetime.fromisoformat(
                dateobs[0:10]
            ) + datetime.timedelta(days=1)
            dateobs = datexx.isoformat()

        polars = header["POLARIZA"]
        if header["NAXIS"] == 3 and polars == "RCP and LCP":
            polars = "RL"

        try:
            unit = header["BUNIT"]
        except:
            unit = header["QUANTITY"]

        dataout = []
        if data.ndim == 2:
            dataout.append(
                spectrogram(
                    data=data,
                    time=time,
                    freq=freq,
                    polar=polars,
                    dateobs=dateobs,
                    unit=unit,
                    dt_base=datet0,
                )
            )
            print(f"读取单偏振数据：{polars}")
        elif data.ndim == 3:
            arr_n = data.shape[0]
            # 使用tqdm显示进度
            for ii in tqdm(range(arr_n), desc="读取偏振数据"):
                polar = polars[ii] * 2
                dataout.append(
                    spectrogram(
                        data=data[ii, :, :],
                        time=time,
                        freq=freq,
                        polar=polar,
                        dateobs=dateobs,
                        unit=unit,
                        dt_base=datet0,
                    )
                )

        return dataout

    except FileNotFoundError:
        print(f"文件未找到：{fn}")
        raise
    except Exception as e:
        print(f"数据处理错误：{e}")
        raise
    finally:
        if hdu is not None:
            hdu.close()


# 优化索引查找算法，使用更高效的numpy函数
def findindex(tx, t1, t2):
    """查找时间/频率范围内的整数索引"""
    if t1 >= t2:
        t1, t2 = t2, t1  # 自动交换，避免逻辑错误

    # 使用numpy的searchsorted更高效地查找索引
    start_idx = np.searchsorted(tx, t1, side="left")
    end_idx = np.searchsorted(tx, t2, side="right") - 1

    # 边界检查
    start_idx = max(0, min(start_idx, len(tx) - 1))
    end_idx = max(0, min(end_idx, len(tx) - 1))

    # 确保起始索引 <= 结束索引
    if start_idx > end_idx:
        start_idx = end_idx

    return start_idx, end_idx


@timing_decorator
def slice_data(Spec, t1, t2, f1, f2):
    datet0 = Spec.dt_base
    tt = Spec.time  # 时间数组（秒）
    Z = Spec.data  # 数据数组 [频率, 时间]
    freq = Spec.freq  # 频率数组（MHz）

    # 计算时间范围对应的秒数
    t1_sec = (t1 - datet0).total_seconds()
    t2_sec = (t2 - datet0).total_seconds()

    # 获取时间索引
    t_start_idx, t_end_idx = findindex(tt, t1_sec, t2_sec)
    # 切片时间数组和数据（使用整数索引）
    tt_out = tt[t_start_idx : t_end_idx + 1]
    Z = Z[:, t_start_idx : t_end_idx + 1]  # [频率, 时间]

    # 处理频率范围
    f_start_idx, f_end_idx = findindex(freq, f1, f2)
    freq_out = freq[f_start_idx : f_end_idx + 1]
    Z = Z[f_start_idx : f_end_idx + 1, :]  # [频率, 时间]

    return Z, tt_out, freq_out


# 优化的偏振比值计算函数，采用全向量化操作提升速度
@timing_decorator
def calculate_polarization_ratio(Z_r, Z_l, epsilon=1e-10):
    """
    计算偏振比值 (R-L)/(R+L) 并显示进度

    参数:
        Z_r: 右旋数据数组
        Z_l: 左旋数据数组
        epsilon: 防止除零的小值
    """
    # 确保数组内存连续，提高计算效率
    Z_r = np.ascontiguousarray(Z_r)
    Z_l = np.ascontiguousarray(Z_l)

    # 确保数据类型一致且适合计算（使用32位浮点数减少计算量）
    if Z_r.dtype != np.float32 or Z_l.dtype != np.float32:
        Z_r = Z_r.astype(np.float32, copy=False)
        Z_l = Z_l.astype(np.float32, copy=False)

    # 显示计算进度
    with tqdm(total=1, desc="计算偏振比值") as pbar:
        # 全数组向量化计算，避免循环开销
        numerator = Z_r - Z_l
        denominator = Z_r + Z_l + epsilon
        ratio = numerator / denominator
        pbar.update(1)

    return ratio


@timing_decorator
def process_and_plot_data(
    data_list,
    t_start,
    t_end,
    f_start,
    f_end,
    rebin_factor,
    plot_ll=True,
    plot_rr=True,
    plot_ratio=True,
    plot_sum=True,
):
    """
    处理并绘制频谱图，支持灵活控制绘制的子图类型

    参数:
        data_list: readcso_spectrofits返回的spectrogram列表
        t_start/t_end: 时间范围（datetime对象）
        f_start/f_end: 频率范围（MHz）
        rebin_factor: 重采样因子
        plot_ll: 是否绘制左旋(LL)频谱图（默认True）
        plot_rr: 是否绘制右旋(RR)频谱图（默认True）
        plot_ratio: 是否绘制偏振比(R-L)/(R+L)图（默认True）
        plot_sum: 是否绘制左旋+右旋(LL+RR)频谱图（默认True）
    """
    # 分离LL和RR数据
    cso_l = None
    cso_r = None
    for data in data_list:
        if "LL" in data.polar:
            cso_l = data
        elif "RR" in data.polar:
            cso_r = data

    if not (cso_l and cso_r):
        raise ValueError("未找到完整的左旋（LL）和右旋（RR）数据")

    # 截取数据
    print("正在切片左旋数据...")
    Z_l, tt_l, freq_l = slice_data(cso_l, t_start, t_end, f_start, f_end)
    print("正在切片右旋数据...")
    Z_r, tt_r, freq_r = slice_data(cso_r, t_start, t_end, f_start, f_end)

    # 校验时间/频率轴一致性
    assert np.allclose(tt_l, tt_r), "左旋/右旋时间轴不一致"
    assert np.allclose(freq_l, freq_r), "左旋/右旋频率轴不一致"

    # 计算重采样因子（避免不必要的大因子）
    t_bin = max(1, len(tt_l) // rebin_factor)
    f_bin = max(1, len(freq_l) // rebin_factor)
    print(f"重采样因子 - 时间: {t_bin}, 频率: {f_bin}")

    # 重采样（使用tqdm显示进度）
    print("正在重采样数据...")
    with tqdm(total=4, desc="重采样进度") as pbar:
        Z_l_rebin = rebin.rebin(Z_l, (f_bin, t_bin))
        pbar.update(1)
        Z_r_rebin = rebin.rebin(Z_r, (f_bin, t_bin))
        pbar.update(1)
        tt_rebin = rebin.rebin(tt_l, (t_bin,))
        pbar.update(1)
        freq_rebin = rebin.rebin(freq_l, (f_bin,))
        pbar.update(1)

    # 计算偏振比值
    ratio = calculate_polarization_ratio(Z_r_rebin, Z_l_rebin)

    # 计算左旋+右旋的和（新增）
    Z_sum_rebin = Z_l_rebin + Z_r_rebin
    epsilon = 1e-10  # 防止log10(0)的数值保护

    # 转换时间轴为datetime
    print("正在准备绘图数据...")
    dtime0 = cso_l.dt_base
    datetime_tt = dtime0 + np.array([datetime.timedelta(seconds=t) for t in tt_rebin])
    xx, yy = np.meshgrid(datetime_tt, freq_rebin)

    # 收集需要绘制的子图配置
    plot_items = []
    if plot_ll:
        Z_ll_log = np.log10(Z_l_rebin + epsilon)
        vmin_ll = np.percentile(Z_ll_log, 6)
        vmax_ll = np.percentile(Z_ll_log, 99.9)
        plot_items.append(
            {
                "data": Z_ll_log,
                "title": f"CSO/CBSm {cso_l.polar} {cso_l.dateobs[:10]}",
                "ylabel": "Frequency (MHz)",
                "cmap": "jet",
                "vmin": vmin_ll,
                "vmax": vmax_ll,
                "cbar_label": r"log$_{10}$ Brightness Temperature (K)",
            }
        )
    if plot_rr:
        Z_rr_log = np.log10(Z_r_rebin + epsilon)
        vmin_rr = np.percentile(Z_rr_log, 6)
        vmax_rr = np.percentile(Z_rr_log, 99.9)
        plot_items.append(
            {
                "data": Z_rr_log,
                "title": f"CSO/CBSm {cso_r.polar} {cso_r.dateobs[:10]}",
                "ylabel": "Frequency (MHz)",
                "cmap": "jet",
                "vmin": vmin_rr,
                "vmax": vmax_rr,
                "cbar_label": r"log$_{10}$ Brightness Temperature (K)",
            }
        )
    if plot_sum:  # 新增：左旋+右旋的配置
        Z_sum_log = np.log10(Z_sum_rebin + epsilon)
        vmin_sum = np.percentile(Z_sum_log, 7)
        vmax_sum = np.percentile(Z_sum_log, 99)
        plot_items.append(
            {
                "data": Z_sum_log,
                "title": f"CSO/CBSm LL+RR {cso_l.dateobs[:10]}",
                "ylabel": "Frequency (MHz)",
                "cmap": "jet",
                "vmin": vmin_sum,
                "vmax": vmax_sum,
                "cbar_label": r"log$_{10}$ Brightness Temperature (K)",
            }
        )
    if plot_ratio:
        plot_items.append(
            {
                "data": ratio,
                "title": "CSO/CBSm Polarization (R-L)/(R+L)",
                "ylabel": "Frequency (MHz)",
                "cmap": "bwr",
                "vmin": -1,
                "vmax": 1,
                "cbar_label": "Polarization Ratio",
            }
        )

    # 无绘图项时直接返回
    if not plot_items:
        print("未选择任何绘图项，跳过绘图")
        return

    # 动态创建子图（根据需要绘制的数量调整）
    n_plots = len(plot_items)
    fig, axs = plt.subplots(
        n_plots, 1, figsize=(12, 3 * n_plots), sharex=True, sharey=True
    )
    fig.subplots_adjust(hspace=0.15)

    # 兼容单张子图的情况
    if n_plots == 1:
        axs = [axs]

    # 绘制所有选中的子图
    print("正在绘制图像...")
    for idx, item in enumerate(plot_items):
        ax = axs[idx]
        im = ax.pcolormesh(
            xx,
            yy,
            item["data"][:-1, :-1],
            shading="flat",
            cmap=item["cmap"],
            vmin=item["vmin"],
            vmax=item["vmax"],
        )
        ax.set_title(item["title"], fontsize=12)
        ax.set_ylabel(item["ylabel"], fontsize=10)
        # 添加颜色条
        cbar = fig.colorbar(im, ax=ax, pad=0.01)
        cbar.set_label(item["cbar_label"], fontsize=9)
        # 刻度样式
        ax.tick_params(axis="x", labelsize=8, rotation=0)
        ax.tick_params(axis="y", labelsize=8)

    # 统一设置x轴格式
    axs[-1].set_xlabel("Time (UT)", fontsize=10)
    for ax in axs:
        ax.xaxis.set_major_locator(mdates.SecondLocator(interval=10))
        ax.xaxis.set_minor_locator(mdates.SecondLocator(interval=2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))

    plt.tight_layout()
    print("绘图完成，显示图像...")
    plt.show()


if __name__ == "__main__":
    # 记录总运行时间
    total_start_time = time.time()

    # 替换为实际文件路径
    path_config = load_script_config(
        "test_cso_spectrogram_processing",
        {
            "file_path": (
                r"D:\spike_topping_type_III\2025\20250124"
                r"\OROCH_MWRS01_SRSP_L1_05M_20250124044743_V01.01.fits"
            )
        },
    )
    file_path = path_config["file_path"]

    print(f"开始处理文件: {file_path}")
    data_list = readcso_spectrofits(file_path)

    # 设置时间和频率范围
    t_start = datetime.datetime(2025, 1, 24, 4, 46, 0)  # 示例时间，可调整
    t_end = datetime.datetime(2025, 1, 24, 4, 48, 0)  # 示例时间，可调整
    f_start = 0  # MHz
    f_end = 600  # MHz
    rebin_factor = 8000  # 重采样因子，可调整

    # ========== 核心控制：调整是否绘制各类图 ==========
    # 示例1：默认绘制所有图（LL、RR、LL+RR、偏振比）
    # process_and_plot_data(data_list, t_start, t_end, f_start, f_end, rebin_factor)

    # 示例2：只绘制LL+RR和偏振比（注释掉示例1，打开此段）
    process_and_plot_data(
        data_list,
        t_start,
        t_end,
        f_start,
        f_end,
        rebin_factor,
        plot_ll=False,
        plot_rr=False,
        plot_ratio=True,
        plot_sum=True,
    )

    # 示例3：只绘制左旋和右旋（注释掉示例1，打开此段）
    # process_and_plot_data(data_list, t_start, t_end, f_start, f_end, rebin_factor,
    #                       plot_ll=True, plot_rr=True, plot_ratio=False, plot_sum=False)

    # 输出总运行时间
    total_end_time = time.time()
    print(f"总运行时间: {total_end_time - total_start_time:.4f} 秒")
