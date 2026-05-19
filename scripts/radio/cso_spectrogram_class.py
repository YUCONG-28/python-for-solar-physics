#!/usr/bin/env python3
# 模块用途: 提供可复用的 CSO 频谱绘图类，支持重采样和时间-频率显示。
# 主要输入: CSO 频谱数据文件和绘图参数。
# 主要输出/运行说明: 输出动态频谱图，适合作为脚本或模块调用。
"""
Created on Sat Dec 13 19:09:12 2025

@author: ninghao
"""

import datetime

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import rebin
from astropy.io import fits

from solar_toolkit.path_config import load_script_config

# %%


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
        # 使用列表推导式简化属性赋值
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
                # 确保所有属性都有一个默认值，即使输入不符合要求
                setattr(self, name, None)


def readcso_spectrofits(fn):
    hdu = None  # 1. 初始化 hdu 为 None
    try:
        # --- 2. 尝试打开文件 ---
        hdu = fits.open(fn)

        # --- 3. 所有读取和处理数据的代码都放在这里 ---
        header = hdu[0].header
        data = hdu[0].data
        print(f"data shape: : {data.shape}. \n")
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
        #### 特别注意，统一偏振表示格式；?????????
        if header["NAXIS"] == 3:
            if polars == "RCP and LCP":
                polars = polars[0] + polars[8]
        try:
            unit = header["BUNIT"]
        except Exception:
            unit = header["QUANTITY"]
        if data.ndim == 2:
            arr_n = 1
            dataout = [
                spectrogram(
                    data=data,
                    time=time,
                    freq=freq,
                    polar=polars,
                    dateobs=dateobs,
                    unit=unit,
                )
            ]
            print("just one data have been read. polar is " + polars)
        if data.ndim == 3:
            #### 偏振放在这个维度上
            arr_n = data.shape[0]
            dataout = []
            for ii in range(arr_n):
                polar = polars[ii] + polars[ii]
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
                print(polar + f" polarize data have been read {ii} in {arr_n} .")

        return dataout

    except FileNotFoundError:
        # 捕获特定的文件打开错误
        print(f"Cant find file: {fn}")
        raise
    except Exception as e:
        # 捕获所有其他错误 (如 KeyError, IndexError, TypeError)
        print(f"Error during data processing for {fn}: {e}")
        # 如果是处理错误，同样要重新抛出，让调用者知道失败了
        raise

    finally:
        # --- 5. 保证关闭句柄 ---
        if hdu is not None:
            hdu.close()
            # print(f"文件句柄已通过 finally 块保证关闭。") # 可选，用于调试


def findindex(tx, t1, t2):
    index1 = []
    index2 = []
    if t1 >= t2:
        print("t1 >= t2 is wrong!")
        return [], []
    else:
        index = np.where(tx >= t1)
        if len(index[0]) > 0:
            index1 = [index[0][0]]
        else:
            print("t1 > tx[-1] is wrong!!")
            return [], []
        index = np.where(tx >= t2)
        if len(index[0]) > 0:
            if index[0][0] <= 0:
                print("t2 <= tx[0] is wrong!!!")
                return [], []
            else:
                index2 = [index[0][0]]
        else:
            if len(index1) > 0:
                index2 = [len(tx) - 1]
            else:
                print("t2 > tx[-1] is wrong!!!!")
                return [], []
        return index1, index2


# ----------------------------------------------------
def slice_data(Spec, t1, t2, f1, f2):
    # try :
    #     ndata = len( Spec ) ## original data number depend on polar
    # except :
    #     print('no data! please load data by readdata()')
    #     print('please first input radio spectral data fits file paths')
    #     return 0

    DATE_OBS = Spec.dateobs
    datet0 = datetime.datetime.fromisoformat(DATE_OBS[0:10])
    tt = Spec.time
    Z = Spec.data
    #                   print('tt length is {}'.format(len(tt)) )
    freq = Spec.freq
    POLARIZA = Spec.polar
    _unused_unit = Spec.unit
    _unused_polss = POLARIZA[0]

    # select time
    ttch = t1 - datet0
    ttch1 = ttch.total_seconds()
    ttch = t2 - datet0
    ttch2 = ttch.total_seconds()
    tindex1, tindex2 = findindex(tt, ttch1, ttch2)
    if len(tindex1) > 0:
        tindex1 = tindex1[0]
    else:
        tindex1 = 0
    if len(tindex2) > 0:
        tindex2 = tindex2[0]
    else:
        tindex2 = len(tt) - 1
    tt_out = tt[tindex1 : tindex2 + 1]
    Z = Z[:, tindex1 : tindex2 + 1]
    # select freq
    findex1, findex2 = findindex(freq, f1, f2)
    if len(findex1) > 0:
        findex1 = findex1[0]
    else:
        findex1 = 0
        print("freq start point set wrong value!")
    if len(findex2) > 0:
        findex2 = findex2[0]
    else:
        findex2 = len(freq) - 1
        print("freq end point set wrong value!")
    # freq_out=freq
    freq_out = freq[findex1 : findex2 + 1]
    Z = Z[findex1 : findex2 + 1, :]

    # if tt[0] < 0 :
    #     dtime0 = dtime0 + datetime.timedelta(days = 1 )

    return Z, tt_out, freq_out


if __name__ == "__main__":
    # DATA DIR
    path_config = load_script_config(
        "cso_spectrogram_class",
        {
            "file_path": (
                r"D:\spike_topping_type_III\20250503"
                r"\OROCH_MWRS01_SRSP_L1_05M_20250503072013_V01.01.fits"
            )
        },
    )
    file_path = path_config["file_path"]
    dataout = readcso_spectrofits(file_path)

    t_start = datetime.datetime(year=2025, month=5, day=3, hour=7, minute=21, second=16)
    t_end = datetime.datetime(year=2025, month=5, day=3, hour=7, minute=21, second=20)

    fstart = 220  # MHz
    fend = 280  # MHz

    rebinNum = 6000

    npolar = len(dataout)
    figsizes = (10.0, 4.0 * npolar)
    fig, axs = plt.subplots(npolar, 1, figsize=figsizes)

    for i, data in enumerate(dataout):
        Z, tt, freq = slice_data(data, t_start, t_end, fstart, fend)
        print(f"sliced data shape: {Z.shape}")
        # tbin = int(  len( data.time ) / rebinNum  )

        # fbin = int(  len( data.freq ) / rebinNum  )
        # Z = rebin.rebin( Z, factor=( fbin, tbin ) ) # Z 维度：[频率, 时间]
        # tt = rebin.rebin( tt, factor=( tbin, ) )
        # freq = rebin.rebin( freq, factor=( fbin, ) )
        # print(f"rebinned data shape: {Z.shape}, {tt.shape}, {freq.shape}.")

        tbin = int(len(tt) / rebinNum)

        fbin = int(len(freq) / rebinNum)
        # print(tbin,fbin)
        if fbin == 0:
            fbin = fbin + 1
        if tbin == 0:
            tbin = tbin + 1
        Z = rebin.rebin(Z, factor=(fbin, tbin))  # Z 维度：[频率, 时间]
        tt = rebin.rebin(tt, factor=(tbin,))
        freq = rebin.rebin(freq, factor=(fbin,))
        print(f"rebinned data shape: {Z.shape}, {tt.shape}, {freq.shape}.")

        # xx, yy = np.meshgrid(tt, freq)
        # plt.pcolormesh(xx, yy, Z,  cmap = 'jet' ,vmin=2,vmax=6)

        Z = np.log10(Z)
        v_min = np.percentile(Z.flatten(), 0.01)
        v_max = np.percentile(Z.flatten(), 99.94)

        # 将秒数时间轴 tt 转换为 datetime 对象数组
        # DATE_OBS = data.dateobs
        dtime0 = data.dt_base
        datetime_tt = np.array([dtime0 + datetime.timedelta(seconds=t) for t in tt])
        xx, yy = np.meshgrid(datetime_tt, freq)

        ax = axs[i]
        psm = ax.pcolormesh(
            xx,
            yy,
            Z[:-1, :-1],
            vmin=v_min,
            vmax=v_max,
            shading="flat",
            cmap="jet",
            rasterized=True,
        )
        cbar = fig.colorbar(psm, ax=ax)

        cbar.set_label("Brightness Temperature (K)", fontsize=11)

        ax.set_ylabel("Frequency (MHz)", fontsize=11)

        ax.set_title(
            "CSO Radio Spectrum " + data.polar[0] + " " + data.dateobs[0:10],
            fontsize=12,
        )

        ax.xaxis.set_minor_locator(mdates.SecondLocator(interval=1))

        formatter = mdates.DateFormatter("%H:%M:%S")  # .%f')
        ax.xaxis.set_major_formatter(formatter)

        # 减小刻度标签字体，为标签留出更多空间
        ax.tick_params(axis="x", labelsize=8)

        # fig = ax.figure
        # fig.autofmt_xdate(rotation=45) # 显式设置旋转角度为 45 度

    axs[1].set_xlabel("Time (UT)", fontsize=11)
    plt.show()
