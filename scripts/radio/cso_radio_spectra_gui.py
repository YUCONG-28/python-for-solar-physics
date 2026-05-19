# 模块用途: 提供 CSO 射电频谱交互式 GUI，用于检查动态频谱、偏振和流量演化。
# 主要输入: CSO 射电观测数据文件。
# 主要输出/运行说明: 启动桌面 GUI；需要 PyQt/绘图库环境支持。
"""
Created on Tue May  3 10:22:08 2022
add flux plot 2024-05-28


add polarization 2025-04-21
2025-04-25  repaire P colorbar
2025-06-16 add pre next frame plot
2025-06-16 add save data in fits
2025-08-16  repaire colorbar set

2025-10-09 plot flux 修正选择


"""

import datetime
import os
import sys
from fnmatch import fnmatch

import astropy.constants as const
import matplotlib.cm as mplcm
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import rebin
from astropy.io import fits

# from PyQt5 import uic
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.ticker import AutoMinorLocator
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QDateTime, Qt
from PyQt5.QtGui import QColor, QDoubleValidator, QIntValidator, QPalette
from scipy import optimize

## 统一使用 一级导入 datetime


# __all__ = ['spectrogram', 'SpectraData']
## fn 含有路径，如果不含路径 搜索当前目录
def file_search(fn, subdir=0):
    findfiles = []
    allv = 0
    if subdir == 1:
        allv = 1
    ## split dir  and base name
    target_dir, infname = os.path.split(fn)
    if len(target_dir) == 0:
        target_dir = "./"
    ## check dir
    walk_generator = os.walk(target_dir)
    for root_path, _dirs, files in walk_generator:
        if allv == 1:
            if len(files) < 1:
                continue
            for file in files:
                if fnmatch(file, infname):
                    findfiles.append(os.path.join(root_path, file))
        else:
            if fnmatch(root_path, target_dir):
                if len(files) < 1:
                    continue
                for file in files:
                    if fnmatch(file, infname):
                        findfiles.append(os.path.join(root_path, file))
    findfiles.sort()
    return findfiles


#### findindex rutine==================================
## 在 tx 中找出 t1 t2的索引
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


def subtrBackgroundminv(data):
    """
    Parameters
    ----------
    data : TYPE
        DESCRIPTION.
        2D (nrow, ncol ) Êý×é
    Returns
    -------
    datasmin : TYPE
        DESCRIPTION.

    """
    rowmin = np.min(data, axis=1)
    nrow, ncol = np.shape(data)
    rowmin[rowmin < 0] = 0
    datasmin = data - np.repeat(np.reshape(rowmin, (nrow, 1)), ncol, axis=1)
    return datasmin


def creatFitsFile(ttx, frequency, dataRL, polssv, datet0, fitsname, BJT2UTC=0):
    # creatFitsFile( ttx, frequency, dataRL, df, et, datedd,  fitsname, BJT2UTC = 0):

    et = np.mean(ttx[1::] - ttx[0:-1:])
    df = np.mean(frequency[1::] - frequency[0:-1:])

    tts = ttx - BJT2UTC
    nfreq = len(frequency)
    ### time shift by seconds from this day 00:00:00
    nt = len(tts)
    nows = datetime.datetime.now()
    datetstart = datet0

    # datetime.datetime(datedd[0],datedd[1],datedd[2],0,0,0)
    s2 = datetstart + datetime.timedelta(seconds=tts[0])
    s3 = datetstart + datetime.timedelta(seconds=tts[-1])

    nowsutc = nows - datetime.timedelta(hours=8)
    creattimes = nowsutc.isoformat()[:-3] + "Z"
    obstimes = s2.isoformat()[:-3] + "Z"
    startTs = s2.isoformat()[:-3] + "Z"
    endTs = s3.isoformat()[:-3] + "Z"
    ttform = str(nt) + "D"
    ffform = str(nfreq) + "D"
    ### creat fits file na me
    # fitsname = outdir + 'OROCH_MWRS01_SRSP_L1_05M_'+ s2.strftime('%Y%m%d%H%M%S') + '_V01.01.fits'
    # fitsname = outdir + 'OROCH_MWRS01_SRSP_L1_STP_'+ s2.strftime('%Y%m%d%H%M%S') + '_V01.01.fits'
    #  2024-03-07 STP -> 05M
    # fitsname = outdir + 'OROCH_MWRS01_SRSP_L1_05M_'+ s2.strftime('%Y%m%d%H%M%S') + '_V01.01.fits'

    if os.path.exists(fitsname):
        os.remove(fitsname)

    # OROCH_MWRSnn_SRSP_L1_05M
    ### creat Primary header
    headerm = fits.Header()
    ##### 添加 主表的 关键字信息 关键字大小写不敏感
    ### 需要变化的关键字
    ### 1 保留关键字===============
    # headerm['FILENAME'] = fitsname
    headerm["ORIGIN"] = "Chinese Meridian Project for Space Environment Monitoring"
    headerm["TELESCOP"] = ("MWRS", "Metric Wave Solar Radio Spectrometer")
    headerm["OBJECT"] = ("SUN", "object description")
    headerm["DATE"] = creattimes
    headerm["DATE-OBS"] = obstimes
    headerm["BUNIT"] = ("SolarFluxUnit(SFU)", "quantities and units")
    headerm["COMMENT"] = (
        "The voltage signals after FFT transmformation, stored as 3-dimesion data array."
    )

    ### 2 自定义通用关键字==========================================================
    headerm["DEV_LOC"] = ("OROCH", "location of the telescope")
    headerm["DEV_LON"] = (122.31, "[degree] east longitude")
    headerm["DEV_LAT"] = (36.84, "[degree] North latitude")
    headerm["DEV_ALT"] = (53.00, "[m] altitude,height above see level")
    headerm["CONTENT"] = "Solar Radio Spectrum"
    # headerm['CONTACT'] = 'ShiWei Feng (winfeng@sdu.edu.cn)'
    headerm["CONTACT"] = "Zhao Wu (wuzhao@sdu.edu.cn)"
    headerm["TIMESYS"] = "UTC"
    headerm["VERSION"] = ("V01.01", "build version of the file")
    headerm["PRODUCER"] = ("OROCH", " at WeiHai operated by ShanDong University")
    headerm["DATE_BEG"] = startTs
    headerm["DATE_END"] = endTs
    headerm["OBS_MODE"] = ("NormalMode", "operation mode of the device")
    headerm["DATA_LEV"] = ("L1", "data level")

    ### 3 辅助关键字==========================================================

    headerm["OP_PARAM"] = ("ADC: 1.25Gsps, FFT length: 16x1024, Average: 64", "")
    headerm["DEV_SPEC"] = (
        "Sensitivity=1SFU; DynamicRange>=60dB",
        "device specifications",
    )
    headerm["DEV_STAT"] = ("N", "state of the device (N/V)")
    headerm["QUAL_FLG"] = ("TBD", "data quality control information")
    headerm["POLARIZA"] = (polssv, "polarization types")
    headerm["FREQ"] = ("90~300 MHz", "frequency range of observation")
    headerm["FREQBEG"] = (f"{frequency[0]:.6f}", "[MHz] begin of frequency")
    headerm["FREQRESO"] = (f"{df:.6f}", "[MHz] frequency resolution")
    headerm["ACCU_TM"] = (f"{et * 1000:.3f}", "[ms] accumulated time")
    headerm["CAL_TEMP"] = ("T", "whether calibrated by temperature")
    #### === end main head set ==========================================

    ### make HDU
    mainHDU = fits.PrimaryHDU(header=headerm, data=dataRL)
    ###  注意字节序
    coltt = fits.Column(name="Time", format=ttform)
    colfreq = fits.Column(name="frequency", format=ffform)
    coldefs = fits.ColDefs([coltt, colfreq])

    bintable_hdu = fits.BinTableHDU.from_columns(coldefs, nrows=1)
    bintable_hdu.data["Time"] = tts
    bintable_hdu.data["frequency"] = frequency
    bintable_hdu.header["Time"] = "shift seconds of the day"
    bintable_hdu.header["freq"] = "observation frequency MHz"

    try:
        ##### creat HDUlist  include one binarytable consisted one row
        hdul = fits.HDUList([mainHDU, bintable_hdu])

        ###### write and close =====
        hdul.writeto(fitsname)
        hdul.close()
    except Exception:
        print("write fits file failed !")
        return 0
    # finfo = os.stat(fitsname)
    # filesize0 = finfo.st_size
    return 1


#### end findindex ##################
### 射电暴拟合窗口 ====
class RadioTypeIIfit(QtWidgets.QWidget):

    SignalClickClose = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Radio Type II for Height Fit")
        #####  fig 区
        self.fig = plt.figure()
        self.ax = self.fig.subplots(1, 1)
        self.canvas = FigureCanvasQTAgg(self.fig)
        # self.tt = None
        # self.ff = None
        self.dateobs = None
        self.typeIIndot = 0
        self.typeIItime = []
        self.typeIIfreq = []
        self.countj = 0  ### 记录调用次数

        ###  GUI 框架 ++++++++++++
        self.baslayout = QtWidgets.QHBoxLayout()
        self.leftw = QtWidgets.QWidget()
        self.vlayout = QtWidgets.QVBoxLayout()
        self.leftw.setLayout(self.vlayout)
        self.leftw.setFixedWidth(300)

        self.Harmboxg = QtWidgets.QGroupBox("Harmonic: ")
        self.Harmlayout = QtWidgets.QVBoxLayout()
        self.Harmboxg.setLayout(self.Harmlayout)
        self.spinBox1 = QtWidgets.QSpinBox()
        self.spinBox1.setRange(1, 20)
        self.spinBox1.setFixedHeight(40)
        fontx = self.spinBox1.font()
        fontx.setPointSize(18)
        self.spinBox1.setFont(fontx)

        self.Harmlayout.addWidget(self.spinBox1)
        self.vlayout.addWidget(self.Harmboxg)

        self.Elecboxg = QtWidgets.QGroupBox("Electron Density Model: ")
        self.Eleclayout = QtWidgets.QVBoxLayout()
        self.Elecboxg.setLayout(self.Eleclayout)
        self.comboBox = QtWidgets.QComboBox()
        self.comboBox.addItem("Newkirk")
        self.comboBox.addItem("Saito")
        self.comboBox.setFixedHeight(40)
        self.Eleclayout.addWidget(self.comboBox)
        self.vlayout.addWidget(self.Elecboxg)

        self.Foldboxg = QtWidgets.QGroupBox("Fold: ")
        self.Foldlayout = QtWidgets.QVBoxLayout()
        self.Foldboxg.setLayout(self.Foldlayout)
        self.spinBox2 = QtWidgets.QSpinBox()
        self.spinBox2.setRange(1, 20)
        self.spinBox2.setFixedHeight(40)
        self.spinBox2.setFont(fontx)

        self.Foldlayout.addWidget(self.spinBox2)
        self.vlayout.addWidget(self.Foldboxg)

        # self.labelb = QtWidgets.QLabel()
        # self.labelb.setText(' Harmonics : ')
        # self.spinBox1 = QtWidgets.QSpinBox()
        # self.spinBox1.setRange(1,20)
        # self.spinBox1.setFixedHeight( 40 )
        # fontx = self.spinBox1.font()
        # fontx.setPointSize(18)
        # self.spinBox1.setFont( fontx )
        # self.vlayout.addWidget( self.labelb  )
        # self.vlayout.addWidget( self.spinBox1  )

        # self.labelc = QtWidgets.QLabel()
        # self.labelc.setText('     Folds : ')
        # self.spinBox2 = QtWidgets.QSpinBox()
        # self.spinBox2.setRange(1,20)
        # self.spinBox2.setFixedHeight( 40 )
        # self.spinBox2.setFont( fontx )

        # self.vlayout.addWidget( self.labelc  )
        # self.vlayout.addWidget( self.spinBox2  )

        self.Hlayout = QtWidgets.QHBoxLayout()
        self.button1 = QtWidgets.QPushButton("Fit")
        self.button1.clicked.connect(self.startfit)

        self.button2 = QtWidgets.QPushButton("SaveFig")
        self.button2.clicked.connect(self.saveThisFig)
        self.button3 = QtWidgets.QPushButton("Exit")
        # self.button3.clicked.connect( self.close )
        self.button3.setStyleSheet(
            "QPushButton {background-color: yellow; color: red;}"
        )

        self.Hlayout.addWidget(self.button1)
        self.Hlayout.addWidget(self.button2)
        self.Hlayout.addWidget(self.button3)
        self.vlayout.addLayout(self.Hlayout)

        self.textBrowser = QtWidgets.QTextBrowser()
        self.vlayout.addWidget(self.textBrowser)

        # self.vlayout.addStretch()
        #### add into  main layout
        self.baslayout.addWidget(self.leftw)
        # self.baslayout.addStretch(0.2)  ## 不好用
        self.baslayout.addWidget(self.canvas)
        self.setLayout(self.baslayout)

    def startfit(self):
        # print( 'index ', self.comboBox.currentIndex() )
        self.index = self.comboBox.currentIndex()
        self.nharm = self.spinBox1.value()
        self.nfold = self.spinBox2.value()
        # print(self.spinBox1.value())
        # print(self.spinBox2.value())
        models = ("Newkirk", "Saito")
        self.ax.clear()
        self.typeIIradioSource(
            dens_model=models[self.index], Nharmset=self.nharm, Nfoldset=self.nfold
        )

        self.fig.canvas.draw()

    def saveThisFig(self):
        file1, ok1 = QtWidgets.QFileDialog.getSaveFileName(
            self, "save TypeII time-Height Fit plot", "./", "(*.png; *.jpg; *.jpeg)"
        )
        self.fig.savefig(file1)

    def closeEvent(self, event):
        ## 发送一个信号
        self.SignalClickClose.emit("tpyeIIfitClose")

    def typeIIradioSource(self, dens_model="Newkirk", Nharmset=2, Nfoldset=1):
        """
        t 时间偏移量  # seconds
        f 频率选取点  # MHz
        dates 日期 # 如 dates = '2022-08-29'
        Nharmset =1 ，2 ，3 ；； 基频选1 ，谐频选2
        Nfoldset = 1  密度模型的倍数

        dens_model = 'Newkirk'  ， 'Saito'  密度模型


        """
        # 观测日期  字符串 '2023-03-30'
        dates = self.dateobs
        if self.typeIIndot < 4:
            print("data dot number is less! ")
            return

        tt = np.array(self.typeIItime)
        # figsize=(10,8)

        ## frequency  MHz
        freqx = np.array(self.typeIIfreq)
        # tt = np.array(self.tt )
        tt = (tt - int(tt[0])) * (3600.0 * 24)

        dtime0 = datetime.datetime.fromisoformat(dates + "T00:00:00")
        freqs = " "
        if Nharmset == 1:
            freqs = "Fundamental"
        if Nharmset == 2:
            freqs = "Harmonic"
        if Nharmset == 3:
            freqs = "Third Times"

        def Newkirkmodel(freqx, Nharm=1, Nfold=1):
            """
            Gordon Newkirk JR 1961, ApJ 133, 983
            THE SOLAR CORONA IN ACTIVE REGIONS AND THE THERMAL ORIGIN
            OF THE SLOWLY VARYING COMPONENT OF SOLAR RADIO RADIATION
            pp 984 equation(1)
            """
            ###====
            lgN0 = np.log10(4.2) + 4.0

            freqp = freqx / Nharm
            kk = (const.e.value * const.e.value) / (
                4.0 * np.pi * np.pi * const.eps0.value * const.m_e.value
            )

            e_density = freqp * freqp / kk

            RR = 4.32 / (np.log10(e_density) + 6.0 - np.log10(Nfold) - lgN0)
            return RR

        def Saitomodel(freqx, Nharm=1, Nfold=1):
            """
            Kuniji Saito, et.al., Solar Physics 55(1977) 121-134
            A study of the background corona near solar minimum
            pp 127 equation (4)

            """
            ###====
            freqp = freqx / Nharm
            kk = (const.e.value * const.e.value) / (
                4.0 * np.pi * np.pi * const.eps0.value * const.m_e.value
            )

            e_density = freqp * freqp / kk
            c1n = (1.36e6, 5.27e6, 3.15e6)  ## background hole ,polar regions hole
            c2n = (1.68e8, 3.54e6, 1.6e6)
            d1n = (2.14, 3.3, 4.71)
            d2n = (6.13, 5.8, 3.01)
            ix = 0
            Ne = e_density * 1.0e6 / Nfold

            # Ne = c1n[ix] * rx**(-d1n[ix]) + c2n[ix] * rx**(-d2n[ix])
            def Ne2culR(Ne):
                rx = 3.50
                rx1 = 1.0
                rx2 = 6.0
                ni = 0
                while ni < 100:
                    Nei = c1n[ix] * rx ** (-d1n[ix]) + c2n[ix] * rx ** (-d2n[ix])
                    if abs(Nei - Ne) < Ne / 100.0:
                        break
                    if Nei - Ne < 0:
                        rxi1 = rx1
                        rx2 = rx

                    if Nei - Ne > 0:
                        rxi1 = rx2
                        rx1 = rx

                    rx = (rx + rxi1) / 2
                    ni += 1
                return rx

            ##############################
            RR = Ne2culR(Ne)
            return RR

        ##############################################################################3

        if dens_model == "Newkirk":
            RR = Newkirkmodel(freqx, Nharm=Nharmset, Nfold=Nfoldset)
        if dens_model == "Saito":
            RR = np.array(
                [
                    Saitomodel(freqx[ii], Nharm=Nharmset, Nfold=Nfoldset)
                    for ii in range(len(freqx))
                ]
            )
        ###   拟合  速度
        Rsunkm = const.R_sun.value / 1000.0  # km
        print(tt)
        print(freqx)
        print(RR)

        ttx = tt.copy()

        def fx_1(x, A, B):
            return A * x + B

        def fx_2(x, A, B, C):
            return A * x**2 + B * x + C

        ### 拟合频漂
        fA1, fB1 = optimize.curve_fit(fx_1, ttx, freqx)[0]
        # yy1 =  ttx * A1 + B1
        ssfdrift = f"Frequency drift: {fA1:f} MHz/s"
        print(ssfdrift)
        self.textBrowser.append(ssfdrift)
        ### 拟合线性速度
        A1, B1 = optimize.curve_fit(fx_1, ttx, RR)[0]
        yy1 = ttx * A1 + B1

        A2, B2, C2 = optimize.curve_fit(fx_2, ttx, RR)[0]
        yy2 = A2 * ttx**2 + B2 * ttx + C2
        ### linear velosity fit v1
        v1 = A1 * Rsunkm  ## km /s

        aa2 = A2 * Rsunkm * 2  ## km /s2
        v2 = B2 * Rsunkm + aa2 * ttx[0]  ## km /s

        ##############################################################################
        dt = tt[1] - tt[0]
        #
        trang1 = dtime0 + datetime.timedelta(seconds=np.double(tt[0] - dt))
        trang2 = dtime0 + datetime.timedelta(seconds=np.double(tt[-1] + dt))

        ttlist = np.array(
            [
                dtime0 + datetime.timedelta(seconds=np.double(tt[ii]))
                for ii in range(len(tt))
            ]
        )

        # fig, ax = plt.subplots(1,1,figsize=figsize)
        dR = RR[1] - RR[0]

        # ax.plot(tt, RR, 'r*')

        self.ax.set_title("Shock Height vs Time " + dates)
        self.ax.set_xlabel("Time ( UT )")

        self.ax.set_xlim([trang1, trang2])
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        self.ax.xaxis.set_minor_locator(mdates.MinuteLocator())

        (line1,) = self.ax.plot(ttlist, yy1, "b")
        (line2,) = self.ax.plot(ttlist, yy2, "g")
        (line3,) = self.ax.plot(ttlist, RR, "r*")
        line1.set_label("1nd fit ")
        line2.set_label("2nd fit ")
        line3.set_label("data points")

        self.ax.set_ylabel("Heliocentric Distances (Rsun)")
        self.ax.set_ylim([RR[0] - dR, RR[-1] + dR])

        ss = (
            dens_model
            + " model:  "
            + freqs
            + f" {Nfoldset:2d} fold model,1nd, shock speed {v1:6.1f} km/s"
        )
        ss2 = (
            dens_model
            + " model:  "
            + freqs
            + f" {Nfoldset:2d} fold model,2nd, shock speed {v2:6.1f} km/s, {aa2:6.1} km/s2"
        )
        self.textBrowser.append(ss)
        self.textBrowser.append(ss2)

        ss = f"1nd, shock speed {v1:6.1f} km/s"
        ss2 = f"2nd, shock speed {v2:6.1f} km/s"

        self.ax.text(
            0.3,
            0.9,
            ss,
            horizontalalignment="center",
            verticalalignment="center",
            transform=self.ax.transAxes,
        )
        self.ax.text(
            0.3,
            0.92,
            ss2,
            horizontalalignment="center",
            verticalalignment="center",
            transform=self.ax.transAxes,
        )
        # self.ax.text(0.3, 0.94, ssfdrift , horizontalalignment='center',
        #      verticalalignment='center', transform=self.ax.transAxes)

        self.ax.legend(loc="lower right")
        # fig.canvas.draw()

    # def close(self):

    #     self.close()


#### 描述设定频谱数据===================
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
    ):
        if isinstance(data, np.ndarray):
            self.data = data
        if isinstance(time, np.ndarray):
            self.time = time
        if isinstance(freq, np.ndarray):
            self.freq = freq
        if isinstance(polar, str):
            self.polar = polar
        if isinstance(dateobs, str):
            self.dateobs = dateobs
        if isinstance(unit, str):
            self.unit = unit
        if isinstance(obsdev, str):
            self.obsdev = obsdev


##### difference device  data read ==================
def readdsrt_spectrofits(fn):
    """
    read in data as polar style;
    只针对 dsrt fits
    当 dsrt 数据格式变化时及时修改
    """
    try:
        hdu = fits.open(fn)
    except Exception:
        print("Cant open this file " + fn)
        raise
    #    hdu = fits.open( fn )
    header = hdu[0].header
    data = hdu[0].data
    time = np.ravel(hdu[1].data["time"])
    freq = np.ravel(hdu[1].data["frequency"])
    ### 注意子午规定的关键词
    try:
        dateobs = header["DATE_OBS"]
    except Exception:
        dateobs = header["DATE-OBS"]

    polars = header["POLARIZA"]
    #### 特别注意，统一偏振表示格式；?????????
    polars = polars[0] + polars[-1]
    try:
        unit = header["QUANTITY"]
    except Exception:
        unit = header["BUNIT"]

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
                )
            )
            print(polar + f" polarize data have been read {ii} in {arr_n} .")
    hdu.close()
    return dataout


def readcso_spectrofits(fn):
    """
    read in data as polar style;
    只针对cso fits  Synthe_CSO_20221112.fits
    1） 第一个数据时间 与 头文件里的开始时间对应；


    当 cso数据格式变化时及时修改
    """
    try:
        hdu = fits.open(fn)
    except Exception:
        print("Cant open this file " + fn)
        raise
    #    hdu = fits.open( fn )
    header = hdu[0].header
    data = hdu[0].data
    time = np.ravel(hdu[1].data["time"])
    freq = np.ravel(hdu[1].data["frequency"])
    ### 注意子午规定的关键词
    try:
        dateobs = header["DATE-OBS"]
    except Exception:
        dateobs = header["DATE_OBS"]

    ####  注意跨天操作 ##########################
    if time[0] < 0:
        datexx = datetime.datetime.fromisoformat(dateobs[0:10]) + datetime.timedelta(
            days=1
        )
        dateobs = datexx.isoformat()
        # dateobs = header['DATE_END']

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
                )
            )
            print(polar + f" polarize data have been read {ii} in {arr_n} .")
    hdu.close()
    return dataout


############ end difference obsovation  ========


class plotdata:
    plot_data = None
    tt = []
    freq = []
    dateobs = ""
    plotpl = " "
    plotmin = 0.5
    plotmax = 20.0
    ranget = []
    rangef = []
    rangetn = []
    rangefn = []
    scalestyle = "linear"


##################################
###############################################################
class plotfluxGUI(QtWidgets.QWidget):
    ### ´´½¨Ò»¸öÐÅºÅ
    SignalClickClose = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Plot flux")
        #### È«¾Ö±äÁ¿
        self.dataPlotInfo = None
        self.specd = None
        self.polars = "HV"
        self.pindex = []
        self.freqobsx = 150.0
        self.plotN = 0
        ########################3
        self.fig = plt.figure()
        self.ax = self.fig.subplots(1, 1)
        self.canvas = FigureCanvasQTAgg(self.fig)

        #### Ò³Ãæ²¼¾Ö

        self.baseHlayout = QtWidgets.QHBoxLayout()

        self.leftw = QtWidgets.QWidget()
        self.leftw.setFixedWidth(400)

        self.vlayout1 = QtWidgets.QVBoxLayout()
        self.leftw.setLayout(self.vlayout1)
        ##########
        # ## ´´½¨Ð£ÑéÆ÷
        _unused_maxvValid = QDoubleValidator(self)
        _unused_intValid = QIntValidator(self)
        ##### ÉèÖÃÆ«ÕñÐÅÏ¢ =====
        self.polarboxg = QtWidgets.QGroupBox("Polarization")
        self.polarLayout = QtWidgets.QHBoxLayout()
        self.polarlabelt0 = QtWidgets.QLabel()
        self.polarlabelt0.setText("Select: (input as: HV ) ")
        self.polarLayout.addWidget(self.polarlabelt0)
        self.polarlineEdit = QtWidgets.QLineEdit()
        self.polarLayout.addWidget(self.polarlineEdit)
        self.polarlineEdit.setFixedWidth(80)
        self.polarlineEdit.setText(self.polars[0])
        # self.polarcomboBox = QtWidgets.QComboBox()
        # self.polarcomboBox.addItem('HH + VV')
        # self.polarcomboBox.addItem('HH')
        # self.polarcomboBox.addItem('VV')
        # self.polarLayout.addWidget( self.polarcomboBox )

        self.polarlabelt1 = QtWidgets.QLabel()
        self.polarlabelt1.setText("All Polarization : " + self.polars)
        self.polarLayout.addWidget(self.polarlabelt1)

        self.polarboxg.setLayout(self.polarLayout)
        self.vlayout1.addWidget(self.polarboxg)
        # self.polarlineEdit.textChanged.connect( self.setpolarindex )

        ###### ÉèÖÃÑ¡ÔñÊ±¼ä¿ò ======
        self.timebox = QtWidgets.QGroupBox("Time")
        self.timeboxV = QtWidgets.QVBoxLayout()
        self.vlayoutH = QtWidgets.QHBoxLayout()

        self.labelt1 = QtWidgets.QLabel()
        self.labelt1.setText("Start : ")
        self.vlayoutH.addWidget(self.labelt1)
        ### start time
        self.Timestart = QtWidgets.QDateTimeEdit()
        self.datet00 = datetime.datetime(2023, 3, 30, 0, 0, 0)

        self.datetdstr = datetime.datetime(2023, 3, 30, 1, 0, 0)
        self.datetdend = datetime.datetime(2023, 3, 30, 8, 0, 0)
        self.begts = int(np.floor((self.datetdstr - self.datet00).total_seconds()))
        self.endts = int(np.ceil((self.datetdend - self.datet00).total_seconds()))

        tt = self.datet00 + datetime.timedelta(seconds=self.begts)
        self.Timestart.setDateTime(
            QDateTime(tt.year, tt.month, tt.day, tt.hour, tt.minute, tt.second)
        )
        # self.Timestart.setDisplayFormat('hh:mm:ss')
        self.Timestart.setDisplayFormat("yyyy-MM-ddThh:mm:ss")

        self.vlayoutH.addWidget(self.Timestart)

        # self.hoSlider1 = QtWidgets.QSlider()
        # self.vlayoutH.addWidget( self.hoSlider1  )

        # self.hoSlider1.setOrientation(Qt.Horizontal)
        # self.hoSlider1.setRange(  self.begts, self.endts )

        # self.hoSlider1.setSingleStep(1)
        # self.hoSlider1.valueChanged.connect( self.setStartTime )

        self.vlayoutH2 = QtWidgets.QHBoxLayout()
        # self.vlayout.addLayout( self.vlayoutH2 )
        self.labelt12 = QtWidgets.QLabel()
        self.labelt12.setText(self.datetdend.strftime("%H:%M:%S"))
        self.vlayoutH.addWidget(self.labelt12)

        #########################################
        self.labelt2 = QtWidgets.QLabel()
        self.labelt2.setText("End   : ")
        self.vlayoutH2.addWidget(self.labelt2)
        ##### end time
        self.Timeend = QtWidgets.QDateTimeEdit()
        self.vlayoutH2.addWidget(self.Timeend)

        tt = self.datet00 + datetime.timedelta(seconds=self.endts)
        self.Timeend.setDateTime(
            QDateTime(tt.year, tt.month, tt.day, tt.hour, tt.minute, tt.second)
        )
        # self.Timeend.setDisplayFormat('hh:mm:ss')
        self.Timeend.setDisplayFormat("yyyy-MM-ddThh:mm:ss")

        # self.hoSlider2.setOrientation(Qt.Horizontal)
        # self.hoSlider2.setRange(   self.begts, self.endts )
        # self.hoSlider2.setSliderPosition( self.endts  )
        # self.hoSlider2.setSingleStep(1)
        # self.hoSlider2.valueChanged.connect( self.setEndTime )

        self.labelt22 = QtWidgets.QLabel()
        self.labelt22.setText(self.datetdend.strftime("%H:%M:%S"))
        self.vlayoutH2.addWidget(self.labelt22)

        self.timeboxV.addLayout(self.vlayoutH)
        self.timeboxV.addLayout(self.vlayoutH2)
        self.timebox.setLayout(self.timeboxV)
        self.vlayout1.addWidget(self.timebox)
        #############################3
        ##### ÉèÖÃÆµÂÊÐÅÏ¢ =====
        self.freqboxg = QtWidgets.QGroupBox("Frequency")
        self.freqLayout = QtWidgets.QVBoxLayout()
        #### Á½¸öºáÌõ-------------------------
        self.freqlayoutH = QtWidgets.QHBoxLayout()
        self.freqlabelt1 = QtWidgets.QLabel()
        self.freqlabelt1.setText("Select Freq [] : ")
        self.freqlayoutH.addWidget(self.freqlabelt1)

        self.freqlineEdit1 = QtWidgets.QLineEdit()
        self.freqlayoutH.addWidget(self.freqlineEdit1)
        self.freqlineEdit1.setFixedWidth(200)

        # self.freqlineEdit1.setValidator( maxvValid )
        self.freqlineEdit1.setText(f"[{self.freqobsx:6.2f}]")

        self.freqLayout.addLayout(self.freqlayoutH)
        self.freqboxg.setLayout(self.freqLayout)
        self.vlayout1.addWidget(self.freqboxg)

        self.Hlayout21 = QtWidgets.QHBoxLayout()
        self.button1 = QtWidgets.QPushButton("Exit")
        # self.button1.setText('close')
        self.button1.clicked.connect(self.myclose)

        self.button2 = QtWidgets.QPushButton("Plot")
        self.Hlayout21.addWidget(self.button2)
        self.Hlayout21.addWidget(self.button1)
        self.vlayout1.addLayout(self.Hlayout21)

        ###############
        self.vlayout2 = QtWidgets.QVBoxLayout()
        # self.Hlayout21 = QtWidgets.QHBoxLayout()
        # self.button1 = QtWidgets.QPushButton('Exit')
        # # self.button1.setText('close')
        # self.button1.clicked.connect( self.myclose )

        # self.button2 = QtWidgets.QPushButton('Plot')
        # self.Hlayout21.addWidget( self.button2 )
        # self.Hlayout21.addWidget( self.button1 )

        self.vlayout2.addWidget(self.canvas)
        # self.vlayout2.addLayout( self.Hlayout21  )

        self.baseHlayout.addWidget(self.leftw)
        self.baseHlayout.addLayout(self.vlayout2)
        self.setLayout(self.baseHlayout)

    # def setpolarindex(self):
    #     self.pindex = []
    #     pols = self.polarlineEdit.text()
    #     for ii in range( self.polars ) :
    #         if self.polars[ii] in pols :
    #             self.pindex.append( ii )

    def closeEvent(self, event):
        ## ¹Ø±Õ´°¿ÚÊ±£¬·¢ËÍÒ»¸öÐÅºÅ
        self.SignalClickClose.emit("pluxplotGUIclose")

    def myclose(self):
        # ¹Ø±Õ´°¿ÚÊ±£¬·¢ËÍÒ»¸öÐÅºÅ
        self.close()


###########################
class dsrtSpectraData:

    def __init__(self, pathslist=None):
        self.filename = []  ### 文件路径列表
        self.nf = 0  ## 文件数目；
        if pathslist is not None:
            self.filename = pathslist
            if isinstance(pathslist, str):
                self.filename = [pathslist]
            if not isinstance(self.filename, list):
                print("filename is not a list")
                raise NameError("filename is wrong")
            self.nf = len(self.filename)
            try:
                print("readdata from " + self.filename[0])
                self.data = readcso_spectrofits(self.filename[0])
                print("read done")
            except Exception:
                print("open file is wrong")
        else:
            self.data = []
            self.plotconfig = []

        try:
            if self.data[0].data.dtype == "u1":
                self.Bytedata = True
        except Exception:
            self.Bytedata = False

        self.figureID = None
        self.axs = []
        self.inaxs = []
        self.cidpress = None
        self.Canvas2PlotSet = None
        self.mainButton2 = None
        self.savefitsdata = []
        ######## work for typeII radio burst fit height ========
        self.RtypeIIfit = RadioTypeIIfit()
        self.RtypeIIfit.button3.clicked.connect(self.RTypeIIfitClose)
        self.RtypeIIfit.SignalClickClose.connect(self.RTypeIIfitClose)
        self.fitnowclick = 0
        self.subbackv = False  ##  substract background

        ####rebin set
        self.rebinsw = True
        self.rebinTnum = 1
        self.rebinFnum = 1
        self.dvalue2 = False
        self.dvalueset = 100.0
        self.Bytedata = False
        # self.RtypeIIfit.typeIIndot = 0
        # self.typeIItime = []
        # self.typeIIfreq = []

    #####################################################
    def plot_image(
        self,
        polar=None,
        scalestyle="linear",
        minv=-5.0,
        maxv=20.0,
        begch=None,
        endch=None,
        newcmp="jet",
        bartext="",
        begff=None,
        endff=None,
        setfontsize=20,
        shadingset="flat",
        figsize=None,
        dpi=None,
        *args,
        **kwargs,
    ):
        """
        polar = None 默认都要画，需要两个框,设置

        控制时间截断  begch='08:28:00', endch='08:55:00'
        控制频率截断  begff=150.0, endff=450.0  ## 注意单位 MHz
        """
        self.savefitsdata = []
        ## check data whether exist
        try:
            ndata = len(self.data)  ## original data number depend on polar
        except Exception:
            print("no data! please load data by readdata()")
            print("please first input radio spectral data fits file paths")
            return 0

        ##  设置图片分辨率
        if dpi is None:
            dpi = 100

        if bartext == "":
            bartext = "linear"
        ## 默认设置的画图
        polar_list = [self.data[kk].polar for kk in range(ndata)]

        if polar is None:
            polar = ""
            for iz in range(ndata):
                polar += polar_list[iz][0]
        else:
            if isinstance(polar, str):
                npolar = len(polar)
                for iz in range(npolar):
                    if polar[iz] == "P" or polar[iz] == "I":
                        # polars = 'PP'
                        print("plot polarization ", polar[iz])
                    else:
                        polars = polar[iz] + polar[iz]
                        if polars not in polar_list:
                            print(polars + " not in data!!!")
                            print("please check in ")
                            print(polar_list)
                            return 0
                ## check
            else:
                print("polar parameter is wrong set!!!")
                return 0
        npolar = len(polar)
        if npolar >= 1:

            self.plotconfig = [plotdata for ii in range(npolar)]
            if figsize is None:
                figsizes = (10.0, 4.0 * npolar)

            if self.figureID is None:
                self.figureID, axs = plt.subplots(npolar, 1, figsize=figsizes, dpi=dpi)
            else:
                self.figureID.set_dpi(dpi)
                self.figureID.set_figwidth(figsizes[0])
                self.figureID.set_figheight(figsizes[1])
            if self.axs == []:
                axs = self.figureID.subplots(npolar, 1)

            if npolar == 1:
                self.axs = [axs]
            else:
                self.axs = list(axs)
            ############################################
            for iz in range(npolar):
                polars = polar[iz] + polar[iz]
                ### 考虑 P 偏振情况
                if polars[0] == "P" or polars[0] == "I":
                    # print('this is test', polars)
                    # polars = 'PP'
                    # iz = 0
                    if len(self.data) > 1:
                        ik = polar_list.index("RR")
                        ZR = self.data[ik].data
                        ik = polar_list.index("LL")
                        ZL = self.data[ik].data

                        # Z = ( ZR - ZL )/ ( ZR + ZL )

                        DATE_OBS = self.data[ik].dateobs
                        datet0 = datetime.datetime.fromisoformat(
                            DATE_OBS[0:11] + "00:00:00"
                        )
                        tt = self.data[ik].time
                        #                   print('tt length is {}'.format(len(tt)) )
                        freq = self.data[ik].freq
                        datess = DATE_OBS[0:10]
                        dtime0 = datetime.datetime.fromisoformat(datess)

                        POLARIZA = self.data[ik].polar
                        _unused_unit = self.data[ik].unit
                        ## 开启时间截取功能========================================
                        if (begch is not None) or (endch is not None):
                            xtimev = 1
                        else:
                            xtimev = 0

                        if xtimev == 1:
                            if begch is not None:
                                if not isinstance(begch, str):
                                    ttch = begch - datet0
                                    ttch1 = ttch.total_seconds()
                                else:
                                    ttch = (
                                        datetime.datetime.fromisoformat(begch) - datet0
                                    )
                                    ttch1 = ttch.total_seconds()
                            else:
                                ttch1 = tt[0]
                            if endch is not None:
                                if not isinstance(endch, str):
                                    ttch = endch - datet0
                                    ttch2 = ttch.total_seconds()
                                else:
                                    ttch = (
                                        datetime.datetime.fromisoformat(endch) - datet0
                                    )
                                    ttch2 = ttch.total_seconds()
                            else:
                                ttch2 = tt[-1]

                            tindex1, tindex2 = findindex(tt, ttch1, ttch2)
                            if len(tindex1) > 0:
                                tindex1 = tindex1[0]
                            else:
                                tindex1 = 0
                            if len(tindex2) > 0:
                                tindex2 = tindex2[0]
                            else:
                                tindex2 = len(tt) - 1
                            tt = tt[tindex1 : tindex2 + 1]
                            # if tt[0] < 0 :
                            #     dtime0 = dtime0 + datetime.timedelta(days = 1 )

                            ZR = ZR[:, tindex1 : tindex2 + 1]
                            ZL = ZL[:, tindex1 : tindex2 + 1]
                            self.plotconfig[iz].rangetn = [tindex1, tindex2]
                        ######### time select done ################################
                        if (begff is not None) or (endff is not None):
                            freqv = 1
                        else:
                            freqv = 0

                        if freqv == 1:
                            if begff is not None:
                                ffch1 = begff
                            else:
                                ffch1 = freq[0]
                            if endff is not None:
                                ffch2 = endff
                            else:
                                ffch2 = freq[-1]
                            findex1, findex2 = findindex(freq, ffch1, ffch2)
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
                            freq = freq[findex1 : findex2 + 1]
                            ZR = ZR[findex1 : findex2 + 1, :]
                            ZL = ZL[findex1 : findex2 + 1, :]
                            self.plotconfig[iz].rangefn = [findex1, findex2]

                        ######### freq select done ################################
                        #                   nt = len( tt )
                        #                   print( 'after tt {}'.format(nt) )
                        #                   print( 'after tt data {}'.format(len( self.data[ik].time ) ) )
                        #                   nf = len(freq)
                        print(f"tt length is {len(tt)}")
                        print(f"freq length is {len(freq)}")

                        if self.rebinsw:
                            tbin = self.rebinTnum
                            fbin = self.rebinFnum
                            ZR = rebin.rebin(ZR, factor=(fbin, tbin))
                            ZL = rebin.rebin(ZL, factor=(fbin, tbin))

                            tt = rebin.rebin(tt, factor=(tbin,))
                            freq = rebin.rebin(freq, factor=(fbin,))

                        if polars == "PP":
                            polss = "P"
                            ###  ============================
                            Z = (ZR - ZL) / (ZR + ZL)

                        if polars == "II":
                            polss = "I"
                            ###  ============================
                            Z = ZR + ZL
                            if self.subbackv:
                                Z = subtrBackgroundminv(Z)

                        # dtime0 = datetime.datetime.fromisoformat( datess )

                        self.savefitsdata.append((tt, freq, Z, polss, datet0))
                        trang1 = dtime0 + datetime.timedelta(milliseconds=tt[0] * 1000)
                        trang2 = dtime0 + datetime.timedelta(milliseconds=tt[-1] * 1000)
                        # setextent = [trang1, trang2, freq[0], freq[-1] ]
                        xx, yy = np.meshgrid(tt, freq)

                        ax1 = self.axs[iz]

                        ax1.set_xlabel("Time (UT)", fontsize=setfontsize)
                        ax1.set_ylabel("Frequency (MHz)", fontsize=setfontsize)
                        # ax1.set_zorder(0)
                        # ax1.axis('off')
                        # ax1.set_mouseover(False)
                        datessx = trang1.isoformat()[0:10]
                        ax1.set_title(
                            "CSO Radio Spectrum " + polss + " " + datessx,
                            fontsize=setfontsize * 1.2,
                        )
                        # ax1.set_xlim([xx[0,0],xx[0,-1]])
                        ax1.set_xlim([trang1, trang2])
                        ax1.set_ylim([freq[0], freq[-1]])
                        # #ax.xticks(rotation=70)
                        # ax1.xaxis.set_major_formatter( mdates.DateFormatter('%H:%M:%S'))
                        if tt[-1] - tt[0] > 300:
                            ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
                            ax1.xaxis.set_minor_locator(mdates.MinuteLocator())
                        else:
                            ax1.xaxis.set_major_formatter(
                                mdates.DateFormatter("%H:%M:%S")
                            )
                            ax1.xaxis.set_minor_locator(mdates.SecondLocator())

                        ax1.yaxis.set_minor_locator(AutoMinorLocator())
                        # ax1.yaxis.set_minor_locator(MultipleLocator(10))
                        # ax.xaxis.set_minor_locator( AutoMinorLocator() )
                        ax1.tick_params(
                            which="both", direction="inout", top=True, right=True
                        )
                        ax1.tick_params(axis="x", labelsize=setfontsize)
                        ax1.tick_params(axis="y", labelsize=setfontsize)
                        ax1.tick_params(which="minor", length=5)
                        ax1.tick_params(which="major", length=10, width=2)

                        ax1in1 = ax1.inset_axes([0.0, 0.0, 1, 1])

                        if polars == "PP":
                            minv = -1.0
                            maxv = 1.0

                            # psm1 = ax1in1.pcolormesh(xx, yy, Z[:-1:,:-1:], vmin=minv, vmax=maxv,
                            # shading='flat',   cmap = newcmp, rasterized=True)
                            if shadingset == "flat":
                                psm1 = ax1in1.pcolormesh(
                                    xx,
                                    yy,
                                    Z[:-1:, :-1:],
                                    vmin=minv,
                                    vmax=maxv,
                                    shading="flat",
                                    cmap="bwr",
                                    rasterized=True,
                                )
                            else:
                                psm1 = ax1in1.pcolormesh(
                                    xx,
                                    yy,
                                    Z,
                                    vmin=minv,
                                    vmax=maxv,
                                    shading=shadingset,
                                    cmap="bwr",
                                )

                            # psm1 = ax1in1.pcolormesh( xx,  yy,  Z,   vmin=minv,  vmax=maxv,
                            #             shading='gouraud',   cmap = newcmp  )
                            # ax1in1.plot(np.array([xx[0,0],xx[0,-1]]), np.array([freq[0],freq[-1]]), zorder=1)
                            # zorder=1
                            ax1in1.set_xlim([xx[0, 0], xx[0, -1]])
                            ax1in1.set_ylim([freq[0], freq[-1]])
                            # ax1in1.set_xlim([trang1,trang2])
                            ax1in1.axis("off")
                            # ax1in1.set_zorder(0)
                            # ax1in1.set_mouseover(True)
                            self.inaxs.append(ax1in1)
                            # bar1 = self.figureID.colorbar(psm1,ax=ax1)
                            # bar1.ax.text(1, maxv+(maxv-minv)/100, bartext )
                            barmap = mplcm.ScalarMappable(cmap="bwr")

                            minvs = minv
                            maxvs = maxv

                            barmap.set_clim(vmin=minvs, vmax=maxvs)
                            bar1 = self.figureID.colorbar(barmap, ax=ax1)
                            # bar1.ax.text(1, maxvs + (maxvs - minvs )/100, 'linear' , color='k')
                            bar1.ax.text(
                                1,
                                maxvs + (maxvs - minvs) / 50,
                                scalestyle,
                                color="k",
                                fontsize=setfontsize,
                            )
                            bar1.ax.tick_params(axis="y", labelsize=setfontsize)

                        if polars == "II":
                            if scalestyle == "log10":
                                bartext = "log10"
                                indexZ = np.where(Z < 1)
                                if len(indexZ[0]) > 0:
                                    Z[indexZ] = 1.0
                                Z = np.log10(Z)
                            # psm1 = ax1.pcolormesh(xx, yy, Z[:-1:,:-1:], vmin=minv, vmax=maxv,
                            #           shading='flat',   cmap = newcmp,zorder=4, rasterized=True)

                            if self.dvalue2:
                                index = np.where(Z >= self.dvalueset)
                                Z[Z < self.dvalueset] = 0
                                # Z[ Z>=self.dvalueset ] = 1
                                Z[index] = 1
                                minv = 0
                                maxv = 1

                            # psm1 = ax1in1.pcolormesh(xx, yy, Z[:-1:,:-1:], vmin=minv, vmax=maxv,
                            # shading='flat',   cmap = newcmp, rasterized=True)
                            if shadingset == "flat":
                                psm1 = ax1in1.pcolormesh(
                                    xx,
                                    yy,
                                    Z[:-1:, :-1:],
                                    vmin=minv,
                                    vmax=maxv,
                                    shading="flat",
                                    cmap=newcmp,
                                    rasterized=True,
                                )
                            else:
                                psm1 = ax1in1.pcolormesh(
                                    xx,
                                    yy,
                                    Z,
                                    vmin=minv,
                                    vmax=maxv,
                                    shading=shadingset,
                                    cmap=newcmp,
                                )

                            # psm1 = ax1in1.pcolormesh( xx,  yy,  Z,   vmin=minv,  vmax=maxv,
                            #             shading='gouraud',   cmap = newcmp  )
                            # ax1in1.plot(np.array([xx[0,0],xx[0,-1]]), np.array([freq[0],freq[-1]]), zorder=1)
                            # zorder=1
                            ax1in1.set_xlim([xx[0, 0], xx[0, -1]])
                            ax1in1.set_ylim([freq[0], freq[-1]])
                            # ax1in1.set_xlim([trang1,trang2])

                            ax1in1.axis("off")
                            # ax1in1.set_zorder(0)
                            # ax1in1.set_mouseover(True)
                            self.inaxs.append(ax1in1)
                            # bar1 = self.figureID.colorbar(psm1,ax=ax1)
                            # bar1.ax.text(1, maxv+(maxv-minv)/100, bartext )
                            barmap = mplcm.ScalarMappable(cmap=newcmp)

                            if self.Bytedata:
                                minvs = minv / 51.0 + 2
                                maxvs = maxv / 51.0 + 2
                            else:
                                minvs = minv
                                maxvs = maxv

                            barmap.set_clim(vmin=minvs, vmax=maxvs)
                            bar1 = self.figureID.colorbar(barmap, ax=ax1)
                            # bar1.ax.text(1, maxvs + (maxvs - minvs )/100, scalestyle , color='k')
                            bar1.ax.text(
                                1,
                                maxvs + (maxvs - minvs) / 50,
                                scalestyle,
                                color="k",
                                fontsize=setfontsize,
                            )
                            bar1.ax.tick_params(axis="y", labelsize=setfontsize)

                        ### record the parameters
                        self.plotconfig[iz].psm = psm1
                        self.plotconfig[iz].plotpl = polss
                        self.plotconfig[iz].plotmin = minv
                        self.plotconfig[iz].plotmax = maxv
                        self.plotconfig[iz].ranget = [tt[0], tt[-1]]
                        self.plotconfig[iz].rangef = [freq[0], freq[-1]]
                        self.plotconfig[iz].scalestyle = scalestyle

                else:
                    # for iz in range(npolar) :
                    # polars = polar[iz] + polar[iz]
                    if polars in polar_list:
                        ik = polar_list.index(polars)
                        Z = self.data[ik].data
                        DATE_OBS = self.data[ik].dateobs
                        datet0 = datetime.datetime.fromisoformat(
                            DATE_OBS[0:11] + "00:00:00"
                        )
                        tt = self.data[ik].time
                        #                   print('tt length is {}'.format(len(tt)) )
                        freq = self.data[ik].freq
                        datess = DATE_OBS[0:10]
                        dtime0 = datetime.datetime.fromisoformat(datess)

                        POLARIZA = self.data[ik].polar
                        _unused_unit = self.data[ik].unit
                        polss = POLARIZA[0]
                        ## 开启时间截取功能========================================
                        if (begch is not None) or (endch is not None):
                            xtimev = 1
                        else:
                            xtimev = 0

                        # if xtimev == 1 :
                        #      if begch != None :
                        #          if len(begch) < 12 :
                        #              ttch = datetime.datetime.fromisoformat( DATE_OBS[0:11] + begch ) - datet0
                        #              ttch1 = ttch.total_seconds()
                        #          else :
                        #              ttch = datetime.datetime.fromisoformat(  begch ) - datet0
                        #              ttch1 = ttch.total_seconds()
                        #      else :
                        #          ttch1 = tt[0]
                        #      if endch != None :
                        #          if len(endch) < 12 :
                        #              ttch = datetime.datetime.fromisoformat( DATE_OBS[0:11] + endch ) - datet0
                        #              ttch2 = ttch.total_seconds()
                        #          else :
                        #              ttch = datetime.datetime.fromisoformat(  endch )  - datet0
                        #              ttch2 = ttch.total_seconds()
                        #      else :
                        #          ttch2 = tt[-1]
                        if xtimev == 1:
                            if begch is not None:
                                if not isinstance(begch, str):
                                    ttch = begch - datet0
                                    ttch1 = ttch.total_seconds()
                                else:
                                    ttch = (
                                        datetime.datetime.fromisoformat(begch) - datet0
                                    )
                                    ttch1 = ttch.total_seconds()
                            else:
                                ttch1 = tt[0]
                            if endch is not None:
                                if not isinstance(endch, str):
                                    ttch = endch - datet0
                                    ttch2 = ttch.total_seconds()
                                else:
                                    ttch = (
                                        datetime.datetime.fromisoformat(endch) - datet0
                                    )
                                    ttch2 = ttch.total_seconds()
                            else:
                                ttch2 = tt[-1]

                            tindex1, tindex2 = findindex(tt, ttch1, ttch2)
                            if len(tindex1) > 0:
                                tindex1 = tindex1[0]
                            else:
                                tindex1 = 0
                            if len(tindex2) > 0:
                                tindex2 = tindex2[0]
                            else:
                                tindex2 = len(tt) - 1
                            tt = tt[tindex1 : tindex2 + 1]
                            # if tt[0] < 0 :
                            #     dtime0 = dtime0 + datetime.timedelta(days = 1 )

                            Z = Z[:, tindex1 : tindex2 + 1]
                            self.plotconfig[iz].rangetn = [tindex1, tindex2]
                        ######### time select done ################################
                        if (begff is not None) or (endff is not None):
                            freqv = 1
                        else:
                            freqv = 0

                        if freqv == 1:
                            if begff is not None:
                                ffch1 = begff
                            else:
                                ffch1 = freq[0]
                            if endff is not None:
                                ffch2 = endff
                            else:
                                ffch2 = freq[-1]
                            findex1, findex2 = findindex(freq, ffch1, ffch2)
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
                            freq = freq[findex1 : findex2 + 1]
                            Z = Z[findex1 : findex2 + 1, :]
                            self.plotconfig[iz].rangefn = [findex1, findex2]

                        ######### freq select done ################################
                        #                   nt = len( tt )
                        #                   print( 'after tt {}'.format(nt) )
                        #                   print( 'after tt data {}'.format(len( self.data[ik].time ) ) )
                        #                   nf = len(freq)
                        print(f"tt length is {len(tt)}")
                        print(f"freq length is {len(freq)}")
                        if self.subbackv:
                            Z = subtrBackgroundminv(Z)

                        if self.rebinsw:
                            tbin = self.rebinTnum
                            fbin = self.rebinFnum
                            Z = rebin.rebin(Z, factor=(fbin, tbin))
                            tt = rebin.rebin(tt, factor=(tbin,))
                            freq = rebin.rebin(freq, factor=(fbin,))

                        self.savefitsdata.append((tt, freq, Z, polss, datet0))
                        # dtime0 = datetime.datetime.fromisoformat( datess )

                        trang1 = dtime0 + datetime.timedelta(milliseconds=tt[0] * 1000)
                        trang2 = dtime0 + datetime.timedelta(milliseconds=tt[-1] * 1000)
                        # setextent = [trang1, trang2, freq[0], freq[-1] ]
                        xx, yy = np.meshgrid(tt, freq)

                        ax1 = self.axs[iz]

                        ax1.set_xlabel("Time (UT)", fontsize=setfontsize)
                        ax1.set_ylabel("Frequency (MHz)", fontsize=setfontsize)
                        # ax1.set_zorder(0)
                        # ax1.axis('off')
                        # ax1.set_mouseover(False)
                        datessx = trang1.isoformat()[0:10]
                        ax1.set_title(
                            "CSO Radio Spectrum " + polss + " " + datessx,
                            fontsize=setfontsize * 1.2,
                        )
                        # ax1.set_xlim([xx[0,0],xx[0,-1]])
                        ax1.set_xlim([trang1, trang2])
                        ax1.set_ylim([freq[0], freq[-1]])
                        # #ax.xticks(rotation=70)
                        # ax1.xaxis.set_major_formatter( mdates.DateFormatter('%H:%M:%S'))
                        if tt[-1] - tt[0] > 300:
                            ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
                            ax1.xaxis.set_minor_locator(mdates.MinuteLocator())
                        else:
                            ax1.xaxis.set_major_formatter(
                                mdates.DateFormatter("%H:%M:%S")
                            )
                            ax1.xaxis.set_minor_locator(mdates.SecondLocator())

                        ax1.yaxis.set_minor_locator(AutoMinorLocator())
                        # ax1.yaxis.set_minor_locator(MultipleLocator(10))
                        # ax.xaxis.set_minor_locator( AutoMinorLocator() )
                        ax1.tick_params(
                            which="both", direction="inout", top=True, right=True
                        )
                        ax1.tick_params(axis="x", labelsize=setfontsize)
                        ax1.tick_params(axis="y", labelsize=setfontsize)
                        ax1.tick_params(which="minor", length=5)
                        ax1.tick_params(which="major", length=10, width=2)

                        ax1in1 = ax1.inset_axes([0.0, 0.0, 1, 1])
                        if scalestyle == "log10":
                            bartext = "log10"
                            indexZ = np.where(Z < 1)
                            if len(indexZ[0]) > 0:
                                Z[indexZ] = 1.0
                            Z = np.log10(Z)
                        # psm1 = ax1.pcolormesh(xx, yy, Z[:-1:,:-1:], vmin=minv, vmax=maxv,
                        #           shading='flat',   cmap = newcmp,zorder=4, rasterized=True)

                        if self.dvalue2:
                            index = np.where(Z >= self.dvalueset)
                            Z[Z < self.dvalueset] = 0
                            # Z[ Z>=self.dvalueset ] = 1
                            Z[index] = 1
                            minv = 0
                            maxv = 1

                        # psm1 = ax1in1.pcolormesh(xx, yy, Z[:-1:,:-1:], vmin=minv, vmax=maxv,
                        # shading='flat',   cmap = newcmp, rasterized=True)
                        if shadingset == "flat":
                            psm1 = ax1in1.pcolormesh(
                                xx,
                                yy,
                                Z[:-1:, :-1:],
                                vmin=minv,
                                vmax=maxv,
                                shading="flat",
                                cmap=newcmp,
                                rasterized=True,
                            )
                        else:
                            psm1 = ax1in1.pcolormesh(
                                xx,
                                yy,
                                Z,
                                vmin=minv,
                                vmax=maxv,
                                shading=shadingset,
                                cmap=newcmp,
                            )

                        # psm1 = ax1in1.pcolormesh( xx,  yy,  Z,   vmin=minv,  vmax=maxv,
                        #             shading='gouraud',   cmap = newcmp  )
                        # ax1in1.plot(np.array([xx[0,0],xx[0,-1]]), np.array([freq[0],freq[-1]]), zorder=1)
                        # zorder=1
                        ax1in1.set_xlim([xx[0, 0], xx[0, -1]])
                        ax1in1.set_ylim([freq[0], freq[-1]])
                        # ax1in1.set_xlim([trang1,trang2])

                        ax1in1.axis("off")
                        # ax1in1.set_zorder(0)
                        # ax1in1.set_mouseover(True)
                        self.inaxs.append(ax1in1)
                        # bar1 = self.figureID.colorbar(psm1,ax=ax1)
                        # bar1.ax.text(1, maxv+(maxv-minv)/100, bartext )
                        barmap = mplcm.ScalarMappable(cmap=newcmp)
                        if scalestyle == "log10":
                            minvs = minv
                            maxvs = maxv
                        else:
                            if self.Bytedata:
                                minvs = minv / 51.0 + 2
                                maxvs = maxv / 51.0 + 2
                                scalestyle = "log10"
                            else:
                                minvs = minv
                                maxvs = maxv

                        barmap.set_clim(vmin=minvs, vmax=maxvs)
                        bar1 = self.figureID.colorbar(barmap, ax=ax1)
                        bar1.ax.text(
                            1,
                            maxvs + (maxvs - minvs) / 50,
                            scalestyle,
                            color="k",
                            fontsize=setfontsize,
                        )
                        bar1.ax.tick_params(axis="y", labelsize=setfontsize)

                        ### record the parameters
                        self.plotconfig[iz].psm = psm1
                        self.plotconfig[iz].plotpl = polss
                        self.plotconfig[iz].plotmin = minv
                        self.plotconfig[iz].plotmax = maxv
                        self.plotconfig[iz].ranget = [tt[0], tt[-1]]
                        self.plotconfig[iz].rangef = [freq[0], freq[-1]]
                        self.plotconfig[iz].scalestyle = scalestyle

    #                   self.plotconfig[iz].

    # ###########################################################
    # ################ wedgit 响应函数======
    # def on_click(event):
    #         if event.button == 1: # 左键点击
    #             x, y = event.xdata, event.ydata
    #             datext = datetime.datetime.utcfromtimestamp( x * 3600 * 24)
    #             tx = (x - np.floor(x))*3600 * 24
    #             print( datext )
    #             print(event)
    #             print(self.axs[0] )
    #             if self.axs[0] == event.inaxes :
    #                 ax22 = self.inaxs[0]
    #             else :
    #                 ax22 = self.inaxs[1]
    #             # print(self.inaxs)
    #             ax22.scatter(tx, y, s=100, color='r') # 在鼠标点击处绘制一个红色圆圈
    #             self.figureID.canvas.draw()
    #             self.typeIItime[self.typeIIndot] = tx
    #             self.typeIIfreq[self.typeIIndot] = y
    #             self.typeIIndot += 1
    #             print(self.typeIIndot )
    #         elif event.button == 3:
    #             print('button 3')
    # tin = self.typeIItime[0:self.typeIIndot]
    # fin = self.typeIIfreq[0:self.typeIIndot]
    # self.figureID.canvas.mpl_disconnect( self.cid )
    # self.figureID.clear()
    # plt.close()

    # # self.figureID.canvas.mpl_disconnect( self.cid )
    # newfig = dsrtTool.typeIIradioSource(tin,fin, datess, Nharmset = 2, Nfoldset = 1 ,
    #                       dens_model = 'Newkirk', figsize=(10,8) )
    # plt.show()
    # print('here')

    # self.cid = self.figureID.canvas.mpl_connect('button_press_event', on_click )
    # plt.show()
    ## 根据提供的 目录 和 文件名搜索
    def searchfile(self, dirpath, tofindname):
        if os.path.isdir(dirpath):
            names = []
            names = os.listdir(dirpath)
            findnames = []
            if len(names) > 0:
                findnames = fnmatch.filter(names, tofindname)
            if len(findnames) > 0:
                findnames.sort()
                self.filename = [os.path.join(dirpath, ss) for ss in findnames]
                self.nf = len(self.filename)
                print(f"have {self.nf} file fund.")
            else:
                print("no find files")
        else:
            print("check filedir path!!!")

    ## 根据提供文件名搜索
    def file_search(self, tofindname):
        self.filename = file_search(tofindname)
        self.nf = len(self.filename)
        if self.nf == 0:
            print("No files, please check filedir path!!!")

    def readdata(self, allread=1):
        """
        内存足够大， allread=1
        不同仪器的fits 文件接口


        """
        self.nf = len(self.filename)
        try:
            if self.nf > 0:
                ## check files is exist
                nameTrue = [os.path.isfile(self.filename[ii]) for ii in range(self.nf)]
                tf = 1
                for ii in range(self.nf):
                    if not nameTrue[ii]:
                        # print( self.filename[ii] + ' this name is wrong ...' )
                        tf *= 0
                if tf == 1:
                    print("filename is already set , next doing... ")
                else:
                    # print(' list of files is wrong, please check them...')
                    return 0
        except Exception:
            # print('check filename ,maybe no file')
            return 0
        if allread == 0:
            # print('readdata from ' + self.filename[0])
            self.data = readcso_spectrofits(self.filename[0])
            # print('read one done')
        if allread == 1:
            # print('will read {} files in data '.format(self.nf) )
            self.data = readcso_spectrofits(self.filename[0])
            if self.nf > 1:
                for ii in range(1, self.nf):
                    data = readcso_spectrofits(self.filename[ii])
                    ## 假设时间序列顺序排列的数据
                    # ik 遍历 不同极化 数据
                    for ik in range(len(self.data)):
                        self.data[ik].data = np.hstack(
                            (self.data[ik].data, data[ik].data)
                        )
                        self.data[ik].time = np.hstack(
                            (self.data[ik].time, data[ik].time)
                        )
                        # self.data[ik].freq = np.hstack((self.data[ik].freq, data[ik].freq))
            # print('read all files into data')

        ## make data info   review  ========
        self.datet0 = datetime.datetime.fromisoformat(
            self.data[0].dateobs[0:10] + "T00:00:00"
        )
        # if self.data[0].time[0] < 0 :
        #    self.datet0 = self.datet0 + datetime.timedelta(days = 1)
        self.beginTime = self.datet0 + datetime.timedelta(seconds=self.data[0].time[0])
        self.endTime = self.datet0 + datetime.timedelta(seconds=self.data[0].time[-1])
        self.resolveTime = self.data[0].time[1] - self.data[0].time[0]
        self.beginFreq = self.data[0].freq[0]
        self.endFreq = self.data[0].freq[-1]
        self.resolveFreq = self.data[0].freq[1] - self.data[0].freq[0]
        ##########################################################################

    def data_info(self):
        ### print  data information
        print("Begin time = ", self.beginTime.isoformat())
        print("end time = ", self.endTime.isoformat())
        print("temporal resolution(seconds) dt = ", self.resolveTime)
        print(f"Begin Freq = {self.beginFreq:5.1f} MHz")
        print(f"end  Freq = {self.endFreq:5.1f} MHz")
        print(f"frequency resolution,  df= {self.resolveFreq:5.1f} MHz")
        npol = len(self.data)
        print("polar data : ")
        for ii in range(npol):
            print(self.data[ii].polar)

    def typeIIfitHeight(self):
        print("tpyeII fit height")
        if self.RtypeIIfit.countj > 0:
            self.RtypeIIfit.ax.clear()
            self.RtypeIIfit.fig.canvas.draw()
        self.RtypeIIfit.countj += 1

        self.mainButton2.setText("TypeII Backbone")
        self.mainButton2.setStyleSheet("QPushButton { color: black}")
        self.mainButton2.clicked.disconnect(self.typeIIfitHeight)
        # print(self.typeIItime )
        # print(self.typeIIfreq )

        ### 解除画布的 点击绑定
        self.figureID.canvas.mpl_disconnect(self.cidpress)
        # self.mainButton2.clicked.connect( self.mainBut2event )
        self.clickAxs = None

        self.RtypeIIfit.show()

    def getDotClick(self, event):
        """
        click for typeII for fit

        """
        if (event.button == 1) and (not event.dblclick):
            if event.inaxes is not None:
                if self.RtypeIIfit.typeIItime == []:
                    self.clickAxs = event.inaxes
                    self.RtypeIIfit.dateobs = (self.data[0].dateobs)[0:10]
                    self.RtypeIIfit.typeIIndot = 0
                    self.RtypeIIfit.typeIIfreq = []
                    self.fitnowclick = 1
                    ### 考虑在 inaxes 上画图 不能正常存选取点的问题；
                    ## savefig 出现问题
                    self.hline = self.clickAxs.plot(
                        self.RtypeIIfit.typeIItime,
                        self.RtypeIIfit.typeIIfreq,
                        "k.",
                        zorder=4,
                    )
                    self.mainButton2.setText("Type II Fitting")
                    self.mainButton2.clicked.connect(self.typeIIfitHeight)
                    #####################################################

                if event.inaxes == self.clickAxs:

                    if self.RtypeIIfit.typeIIndot == 0:
                        ### 避免调整窗口，如果调整 图像将不准确；
                        # self.figureID.canvas.draw()
                        self.bg = self.figureID.canvas.copy_from_bbox(
                            self.figureID.bbox
                        )
                        self.figureID.canvas.blit(self.figureID.bbox)
                    self.figureID.canvas.restore_region(self.bg)
                    ### 记录数据
                    self.RtypeIIfit.typeIItime.append(event.xdata)
                    self.RtypeIIfit.typeIIfreq.append(event.ydata)
                    self.RtypeIIfit.typeIIndot += 1

                    self.hline[0].set_xdata(self.RtypeIIfit.typeIItime)
                    self.hline[0].set_ydata(self.RtypeIIfit.typeIIfreq)
                    # self.fig.canvas.draw()
                    # self.fig.canvas.flush_events()
                    self.clickAxs.draw_artist(self.hline[0])
                    self.figureID.canvas.blit(self.figureID.bbox)
                    self.figureID.canvas.flush_events()
        elif (event.button == 3) and (not event.dblclick):
            #### 重新选择 点点
            if event.inaxes is not None:
                if event.inaxes == self.clickAxs:
                    self.mainButton2.setText("Type II Fitting")
                    self.mainButton2.clicked.disconnect(self.typeIIfitHeight)
                    self.clickAxs = None
                    self.RtypeIIfit.typeIIndot = 0
                    self.RtypeIIfit.typeIIfreq = []
                    self.RtypeIIfit.typeIItime = []
                    self.hline[0].remove()

                    self.figureID.canvas.restore_region(self.bg)
                    # self.fig.canvas.draw()
                    # self.fig.canvas.flush_events()
                    # self.clickAxs.draw_artist(self.hline[0])
                    self.figureID.canvas.blit(self.figureID.bbox)
                    self.figureID.canvas.flush_events()
                    # self.figureID.canvas.mpl_disconnect(self.cidpress )

        elif (event.button == 3) and event.dblclick:
            ### 双击右键 退出 拟合状态
            if self.cidpress is not None:
                self.figureID.canvas.mpl_disconnect(self.cidpress)
            self.Canvas2PlotSet.emit("tpyeIIfitClose")
            self.mainButton2.setText("TypeII Backbone")
            self.mainButton2.setStyleSheet("QPushButton { color: black}")
            if self.RtypeIIfit.typeIIndot > 0:
                self.mainButton2.clicked.disconnect(self.typeIIfitHeight)
                self.clickAxs = None
                self.fitnowclick = 0
                self.RtypeIIfit.typeIIndot = 0
                self.RtypeIIfit.typeIIfreq = []
                self.RtypeIIfit.typeIItime = []
                self.hline[0].remove()
                self.figureID.canvas.restore_region(self.bg)
                self.figureID.canvas.blit(self.figureID.bbox)
                self.figureID.canvas.flush_events()

            self.mainButton2.clicked.connect(self.mainBut2event)

    def mainBut2event(self):
        if self.cidpress is not None:
            self.figureID.canvas.mpl_disconnect(self.cidpress)
        self.cidpress = self.figureID.canvas.mpl_connect(
            "button_press_event", self.getDotClick
        )
        self.mainButton2.setStyleSheet(
            "QPushButton {background-color: green; color: red;}"
        )
        self.mainButton2.clicked.disconnect(self.mainBut2event)

    def RTypeIIfitClose(self):
        ## 关闭 拟合窗口；
        self.mainButton2.clicked.connect(self.mainBut2event)
        self.RtypeIIfit.typeIIndot = 0
        self.RtypeIIfit.typeIIfreq = []
        self.RtypeIIfit.typeIItime = []
        ## 刷新 主界面界面
        self.figureID.canvas.restore_region(self.bg)
        self.figureID.canvas.blit(self.figureID.bbox)
        self.figureID.canvas.flush_events()
        self.Canvas2PlotSet.emit("tpyeIIfitClose")
        ## 关闭窗口
        self.RtypeIIfit.textBrowser.clear()
        self.RtypeIIfit.close()


###############################################################


#### 显示数据信息和 画图设置
class dataPlotInfoWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Data and Plot")
        #### 全局变量
        self.plotgoesV = True
        self.freqobs1 = 150.0
        self.freqobs2 = 450.0
        self.dayShift = 0  ## 控制是否是前一天
        self.datet00 = None  ### 观测日期  datetime 类
        self.datetdstr = None
        self.datetdend = None
        self.begDateTset = None
        self.endDateTset = None
        self.polars = ""
        ###########################
        self.vlayout = QtWidgets.QVBoxLayout()

        self.textBrowser = QtWidgets.QTextBrowser()
        self.vlayout.addWidget(self.textBrowser)

        # ## 创建校验器
        maxvValid = QDoubleValidator(self)
        intValid = QIntValidator(self)
        ##### 设置偏振信息 =====
        self.polarboxg = QtWidgets.QGroupBox("Polarization")
        self.polarLayout = QtWidgets.QHBoxLayout()
        self.polarlabelt0 = QtWidgets.QLabel()
        self.polarlabelt0.setText("Select  : (default all, input as: HV ) ")
        self.polarLayout.addWidget(self.polarlabelt0)
        self.polarlineEdit = QtWidgets.QLineEdit()
        self.polarLayout.addWidget(self.polarlineEdit)
        self.polarlineEdit.setFixedWidth(80)

        # self.polarcomboBox = QtWidgets.QComboBox()
        # self.polarcomboBox.addItem('HH + VV')
        # self.polarcomboBox.addItem('HH')
        # self.polarcomboBox.addItem('VV')
        # self.polarLayout.addWidget( self.polarcomboBox )

        self.polarlabelt1 = QtWidgets.QLabel()
        self.polarlabelt1.setText("All Polarization : " + self.polars)
        self.polarLayout.addWidget(self.polarlabelt1)

        self.polarboxg.setLayout(self.polarLayout)
        self.vlayout.addWidget(self.polarboxg)
        ###### 设置选择时间框 ======
        self.timebox = QtWidgets.QGroupBox("Time")
        self.timeboxV = QtWidgets.QVBoxLayout()

        self.vlayoutH = QtWidgets.QHBoxLayout()
        # self.vlayout.addLayout( self.vlayoutH )

        self.labelt1 = QtWidgets.QLabel()
        self.labelt1.setText("Start : ")
        self.vlayoutH.addWidget(self.labelt1)
        ### start time
        self.Timestart = QtWidgets.QDateTimeEdit()
        self.datet00 = datetime.datetime(2023, 3, 30, 0, 0, 0)

        self.datetdstr = datetime.datetime(2023, 3, 30, 1, 0, 0)
        self.datetdend = datetime.datetime(2023, 3, 30, 8, 0, 0)
        self.begts = int(np.floor((self.datetdstr - self.datet00).total_seconds()))
        self.endts = int(np.ceil((self.datetdend - self.datet00).total_seconds()))

        tt = self.datet00 + datetime.timedelta(seconds=self.begts)
        self.Timestart.setDateTime(
            QDateTime(tt.year, tt.month, tt.day, tt.hour, tt.minute, tt.second)
        )
        # self.Timestart.setDisplayFormat('hh:mm:ss')
        self.Timestart.setDisplayFormat("yyyy-MM-ddThh:mm:ss")
        self.Timestart.dateTimeChanged.connect(self.setslider1)

        self.vlayoutH.addWidget(self.Timestart)

        self.hoSlider1 = QtWidgets.QSlider()
        self.vlayoutH.addWidget(self.hoSlider1)

        self.hoSlider1.setOrientation(Qt.Horizontal)
        self.hoSlider1.setRange(self.begts, self.endts)

        self.hoSlider1.setSingleStep(1)
        self.hoSlider1.valueChanged.connect(self.setStartTime)

        self.vlayoutH2 = QtWidgets.QHBoxLayout()
        # self.vlayout.addLayout( self.vlayoutH2 )
        self.labelt12 = QtWidgets.QLabel()
        self.labelt12.setText(self.datetdend.strftime("%H:%M:%S"))
        self.vlayoutH.addWidget(self.labelt12)

        #########################################
        self.labelt2 = QtWidgets.QLabel()
        self.labelt2.setText("End   : ")
        self.vlayoutH2.addWidget(self.labelt2)
        ##### end time
        self.Timeend = QtWidgets.QDateTimeEdit()
        self.vlayoutH2.addWidget(self.Timeend)
        self.hoSlider2 = QtWidgets.QSlider()
        self.vlayoutH2.addWidget(self.hoSlider2)
        tt = self.datet00 + datetime.timedelta(seconds=self.endts)
        self.Timeend.setDateTime(
            QDateTime(tt.year, tt.month, tt.day, tt.hour, tt.minute, tt.second)
        )
        # self.Timeend.setDisplayFormat('hh:mm:ss')
        self.Timeend.setDisplayFormat("yyyy-MM-ddThh:mm:ss")
        self.Timeend.dateTimeChanged.connect(self.setslider2)

        self.hoSlider2.setOrientation(Qt.Horizontal)
        self.hoSlider2.setRange(self.begts, self.endts)
        self.hoSlider2.setSliderPosition(self.endts)
        self.hoSlider2.setSingleStep(1)
        self.hoSlider2.valueChanged.connect(self.setEndTime)

        self.labelt22 = QtWidgets.QLabel()
        self.labelt22.setText(self.datetdend.strftime("%H:%M:%S"))
        self.vlayoutH2.addWidget(self.labelt22)

        self.timeboxV.addLayout(self.vlayoutH)
        self.timeboxV.addLayout(self.vlayoutH2)
        self.timebox.setLayout(self.timeboxV)
        self.vlayout.addWidget(self.timebox)
        #############################3
        ##### 设置频率信息 =====
        self.freqboxg = QtWidgets.QGroupBox("Frequency")
        self.freqLayout = QtWidgets.QVBoxLayout()
        #### 两个横条-------------------------
        self.freqlayoutH = QtWidgets.QHBoxLayout()
        self.freqlabelt1 = QtWidgets.QLabel()
        self.freqlabelt1.setText("Start : ")
        self.freqlayoutH.addWidget(self.freqlabelt1)

        self.freqlineEdit1 = QtWidgets.QLineEdit()
        self.freqlayoutH.addWidget(self.freqlineEdit1)
        self.freqlineEdit1.setFixedWidth(120)
        self.freqlineEdit1.setValidator(maxvValid)
        self.freqlineEdit1.setText(f"{self.freqobs1:6.2f}")
        self.freqlineEdit1.textChanged.connect(self.setFreqSlider1)

        self.freqlabelt11 = QtWidgets.QLabel()
        self.freqlabelt11.setText(f" MHz {self.freqobs1:6.2f}")
        self.freqlayoutH.addWidget(self.freqlabelt11)

        self.freqSlider1 = QtWidgets.QSlider()
        self.freqlayoutH.addWidget(self.freqSlider1)
        self.freqSlider1.setOrientation(Qt.Horizontal)
        self.freqSlider1.setRange(int(self.freqobs1 - 1), int(self.freqobs2 + 1))
        self.freqSlider1.setSingleStep(1)

        self.freqSlider1.valueChanged.connect(self.setStartFreq)

        self.freqlabelt12 = QtWidgets.QLabel()
        self.freqlabelt12.setText(f"{self.freqobs2:6.2f} MHz")
        self.freqlayoutH.addWidget(self.freqlabelt12)

        self.freqlayoutH2 = QtWidgets.QHBoxLayout()
        self.freqlabelt2 = QtWidgets.QLabel()
        self.freqlabelt2.setText("End   : ")
        self.freqlayoutH2.addWidget(self.freqlabelt2)

        ### 文本框
        self.freqlineEdit2 = QtWidgets.QLineEdit()
        self.freqlayoutH2.addWidget(self.freqlineEdit2)
        self.freqlineEdit2.setFixedWidth(120)
        self.freqlineEdit2.setValidator(maxvValid)
        self.freqlineEdit2.setText(f"{self.freqobs2:6.2f}")
        self.freqlineEdit2.textChanged.connect(self.setFreqSlider2)

        self.freqlabelt21 = QtWidgets.QLabel()
        self.freqlabelt21.setText(f" MHz {self.freqobs1:6.2f}")
        self.freqlayoutH2.addWidget(self.freqlabelt21)

        self.freqSlider2 = QtWidgets.QSlider()
        self.freqlayoutH2.addWidget(self.freqSlider2)
        self.freqSlider2.setOrientation(Qt.Horizontal)
        self.freqSlider2.setRange(int(self.freqobs1 - 1), int(self.freqobs2 + 1))
        self.freqSlider2.setSingleStep(1)
        self.freqSlider2.setSliderPosition(int(self.freqobs2))
        self.freqSlider2.valueChanged.connect(self.setEndFreq)

        self.freqlabelt22 = QtWidgets.QLabel()
        self.freqlabelt22.setText(f"{self.freqobs2:6.2f} MHz")
        self.freqlayoutH2.addWidget(self.freqlabelt22)

        self.freqLayout.addLayout(self.freqlayoutH)
        self.freqLayout.addLayout(self.freqlayoutH2)
        self.freqboxg.setLayout(self.freqLayout)
        self.vlayout.addWidget(self.freqboxg)
        #### 设置数据rebin 默认数据 rebin
        self.rebinboxg = QtWidgets.QGroupBox("Rebin ")
        self.rebinLayout = QtWidgets.QHBoxLayout()
        ### check box
        self.checkBox = QtWidgets.QCheckBox("rebin ")
        self.rebinLayout.addWidget(self.checkBox)
        self.checkBox.setChecked(True)
        #### rebin number
        intValid.setRange(1, 1000000)
        self.checklabelT = QtWidgets.QLabel()
        self.checklabelT.setText("Time num:  ")
        self.rebinLayout.addWidget(self.checklabelT)
        self.checklineEdit1 = QtWidgets.QLineEdit()
        self.rebinLayout.addWidget(self.checklineEdit1)
        self.checklineEdit1.setValidator(intValid)

        self.checklabelF = QtWidgets.QLabel()
        self.checklabelF.setText("Frequency num:  ")
        self.rebinLayout.addWidget(self.checklabelF)
        self.checklineEdit2 = QtWidgets.QLineEdit()
        self.rebinLayout.addWidget(self.checklineEdit2)
        self.checklineEdit2.setValidator(intValid)

        self.rebinboxg.setLayout(self.rebinLayout)
        self.vlayout.addWidget(self.rebinboxg)
        ##### 设置归一化信息 =====
        self.scaleboxg = QtWidgets.QGroupBox("Scale ")
        self.scaleLayout0 = QtWidgets.QVBoxLayout()
        self.scaleLayout = QtWidgets.QHBoxLayout()
        self.scaleLayout2 = QtWidgets.QHBoxLayout()
        ####
        self.scalecomboBox = QtWidgets.QComboBox()
        self.scaleLayout.addWidget(self.scalecomboBox)
        self.scalecomboBox.addItem("log10")
        self.scalecomboBox.addItem("linear")
        # self.colorcomboBox.addItem('gray')

        self.scalecomboBox.setFixedHeight(30)
        self.scalelabelt1 = QtWidgets.QLabel()
        self.scalelabelt1.setText("Maximum:  ")
        self.scaleLayout.addWidget(self.scalelabelt1)
        self.scalelineEdit1 = QtWidgets.QLineEdit()
        self.scaleLayout.addWidget(self.scalelineEdit1)

        self.scalelineEdit1.setText("4.0")
        # ## 创建校验器
        # maxvValid = QDoubleValidator( self )
        self.scalelineEdit1.setValidator(maxvValid)
        self.scalelineEdit1.textChanged.connect(self.scalemaxmin)

        self.scalelabelt2 = QtWidgets.QLabel()
        self.scalelabelt2.setText("Minimum:  ")
        self.scaleLayout.addWidget(self.scalelabelt2)

        self.scalelineEdit2 = QtWidgets.QLineEdit()
        self.scaleLayout.addWidget(self.scalelineEdit2)
        self.scalelineEdit2.setText("1.0")
        ## 设置校验器
        self.scalelineEdit2.setValidator(maxvValid)
        self.scalelineEdit2.textChanged.connect(self.scalemaxmin)

        self.scalelabelt3 = QtWidgets.QLabel()
        self.scalelabelt3.setText("          ")
        self.scaleLayout.addWidget(self.scalelabelt3)
        self.scalelabelt3.setStyleSheet("QLabel { color : red; }")
        self.scaleLayout0.addLayout(self.scaleLayout)
        # self.scaleboxg.setLayout( self.scaleLayout  )

        self.checkBox2zh = QtWidgets.QCheckBox("2 value scale ")
        self.scaleLayout2.addWidget(self.checkBox2zh)
        self.checkBox2zh.setChecked(False)
        self.scalelabelta2 = QtWidgets.QLabel()
        self.scalelabelta2.setText("Set value :  ")
        self.scaleLayout2.addWidget(self.scalelabelta2)
        self.valueEdit1 = QtWidgets.QLineEdit()
        self.scaleLayout2.addWidget(self.valueEdit1)
        self.valueEdit1.setFixedWidth(100)
        self.valueEdit1.setValidator(maxvValid)
        self.valueEdit1.setText(f"{100:6.2f}")
        ########
        self.checkBoxSB = QtWidgets.QCheckBox("subtract Background")
        self.scaleLayout2.addWidget(self.checkBoxSB)
        self.checkBoxSB.setChecked(False)

        self.scaleLayout0.addLayout(self.scaleLayout2)

        self.scaleboxg.setLayout(self.scaleLayout0)
        self.vlayout.addWidget(self.scaleboxg)

        ##### 设置 色表 信息 =====
        self.colormboxg = QtWidgets.QGroupBox("Color")
        self.colorLayout = QtWidgets.QHBoxLayout()
        #### 下拉框

        self.colorlabelt1 = QtWidgets.QLabel()
        self.colorlabelt1.setText("Select:   ")
        self.colorcomboBox = QtWidgets.QComboBox()
        self.colorcomboBox.addItem("jet")
        self.colorcomboBox.addItem("hot")
        self.colorcomboBox.addItem("gray")

        self.colorcomboBox.setFixedHeight(30)

        self.colorLayout.addWidget(self.colorlabelt1)
        self.colorLayout.addWidget(self.colorcomboBox)

        self.colormboxg.setLayout(self.colorLayout)
        self.vlayout.addWidget(self.colormboxg)
        #######################################
        ##### 设置 pcolormesh method 信息 =====
        self.pcolormboxg = QtWidgets.QGroupBox("pcolormeshsetting")
        self.pcolorLayout = QtWidgets.QHBoxLayout()
        #### 下拉框

        self.pcolorlabelt1 = QtWidgets.QLabel()
        self.pcolorlabelt1.setText("shading =   ")
        self.pcolorcomboBox = QtWidgets.QComboBox()
        self.pcolorcomboBox.addItem("flat")
        self.pcolorcomboBox.addItem("nearest")
        self.pcolorcomboBox.addItem("gouraud")
        # self.pcolorcomboBox.addItem('flat')

        self.pcolorcomboBox.setFixedHeight(30)

        self.pcolorLayout.addWidget(self.pcolorlabelt1)
        self.pcolorLayout.addWidget(self.pcolorcomboBox)

        self.pcolormboxg.setLayout(self.pcolorLayout)
        self.vlayout.addWidget(self.pcolormboxg)
        #######################################
        self.Hlayout = QtWidgets.QHBoxLayout()
        self.button1 = QtWidgets.QPushButton("Exit")
        # self.button1.setText('close')
        self.button1.clicked.connect(self.myclose)

        self.button2 = QtWidgets.QPushButton("Plot")
        # self.button1.setText('close')
        # self.button2.clicked.connect( self.openfile )
        self.Hlayout.addWidget(self.button2)
        self.Hlayout.addWidget(self.button1)
        self.vlayout.addLayout(self.Hlayout)
        ###################################
        self.setLayout(self.vlayout)

    ###########################################################################
    def dataPInfoShow(self, intex):
        self.textBrowser.setText("Data Information: ")
        for ss in intex:
            self.textBrowser.append(ss)
        self.show()

    def myclose(self):
        # if self.but2cid != None :
        #     self.but2cid = None
        self.close()

    def setStartTime(self):
        tts = 1.0 * self.hoSlider1.value()
        if tts < 0:
            self.dayShift = -1
        tt = self.datet00 + datetime.timedelta(seconds=tts)

        self.Timestart.setDateTime(
            QDateTime(tt.year, tt.month, tt.day, tt.hour, tt.minute, tt.second)
        )
        if self.hoSlider1.value() > self.hoSlider2.value():
            self.hoSlider2.setSliderPosition(self.hoSlider1.value())
        self.begDateTset = tt

    def setStartFreq(self):
        ffs = 1.0 * self.freqSlider1.value()
        self.freqlineEdit1.setText(f"{ffs:6.2f}")
        if self.freqSlider1.value() > self.freqSlider2.value():
            self.freqSlider2.setSliderPosition(self.freqSlider1.value())

    def setEndFreq(self):
        ffs = 1.0 * self.freqSlider2.value()
        self.freqlineEdit2.setText(f"{ffs:6.2f}")
        if self.freqSlider1.value() > self.freqSlider2.value():
            self.freqSlider1.setSliderPosition(self.freqSlider2.value())

    def setFreqSlider1(self):
        palette = self.freqlineEdit2.palette()
        palette.setColor(QPalette.Text, QColor("black"))
        ffs = float(self.freqlineEdit1.text())
        self.plotgoesV = True
        self.freqSlider1.setSliderPosition(int(ffs))
        if ffs > float(self.freqlineEdit2.text()):
            palette.setColor(QPalette.Text, QColor("red"))
            self.plotgoesV = False
        self.freqlineEdit1.setPalette(palette)
        self.freqlineEdit2.setPalette(palette)

    def setFreqSlider2(self):
        palette = self.freqlineEdit2.palette()
        palette.setColor(QPalette.Text, QColor("black"))
        self.plotgoesV = True
        ffs = float(self.freqlineEdit2.text())
        self.freqSlider2.setSliderPosition(int(ffs))
        if ffs < float(self.freqlineEdit1.text()):
            palette.setColor(QPalette.Text, QColor("red"))
            self.plotgoesV = False
        self.freqlineEdit1.setPalette(palette)
        self.freqlineEdit2.setPalette(palette)

    def setslider1(self):
        ttt = self.Timestart.dateTime()
        tt = datetime.datetime(
            ttt.date().year(),
            ttt.date().month(),
            ttt.date().day(),
            ttt.time().hour(),
            ttt.time().minute(),
            ttt.time().second(),
        )
        posnt = int((tt - self.datet00).total_seconds())
        self.hoSlider1.setSliderPosition(posnt)
        if self.hoSlider1.value() > self.hoSlider2.value():
            self.hoSlider2.setSliderPosition(posnt)
        self.begDateTset = tt

    def setEndTime(self):
        tts = 1.0 * self.hoSlider2.value()
        # print(tts)
        tt = self.datet00 + datetime.timedelta(seconds=tts)
        # print(tt )
        self.Timeend.setDateTime(
            QDateTime(tt.year, tt.month, tt.day, tt.hour, tt.minute, tt.second)
        )
        if self.hoSlider1.value() > self.hoSlider2.value():
            self.hoSlider1.setSliderPosition(self.hoSlider2.value())
        self.endDateTset = tt

    def setslider2(self):
        ttt = self.Timeend.dateTime()
        tt = datetime.datetime(
            ttt.date().year(),
            ttt.date().month(),
            ttt.date().day(),
            ttt.time().hour(),
            ttt.time().minute(),
            ttt.time().second(),
        )
        posnt = int((tt - self.datet00).total_seconds())
        self.hoSlider2.setSliderPosition(posnt)
        if self.hoSlider1.value() > self.hoSlider2.value():
            self.hoSlider1.setSliderPosition(posnt)
        self.endDateTset = tt

    def scalemaxmin(self):
        palette = self.scalelineEdit1.palette()
        palette.setColor(QPalette.Text, QColor("black"))
        errotext = "          "
        self.plotgoesV = True
        # print('============================================')
        if float(self.scalelineEdit2.text()) > float(self.scalelineEdit1.text()):
            # print('error set')
            errotext = "error set "
            self.plotgoesV = False
            palette.setColor(QPalette.Text, QColor("red"))

        self.scalelineEdit1.setPalette(palette)
        self.scalelineEdit2.setPalette(palette)
        self.scalelabelt3.setText(errotext)


###########################################################################


#### 显示 fits 文件信息
class FileInfoWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CSO File Information")
        self.vlayout = QtWidgets.QVBoxLayout()

        self.textBrowser = QtWidgets.QTextBrowser()
        # self.textBrowser.setFixedWidth(800)
        self.vlayout.addWidget(self.textBrowser)

        self.Hlayout = QtWidgets.QHBoxLayout()
        self.button1 = QtWidgets.QPushButton("Exit")
        # self.button1.setText('close')
        self.button1.clicked.connect(self.myclose)

        self.button2 = QtWidgets.QPushButton("Load")
        # self.button1.setText('close')
        # self.button2.clicked.connect( self.openfile )
        self.Hlayout.addWidget(self.button2)
        self.Hlayout.addWidget(self.button1)

        # self.but2cid = None

        self.vlayout.addLayout(self.Hlayout)

        self.setLayout(self.vlayout)

    def FileInfoShow(self, intex):
        self.textBrowser.setText("File Information: ")
        for ss in intex:
            self.textBrowser.append(ss)
        self.show()

    def myclose(self):
        # if self.but2cid != None :
        #     self.but2cid = None
        self.close()


class dsrtSpecWindow(QtWidgets.QWidget):
    ###
    ### 子类上传 回调信息
    Canvas2PlotSet = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CSO Spectra")
        ####### 全局变量
        self.files = []  ### 需要处理的文件
        self.fig = plt.figure()  ### matplotlib 画图区
        self.ax = []  ### 坐标轴
        self.fileinfo = FileInfoWindow()
        self.specd = dsrtSpectraData()
        self.specd.figureID = self.fig
        self.dataPlotInfo = dataPlotInfoWindow()
        self.Canvas2PlotSet.connect(self.signalset)
        self.specd.Canvas2PlotSet = self.Canvas2PlotSet
        self.plotflux = plotfluxGUI()
        self.prefnext = 0
        self.replotv = False  ## 是否是 重画
        self.numplot = 0  ## 画图次数
        #### sav figure name
        self.savjpgname = "./"
        ##### sav fits name
        self.savfitsname = "./"
        ###################
        self.mainUiSet()

    def mainUiSet(self):
        self.baslayout = QtWidgets.QVBoxLayout()
        self.Hlayout = QtWidgets.QHBoxLayout()

        self.button1 = QtWidgets.QPushButton("File")
        self.button1.clicked.connect(self.filesearch)
        self.Hlayout.addWidget(self.button1)

        # self.button2 = QtWidgets.QPushButton('TypeII Fit')
        self.button2 = QtWidgets.QPushButton("TypeII Backbone")
        # self.button2.clicked.connect( self.filesearch )
        self.Hlayout.addWidget(self.button2)
        self.buttonflux = QtWidgets.QPushButton("Plot Flux")
        # self.button2.clicked.connect( self.filesearch )
        self.Hlayout.addWidget(self.buttonflux)

        self.button3 = QtWidgets.QPushButton("Save Figure")
        # self.button2.clicked.connect( self.filesearch )
        self.Hlayout.addWidget(self.button3)
        self.button4 = QtWidgets.QPushButton("Exit")
        self.Hlayout.addWidget(self.button4)
        self.button4.clicked.connect(self.MainClose)

        self.specd.mainButton2 = self.button2

        self.Hlayout2 = QtWidgets.QHBoxLayout()
        self.button21 = QtWidgets.QPushButton("pref")
        self.lineEdit21 = QtWidgets.QLineEdit()
        self.lineEdit21.setFixedWidth(120)
        self.lineEdit21.setText("0")

        self.scalelabelta21 = QtWidgets.QLabel()
        self.scalelabelta21.setText(" Seconds")
        self.button22 = QtWidgets.QPushButton("next")
        self.lineEdit22 = QtWidgets.QLineEdit()
        self.lineEdit22.setText("x=, y=, z=")

        self.button23 = QtWidgets.QPushButton("savefits")
        self.Hlayout2.addWidget(self.button21)
        self.Hlayout2.addWidget(self.lineEdit21)
        self.Hlayout2.addWidget(self.scalelabelta21)
        self.Hlayout2.addWidget(self.button22)
        self.Hlayout2.addWidget(self.lineEdit22)
        self.Hlayout2.addWidget(self.button23)

        #### 提取canvas
        self.canvas = FigureCanvasQTAgg(self.fig)

        ####

        #### 添加 组件到 垂直层
        self.baslayout.addLayout(self.Hlayout)
        self.baslayout.addLayout(self.Hlayout2)

        self.baslayout.addWidget(self.canvas)

        ### 添加基层布局到主窗口
        self.setLayout(self.baslayout)

        ####

    def filesearch(self):
        files, ok1 = QtWidgets.QFileDialog.getOpenFileNames(
            self, "choose dsrt radio spectro Fits", "./", "(*.fits)"
        )
        #          "All Files (*);;Text Files (*.fits)")
        # print(files,ok1)
        self.files = files
        self.specd.filename = files
        self.specd.nf = len(files)
        if len(files) > 0:
            self.fileinfo.button2.clicked.connect(self.loaddata)

        #    showtex = '/n'.join( files )
        # else :
        #    showtex = 'no files input!/n'
        self.fileinfo.FileInfoShow(files)

    def loaddata(self):
        self.specd.readdata(allread=1)
        ######  set dataPlotInfo GUI

        npolar = len(self.specd.data)
        if npolar == 0:
            self.fileinfo.FileInfoShow(" something is wrong !")
            return
        self.dataPlotInfo.dataPInfoShow(
            [
                "Start Time :" + self.specd.beginTime.isoformat(),
                "End Time :" + self.specd.endTime.isoformat(),
                f"Time Resolution : {self.specd.resolveTime:f} seconds ",
                f"Frequency Resolution : {self.specd.resolveFreq * 1000:f} kHz",
                f"Time Length is {len(self.specd.data[0].time)}",
                f"Frequency Length is {len(self.specd.data[0].freq)}",
            ]
        )

        ### 设置初始日期 ====
        self.dataPlotInfo.datet00 = self.specd.datet0
        ### 设置偏振 ======
        self.dataPlotInfo.polars = "".join(
            [self.specd.data[kk].polar[0] for kk in range(npolar)]
        )
        self.dataPlotInfo.polarlineEdit.setText(self.dataPlotInfo.polars)
        self.dataPlotInfo.polarlabelt1.setText(
            "All Polarization : " + self.dataPlotInfo.polars
        )

        ##### 设置时间 ######
        self.dataPlotInfo.datetdstr = self.specd.beginTime
        self.dataPlotInfo.datetdend = self.specd.endTime
        self.dataPlotInfo.begts = int(
            np.floor(
                (
                    self.dataPlotInfo.datetdstr - self.dataPlotInfo.datet00
                ).total_seconds()
            )
        )
        self.dataPlotInfo.endts = int(
            np.ceil(
                (
                    self.dataPlotInfo.datetdend - self.dataPlotInfo.datet00
                ).total_seconds()
            )
        )

        tt = self.dataPlotInfo.datet00 + datetime.timedelta(
            seconds=self.dataPlotInfo.begts
        )
        self.dataPlotInfo.Timestart.setDateTime(
            QDateTime(tt.year, tt.month, tt.day, tt.hour, tt.minute, tt.second)
        )

        self.dataPlotInfo.hoSlider1.setRange(
            self.dataPlotInfo.begts, self.dataPlotInfo.endts
        )
        self.dataPlotInfo.hoSlider1.setSliderPosition(self.dataPlotInfo.begts)
        self.dataPlotInfo.hoSlider2.setRange(
            self.dataPlotInfo.begts, self.dataPlotInfo.endts
        )
        self.dataPlotInfo.hoSlider2.setSliderPosition(self.dataPlotInfo.endts)

        tt = self.dataPlotInfo.datet00 + datetime.timedelta(
            seconds=self.dataPlotInfo.endts
        )
        self.dataPlotInfo.Timeend.setDateTime(
            QDateTime(tt.year, tt.month, tt.day, tt.hour, tt.minute, tt.second)
        )
        ## 结束时间
        self.dataPlotInfo.labelt12.setText(
            self.dataPlotInfo.datetdend.strftime("%H:%M:%S")
        )
        self.dataPlotInfo.labelt22.setText(
            self.dataPlotInfo.datetdend.strftime("%H:%M:%S")
        )

        ########设置频率 =========
        self.dataPlotInfo.freqobs1 = self.specd.beginFreq
        self.dataPlotInfo.freqobs2 = self.specd.endFreq
        self.dataPlotInfo.freqlineEdit1.setText(f"{self.dataPlotInfo.freqobs1:6.2f}")
        self.dataPlotInfo.freqlineEdit2.setText(f"{self.dataPlotInfo.freqobs2:6.2f}")
        self.dataPlotInfo.freqSlider1.setRange(
            int(self.dataPlotInfo.freqobs1 - 1), int(self.dataPlotInfo.freqobs2 + 1)
        )
        self.dataPlotInfo.freqSlider2.setRange(
            int(self.dataPlotInfo.freqobs1 - 1), int(self.dataPlotInfo.freqobs2 + 1)
        )
        self.dataPlotInfo.freqSlider1.setSliderPosition(int(self.dataPlotInfo.freqobs1))
        self.dataPlotInfo.freqSlider2.setSliderPosition(int(self.dataPlotInfo.freqobs2))

        self.dataPlotInfo.freqlabelt11.setText(
            f" MHz {self.dataPlotInfo.freqobs1:6.2f}"
        )
        self.dataPlotInfo.freqlabelt21.setText(
            f" MHz {self.dataPlotInfo.freqobs1:6.2f}"
        )
        self.dataPlotInfo.freqlabelt12.setText(
            f" MHz {self.dataPlotInfo.freqobs2:6.2f}"
        )
        self.dataPlotInfo.freqlabelt22.setText(
            f" MHz {self.dataPlotInfo.freqobs2:6.2f}"
        )
        #### 设置rebin
        self.specd.rebinsw = self.dataPlotInfo.checkBox.isChecked()
        self.specd.subbackv = self.dataPlotInfo.checkBoxSB.isChecked()

        if self.specd.rebinsw:
            rebinNum = 2000
            self.specd.rebinTnum = int(len(self.specd.data[0].time) / rebinNum)
            self.specd.rebinFnum = int(len(self.specd.data[0].freq) / rebinNum)
            if (self.specd.rebinTnum + self.specd.rebinFnum) == 0:
                self.dataPlotInfo.checkBox.setChecked(False)

            if self.specd.rebinTnum == 0:
                self.specd.rebinTnum = 1
            if self.specd.rebinFnum == 0:
                self.specd.rebinFnum = 1
            self.dataPlotInfo.checklineEdit1.setText(f"{self.specd.rebinTnum:d}")
            self.dataPlotInfo.checklineEdit2.setText(f"{self.specd.rebinFnum:d}")

        if self.numplot == 0:
            self.dataPlotInfo.button2.clicked.connect(self.plotimg)
        else:
            self.dataPlotInfo.button2.clicked.connect(self.replotimg)
        self.numplot += 1
        self.fileinfo.close()

    def MainClose(self):
        self.dataPlotInfo.close()
        self.fileinfo.close()

        self.close()

    def plotimg(self):
        ### 获取偏振字符串
        polars = self.dataPlotInfo.polarlineEdit.text()
        if polars == "":
            polars = None
        #### 获取时间范围
        t1 = self.dataPlotInfo.Timestart.dateTime()
        t1ch = datetime.datetime(
            t1.date().year(),
            t1.date().month(),
            t1.date().day(),
            t1.time().hour(),
            t1.time().minute(),
            t1.time().second(),
        )
        t1 = self.dataPlotInfo.Timeend.dateTime()
        t2ch = datetime.datetime(
            t1.date().year(),
            t1.date().month(),
            t1.date().day(),
            t1.time().hour(),
            t1.time().minute(),
            t1.time().second(),
        )
        ###### 获取频率范围=====
        f1 = float(self.dataPlotInfo.freqlineEdit1.text())
        f2 = float(self.dataPlotInfo.freqlineEdit2.text())
        ##### 获取归一化方式
        scaleway = self.dataPlotInfo.scalecomboBox.currentText()
        maxvs = float(self.dataPlotInfo.scalelineEdit1.text())
        minvs = float(self.dataPlotInfo.scalelineEdit2.text())
        ######  获取 色表 ===
        cmaps = self.dataPlotInfo.colorcomboBox.currentText()
        ######  获取 pcolormesh shading set ===
        pshading = self.dataPlotInfo.pcolorcomboBox.currentText()

        ##### 获取 rebin 设置 =====
        self.specd.rebinsw = self.dataPlotInfo.checkBox.isChecked()
        self.specd.subbackv = self.dataPlotInfo.checkBoxSB.isChecked()
        if self.dataPlotInfo.checklineEdit1.text() == "":
            self.specd.rebinTnum = 1
        else:
            self.specd.rebinTnum = int(self.dataPlotInfo.checklineEdit1.text())

        if self.dataPlotInfo.checklineEdit2.text() == "":
            self.specd.rebinFnum = 1
        else:
            self.specd.rebinFnum = int(self.dataPlotInfo.checklineEdit2.text())
        self.specd.dvalue2 = self.dataPlotInfo.checkBox2zh.isChecked()
        if self.specd.dvalue2:
            self.specd.dvalueset = float(self.dataPlotInfo.valueEdit1.text())

        ###### 输入画图 =====
        # self.specd.plot_image(begch='07:35:30', endch='07:38:00',scalestyle = 'log10', endff = 250, minv=1.0, maxv=4.0 )
        self.specd.plot_image(
            begch=t1ch,
            endch=t2ch,
            scalestyle=scaleway,
            begff=f1,
            endff=f2,
            minv=minvs,
            maxv=maxvs,
            polar=polars,
            newcmp=cmaps,
            shadingset=pshading,
        )

        self.fig.canvas.draw()
        #     specd.figureID
        self.dataPlotInfo.button2.setText("RePlot")
        self.dataPlotInfo.close()
        self.button2.clicked.connect(self.specd.mainBut2event)
        self.button3.clicked.connect(self.saveThisFig)
        self.buttonflux.clicked.connect(self.fluxplotfun)
        self.plotflux.SignalClickClose.connect(self.fluxguiExit)
        self.button21.clicked.connect(self.buttonpref)
        self.button22.clicked.connect(self.buttonnext)
        self.button23.clicked.connect(self.savefitsFile)

        self.specd.cidpress = self.specd.figureID.canvas.mpl_connect(
            "button_press_event", self.replotset
        )

    def saveThisFig(self):
        options = QtWidgets.QFileDialog.Options()
        # options = QtWidgets.QFileDialog.DontUseNativeDialog  # ½ûÓÃÔ­Éú¶Ô»°¿ò
        # options |= QtWidgets.QFileDialog.DontConfirmOverwrite
        options |= QtWidgets.QFileDialog.ExistingFile
        t1 = self.dataPlotInfo.Timestart.dateTime()
        t1ch = datetime.datetime(
            t1.date().year(),
            t1.date().month(),
            t1.date().day(),
            t1.time().hour(),
            t1.time().minute(),
            t1.time().second(),
        )
        self.savjpgname = (
            os.path.dirname(self.savjpgname)
            + "/CBSm"
            + t1ch.strftime("%Y-%m-%dT%H%M%S")
            + ".jpg"
        )

        file1, ok1 = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "save radio spectro plot",
            self.savjpgname,
            "(*.png; *.jpg; *.jpeg; *.eps)",
            options=options,
        )
        # self.fig.canvas.draw()
        # if self.specd.fitnowclick == 1 :
        #     # self.specd.figureID.canvas.mpl_disconnect(self.specd.cidpress )
        #     self.fig.savefig( file1 )
        #     # self.specd.cidpress = self.specd.figureID.canvas.mpl_connect(
        #     #     'button_press_event', self.specd.getDotClick )

        # else :
        #     self.fig.savefig( file1  )

        self.savjpgname = file1

        # if

        self.fig.savefig(file1)

    def replotset(self, event):
        if event.button == 1:
            if event.dblclick:
                if event.inaxes is not None:
                    if not self.replotv:
                        self.dataPlotInfo.button2.clicked.disconnect(self.plotimg)
                        self.dataPlotInfo.button2.clicked.connect(self.replotimg)
                    self.replotv = True
                    self.dataPlotInfo.show()

            else:
                ### disp 坐标和数据
                if event.inaxes is not None:
                    ### present axis is na
                    axkk = self.specd.axs.index(event.inaxes)

                    xk = event.xdata
                    yk = event.ydata
                    zk, xkts = self.getdatabyxy(xk, yk, axkk)

                    self.lineEdit22.setText(
                        f"x={xkts} UT,  y={yk:.3f} MHz,  z={zk:.3f}"
                    )

        # print('replot ')

    def getdatabyxy(self, xk, yk, axkk):
        # polars = self.dataPlotInfo.polarlineEdit.text()
        # self.savefitsdata.append( (tt,freq,Z,polss,datet0) )
        ts = (xk - int(xk)) * (24 * 3600)
        if ts > 21 * 3600:
            ts = ts - 24 * 3600
        tt = self.specd.savefitsdata[axkk][0]
        ff = self.specd.savefitsdata[axkk][1]
        zz = self.specd.savefitsdata[axkk][2]
        tindex = np.where(tt >= ts)
        findex = np.where(ff >= yk)
        zk = zz[findex[0][0], tindex[0][0]]
        xkt = self.specd.savefitsdata[axkk][4] + datetime.timedelta(seconds=ts)
        xkts = xkt.isoformat()
        return zk, xkts

    #### 接收 信号 用于 typeII fit 关闭时 重新设置画布响应函数
    def signalset(self, sss):
        if sss == "tpyeIIfitClose":
            self.specd.cidpress = self.specd.figureID.canvas.mpl_connect(
                "button_press_event", self.replotset
            )
            # self.dataPlotInfo.button2.clicked.disconnect( self.plotimg )
            # self.dataPlotInfo.button2.clicked.connect( self.replotimg )
            # self.dataPlotInfo.show()
            self.specd.fitnowclick = 0
        # print('signal ')

    def buttonpref(self):
        self.prefnext = 1
        self.plotprenextf()
        self.replotimg()

    def buttonnext(self):
        self.prefnext = 2
        self.plotprenextf()
        self.replotimg()

    def plotprenextf(self):
        jiange = float(self.lineEdit21.text())
        t1 = self.dataPlotInfo.Timestart.dateTime()
        t1ch = datetime.datetime(
            t1.date().year(),
            t1.date().month(),
            t1.date().day(),
            t1.time().hour(),
            t1.time().minute(),
            t1.time().second(),
        )
        t2 = self.dataPlotInfo.Timeend.dateTime()
        t2ch = datetime.datetime(
            t2.date().year(),
            t2.date().month(),
            t2.date().day(),
            t2.time().hour(),
            t2.time().minute(),
            t2.time().second(),
        )

        if jiange < 1:
            jiange = (t2ch - t1ch).total_seconds()

        if self.prefnext == 1:
            tt = t1ch - datetime.timedelta(seconds=jiange)
            if tt > self.specd.beginTime:
                self.dataPlotInfo.Timestart.setDateTime(
                    QDateTime(tt.year, tt.month, tt.day, tt.hour, tt.minute, tt.second)
                )
                tt = t1ch
                self.dataPlotInfo.Timeend.setDateTime(
                    QDateTime(tt.year, tt.month, tt.day, tt.hour, tt.minute, tt.second)
                )
        if self.prefnext == 2:
            tt = t2ch + datetime.timedelta(seconds=jiange)
            if tt < self.specd.endTime:
                self.dataPlotInfo.Timeend.setDateTime(
                    QDateTime(tt.year, tt.month, tt.day, tt.hour, tt.minute, tt.second)
                )
                tt = t2ch
                self.dataPlotInfo.Timestart.setDateTime(
                    QDateTime(tt.year, tt.month, tt.day, tt.hour, tt.minute, tt.second)
                )

    def replotimg(self):

        ### 获取偏振字符串
        polars = self.dataPlotInfo.polarlineEdit.text()
        if polars == "":
            polars = None
        #### 获取时间范围
        t1 = self.dataPlotInfo.Timestart.dateTime()
        t1ch = datetime.datetime(
            t1.date().year(),
            t1.date().month(),
            t1.date().day(),
            t1.time().hour(),
            t1.time().minute(),
            t1.time().second(),
        )
        t1 = self.dataPlotInfo.Timeend.dateTime()
        t2ch = datetime.datetime(
            t1.date().year(),
            t1.date().month(),
            t1.date().day(),
            t1.time().hour(),
            t1.time().minute(),
            t1.time().second(),
        )
        ###### 获取频率范围=====
        f1 = float(self.dataPlotInfo.freqlineEdit1.text())
        f2 = float(self.dataPlotInfo.freqlineEdit2.text())
        ##### 获取归一化方式
        scaleway = self.dataPlotInfo.scalecomboBox.currentText()
        maxvs = float(self.dataPlotInfo.scalelineEdit1.text())
        minvs = float(self.dataPlotInfo.scalelineEdit2.text())
        ######  获取 色表 ===
        cmaps = self.dataPlotInfo.colorcomboBox.currentText()
        #######  获取 pcolormesh shading set ===
        pshading = self.dataPlotInfo.pcolorcomboBox.currentText()
        ##### 获取 rebin 设置 =====
        self.specd.rebinsw = self.dataPlotInfo.checkBox.isChecked()
        self.specd.subbackv = self.dataPlotInfo.checkBoxSB.isChecked()

        if self.dataPlotInfo.checklineEdit1.text() == "":
            self.specd.rebinTnum = 1
        else:
            self.specd.rebinTnum = int(self.dataPlotInfo.checklineEdit1.text())

        if self.dataPlotInfo.checklineEdit2.text() == "":
            self.specd.rebinFnum = 1
        else:
            self.specd.rebinFnum = int(self.dataPlotInfo.checklineEdit2.text())
        self.specd.dvalue2 = self.dataPlotInfo.checkBox2zh.isChecked()
        if self.specd.dvalue2:
            self.specd.dvalueset = float(self.dataPlotInfo.valueEdit1.text())

        self.fig.clear()
        self.ax = []
        self.specd.axs = []
        self.specd.inaxs = []
        self.specd.plotconfig = []

        ###### 输入画图 =====
        # self.specd.plot_image(begch='07:35:30', endch='07:38:00',scalestyle = 'log10', endff = 250, minv=1.0, maxv=4.0 )
        self.specd.plot_image(
            begch=t1ch,
            endch=t2ch,
            scalestyle=scaleway,
            begff=f1,
            endff=f2,
            minv=minvs,
            maxv=maxvs,
            polar=polars,
            newcmp=cmaps,
            shadingset=pshading,
        )

        self.fig.canvas.draw()
        #     specd.figureID
        # 关闭 设置框
        self.numplot += 1
        self.dataPlotInfo.close()

        # self.button2.clicked.connect( self.specd.mainBut2event )

        # self.specd.cidpress = self.specd.figureID.canvas.mpl_connect(
        #     'button_press_event', self.replotset  )

    def fluxplotfun(self):
        self.plotflux.polars = self.dataPlotInfo.polars
        self.plotflux.polarlineEdit.setText(self.plotflux.polars[0])
        self.plotflux.polarlabelt1.setText("from " + self.plotflux.polars)
        #### ÉèÖÃÊ±¼ä===
        self.plotflux.Timestart.setDateTime(
            QDateTime(
                self.dataPlotInfo.begDateTset.year,
                self.dataPlotInfo.begDateTset.month,
                self.dataPlotInfo.begDateTset.day,
                self.dataPlotInfo.begDateTset.hour,
                self.dataPlotInfo.begDateTset.minute,
                self.dataPlotInfo.begDateTset.second,
            )
        )
        self.plotflux.Timeend.setDateTime(
            QDateTime(
                self.dataPlotInfo.endDateTset.year,
                self.dataPlotInfo.endDateTset.month,
                self.dataPlotInfo.endDateTset.day,
                self.dataPlotInfo.endDateTset.hour,
                self.dataPlotInfo.endDateTset.minute,
                self.dataPlotInfo.endDateTset.second,
            )
        )
        ### set label time
        tt = self.dataPlotInfo.datet00 + datetime.timedelta(
            seconds=self.dataPlotInfo.begts
        )
        self.plotflux.labelt12.setText(tt.strftime("%H:%M:%S"))
        tt = self.dataPlotInfo.datet00 + datetime.timedelta(
            seconds=self.dataPlotInfo.endts
        )
        self.plotflux.labelt22.setText(tt.strftime("%H:%M:%S"))
        ###########ÉèÖÃÆµÂÊ

        self.plotflux.plotN = 0
        self.plotflux.button2.clicked.connect(self.mainplotflux)
        self.plotflux.show()

    def mainplotflux(self):
        ##
        if self.plotflux.plotN > 0:
            ## clear line
            for ki in range(len(self.plotflux.hline)):
                hlinex = self.plotflux.hline[ki]
                for kii in range(len(hlinex)):
                    hlinek = hlinex[kii]
                    hlinek[0].remove()

        self.plotflux.pindex = []
        self.plotflux.polars = self.plotflux.polarlineEdit.text()
        polar_list = [self.specd.data[kk].polar for kk in range(len(self.specd.data))]
        for ii in range(len(self.plotflux.polars)):
            p2s = self.plotflux.polars[ii] + self.plotflux.polars[ii]
            if p2s in polar_list:
                iik = polar_list.index(p2s)
                self.plotflux.pindex.append(iik)

        if len(self.plotflux.pindex) > 0:
            ### »ñÈ¡Ê±¼ä
            #### »ñÈ¡Ê±¼ä·¶Î§
            t1 = self.plotflux.Timestart.dateTime()
            t1ch = datetime.datetime(
                t1.date().year(),
                t1.date().month(),
                t1.date().day(),
                t1.time().hour(),
                t1.time().minute(),
                t1.time().second(),
            )
            t1 = self.plotflux.Timeend.dateTime()
            t2ch = datetime.datetime(
                t1.date().year(),
                t1.date().month(),
                t1.date().day(),
                t1.time().hour(),
                t1.time().minute(),
                t1.time().second(),
            )
            xtimev = 1
            ######## »ñÈ¡ÆµÂÊ
            try:
                # exec( 'freqx = ' + self.plotflux.freqlineEdit1.text()  )
                ss = self.plotflux.freqlineEdit1.text()
                sx = ss.replace("[", "")
                sx = sx.replace("]", "")
                sxx = sx.split(",")
                if len(sxx) > 0:
                    freqx = [float(kk) for kk in sxx]
                else:
                    freqx = [245]
            except Exception:
                freqx = [245]

            self.plotflux.ax.clear()
            self.plotflux.hline = []
            self.plotflux.fluxline = []
            plotpslist = [
                self.specd.plotconfig[iz].plotpl
                for iz in range(len(self.specd.plotconfig))
            ]

            #### if  plot I P 的情况

            for ik in self.plotflux.pindex:
                freq = self.specd.data[ik].freq
                tt = self.specd.data[ik].time
                Z = self.specd.data[ik].data
                ##########

                ffindex = []
                for ii in range(len(freqx)):
                    index = np.where(freq >= freqx[ii])
                    ffindex.append(index[0][0])

                ffindex = np.array(ffindex)
                freqch = freq[ffindex]
                ## ¿ªÆôÊ±¼ä½ØÈ¡¹¦ÄÜ========================================
                if xtimev == 1:
                    ttch = t1ch - self.dataPlotInfo.datet00
                    ttch1 = ttch.total_seconds()
                    ttch = t2ch - self.dataPlotInfo.datet00
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
                    ttax = tt[tindex1 : tindex2 + 1]
                    ttaxd = np.array(
                        [
                            self.dataPlotInfo.datet00
                            + datetime.timedelta(seconds=ttax[kk])
                            for kk in range(len(ttax))
                        ]
                    )
                    xrange = [ttaxd[0], ttaxd[-1]]
                    fluxdata = Z[ffindex, tindex1 : tindex2 + 1]
                    fluxdata = fluxdata.T
                    hlineik = []
                    fluxps = polar_list[ik]
                    for ii in range(len(freqch)):
                        if fluxps[0] in plotpslist:
                            ika = plotpslist.index(fluxps[0])

                        else:
                            ika = 0

                        hline = self.specd.inaxs[ika].plot(
                            np.array([ttax[0], ttax[-1]]),
                            np.ones(2) * freqch[ii],
                            "r--",
                        )
                        hlineik.append(hline)
                        # self.specd.inaxs[ik].draw_artist( hline[0] )
                        # flinelabel =
                        fline = self.plotflux.ax.plot(
                            ttaxd,
                            np.ravel(fluxdata[:, ii]),
                            label=polar_list[ik] + f" {freqch[ii]:.2f} MHz",
                        )
                        self.plotflux.fluxline.append(fline)

                # self.plotflux.ax.plot(ttaxd, fluxdata )
                self.plotflux.hline.append(hlineik)

            self.plotflux.ax.set_title("Flux vs Time " + t1ch.strftime("%Y-%m-%d"))
            self.plotflux.ax.set_xlabel("Time ( UT )")
            self.plotflux.ax.set_ylabel("Flux ( K )")
            self.plotflux.ax.set_xlim(xrange)
            self.plotflux.ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
            self.plotflux.ax.xaxis.set_minor_locator(mdates.MinuteLocator())
            self.plotflux.ax.legend()
            self.plotflux.fig.canvas.draw()
            # self.axx.draw_artist(self.hline[0])
            # self.specd.fig.canvas.blit(self.fig.bbox)
            # self.specd.fig.canvas.flush_events()
            self.fig.canvas.draw()
            self.plotflux.plotN += 1
            # ax1.set_xlim([trang1,trang2])
            # ax1.set_ylim([freq[0],freq[-1] ])
            # # #ax.xticks(rotation=70)
            # ax1.xaxis.set_major_formatter( mdates.DateFormatter('%H:%M:%S'))

    def fluxguiExit(self, sss):
        ## ¹Ø±Õ ÄâºÏ´°¿Ú£»
        # self.mainButton2.clicked.connect( self.mainBut2event )
        # self.RtypeIIfit.typeIIndot = 0
        # self.RtypeIIfit.typeIIfreq = []
        # self.RtypeIIfit.typeIItime = []
        # ## Ë¢ÐÂ Ö÷½çÃæ½çÃæ
        # self.figureID.canvas.restore_region(self.bg)
        # self.figureID.canvas.blit(self.figureID.bbox)
        # self.figureID.canvas.flush_events()
        # self.Canvas2PlotSet.emit('tpyeIIfitClose')
        ## ¹Ø±ÕÊ±£¬Çå³ýÖ÷½çÃæÉÏµÄ Ïß£¬
        if sss == "pluxplotGUIclose":
            if self.plotflux.plotN > 0:
                ## clear line
                for ki in range(len(self.plotflux.hline)):
                    hlinex = self.plotflux.hline[ki]
                    for kii in range(len(hlinex)):
                        hlinek = hlinex[kii]
                        hlinek[0].remove()
                self.fig.canvas.draw()

        # self.plotflux.close()

    def savefitsFile(self):
        options = QtWidgets.QFileDialog.Options()
        # options = QtWidgets.QFileDialog.DontUseNativeDialog  # ½ûÓÃÔ­Éú¶Ô»°¿ò
        # options |= QtWidgets.QFileDialog.DontConfirmOverwrite
        options |= QtWidgets.QFileDialog.ExistingFile
        t1 = self.dataPlotInfo.Timestart.dateTime()
        t1ch = datetime.datetime(
            t1.date().year(),
            t1.date().month(),
            t1.date().day(),
            t1.time().hour(),
            t1.time().minute(),
            t1.time().second(),
        )
        self.savfitsname = (
            os.path.dirname(self.savfitsname)
            + "/CBSm"
            + t1ch.strftime("%Y-%m-%dT%H%M%S")
            + ".fits"
        )

        file1, ok1 = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "save radio spectro plot data in fits",
            self.savfitsname,
            "(*.fits)",
            options=options,
        )

        self.savfitsname = file1
        if len(self.specd.savefitsdata) > 0:
            ndatalist = len(self.specd.savefitsdata)
            ttsav = self.specd.savefitsdata[0][0]
            ffsav = self.specd.savefitsdata[0][1]
            dataRL = self.specd.savefitsdata[0][2]
            polsav = self.specd.savefitsdata[0][3]
            datet0 = self.specd.savefitsdata[0][4]
            if ndatalist > 1:
                # dataRL = np.zeros( ( ndatalist, dataRL.shape[0], dataRL.shape[1]) )
                dataRL = np.repeat(
                    np.reshape(dataRL, (1, dataRL.shape[0], dataRL.shape[1])),
                    ndatalist,
                    axis=0,
                )
                for ii in range(1, ndatalist):
                    # ttsav = np.hstack( (ttsav, self.specd.savefitsdata[ii][0]))
                    polsav = polsav + self.specd.savefitsdata[ii][3]
                    dataRL[ii, :, :] = self.specd.savefitsdata[ii][2]
            if (
                creatFitsFile(ttsav, ffsav, dataRL, polsav, datet0, file1, BJT2UTC=0)
                == 1
            ):
                print("sucessful write fits")


#####################################################################################


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    dsrtw = dsrtSpecWindow()
    dsrtw.show()
    sys.exit(app.exec_())
