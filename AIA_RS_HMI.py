# -*- coding: utf-8 -*-
"""
Created on Wed Jan 21 22:57:26 2026

@author: Severus

"""

import matplotlib

matplotlib.use("Agg")  # ★ 优化5：非交互后端，子进程安全，节省内存

import gc
import glob
import os
import re
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import lru_cache, partial
from typing import Dict, List, Optional, Tuple

import astropy.units as u
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import psutil
import sunpy.coordinates
import sunpy.map
from astropy.convolution import Gaussian2DKernel, convolve
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS
from matplotlib.lines import Line2D
from matplotlib.patches import Ellipse
from scipy.ndimage import gaussian_filter
from sunpy.coordinates import frames

warnings.filterwarnings("ignore")

plt.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

# ============================================================
#  模块级预编译正则
# ============================================================
_RE_MHZ = re.compile(r"(\d+\.?\d*)\s*MHz", re.IGNORECASE)
_RE_AIA_PATS = [
    re.compile(r"aia\.lev1_euv_12s\.(\d{4}-\d{2}-\d{2}T\d{6}Z)\.\d+\.image_lev1\.fits"),
    re.compile(r"aia\.lev1_euv_12s\.(\d{4}-\d{2}-\d{2}T\d{6}Z)"),
    re.compile(r"(\d{4}-\d{2}-\d{2}T\d{6}Z)"),
    re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)"),
    re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"),
    re.compile(r"(\d{4}\d{2}\d{2}T\d{2}\d{2}\d{2})"),
]
_RE_HMI_PAT = re.compile(r"(\d{8})_(\d{6})")
_RE_BAND_SORTED = re.compile(r"(\d+\.?\d*)MHz")
# 新增正则表达式，用于解析新的文件名格式
_RE_RADIO_PAT_YYYYJJJ = re.compile(r"(\d{7})_(\d{6})_(\d{1,3})")  # 射电文件：YYYYJJJ_HHMMSS_SSS
_RE_RADIO_PAT_YYYYMMDD = re.compile(r"(\d{8})_(\d{6})")  # 射电文件：YYYYMMDD_HHMMSS
_RE_AIA_NEW_PAT = re.compile(r"aia\.lev1_euv_12s\.(\d{4}-\d{2}-\d{2}T\d{6}Z)\.\d+\.image_lev1\.fits")  # 新的AIA文件名
_RE_HMI_NEW_PAT = re.compile(r"hmi\.M_45s\.(\d{8})_(\d{6})_TAI")  # 新的HMI文件名
# 扩展时间格式常量
_DATETIME_FMTS = [
    # 标准ISO格式
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H%M%S.%f",
    "%Y-%m-%dT%H%M%S",
    # 带时区信息
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H%M%S.%fZ",
    "%Y%m%dT%H%M%SZ",
    # 空格分隔
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H%M%S.%f",
    "%Y-%m-%d %H%M%S",
    # 简写格式
    "%Y%m%dT%H%M%S.%f",
    "%Y%m%dT%H%M%S",
    "%Y%m%d%H%M%S.%f",
    "%Y%m%d%H%M%S",
    # HMI格式
    "%Y%m%d_%H%M%S",
    # 其他常见格式
    "%d/%m/%YT%H:%M:%S.%f",
    "%d/%m/%YT%H:%M:%S",
    "%d-%b-%YT%H:%M:%S.%f",
    "%d-%b-%YT%H:%M:%S",
    # 射电文件特殊格式
    "%Y%m%d%H%M%S",  # 20250124044317
    "%Y%m%d%H%M%S.%f",  # 20250124044317.38
    "%Y%j%H%M%S.%f",  # 年+儒略日格式: 2025124_044317_038
    "%Y%j%H%M%S",  # 年+儒略日格式无毫秒
]


# ============================================================
#  配置类简化
# ============================================================
@dataclass
class Config:
    radio_base_dir: str = r"D:\spike_topping_type_III\2025\20250124\RS_0447-0450"
    aia_base_dir: str = r"D:\spike_topping_type_III\2025\20250124\AIA\171\1"
    hmi_base_dir: str = r"D:\spike_topping_type_III\2025\20250124\AIA\hmi\1"
    output_dir: str = r"D:\spike_topping_type_III\2025\20250124\AIA_RS_HMI\LL"

    save_figure: bool = True
    dpi: int = 300
    aia_file_start_idx: int = 392
    aia_file_end_idx: Optional[int] = 397

    selected_bands: List[str] = field(
        default_factory=lambda: [
            "149MHz",
            "164MHz",
            "190MHz",
            "223MHz",
            "238MHz",
            "300MHz",
            "309MHz",
            "324MHz",
        ]
    )
    polarization_mode: str = "LL"
    radio_time_threshold: int = 6
    max_radio_per_band: int = 28

    normalization_mode: str = "peak"  # 'peak' 或 'rms'
    contour_levels_peak: List[float] = field(default_factory=lambda: [0.95])
    rms_sigma_levels: List[float] = field(default_factory=lambda: [5.0, 15.0, 30.0])
    rms_box_fraction: float = 0.15

    contour_linewidths: List[float] = field(default_factory=lambda: [2.0])
    contour_alpha: float = 0.90
    contour_smooth_sigma: float = 0  # 展示级平滑 sigma（像素），0 = 关闭

    show_beam: bool = True
    beam_inset_fraction: float = 0.12

    overlay_hmi: bool = True
    hmi_time_threshold: int = 24
    hmi_threshold_gauss: float = 0.0
    hmi_sigma: int = 2
    hmi_levels_gauss: List[float] = field(default_factory=lambda: [100.0])

    aia_vmin: float = 16
    aia_vmax: float = 6666
    aia_cmap: str = "sdoaia171"
    roi_bottom_left: List[float] = field(default_factory=lambda: [-3000, -3000])
    roi_top_right: List[float] = field(default_factory=lambda: [3000, 3000])

    band_colors_dict: dict = field(
        default_factory=lambda: {
            "149.0MHz": ("cyan", "deepskyblue"),
            "164.0MHz": ("lime", "green"),
            "190.0MHz": ("magenta", "darkviolet"),
            "205.0MHz": ("yellow", "orange"),
            "223.0MHz": ("red", "darkred"),
            "238.0MHz": ("white", "lightgray"),
        }
    )
    default_colors: List[Tuple] = field(
        default_factory=lambda: [
            ("yellow", "orange"),
            ("red", "darkred"),
            ("white", "lightgray"),
            ("pink", "hotpink"),
            ("skyblue", "deepskyblue"),
            ("violet", "darkviolet"),
        ]
    )

    # 简化选项
    num_workers: int = 8
    memory_limit_pct: float = 85.0
    radio_use_float32: bool = True

    # 简化：移除通量归一化和复杂验证
    apply_background_subtraction: bool = False  # 简化：默认不应用背景扣除
    debug_mode: bool = True  # 改为True以显示详细匹配信息

    # 简化重投影选项
    coordinate_search_radius: float = 3.0  # 坐标查找搜索半径（度），用于KD树最近邻匹配
    quick_test: bool = False
    test_file_limit: int = 5  # 快速测试时的文件数量限制

    # 新增配置：是否使用赤经赤纬坐标图
    use_radec_maps: bool = False  # True: 使用赤经赤纬文件; False: 直接转换为太阳坐标
    radio_to_solar_scale_factor: float = (
        0.1  # 射电坐标到太阳坐标的缩放因子，默认改为0.1
    )

    # 新增：自动调整坐标缩放的选项
    auto_adjust_scale_factor: bool = True  # 自动调整缩放因子
    min_pixels_in_view: int = 100  # AISA视野内最小像素数
    max_scale_factor_adjustments: int = 3  # 最大调整次数

    # 修改默认缩放因子为0.05，以更好地匹配AIA视野
    radio_to_solar_scale_factor: float = (
        0.05  # 射电坐标到太阳坐标的缩放因子，默认改为0.05
    )


# ============================================================
#  颜色缓存
# ============================================================
def _build_band_color_cache(cfg: Config) -> List[Tuple[float, Tuple]]:
    """将 band_colors_dict 解析为 [(mhz_float, (main, dark)), ...]，仅需调用一次。"""
    cache = []
    for key, val in cfg.band_colors_dict.items():
        m = _RE_MHZ.search(key)
        if m:
            cache.append((float(m.group(1)), val))
    return cache


# ============================================================
#  Gaussian 核缓存
# ============================================================
@lru_cache(maxsize=16)
def _make_gaussian_kernel(sigma: float) -> Gaussian2DKernel:
    """相同 sigma 只创建一次 Gaussian2DKernel 对象。"""
    return Gaussian2DKernel(x_stddev=sigma)


# ============================================================
#  内存监控
# ============================================================
def check_memory_usage(limit: float = 90.0):
    """检查内存占用，超过阈值则执行垃圾回收并等待释放。"""
    mem_percent = psutil.virtual_memory().percent
    if mem_percent >= limit:
        print(
            f"\n[警告] 内存占用已达 {mem_percent}% (阈值: {limit}%)，正在执行深度清理并挂起..."
        )
        while psutil.virtual_memory().percent >= limit:
            gc.collect()
            time.sleep(1.0)
        print(f"[恢复] 内存占用已降至 {psutil.virtual_memory().percent}%，恢复执行。")


# ============================================================
#  时间解析
# ============================================================
def _parse_flexible_datetime(date_str: str) -> Optional[datetime]:
    """灵活解析各种时间格式"""
    # 清理字符串
    date_str = date_str.strip()

    # 特殊处理：17位数字格式（YYYYMMDDHHMMSSmmm）- 这是最常见的问题
    if len(date_str) == 17 and date_str.isdigit():
        try:
            year = int(date_str[0:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])
            hour = int(date_str[8:10])
            minute = int(date_str[10:12])
            second = int(date_str[12:14])
            millisecond = int(date_str[14:17])
            microsecond = millisecond * 1000
            return datetime(year, month, day, hour, minute, second, microsecond)
        except Exception:
            pass

    # 特殊处理：处理下划线分隔的格式，如"2025124_044317_038"
    if "_" in date_str:
        parts = date_str.split("_")
        if len(parts) >= 2:
            # 格式: 年儒略日_时分秒_毫秒
            date_part = parts[0]  # 如"2025124"
            time_part = parts[1]  # 如"044317"

            # 将年儒略日转换为标准日期
            if len(date_part) == 7:  
                year = int(date_part[:4])
                parsed_date = None
                
                # 1. 优先尝试解析为 YYYYmDD (缺少月份前导零，如 2025124 -> 2025-01-24)
                try:
                    month_candidate = int(date_part[4:5])
                    day_candidate = int(date_part[5:7])
                    parsed_date = datetime(year, month_candidate, day_candidate)
                except ValueError:
                    pass  # 如果遇到非法月日（如2025135），自动跳过
                
                # 2. 如果不符合 YYYYmDD，则回退到 年+儒略日 (YYYYDDD) 逻辑
                if parsed_date is None:
                    try:
                        doy = int(date_part[4:])
                        parsed_date = datetime(year, 1, 1) + timedelta(days=doy - 1)
                    except Exception:
                        pass
                
                if parsed_date is not None:
                    # 解析时间部分
                    if len(time_part) == 6:  # HHMMSS
                        hour = int(time_part[0:2])
                        minute = int(time_part[2:4])
                        second = int(time_part[4:6])

                        # 处理毫秒部分
                        microsecond = 0
                        if len(parts) > 2 and parts[2]:
                            # 毫秒部分，可能为"038"或"38"或"3"
                            ms_str = parts[2].strip().ljust(3, "0")[:3]
                            microsecond = int(ms_str) * 1000

                        return datetime(
                            parsed_date.year,
                            parsed_date.month,
                            parsed_date.day,
                            hour,
                            minute,
                            second,
                            microsecond,
                        )

    # 处理小数点格式
    if "." in date_str:
        integer_part, decimal_part = date_str.split(".")
        # 补全小数位到6位
        decimal_part = decimal_part.ljust(6, "0")[:6]
        date_str = f"{integer_part}.{decimal_part}"

    # 尝试标准格式
    for fmt in _DATETIME_FMTS:
        try:
            # 根据格式处理小数点
            if ".%f" in fmt:
                # 确保有足够的小数位
                if "." not in date_str:
                    date_str = date_str + ".0"
                # 补全小数位到6位
                if "." in date_str:
                    integer_part, decimal_part = date_str.split(".")
                    decimal_part = decimal_part.ljust(6, "0")[:6]
                    date_str = f"{integer_part}.{decimal_part}"

            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    # 特殊处理：尝试14位数字格式（YYYYMMDDHHMMSS）
    if len(date_str) >= 14 and date_str[:14].isdigit():
        try:
            year = int(date_str[0:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])
            hour = int(date_str[8:10])
            minute = int(date_str[10:12])
            second = int(date_str[12:14])

            microsecond = 0
            if len(date_str) > 14 and date_str[14] == ".":
                # 处理小数秒
                ms_str = date_str[15:].ljust(6, "0")[:6]
                microsecond = int(ms_str)
            elif len(date_str) > 14:
                # 处理没有小数点的小数部分
                remaining = date_str[14:]
                if remaining.isdigit():
                    # 如果是3位数字，认为是毫秒
                    if len(remaining) == 3:
                        millisecond = int(remaining)
                        microsecond = millisecond * 1000
                    else:
                        # 否则直接填充到6位
                        ms_str = remaining.ljust(6, "0")[:6]
                        microsecond = int(ms_str)

            return datetime(year, month, day, hour, minute, second, microsecond)
        except Exception:
            pass

    return None


def parse_radio_time_from_filename(filename: str) -> Optional[datetime]:
    """从射电文件名中提取观测时间（支持多种格式，包括新格式）"""
    basename = os.path.basename(filename)
    
    # 新格式：223MHz_2025124_043740_183.fits (YYYYJJJ_HHMMSS_SSS)
    m1 = _RE_RADIO_PAT_YYYYJJJ.search(basename)
    if m1:
        date_part = m1.group(1)  # 2025124 (年+儒略日)
        time_part = m1.group(2)  # 043740 (时分秒)
        ms_part = m1.group(3)    # 183 (毫秒)
        
        # 构建时间字符串
        time_str = f"{date_part}_{time_part}_{ms_part}"
        parsed_time = _parse_flexible_datetime(time_str)
        if parsed_time:
            return parsed_time
    
    # 其他常见格式
    m2 = _RE_RADIO_PAT_YYYYMMDD.search(basename)
    if m2:
        date_part = m2.group(1)  # YYYYMMDD
        time_part = m2.group(2)  # HHMMSS
        time_str = f"{date_part}_{time_part}"
        parsed_time = _parse_flexible_datetime(time_str)
        if parsed_time:
            return parsed_time
    
    # 尝试从头文件读取
    try:
        if os.path.exists(filename):
            header = fits.getheader(filename, 0)
            date_obs = str(header.get("DATE-OBS", "")).strip()
            if date_obs:
                parsed_time = _parse_flexible_datetime(date_obs)
                if parsed_time:
                    return parsed_time
    except Exception:
        pass
    
    return None


def parse_aia_time_from_filename(filename: str) -> Optional[datetime]:
    """从 AIA 文件名中提取观测时间（支持多种命名模式，包括新格式）。"""
    basename = os.path.basename(filename)

    # 尝试从FITS头直接读取（如果文件可访问）
    try:
        if os.path.exists(filename):
            header = fits.getheader(filename, 0)
            date_obs = str(header.get("DATE-OBS", "")).strip()
            if date_obs:
                parsed_time = _parse_flexible_datetime(date_obs)
                if parsed_time:
                    return parsed_time
    except Exception:
        pass

    # 优先尝试新格式：aia.lev1_euv_12s.2025-01-24T033025Z.94.image_lev1.fits
    m = _RE_AIA_NEW_PAT.search(basename)
    if m:
        ts = m.group(1)  # 如 "2025-01-24T033025Z"
        ts = ts.rstrip("Z")
        parsed_time = _parse_flexible_datetime(ts)
        if parsed_time:
            return parsed_time

    # 原有的解析模式
    for pat in _RE_AIA_PATS:
        m = pat.search(basename)
        if m:
            ts = m.group(1)
            # 移除常见的后缀
            ts = ts.rstrip("Z")
            parsed_time = _parse_flexible_datetime(ts)
            if parsed_time:
                return parsed_time

    # 如果都没成功，尝试直接提取数字部分
    import re
    all_digits = re.findall(r"\d{4,}", basename)
    for digits in all_digits:
        if len(digits) >= 8:  # 至少要有年月日
            parsed_time = _parse_flexible_datetime(digits)
            if parsed_time:
                return parsed_time

    # 调试：打印文件名以帮助诊断
    print(f"    调试: 无法解析AIA文件名: {basename}")
    return None


def parse_hmi_time_from_filename(filename: str) -> Optional[datetime]:
    """从 HMI 文件名中提取观测时间（支持多种格式，包括新格式）"""
    basename = os.path.basename(filename)
    
    # 新格式：hmi.M_45s.20250124_033215_TAI.2.magnetogram.fits
    m1 = _RE_HMI_NEW_PAT.search(basename)
    if m1:
        date_part = m1.group(1)  # 20250124
        time_part = m1.group(2)  # 033215
        time_str = f"{date_part}_{time_part}"
        try:
            return datetime.strptime(time_str, "%Y%m%d_%H%M%S")
        except ValueError:
            pass
    
    # 原有的HMI格式
    m2 = _RE_HMI_PAT.search(basename)
    if m2:
        try:
            return datetime.strptime(f"{m2.group(1)}_{m2.group(2)}", "%Y%m%d_%H%M%S")
        except ValueError:
            pass
    
    return None


# ============================================================
#  从 AIA_RS.py 复制的函数
# ============================================================

def get_sun_center_and_radius(header):
    """从FITS头文件中获取太阳中心坐标和半径（从AIA_RS.py复制）"""
    try:
        # 获取太阳中心像素位置
        crpix1 = header.get("CRPIX1", 0)
        crpix2 = header.get("CRPIX2", 0)

        # 获取太阳中心坐标（角秒）
        crval1 = header.get("CRVAL1", 0)
        crval2 = header.get("CRVAL2", 0)

        # 获取像素比例
        cdelt1 = header.get("CDELT1", 1)
        cdelt2 = header.get("CDELT2", 1)

        # 获取太阳半径
        if "RSUN_OBS" in header:
            rsun_obs = header["RSUN_OBS"]  # 角秒
        elif "R_SUN" in header and "CDELT1" in header:
            # 如果半径是像素单位，转换为角秒
            rsun_obs = abs(header["R_SUN"] * header["CDELT1"])
        else:
            rsun_obs = 960.0  # 默认值

        return crpix1, crpix2, crval1, crval2, cdelt1, cdelt2, rsun_obs
    except Exception as e:
        print(f"获取太阳信息时出错: {e}")
        return 0, 0, 0, 0, 1, 1, 960.0


def calculate_image_extent(data_shape, crpix1, crpix2, crval1, crval2, cdelt1, cdelt2):
    """计算图像的完整范围（角秒）（从AIA_RS.py复制）"""
    nx, ny = data_shape[1], data_shape[0]

    # 计算每个像素的角秒坐标
    # 像素索引从1开始，所以第一个像素的位置是 (1 - crpix1) * cdelt1 + crval1
    x_min = crval1 + (1 - crpix1) * cdelt1
    x_max = crval1 + (nx - crpix1) * cdelt1
    y_min = crval2 + (1 - crpix2) * cdelt2
    y_max = crval2 + (ny - crpix2) * cdelt2

    # 确保正确的顺序（x从左到右，y从下到上）
    if cdelt1 > 0:
        x_extent = [x_min, x_max]
    else:
        x_extent = [x_max, x_min]

    if cdelt2 > 0:
        y_extent = [y_min, y_max]
    else:
        y_extent = [y_max, y_min]

    return x_extent, y_extent


# ============================================================
#  简化射电数据工具
# ============================================================
def extract_radio_2d_data(
    fits_path: str, use_float32: bool = True, cfg: Optional[Config] = None
) -> Tuple[
    np.ndarray, Optional[np.ndarray], Optional[np.ndarray], fits.Header, Optional[WCS]
]:
    """
    简化版：提取射电数据和坐标图
    修改：根据cfg.use_radec_maps决定是否加载坐标图文件
    增强：改进坐标图文件搜索逻辑
    """
    try:
        with fits.open(fits_path) as hdu_data:
            data = hdu_data[0].data
            # 简化维度压缩逻辑
            while data.ndim > 2:
                data = data[0]
            data = np.squeeze(data)
            header = hdu_data[0].header.copy()

            ra_map = None
            dec_map = None

            # 如果使用赤经赤纬坐标图
            if cfg is not None and cfg.use_radec_maps:
                # 获取基目录和文件名
                base_dir = os.path.dirname(fits_path)
                base_name = os.path.basename(fits_path)

                # 提取频率 - 改进正则表达式匹配
                freq_match = re.search(r"(\d+)MHz", base_name, re.IGNORECASE)
                freq_value = None
                if freq_match:
                    freq_value = freq_match.group(1)  # 如 "149"
                else:
                    # 尝试从目录名提取频率
                    dir_name = os.path.basename(base_dir)
                    dir_freq_match = re.search(r"(\d+)MHz", dir_name, re.IGNORECASE)
                    if dir_freq_match:
                        freq_value = dir_freq_match.group(1)

                if freq_value:
                    # 构建坐标图文件名模式
                    ra_patterns = [
                        f"{freq_value}MHz_RightAscensionDegree.fits",
                        f"{freq_value}MHz_RA.fits",
                        f"*{freq_value}*RightAscension*.fits",
                        f"*{freq_value}*RA*.fits"
                    ]
                    
                    dec_patterns = [
                        f"{freq_value}MHz_DeclinationDegree.fits",
                        f"{freq_value}MHz_Dec.fits",
                        f"*{freq_value}*Declination*.fits",
                        f"*{freq_value}*Dec*.fits"
                    ]

                    # 搜索坐标图文件
                    search_dirs = [
                        base_dir,  # 当前目录
                        os.path.dirname(base_dir),  # 父目录
                        os.path.join(os.path.dirname(base_dir), "..")  # 祖父目录
                    ]

                    ra_file_found = False
                    dec_file_found = False
                    
                    for search_dir in search_dirs:
                        if not os.path.isdir(search_dir):
                            continue
                            
                        # 查找赤经文件
                        if not ra_file_found:
                            for pattern in ra_patterns:
                                matches = glob.glob(os.path.join(search_dir, pattern))
                                for match in matches:
                                    try:
                                        with fits.open(match) as hdu_ra:
                                            ra_map = hdu_ra[0].data
                                            while ra_map.ndim > 2:
                                                ra_map = ra_map[0]
                                            ra_map = np.squeeze(ra_map)
                                            if use_float32:
                                                ra_map = ra_map.astype(np.float32)
                                        if cfg.debug_mode:
                                            print(f"    [坐标图] 已加载RA文件: {os.path.basename(match)}")
                                        ra_file_found = True
                                        break
                                    except Exception as e:
                                        if cfg.debug_mode:
                                            print(f"    [坐标图] 加载RA文件失败 {os.path.basename(match)}: {e}")
                                if ra_file_found:
                                    break

                        # 查找赤纬文件
                        if not dec_file_found:
                            for pattern in dec_patterns:
                                matches = glob.glob(os.path.join(search_dir, pattern))
                                for match in matches:
                                    try:
                                        with fits.open(match) as hdu_dec:
                                            dec_map = hdu_dec[0].data
                                            while dec_map.ndim > 2:
                                                dec_map = dec_map[0]
                                            dec_map = np.squeeze(dec_map)
                                            if use_float32:
                                                dec_map = dec_map.astype(np.float32)
                                        if cfg.debug_mode:
                                            print(f"    [坐标图] 已加载Dec文件: {os.path.basename(match)}")
                                        dec_file_found = True
                                        break
                                    except Exception as e:
                                        if cfg.debug_mode:
                                            print(f"    [坐标图] 加载Dec文件失败 {os.path.basename(match)}: {e}")
                                if dec_file_found:
                                    break
                                    
                        if ra_file_found and dec_file_found:
                            break

                    if cfg.debug_mode:
                        if ra_file_found and dec_file_found:
                            print(f"    [坐标图] 成功加载赤经赤纬坐标图，形状: {ra_map.shape}")
                        else:
                            print(f"    [坐标图] 警告: 未找到完整的坐标图文件 (RA: {ra_file_found}, Dec: {dec_file_found})")
                else:
                    if cfg.debug_mode:
                        print(f"    [坐标图] 无法从文件名提取频率: {base_name}")

            else:
                # 不使用坐标图文件，直接生成太阳坐标
                if cfg is not None and cfg.debug_mode:
                    print(f"    [坐标图] 不使用赤经赤纬文件，直接生成太阳坐标")

                # 放弃使用sunpy.map，直接调用generate_solar_coordinates
                # 根据射电数据形状和AIA视野自动调整缩放因子
                ny, nx = data.shape

                # 根据射电数据大小估计初始缩放因子
                # 256x256图像对应约±18000角秒，需要缩小到±1200角秒
                # 缩放因子约为1200/18000=0.067
                base_scale_factor = 0.067

                # 如果图像尺寸不同，进一步调整
                if ny > 256 or nx > 256:
                    # 更大的图像通常有更大的视场，需要进一步缩小
                    base_scale_factor = base_scale_factor * 256 / max(ny, nx)

                # 应用配置中的缩放因子
                effective_scale_factor = (
                    base_scale_factor * cfg.radio_to_solar_scale_factor
                )

                if cfg.debug_mode:
                    print(f"    [坐标生成] 图像尺寸: {ny}x{nx}")
                    print(f"    [坐标生成] 基础缩放因子: {base_scale_factor:.4f}")
                    print(
                        f"    [坐标生成] 配置缩放因子: {cfg.radio_to_solar_scale_factor:.4f}"
                    )
                    print(f"    [坐标生成] 有效缩放因子: {effective_scale_factor:.4f}")

                # 临时修改配置的缩放因子用于生成坐标
                # 注意：我们创建一个配置副本以避免修改原始配置
                from copy import copy

                cfg_copy = copy(cfg)
                cfg_copy.radio_to_solar_scale_factor = effective_scale_factor

                # 生成太阳坐标
                ra_map, dec_map = generate_solar_coordinates(
                    data.shape, header, cfg_copy
                )

            dtype = np.float32 if use_float32 else np.float64
            return data.astype(dtype), ra_map, dec_map, header, None

    except Exception as e:
        print(f"读取FITS文件失败 {fits_path}: {e}")
        return None, None, None, None, None


def estimate_rms_noise(data: np.ndarray, box_fraction: float = 0.15) -> float:
    """通过图像四个角部区域估算背景噪声 RMS（用于 rms 模式等值线）。"""
    ny, nx = data.shape
    bx = max(int(nx * box_fraction), 5)
    by = max(int(ny * box_fraction), 5)

    # 提取四个角区域
    corners = [data[:by, :bx], data[:by, -bx:], data[-by:, :bx], data[-by:, -bx:]]

    # 合并角部像素
    corner_pixels = np.concatenate([c.ravel() for c in corners])
    corner_pixels = corner_pixels[~np.isnan(corner_pixels)]

    if len(corner_pixels) < 10:
        # 如果角部像素不足，使用边缘像素
        edges = np.concatenate(
            [
                data[:by, :].ravel(),
                data[-by:, :].ravel(),
                data[:, :bx].ravel(),
                data[:, -bx:].ravel(),
            ]
        )
        edge_pixels = edges[~np.isnan(edges)]
        if len(edge_pixels) > 0:
            corner_pixels = edge_pixels

    if len(corner_pixels) == 0:
        return float(np.nanstd(data) * 0.1)

    # 使用中值绝对偏差（MAD）进行鲁棒估计
    median = np.median(corner_pixels)
    mad = np.median(np.abs(corner_pixels - median))
    std_est = mad * 1.4826  # 转换为标准差

    # 3-sigma裁剪去除异常值
    filtered = corner_pixels[np.abs(corner_pixels - median) < 3 * std_est]

    if len(filtered) > 0:
        return float(np.std(filtered))
    else:
        return float(std_est)


def compute_contour_levels(data: np.ndarray, cfg: Config) -> List[float]:
    """支持 normalization_mode='peak'（默认）和 'rms' 两种模式。"""
    finite_data = data[np.isfinite(data)]
    if len(finite_data) == 0:
        return []

    # 应用背景扣除（如果启用）
    if cfg.apply_background_subtraction:
        if cfg.background_estimation_method == "median":
            background = np.median(finite_data)
        elif cfg.background_estimation_method == "minimum":
            background = np.percentile(finite_data, 5)
        else:  # 'corner'
            background = estimate_rms_noise(data, cfg.rms_box_fraction)
        data = data - background

    if cfg.normalization_mode == "rms":
        rms = estimate_rms_noise(data, cfg.rms_box_fraction)
        if rms <= 0:
            return []
        peak = float(np.nanmax(finite_data))
        levels = [s * rms for s in cfg.rms_sigma_levels if 0 < s * rms < peak]
    else:
        peak = float(np.nanmax(finite_data))
        levels = [f * peak for f in cfg.contour_levels_peak]

    return levels if levels else []


# ============================================================
#  太阳位置计算辅助函数
# ============================================================
def get_solar_position(obs_time: datetime) -> Tuple[float, float]:
    """
    计算观测时刻太阳中心在ICRS坐标系中的位置

    参数:
        obs_time: 观测时间

    返回:
        (sun_ra, sun_dec): 太阳中心的赤经赤纬（度）
    """
    try:
        from astropy.coordinates import get_sun
        from astropy.time import Time

        # 将datetime转换为astropy Time对象，指定时间尺度
        astropy_time = Time(obs_time, format="datetime", scale="utc")

        # 计算太阳位置
        sun_coord = get_sun(astropy_time)

        return sun_coord.ra.deg, sun_coord.dec.deg
    except Exception as e:
        # 如果失败，返回近似值（对于2025年1月24日04:43:17，太阳大约在RA=306.4°, Dec=-19.2°）
        # 根据测试输出，我们知道这个时间的太阳位置
        print(f"    [警告] 使用astropy计算太阳位置失败: {e}")
        print(f"    [警告] 使用近似太阳位置: RA=306.413395°, Dec=-19.231661°")
        return 306.413395, -19.231661  # 2025-01-24 04:43:17的太阳位置


# ============================================================
#  新增函数：生成太阳坐标
# ============================================================
def generate_solar_coordinates(
    shape: Tuple[int, int], header: fits.Header, cfg: Config
) -> Tuple[np.ndarray, np.ndarray]:
    """
    生成射电数据对应的太阳坐标（Tx, Ty）
    增强：更智能地处理像素尺度和缩放因子

    参数:
        shape: 数据形状 (ny, nx)
        header: FITS头信息
        cfg: 配置对象

    返回:
        tx_map: Tx坐标图（太阳X坐标，角秒）
        ty_map: Ty坐标图（太阳Y坐标，角秒）
    """
    ny, nx = shape

    # 创建网格
    y_indices, x_indices = np.indices((ny, nx))

    # 获取图像中心
    center_x = nx // 2
    center_y = ny // 2

    # 尝试从头文件中获取像素尺度
    # 注意：射电数据通常以度为单位，需要转换为角秒
    cdelt1 = header.get("CDELT1", 0.0)  # 度/像素
    cdelt2 = header.get("CDELT2", 0.0)  # 度/像素

    # 如果头文件中没有，使用默认值
    if cdelt1 == 0.0:
        # 根据图像尺寸估计像素尺度
        # 256x256图像通常对应约±1度的视场
        if nx == 256 and ny == 256:
            cdelt1 = 0.0078  # 度/像素，约28角秒/像素
        else:
            # 更大的图像通常有更高的分辨率
            cdelt1 = 0.0039  # 度/像素，约14角秒/像素

    if cdelt2 == 0.0:
        cdelt2 = cdelt1

    # 转换为角秒/像素
    cdelt1_arcsec = cdelt1 * 3600.0 * cfg.radio_to_solar_scale_factor
    cdelt2_arcsec = cdelt2 * 3600.0 * cfg.radio_to_solar_scale_factor

    # 生成Tx, Ty坐标（太阳坐标，角秒）
    # 注意：太阳坐标系中，Tx向右为正，Ty向上为正
    tx_map = (x_indices - center_x) * cdelt1_arcsec
    ty_map = (y_indices - center_y) * cdelt2_arcsec

    # 调试信息
    if cfg.debug_mode:
        print(f"    [太阳坐标] 生成坐标图: 形状={shape}")
        print(f"    [太阳坐标] 像素尺度: CDELT1={cdelt1}度 -> {cdelt1_arcsec}角秒/像素")
        print(f"    [太阳坐标] 有效缩放因子: {cfg.radio_to_solar_scale_factor}")
        print(f"    [太阳坐标] Tx范围: [{tx_map.min():.1f}, {tx_map.max():.1f}]角秒")
        print(f"    [太阳坐标] Ty范围: [{ty_map.min():.1f}, {ty_map.max():.1f}]角秒")

    return tx_map, ty_map


# ============================================================
#  添加新的辅助函数：自动调整坐标缩放因子
# ============================================================
def auto_adjust_coordinate_scale(
    radio_data: np.ndarray,
    ra_map: np.ndarray,
    dec_map: np.ndarray,
    aia_cutout_map,
    cfg: Config,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    自动调整射电坐标到太阳坐标的缩放因子
    使更多射电像素位于AIA视野内
    """
    if not cfg.auto_adjust_scale_factor or cfg.radio_to_solar_scale_factor == 1.0:
        return ra_map, dec_map, cfg.radio_to_solar_scale_factor

    ny, nx = radio_data.shape

    # 获取AIA视野范围
    bl = aia_cutout_map.bottom_left_coord
    tr = aia_cutout_map.top_right_coord

    # 初始缩放因子
    scale_factor = cfg.radio_to_solar_scale_factor

    # 尝试不同的缩放因子
    for attempt in range(cfg.max_scale_factor_adjustments):
        # 使用当前缩放因子生成坐标
        if attempt > 0:
            scale_factor = scale_factor * 0.5  # 每次减半

        # 生成调整后的坐标
        adjusted_ra_map, adjusted_dec_map = generate_solar_coordinates(
            (ny, nx), fits.Header(), cfg  # 空header
        )

        # 计算有多少像素在AIA视野内
        in_view_mask = (
            (adjusted_ra_map >= bl.Tx.arcsec)
            & (adjusted_ra_map <= tr.Tx.arcsec)
            & (adjusted_dec_map >= bl.Ty.arcsec)
            & (adjusted_dec_map <= tr.Ty.arcsec)
        )
        n_in_view = int(np.sum(in_view_mask))

        if cfg.debug_mode:
            print(
                f"    [自动调整] 尝试#{attempt+1}: 缩放因子={scale_factor}, "
                f"视野内像素={n_in_view}/{ny*nx} ({(n_in_view/(ny*nx)*100):.1f}%)"
            )

        # 如果达到最小像素数要求，返回调整后的坐标
        if n_in_view >= cfg.min_pixels_in_view:
            if cfg.debug_mode:
                print(f"    [自动调整] 使用缩放因子={scale_factor}")
            return adjusted_ra_map, adjusted_dec_map, scale_factor

    # 如果所有尝试都失败，返回原始坐标
    if cfg.debug_mode:
        print(f"    [自动调整] 未能找到合适缩放因子，使用默认值")
    return ra_map, dec_map, cfg.radio_to_solar_scale_factor


# ============================================================
#  简化的射电数据投影方法（参照AIA_RS.py）
# ============================================================

def reproject_radio_simple_scale(
    radio_data: np.ndarray,
    radio_header: fits.Header,
    aia_cutout_map,
    cfg: Config,
) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """
    简化的射电数据投影方法，参照AIA_RS.py
    返回: (重投影数据, Tx坐标数组, Ty坐标数组)
    """
    try:
        # 获取射电图像的太阳信息
        (radio_crpix1, radio_crpix2, radio_crval1, radio_crval2, 
         radio_cdelt1, radio_cdelt2, radio_rsun) = get_sun_center_and_radius(radio_header)
        
        # 获取AIA图像的太阳信息
        aia_header = aia_cutout_map.meta
        (aia_crpix1, aia_crpix2, aia_crval1, aia_crval2,
         aia_cdelt1, aia_cdelt2, aia_rsun) = get_sun_center_and_radius(aia_header)
        
        if cfg.debug_mode:
            print(f"    [简单投影] AIA太阳半径: {aia_rsun:.1f} arcsec")
            print(f"    [简单投影] 射电太阳半径: {radio_rsun:.1f} arcsec")
            print(f"    [简单投影] 射电像素比例: {radio_cdelt1:.6f} arcsec/pixel")
            print(f"    [简单投影] 射电图像尺寸: {radio_data.shape}")
        
        # 计算射电图像的完整范围
        radio_x_extent, radio_y_extent = calculate_image_extent(
            radio_data.shape,
            radio_crpix1, radio_crpix2,
            radio_crval1, radio_crval2,
            radio_cdelt1, radio_cdelt2,
        )
        
        # 计算缩放因子，使射电太阳半径与AIA太阳半径匹配
        scale_factor = aia_rsun / radio_rsun
        
        # 计算缩放后的射电图像范围
        radio_center_x = radio_crval1
        radio_center_y = radio_crval2
        
        scaled_radio_x_min = radio_center_x + (radio_x_extent[0] - radio_center_x) * scale_factor
        scaled_radio_x_max = radio_center_x + (radio_x_extent[1] - radio_center_x) * scale_factor
        scaled_radio_y_min = radio_center_y + (radio_y_extent[0] - radio_center_y) * scale_factor
        scaled_radio_y_max = radio_center_y + (radio_y_extent[1] - radio_center_y) * scale_factor
        
        scaled_radio_extent = [
            min(scaled_radio_x_min, scaled_radio_x_max),
            max(scaled_radio_x_min, scaled_radio_x_max),
            min(scaled_radio_y_min, scaled_radio_y_max),
            max(scaled_radio_y_min, scaled_radio_y_max),
        ]
        
        if cfg.debug_mode:
            print(f"    [简单投影] 缩放因子: {scale_factor:.4f}")
            print(f"    [简单投影] 缩放后射电范围: X={scaled_radio_extent[0]:.0f}~{scaled_radio_extent[1]:.0f}, "
                  f"Y={scaled_radio_extent[2]:.0f}~{scaled_radio_extent[3]:.0f}")
        
        # 创建射电图像的像素网格
        ny, nx = radio_data.shape
        y_indices, x_indices = np.indices((ny, nx))
        
        # 计算每个像素在缩放后的太阳坐标
        # 线性插值：像素索引 -> 缩放后的角秒坐标
        tx_map = scaled_radio_extent[0] + (x_indices / (nx - 1)) * (scaled_radio_extent[1] - scaled_radio_extent[0])
        ty_map = scaled_radio_extent[2] + (y_indices / (ny - 1)) * (scaled_radio_extent[3] - scaled_radio_extent[2])
        
        # 获取AIA图像的范围
        aia_x_extent, aia_y_extent = calculate_image_extent(
            aia_cutout_map.data.shape,
            aia_crpix1, aia_crpix2,
            aia_crval1, aia_crval2,
            aia_cdelt1, aia_cdelt2,
        )
        
        aia_extent = [
            min(aia_x_extent[0], aia_x_extent[1]),
            max(aia_x_extent[0], aia_x_extent[1]),
            min(aia_y_extent[0], aia_y_extent[1]),
            max(aia_y_extent[0], aia_y_extent[1]),
        ]
        
        # 将射电数据重采样到AIA网格
        # 首先，创建射电数据的插值器
        from scipy.interpolate import RegularGridInterpolator
        
        # 创建射电数据的规则网格
        x_radio = np.linspace(scaled_radio_extent[0], scaled_radio_extent[1], nx)
        y_radio = np.linspace(scaled_radio_extent[2], scaled_radio_extent[3], ny)
        
        # 清理射电数据中的NaN
        radio_data_clean = np.nan_to_num(radio_data, nan=0.0, posinf=0.0, neginf=0.0)
        
        # 创建插值器
        interpolator = RegularGridInterpolator(
            (y_radio, x_radio),  # 注意：scipy要求y在前，x在后
            radio_data_clean,
            method='linear',
            bounds_error=False,
            fill_value=0.0
        )
        
        # 创建AIA图像的网格
        ny_aia, nx_aia = aia_cutout_map.data.shape
        x_aia = np.linspace(aia_extent[0], aia_extent[1], nx_aia)
        y_aia = np.linspace(aia_extent[2], aia_extent[3], ny_aia)
        
        # 生成AIA网格点
        X_aia, Y_aia = np.meshgrid(x_aia, y_aia)
        
        # 插值到AIA网格
        points = np.column_stack([Y_aia.ravel(), X_aia.ravel()])
        reprojected = interpolator(points).reshape(ny_aia, nx_aia)
        
        # 创建AIA网格的Tx, Ty坐标
        tx_aia = X_aia
        ty_aia = Y_aia
        
        if cfg.debug_mode:
            valid_count = np.sum(~np.isnan(reprojected))
            print(f"    [简单投影] 成功重投影: 有效像素 {valid_count}/{ny_aia*nx_aia}")
            print(f"    [简单投影] 重投影数据范围: [{np.nanmin(reprojected):.2e}, {np.nanmax(reprojected):.2e}]")
        
        return reprojected, tx_aia, ty_aia
        
    except Exception as e:
        if cfg.debug_mode:
            print(f"    [简单投影] 异常: {e}")
            import traceback
            traceback.print_exc()
        return None


# ============================================================
#  坐标预处理：弧度判断 + 绝对/相对坐标判断 + CRVAL叠加
# ============================================================
def _preprocess_radec_maps(
    ra_map: np.ndarray,
    dec_map: np.ndarray,
    radio_header: Optional[fits.Header],
    cfg: Config,
) -> Tuple[np.ndarray, np.ndarray, bool]:
    """
    统一坐标预处理，返回处理后的赤经赤纬（度）。
    特别处理：对于坐标图文件，假设坐标已经是度，并且是绝对坐标
    """
    # 如果使用赤经赤纬坐标图，这些坐标应该是绝对坐标（单位为度）
    if cfg.use_radec_maps:
        if cfg.debug_mode:
            print(f"    [坐标预处理] 使用赤经赤纬坐标图模式")
        
        ra = ra_map.copy().astype(np.float64)
        dec = dec_map.copy().astype(np.float64)
        
        # 检查数据有效性
        ra_fin = ra[np.isfinite(ra)]
        dec_fin = dec[np.isfinite(dec)]
        if len(ra_fin) == 0 or len(dec_fin) == 0:
            if cfg.debug_mode:
                print(f"    [坐标预处理] 警告: 坐标图中包含大量NaN值")
            return ra, dec, False
            
        # 统计坐标范围
        ra_min, ra_max = float(ra_fin.min()), float(ra_fin.max())
        dec_min, dec_max = float(dec_fin.min()), float(dec_fin.max())
        
        if cfg.debug_mode:
            print(f"    [坐标预处理] 赤经范围: [{ra_min:.6f}, {ra_max:.6f}] 度")
            print(f"    [坐标预处理] 赤纬范围: [{dec_min:.6f}, {dec_max:.6f}] 度")
        
        # 检查是否为合理的赤经赤纬坐标
        # 赤经通常为0-360度，赤纬为-90到90度
        is_absolute = True  # 坐标图文件提供的是绝对坐标
        
        # 如果赤经不在0-360范围内，进行调整
        if ra_min < 0 or ra_max > 360:
            if cfg.debug_mode:
                print(f"    [坐标预处理] 赤经超出[0,360)范围，进行标准化")
            ra = np.mod(ra, 360.0)
        
        # 赤纬应该在-90到90度之间
        if dec_min < -90 or dec_max > 90:
            if cfg.debug_mode:
                print(f"    [坐标预处理] 警告: 赤纬超出[-90,90]范围: [{dec_min:.2f}, {dec_max:.2f}]")
        
        # 检查坐标范围是否合理（对于太阳射电，视场通常很小）
        ra_range = ra_max - ra_min
        dec_range = dec_max - dec_min
        
        if cfg.debug_mode:
            print(f"    [坐标预处理] 赤经跨度: {ra_range:.4f}度")
            print(f"    [坐标预处理] 赤纬跨度: {dec_range:.4f}度")
        
        # 对于太阳射电观测，通常视场很小（几度以内）
        # 但如果坐标图文件提供的是绝对坐标，即使是小视场，坐标值也是绝对值
        if ra_range < 10 and dec_range < 10:
            if cfg.debug_mode:
                print(f"    [坐标预处理] 小视场坐标（可能是相对坐标或局部天区）")
        
        # 坐标图文件通常提供绝对坐标，但我们需要验证
        # 检查坐标中值是否接近太阳位置
        ra_median = float(np.median(ra_fin))
        dec_median = float(np.median(dec_fin))
        
        if cfg.debug_mode:
            print(f"    [坐标预处理] 坐标中值: RA={ra_median:.4f}°, Dec={dec_median:.4f}°")
        
        # 返回绝对坐标
        return ra, dec, False  # 第三个参数为False表示绝对坐标
        
    else:
        # 原有的太阳坐标模式处理逻辑保持不变
        # 如果使用太阳坐标模式
        if cfg.debug_mode:
            print(f"    [坐标预处理] 使用太阳坐标模式")
            print(
                f"    [坐标预处理] Tx范围: [{ra_map.min():.1f}, {ra_map.max():.1f}]角秒"
            )
            print(
                f"    [坐标预处理] Ty范围: [{dec_map.min():.1f}, {dec_map.max():.1f}]角秒"
            )

        # 对于太阳坐标，我们直接返回，并标记为相对坐标
        return ra_map, dec_map, True


# ============================================================
#  简化重投影函数 - 添加使用sunpy.map的直接绘制方法
# ============================================================
def reproject_radio_sunpy_map(
    radio_map: sunpy.map.GenericMap, aia_cutout_map: sunpy.map.GenericMap, cfg: Config
) -> Optional[np.ndarray]:
    """
    使用sunpy.map的直接方法将射电数据重投影到AIA坐标系
    参考示例代码，直接使用sunpy的坐标转换功能
    """
    try:
        # 检查射电地图是否有有效的坐标系
        if (
            not hasattr(radio_map, "coordinate_frame")
            or radio_map.coordinate_frame is None
        ):
            if cfg.debug_mode:
                print("    [sunpy重投影] 射电数据没有有效的坐标系信息")
            return None

        # 检查射电数据是否在太阳坐标系中
        if not hasattr(radio_map.coordinate_frame, "Tx"):
            if cfg.debug_mode:
                print("    [sunpy重投影] 射电数据不在太阳坐标系中")
            return None

        # 获取射电数据的形状
        ny_radio, nx_radio = radio_map.data.shape

        # 创建射电数据的像素网格
        y_radio, x_radio = np.meshgrid(
            np.arange(ny_radio), np.arange(nx_radio), indexing="ij"
        )

        # 将射电像素坐标转换为世界坐标
        radio_coords = radio_map.pixel_to_world(x_radio * u.pix, y_radio * u.pix)

        # 将射电世界坐标转换为AIA像素坐标
        aia_pixel_coords = aia_cutout_map.wcs.world_to_pixel(radio_coords)

        # 提取像素坐标
        aia_x_pixels = aia_pixel_coords[0].value
        aia_y_pixels = aia_pixel_coords[1].value

        # 获取AIA图像的形状
        ny_aia, nx_aia = aia_cutout_map.data.shape

        # 创建输出数组
        output = np.full((ny_aia, nx_aia), np.nan, dtype=np.float32)

        # 过滤有效点
        valid_mask = (
            np.isfinite(aia_x_pixels)
            & np.isfinite(aia_y_pixels)
            & np.isfinite(radio_map.data)
        )

        if np.sum(valid_mask) == 0:
            if cfg.debug_mode:
                print("    [sunpy重投影] 没有有效的坐标点")
            return None

        # 提取有效点的坐标和数据
        valid_x = aia_x_pixels[valid_mask]
        valid_y = aia_y_pixels[valid_mask]
        valid_data = radio_map.data[valid_mask]

        # 转换为整数像素坐标
        x_int = np.round(valid_x).astype(int)
        y_int = np.round(valid_y).astype(int)

        # 过滤在AIA图像边界内的点
        in_bounds = (x_int >= 0) & (x_int < nx_aia) & (y_int >= 0) & (y_int < ny_aia)

        if np.sum(in_bounds) == 0:
            if cfg.debug_mode:
                print("    [sunpy重投影] 没有点在AIA图像边界内")
            return None

        # 提取边界内的数据
        x_in = x_int[in_bounds]
        y_in = y_int[in_bounds]
        data_in = valid_data[in_bounds]

        # 使用最大值散射到输出数组
        acc = np.full((ny_aia, nx_aia), -np.inf, dtype=np.float64)
        np.maximum.at(acc, (y_in, x_in), data_in)

        output = np.where(acc > -np.inf, acc.astype(np.float32), np.nan)

        # 间隙填充
        nan_mask = np.isnan(output)
        if nan_mask.any():
            fill_sigma = 15.0
            filled = np.where(nan_mask, 0.0, output)
            weights = (~nan_mask).astype(np.float64)
            sm_d = gaussian_filter(filled.astype(np.float64), sigma=fill_sigma)
            sm_w = gaussian_filter(weights, sigma=fill_sigma)
            with np.errstate(invalid="ignore", divide="ignore"):
                diffused = np.where(sm_w > 1e-6, sm_d / sm_w, np.nan)
            output = np.where(nan_mask, diffused.astype(np.float32), output)

        if cfg.debug_mode:
            valid_count = np.sum(~np.isnan(output))
            print(f"    [sunpy重投影] 成功: 有效像素 {valid_count}/{ny_aia*nx_aia}")

        return output

    except Exception as e:
        if cfg.debug_mode:
            print(f"    [sunpy重投影] 异常: {e}")
            import traceback

            traceback.print_exc()
        return None


# ============================================================
#  前向投影贴图
# ============================================================
def reproject_radio_forward_paste(
    radio_data: np.ndarray,
    ra_map: np.ndarray,
    dec_map: np.ndarray,
    aia_cutout_map,
    cfg: Config,
    radio_header: Optional[fits.Header] = None,
) -> Optional[np.ndarray]:

    try:
        # 如果sunpy.map方法不可用或失败，使用原来的前向投影贴图法
        ny_aia, nx_aia = aia_cutout_map.data.shape

        # ── 坐标预处理 ─────────────────────────────────────────────────────
        if ra_map is None or dec_map is None:
            if cfg.debug_mode:
                print("    [前向投影] 失败：坐标图为 None")
            return None

        if ra_map.shape != radio_data.shape or dec_map.shape != radio_data.shape:
            if cfg.debug_mode:
                print(
                    f"    [前向投影] 失败：坐标图形状不匹配 "
                    f"data={radio_data.shape} RA={ra_map.shape} Dec={dec_map.shape}"
                )
            return None

        # 预处理坐标图
        ra_abs, dec_abs, is_relative = _preprocess_radec_maps(
            ra_map, dec_map, radio_header, cfg
        )

        # 如果使用赤经赤纬坐标图，这些是绝对坐标，需要转换为太阳坐标
        if cfg.use_radec_maps:
            if cfg.debug_mode:
                print(f"    [坐标转换] 使用赤经赤纬坐标图，转换为太阳坐标")
            
            # 获取射电观测时间
            radio_time = None
            if radio_header is not None:
                try:
                    time_keys = [
                        "DATE-OBS", "DATE_OBS", "DATEOBS",
                        "DATE-BEG", "DATE_BEG", "DATEBEG",
                    ]
                    for key in time_keys:
                        if key in radio_header:
                            date_str = str(radio_header[key]).strip()
                            if date_str:
                                if "  " in date_str:
                                    date_str = " ".join(date_str.split())
                                radio_time = _parse_flexible_datetime(date_str)
                                if radio_time:
                                    break
                except Exception:
                    pass

            # 如果无法获取射电时间，使用AIA时间
            if radio_time is None:
                try:
                    radio_time = aia_cutout_map.date.to_datetime()
                except Exception:
                    from datetime import datetime
                    radio_time = datetime.now()

            if cfg.debug_mode:
                print(f"    [时间信息] 射电观测时间: {radio_time}")

            # 获取太阳中心位置（赤经赤纬）
            try:
                from astropy.coordinates import get_sun
                from astropy.time import Time

                astropy_time = Time(radio_time, format="datetime", scale="utc")
                sun_coord = get_sun(astropy_time)
                sun_ra = sun_coord.ra.deg
                sun_dec = sun_coord.dec.deg

                if cfg.debug_mode:
                    print(f"    [太阳位置] 太阳中心: RA={sun_ra:.6f}°, Dec={sun_dec:.6f}°")

                # 将赤经赤纬坐标转换为太阳坐标
                # 首先，将射电坐标与太阳中心坐标对齐
                # 注意：赤经赤纬坐标是球面坐标，需要转换为平面坐标（日面坐标）
                
                # 创建射电坐标的SkyCoord对象（ICRS坐标系）
                radio_coords = SkyCoord(
                    ra=ra_abs * u.deg,
                    dec=dec_abs * u.deg,
                    frame='icrs',
                    obstime=astropy_time
                )
                
                # 转换为太阳坐标系（Helioprojective）
                with sunpy.coordinates.propagate_with_solar_surface():
                    radio_hpc = radio_coords.transform_to(aia_cutout_map.coordinate_frame)
                
                if cfg.debug_mode:
                    # 提取Tx, Ty坐标
                    tx = radio_hpc.Tx.arcsec
                    ty = radio_hpc.Ty.arcsec
                    fin_h = np.isfinite(tx) & np.isfinite(ty)
                    if fin_h.any():
                        print(f"    [坐标转换] 转换后太阳坐标范围:")
                        print(f"      Tx: [{tx[fin_h].min():.1f}, {tx[fin_h].max():.1f}]角秒")
                        print(f"      Ty: [{ty[fin_h].min():.1f}, {ty[fin_h].max():.1f}]角秒")
                        
                        # 检查AIA视野范围
                        bl = aia_cutout_map.bottom_left_coord
                        tr = aia_cutout_map.top_right_coord
                        print(f"    [坐标转换] AIA视野范围:")
                        print(f"      Tx: [{bl.Tx.arcsec:.1f}, {tr.Tx.arcsec:.1f}]角秒")
                        print(f"      Ty: [{bl.Ty.arcsec:.1f}, {tr.Ty.arcsec:.1f}]角秒")
                        
                        # 计算在AIA视野内的像素比例
                        in_aia_view = (
                            (tx[fin_h] >= bl.Tx.arcsec) &
                            (tx[fin_h] <= tr.Tx.arcsec) &
                            (ty[fin_h] >= bl.Ty.arcsec) &
                            (ty[fin_h] <= tr.Ty.arcsec)
                        )
                        n_in_view = int(np.sum(in_aia_view))
                        total_valid = int(np.sum(fin_h))
                        print(f"    [坐标转换] 射电像素在AIA视野内: {n_in_view}/{total_valid} ({n_in_view/max(total_valid,1)*100:.1f}%)")
            
            except Exception as e:
                if cfg.debug_mode:
                    print(f"    [警告] 坐标转换失败: {e}")
                    import traceback
                    traceback.print_exc()
                return None
                
        else:
            # 原有的太阳坐标模式处理逻辑
            # 对于太阳坐标，ra_abs和dec_abs实际上是Tx和Ty（角秒）
            # 直接构建太阳坐标
            try:
                # 直接使用Tx, Ty构建太阳坐标
                radio_hpc = SkyCoord(
                    Tx=ra_abs * u.arcsec,
                    Ty=dec_abs * u.arcsec,
                    frame=aia_cutout_map.coordinate_frame,
                )

                if cfg.debug_mode:
                    tx = radio_hpc.Tx.arcsec
                    ty = radio_hpc.Ty.arcsec
                    fin_h = np.isfinite(tx) & np.isfinite(ty)
                    if fin_h.any():
                        print(
                            f"    [太阳坐标模式] Tx范围: [{tx[fin_h].min():.1f}, {tx[fin_h].max():.1f}]角秒"
                        )
                        print(
                            f"    [太阳坐标模式] Ty范围: [{ty[fin_h].min():.1f}, {ty[fin_h].max():.1f}]角秒"
                        )

        # ── 有效点筛选 ────────────────────────────────────────────────────
        # 注意：对于赤经赤纬模式，radio_hpc可能是一个标量或数组
        # 我们需要确保正确提取有效点的坐标
        
        # 创建有效点掩码
        if cfg.use_radec_maps:
            # 对于赤经赤纬模式，radio_hpc是从坐标转换得到的
            # 我们需要确保ra_abs和dec_abs与radio_data形状相同
            valid_mask = (
                np.isfinite(ra_abs) & np.isfinite(dec_abs) & np.isfinite(radio_data)
            )
        else:
            # 对于太阳坐标模式
            valid_mask = (
                np.isfinite(ra_abs) & np.isfinite(dec_abs) & np.isfinite(radio_data)
            )
        
        n_valid = int(np.sum(valid_mask))
        if n_valid < 9:
            if cfg.debug_mode:
                print(f"    [前向投影] 失败：有效点不足 ({n_valid})")
            return None

        v_data = radio_data[valid_mask].astype(np.float64)

        if cfg.debug_mode:
            print(f"    [前向投影] 有效射电像素: {n_valid}")

        # 获取像素坐标
        if cfg.use_radec_maps:
            # 对于赤经赤纬坐标，radio_hpc已经是转换后的太阳坐标
            # 提取有效点的坐标
            if hasattr(radio_hpc, '__len__') and len(radio_hpc) > 1:
                # radio_hpc是数组
                radio_hpc_valid = radio_hpc[valid_mask]
            else:
                # radio_hpc是标量或单个坐标对象
                radio_hpc_valid = radio_hpc
        else:
            # 对于太阳坐标，我们已经有radio_hpc
            if hasattr(radio_hpc, '__len__') and len(radio_hpc) > 1:
                radio_hpc_valid = radio_hpc[valid_mask]
            else:
                radio_hpc_valid = radio_hpc

        # 计算像素坐标
        px_f, py_f = aia_cutout_map.wcs.world_to_pixel(radio_hpc_valid)
        px_f = np.asarray(px_f, dtype=np.float64)
        py_f = np.asarray(py_f, dtype=np.float64)

        # 修复维度问题
        if np.isscalar(px_f):
            px_f = np.array([px_f])
            py_f = np.array([py_f])

        # ── 像素坐标有效性 & 边界过滤 ────────────────────────────────────
        fin_pix = np.isfinite(px_f) & np.isfinite(py_f)

        # 修复维度不匹配问题
        if v_data.ndim == 1:
            if fin_pix.size != v_data.size:
                if cfg.debug_mode:
                    print(f"    [维度修复] 调整fin_pix维度: {fin_pix.shape} -> 与v_data匹配: {v_data.shape}")
                # 调整fin_pix维度
                if fin_pix.size > v_data.size:
                    fin_pix = fin_pix[:v_data.size]
                elif fin_pix.size < v_data.size:
                    fin_pix = np.concatenate([fin_pix, np.zeros(v_data.size - fin_pix.size, dtype=bool)])

        px_i = np.round(px_f[fin_pix]).astype(int)
        py_i = np.round(py_f[fin_pix]).astype(int)
        v_vals = v_data[fin_pix]

        in_bounds = (px_i >= 0) & (px_i < nx_aia) & (py_i >= 0) & (py_i < ny_aia)

        n_in = int(np.sum(in_bounds))
        if cfg.debug_mode:
            print(f"    [前向投影] 射电像素落入AIA视野: {n_in} / {int(np.sum(fin_pix))} ({n_in/max(int(np.sum(fin_pix)),1)*100:.1f}%)")

        if n_in == 0:
            if cfg.debug_mode:
                print(f"    [诊断] 没有像素落入AIA视野")
            return None

        b_px = px_i[in_bounds]
        b_py = py_i[in_bounds]
        b_vals = v_vals[in_bounds]

        # ── 散射：取最大值（保留峰值，不被低值覆盖）─────────────────────
        acc = np.full((ny_aia, nx_aia), -np.inf, dtype=np.float64)
        np.maximum.at(acc, (b_py, b_px), b_vals)

        output = np.where(acc > -np.inf, acc, np.nan).astype(np.float32)

        # ── 间隙填充 ───────────────────────────────────────────────────
        nan_mask = np.isnan(output)
        if nan_mask.any():
            fill_sigma = 15.0
            filled = np.where(nan_mask, 0.0, output)
            weights = (~nan_mask).astype(np.float64)
            sm_d = gaussian_filter(filled.astype(np.float64), sigma=fill_sigma)
            sm_w = gaussian_filter(weights, sigma=fill_sigma)
            with np.errstate(invalid="ignore", divide="ignore"):
                diffused = np.where(sm_w > 1e-6, sm_d / sm_w, np.nan)
            output = np.where(nan_mask, diffused.astype(np.float32), output)

        valid_final = int(np.sum(~np.isnan(output)))
        if valid_final == 0:
            return None

        if cfg.debug_mode:
            peak_val = float(np.nanmax(output))
            print(f"    [前向投影] 成功: 有效像素 {valid_final}/{ny_aia*nx_aia} 峰值 {peak_val:.4g}")

        return output

    except Exception as e:
        if cfg.debug_mode:
            print(f"    [前向投影] 异常: {e}")
            import traceback
            traceback.print_exc()
        return None


def reproject_radio_to_aia(
    radio_data: np.ndarray,
    radio_header: fits.Header,
    ra_map: Optional[np.ndarray],
    dec_map: Optional[np.ndarray],
    aia_cutout_map,  # sunpy.map.GenericMap
    cfg: Config,
) -> Optional[np.ndarray]:
    """
    入口函数：调用前向投影贴图法将射电数据映射到AIA坐标系。
    """
    if ra_map is None or dec_map is None:
        if cfg.debug_mode:
            print("    reproject_radio_to_aia: 无坐标图，跳过")
        return None

    return reproject_radio_forward_paste(
        radio_data, ra_map, dec_map, aia_cutout_map, cfg, radio_header=radio_header
    )


# ============================================================
#  展示级等值线平滑（归一化卷积，正确处理 NaN 边界）
# ============================================================
def smooth_for_contour(data: np.ndarray, sigma: float) -> np.ndarray:
    """
    仅用于绘图前展示，不修改分析数据。
    归一化卷积：smooth(data) / smooth(valid_mask)，NaN 区域不扩散。
    scipy.gaussian_filter 比 astropy convolve 快约 10×。
    """
    if sigma <= 0:
        return data
    nan_mask = np.isnan(data)
    filled = np.where(nan_mask, 0.0, data)
    weights = (~nan_mask).astype(np.float64)
    smooth_d = gaussian_filter(filled, sigma=sigma)
    smooth_w = gaussian_filter(weights, sigma=sigma)
    with np.errstate(invalid="ignore", divide="ignore"):
        result = np.where(smooth_w > 1e-6, smooth_d / smooth_w, np.nan)
    return result


# ============================================================
#  波束与颜色工具
# ============================================================
def get_beam_params_from_header(header: fits.Header) -> Optional[Dict]:
    """从 FITS 头提取波束椭圆参数：BMAJ(角秒), BMIN(角秒), BPA(度)。"""
    bmaj = header.get("BMAJ", None)
    bmin = header.get("BMIN", None)
    bpa = header.get("BPA", 0.0)
    if bmaj is None or bmin is None:
        return None
    return {
        "bmaj_arcsec": float(bmaj) * 3600.0,
        "bmin_arcsec": float(bmin) * 3600.0,
        "bpa_deg": float(bpa),
    }


def draw_beam_ellipse_pixel(
    ax, beam: Dict, aia_cutout_map: sunpy.map.GenericMap, color: str = "white"
):
    """在图像左下角绘制波束椭圆（像素坐标）。"""
    cdelt = abs(aia_cutout_map.scale.axis1.to(u.arcsec / u.pix).value)
    bmaj_px = beam["bmaj_arcsec"] / cdelt
    bmin_px = beam["bmin_arcsec"] / cdelt
    ny, nx = aia_cutout_map.data.shape
    cx_px, cy_px = nx * 0.08, ny * 0.08
    ellipse = Ellipse(
        xy=(cx_px, cy_px),
        width=bmin_px,
        height=bmaj_px,
        angle=beam["bpa_deg"],
        linewidth=1.5,
        edgecolor=color,
        facecolor="none",
        alpha=0.85,
    )
    ax.add_patch(ellipse)
    ax.text(
        cx_px,
        cy_px - bmaj_px * 0.7,
        "Beam",
        color=color,
        fontsize=8,
        ha="center",
        va="top",
        alpha=0.85,
    )


def get_band_color(
    band_label: str, band_idx: int, cfg: Config, color_cache: Optional[List] = None
) -> Tuple[str, str]:
    """根据波段标签返回 (主色, 暗色) 对，优先使用缓存中的精确频率匹配。"""
    m = _RE_MHZ.search(band_label)
    if m and color_cache is not None:
        label_mhz = float(m.group(1))
        for key_mhz, val in color_cache:
            if abs(key_mhz - label_mhz) < 0.5:
                return val
    return cfg.default_colors[band_idx % len(cfg.default_colors)]


def process_hmi_for_overlay(
    hmi_file: str, target_wcs, cfg: Config
) -> Optional[sunpy.map.GenericMap]:
    """
    处理 HMI 磁图：重投影到目标 WCS，高斯平滑，阈值过滤，返回可用于等值线绘制的 map。
    """
    try:
        hmi_map = sunpy.map.Map(hmi_file)
        with sunpy.coordinates.propagate_with_solar_surface():
            aligned = hmi_map.reproject_to(target_wcs)
        smoothed = gaussian_filter(aligned.data, sigma=cfg.hmi_sigma)
        smoothed[np.abs(smoothed) < cfg.hmi_threshold_gauss] = 0
        return sunpy.map.Map(smoothed, aligned.meta)
    except Exception:
        return None


# ============================================================
#  简化核心分组处理逻辑
# ============================================================
def process_aia_group(
    aia_file: str,
    hmi_file: Optional[str],
    sub_tasks: List[Tuple[int, Dict]],
    task_index: int,
    total_tasks: int,
    cfg: Config,
    color_cache: List,
):
    """
    简化版：移除太阳自转修正和高度计算
    """
    check_memory_usage(limit=cfg.memory_limit_pct)
    print(f"\n[{task_index}/{total_tasks}] 加载 AIA: {os.path.basename(aia_file)}")

    selected_bands_idx: Dict[str, int] = {
        b: i for i, b in enumerate(cfg.selected_bands)
    }
    aia_cmap_name = cfg.aia_cmap if cfg.aia_cmap in plt.colormaps() else "hot"

    aia_map = cutout_aia = hmi_processed = None

    try:
        aia_map = sunpy.map.Map(aia_file)
        aia_time = (
            aia_map.date.to_datetime()
            if hasattr(aia_map, "date")
            else parse_aia_time_from_filename(os.path.basename(aia_file))
        )

        # 裁剪 ROI
        bl = SkyCoord(
            Tx=cfg.roi_bottom_left[0] * u.arcsec,
            Ty=cfg.roi_bottom_left[1] * u.arcsec,
            frame=aia_map.coordinate_frame,
        )
        tr = SkyCoord(
            Tx=cfg.roi_top_right[0] * u.arcsec,
            Ty=cfg.roi_top_right[1] * u.arcsec,
            frame=aia_map.coordinate_frame,
        )
        cutout_aia = aia_map.submap(bl, top_right=tr)

        # 预处理 HMI 磁图（若启用）
        hmi_processed = (
            process_hmi_for_overlay(hmi_file, cutout_aia.wcs, cfg)
            if cfg.overlay_hmi and hmi_file
            else None
        )

        # 创建输出目录
        if cfg.save_figure:
            os.makedirs(cfg.output_dir, exist_ok=True)

        # 遍历该 AIA 对应的每个射电时间切片
        for sub_index, single_slice_bands in sub_tasks:
            check_memory_usage(limit=cfg.memory_limit_pct)
            print(f"  -> 绘制序列帧 {sub_index + 1}/{len(sub_tasks)}")

            fig = plt.figure(figsize=(12, 10))
            ax = fig.add_subplot(111, projection=cutout_aia.wcs)

            # --- 1. 绘制 AIA 底图 ---
            cutout_aia.plot(
                axes=ax,
                norm=mcolors.LogNorm(vmin=cfg.aia_vmin, vmax=cfg.aia_vmax),
                cmap=aia_cmap_name,
                title=False,
            )
            ax.coords.grid(False)

            legend_handles = []
            first_radio_time = None
            collected_beams: Dict[str, Dict] = {}

            # --- 2. 叠加 HMI 等值线（正极红，负极蓝）---
            if hmi_processed is not None:
                ax.contour(
                    hmi_processed.data,
                    levels=cfg.hmi_levels_gauss,
                    colors=["red"],
                    linewidths=0.8,
                    alpha=0.7,
                )
                ax.contour(
                    hmi_processed.data,
                    levels=[-lv for lv in cfg.hmi_levels_gauss],
                    colors=["blue"],
                    linewidths=0.8,
                    alpha=0.7,
                )
                legend_handles += [
                    Line2D(
                        [0],
                        [0],
                        color="red",
                        lw=0.8,
                        label=f"+{cfg.hmi_levels_gauss[0]:.0f}G",
                    ),
                    Line2D(
                        [0],
                        [0],
                        color="blue",
                        lw=0.8,
                        label=f"-{cfg.hmi_levels_gauss[0]:.0f}G",
                    ),
                ]

            # 按频率排序波段
            sorted_bands = sorted(
                single_slice_bands.items(),
                key=lambda x: (
                    float(_RE_BAND_SORTED.search(x[0]).group(1))
                    if _RE_BAND_SORTED.search(x[0])
                    else 0.0
                ),
            )

            # --- 3. 叠加射电等值线（每个波段一种颜色）---
            for band_idx, (band_label, file_list) in enumerate(sorted_bands):
                orig_band_idx = selected_bands_idx.get(band_label, band_idx)
                main_color, dark_color = get_band_color(
                    band_label, orig_band_idx, cfg, color_cache
                )

                drawn_any = False
                for fits_path, polarization, radio_time in file_list:
                    if (
                        cfg.polarization_mode != "BOTH"
                        and polarization != cfg.polarization_mode
                    ):
                        continue

                    try:
                        # 提取射电数据和坐标图
                        radio_data_2d, ra_map, dec_map, radio_header_2d, _ = (
                            extract_radio_2d_data(
                                fits_path, use_float32=cfg.radio_use_float32, cfg=cfg
                            )
                        )

                        if radio_data_2d is None or radio_data_2d.size == 0:
                            continue

                        # 获取波束信息
                        beam = get_beam_params_from_header(radio_header_2d)
                        if beam and band_label not in collected_beams:
                            collected_beams[band_label] = beam

                        # 使用简化的投影方法（参照AIA_RS.py）
                        result = reproject_radio_simple_scale(
                            radio_data_2d,
                            radio_header_2d,
                            cutout_aia,
                            cfg,
                        )

                        if result is not None:
                            reprojected, tx_map, ty_map = result
                        else:
                            reprojected = None

                        if (
                            reprojected is None
                            or np.isnan(np.nanmax(reprojected))
                            or np.nanmax(reprojected) <= 0
                        ):
                            continue

                        # 计算等值线级别
                        display_data = smooth_for_contour(
                            reprojected, cfg.contour_smooth_sigma
                        )
                        levels = compute_contour_levels(display_data, cfg)
                        if not levels:
                            continue

                        # 绘制等值线
                        n_lev = len(levels)
                        lws = [
                            cfg.contour_linewidths[
                                min(i, len(cfg.contour_linewidths) - 1)
                            ]
                            for i in range(n_lev)
                        ]
                        colors_list = [
                            dark_color if i < n_lev - 1 else main_color
                            for i in range(n_lev)
                        ]

                        ax.contour(
                            display_data,
                            levels=levels,
                            colors=colors_list,
                            linewidths=lws,
                            alpha=cfg.contour_alpha,
                        )

                        if radio_time and first_radio_time is None:
                            first_radio_time = radio_time
                        drawn_any = True

                    except Exception:
                        pass

                if drawn_any:
                    legend_handles.append(
                        Line2D(
                            [0],
                            [0],
                            color=main_color,
                            linewidth=2.0,
                            label=f"{band_label}",
                        )
                    )

            # --- 4. 绘制波束椭圆（左下角）---
            if cfg.show_beam and collected_beams:
                for b_idx, (b_label, beam) in enumerate(collected_beams.items()):
                    b_color, _ = get_band_color(b_label, b_idx, cfg, color_cache)
                    draw_beam_ellipse_pixel(ax, beam, cutout_aia, color=b_color)

            # --- 5. 绘制日面边缘（太阳轮廓）---
            cutout_aia.draw_limb(
                axes=ax,
                color="gray",
                linewidth=1.0,
                linestyle="--",
                alpha=0.6,
                label="Solar limb",
            )

            # --- 6. 图例与标题设置 ---
            title_time = (
                first_radio_time.strftime("%Y-%m-%d %H:%M:%S") + " UT"
                if first_radio_time
                else os.path.basename(aia_file)
            )
            ax.set_title(
                f"AIA 171Å + Radio ({cfg.polarization_mode}) + HMI\n{title_time}",
                fontsize=12,
                pad=10,
                color="white",
            )
            ax.legend(
                handles=legend_handles,
                loc="upper right",
                fontsize=9,
                framealpha=0.6,
                facecolor="black",
                labelcolor="white",
            )

            # --- 7. 样式调整与保存 ---
            fig.patch.set_facecolor("black")
            ax.set_facecolor("black")
            ax.tick_params(colors="white", direction="in")
            for spine in ax.spines.values():
                spine.set_edgecolor("white")
            ax.coords[0].set_axislabel("Solar X (arcsec)", color="white")
            ax.coords[1].set_axislabel("Solar Y (arcsec)", color="white")

            if cfg.save_figure:
                radio_time_str = (
                    first_radio_time.strftime("%Y%m%d_%H%M%S")
                    if first_radio_time
                    else f"unknown_{sub_index}"
                )
                output_filename = f"{radio_time_str}_{cfg.polarization_mode}_seq{sub_index + 1:02d}.png"
                plt.savefig(
                    os.path.join(cfg.output_dir, output_filename),
                    dpi=cfg.dpi,
                    bbox_inches="tight",
                    facecolor="black",
                )

            fig.clf()
            plt.close(fig)
            gc.collect()

    except Exception:
        import traceback

        traceback.print_exc()

    finally:
        del aia_map, cutout_aia, hmi_processed
        gc.collect()


# ============================================================
#  ★ 优化4：射电头文件并行读取（线程池，I/O 密集型）
# ============================================================
def parse_radio_time_from_header(header: fits.Header) -> Optional[datetime]:
    """从FITS头中解析射电观测时间（支持多种关键字和格式）。"""
    # 尝试多个可能的时间关键字
    time_keys = [
        "DATE-OBS",
        "DATE_OBS",
        "DATEOBS",
        "DATE-BEG",
        "DATE_BEG",
        "DATEBEG",
        "TIME-OBS",
        "DATE",
    ]

    for key in time_keys:
        if key in header:
            date_str = str(header[key]).strip()
            if not date_str:
                continue

            # 特殊处理：射电文件的时间格式可能有空格和毫秒，如"20250124045855  3"
            # 处理多个空格的情况
            if "  " in date_str:
                # 将多个空格替换为单个空格
                date_str = " ".join(date_str.split())

            # 如果包含空格分隔的数字，将其转换为小数点格式
            if " " in date_str:
                parts = date_str.split(" ")
                if len(parts) == 2:
                    # 格式: "20250124045855 3" -> "20250124045855.003"
                    integer_part = parts[0]
                    decimal_part = parts[1].ljust(3, "0")[:3]  # 补零到3位毫秒
                    date_str = f"{integer_part}.{decimal_part}"

            # 移除可能的尾部'Z'字符
            date_str = date_str.rstrip("Z")

            # 尝试解析不同格式
            parsed_time = _parse_flexible_datetime(date_str)
            if parsed_time:
                return parsed_time

            # 调试：打印无法解析的原始字符串
            # 注意：这里需要访问cfg，但函数签名中没有cfg参数
            # 我们将在调用处通过全局cfg或修改函数签名来处理
            # 暂时注释掉这行，避免NameError
            # print(f"    调试: 无法解析时间字符串: '{date_str}' (长度: {len(date_str)})")

    # 如果所有方法都失败，返回None
    return None


def _read_one_radio_header(
    rf: str, selected_bands: Tuple[str, ...], pol: str, cfg: Config
) -> Optional[Dict]:
    """
    优化版：改进时间解析和错误处理，优先从文件名解析时间
    """
    band_found = next((b for b in selected_bands if b in rf), None)
    if not band_found:
        return None
    try:
        # 优先从文件名解析时间
        r_time = parse_radio_time_from_filename(rf)
        
        if r_time:
            return {"path": rf, "band": band_found, "pol": pol, "time": r_time}
        
        # 如果文件名解析失败，尝试从头文件读取
        hdr = fits.getheader(rf)
        r_time = parse_radio_time_from_header(hdr)

        if r_time:
            return {"path": rf, "band": band_found, "pol": pol, "time": r_time}
        else:
            # 调试信息
            if cfg.debug_mode:
                print(f"    警告: 无法解析射电文件时间: {os.path.basename(rf)}")

    except Exception as e:
        if cfg.debug_mode:
            print(
                f"    读取射电文件头出错: {os.path.basename(rf)}, 错误: {str(e)[:100]}"
            )

    return None


# ============================================================
def build_matched_pairs(cfg: Config) -> List[Tuple[str, Optional[str], List]]:
    """
    优化版：改进时间匹配逻辑，添加详细调试信息
    """
    print("=" * 60)
    print("正在扫描并进行横向切片匹配，请稍候...")

    aia_files = sorted(glob.glob(os.path.join(cfg.aia_base_dir, "*.fits")))
    hmi_files = sorted(glob.glob(os.path.join(cfg.hmi_base_dir, "*.fits")))

    if not aia_files:
        print("[错误] 找不到 AIA 文件，请检查 cfg.aia_base_dir")
        return []

    # 快速测试模式
    if cfg.quick_test:
        print("[快速测试模式] 只处理前几个文件")
        aia_files = aia_files[: min(5, len(aia_files))]

    hmi_times = []
    for hf in hmi_files:
        t = parse_hmi_time_from_filename(os.path.basename(hf))
        if t:
            hmi_times.append((hf, t))

    pol = cfg.polarization_mode
    files_in_pol_dir = glob.glob(
        os.path.join(cfg.radio_base_dir, "**", pol, "*.fits"), recursive=True
    )
    files_with_pol_name = glob.glob(
        os.path.join(cfg.radio_base_dir, "**", f"*{pol}*.fits"), recursive=True
    )

    # 过滤掉坐标图文件
    radio_files = []
    for f in list(set(files_in_pol_dir + files_with_pol_name)):
        if "_RightAscensionDegree.fits" in f or "_DeclinationDegree.fits" in f:
            continue  # 跳过坐标图文件
        radio_files.append(f)

    # 快速测试模式
    if cfg.quick_test:
        radio_files = radio_files[: min(10, len(radio_files))]

    print(f"成功锁定 {len(radio_files)} 个 {pol} 射电数据文件。正在并发提取观测时间...")

    # ★ 优化4：线程池并发读取头文件
    max_io_threads = min(32, (os.cpu_count() or 4) * 2, max(1, len(radio_files)))
    selected_bands_tuple = tuple(cfg.selected_bands)
    _read_fn = partial(
        _read_one_radio_header, selected_bands=selected_bands_tuple, pol=pol, cfg=cfg
    )

    radio_cache: List[Dict] = []
    with ThreadPoolExecutor(max_workers=max_io_threads) as executor:
        results = executor.map(_read_fn, radio_files)
        radio_cache = [r for r in results if r is not None]

    print(f"  读取完毕，有效射电观测记录: {len(radio_cache)} 条")

    # 打印时间范围信息
    if radio_cache:
        radio_times = [rc["time"] for rc in radio_cache]
        min_time = min(radio_times)
        max_time = max(radio_times)
        print(f"  射电时间范围: {min_time} 到 {max_time}")

    start_idx = cfg.aia_file_start_idx if cfg.aia_file_start_idx is not None else 0
    end_idx = (
        cfg.aia_file_end_idx if cfg.aia_file_end_idx is not None else len(aia_files)
    )
    target_aia_files = aia_files[start_idx:end_idx]

    hmi_threshold_sec = cfg.hmi_time_threshold * 3600
    grouped_tasks = []

    # 统计信息
    match_stats = {"aia_processed": 0, "aia_matched": 0, "total_slices": 0}

    for aia_file in target_aia_files:
        match_stats["aia_processed"] += 1
        aia_time = parse_aia_time_from_filename(os.path.basename(aia_file))
        if not aia_time:
            print(f"  警告: 无法解析AIA文件时间: {os.path.basename(aia_file)}")
            continue

        # 寻找时间上最接近的 HMI 文件
        best_hmi = None
        if hmi_times:
            valid_hmis = [
                hf
                for hf in hmi_times
                if abs((hf[1] - aia_time).total_seconds()) <= hmi_threshold_sec
            ]
            if valid_hmis:
                best_hmi = min(
                    valid_hmis, key=lambda x: abs((x[1] - aia_time).total_seconds())
                )[0]

        # 收集时间阈值内的射电数据，按波段分组
        band_groups: Dict[str, list] = {}
        for rc in radio_cache:
            time_diff = abs((rc["time"] - aia_time).total_seconds())
            if time_diff <= cfg.radio_time_threshold:
                band_groups.setdefault(rc["band"], []).append(
                    (rc["path"], rc["pol"], rc["time"], time_diff)
                )

        if not band_groups:
            if cfg.debug_mode:
                print(
                    f"  AIA时间 {aia_time}: 无射电数据匹配 (阈值: {cfg.radio_time_threshold}秒)"
                )
            continue

        match_stats["aia_matched"] += 1

        # 调试信息：显示每个波段的匹配情况
        if cfg.debug_mode:
            print(f"  AIA时间 {aia_time}:")
            for band, files in band_groups.items():
                print(f"    波段 {band}: {len(files)} 个文件")
                for f in files[:2]:  # 只显示前2个
                    print(f"      时间差: {f[3]:.1f}秒, 文件: {os.path.basename(f[0])}")

        # 匹配阶段排序 + 截断
        for band in band_groups:
            # 按时间差排序，选择最接近的
            band_groups[band].sort(key=lambda x: x[3])  # 按时间差排序
            band_groups[band] = band_groups[band][: cfg.max_radio_per_band]

        # 确定横向切片数量：取所有波段的最小文件数
        min_count = min(len(v) for v in band_groups.values())
        if min_count == 0:
            if cfg.debug_mode:
                print(f"    警告: 某些波段没有匹配文件")
            continue

        # 构建横向切片
        tasks_for_this_aia = []
        for sub_index in range(min_count):
            slice_bands = {}
            for band in band_groups:
                if sub_index < len(band_groups[band]):
                    slice_bands[band] = [band_groups[band][sub_index][:3]]  # 去掉时间差

            if slice_bands:  # 确保切片不为空
                tasks_for_this_aia.append((sub_index, slice_bands))
                match_stats["total_slices"] += 1

        if tasks_for_this_aia:
            grouped_tasks.append((aia_file, best_hmi, tasks_for_this_aia))

            # 打印匹配成功信息
            if cfg.debug_mode:
                print(f"    成功创建 {len(tasks_for_this_aia)} 个切片")

    # 打印统计信息
    print(f"\n匹配结果统计:")
    print(f"  处理的AIA文件: {match_stats['aia_processed']}")
    print(f"  成功匹配的AIA文件: {match_stats['aia_matched']}")
    print(f"  创建的切片总数: {match_stats['total_slices']}")
    print(f"  成功创建了 {len(grouped_tasks)} 组以 AIA 为核心的任务。")
    print("=" * 60)
    return grouped_tasks


# ============================================================
#  ★ 优化1：子进程初始化器
# ============================================================
def _worker_init():
    """
    ProcessPoolExecutor 子进程启动时调用，确保每个 worker 使用非交互式
    Matplotlib 后端（Agg），避免 GUI 资源争用和内存泄漏。
    """
    import matplotlib

    matplotlib.use("Agg")
    import warnings

    warnings.filterwarnings("ignore")


# ============================================================
#  简化主函数
# ============================================================
def test_time_parsing():
    """测试时间解析函数是否正常工作"""
    test_cases = [
        "20250124045940760",  # 17位数字格式
        "20250124044317 38",  # 空格分隔
        "2025124_044317_038",  # 儒略日格式
        "2025-01-24T04:43:17.038Z",  # ISO格式
    ]

    print("测试时间解析:")
    for test_str in test_cases:
        result = _parse_flexible_datetime(test_str)
        if result:
            print(f"  '{test_str}' -> {result}")
        else:
            print(f"  '{test_str}' -> 解析失败")


def main():
    cfg = Config()

    # 测试时间解析
    if cfg.debug_mode:
        test_time_parsing()

        # 测试太阳位置计算
        print("\n测试太阳位置计算:")
        test_time = datetime(2025, 1, 24, 4, 43, 17)
        try:
            from astropy.coordinates import get_sun
            from astropy.time import Time

            # 正确的时间转换
            astropy_time = Time(test_time, format="datetime", scale="utc")
            sun_coord = get_sun(astropy_time)
            sun_ra = sun_coord.ra.deg
            sun_dec = sun_coord.dec.deg

            print(f"  测试时间: {test_time}")
            print(f"  太阳位置: RA={sun_ra:.6f}°, Dec={sun_dec:.6f}°")

            # 同时测试get_solar_position函数
            sun_ra2, sun_dec2 = get_solar_position(test_time)
            print(f"  通过get_solar_position函数:")
            print(f"    太阳位置: RA={sun_ra2:.6f}°, Dec={sun_dec2:.6f}°")
        except Exception as e:
            print(f"  太阳位置计算失败: {e}")
            import traceback

            traceback.print_exc()

    # 颜色缓存整个运行只构建一次
    color_cache = _build_band_color_cache(cfg)

    grouped_tasks = build_matched_pairs(cfg)
    if not grouped_tasks:
        print("[提示] 没有找到匹配的数据对。请检查时间阈值或路径设置。")
        return

    total = len(grouped_tasks)

    # 单进程模式（简化）
    print(f"[模式] 单进程，共 {total} 组任务")
    for task_index, (aia_file, hmi_file, sub_tasks) in enumerate(grouped_tasks):
        process_aia_group(
            aia_file=aia_file,
            hmi_file=hmi_file,
            sub_tasks=sub_tasks,
            task_index=task_index + 1,
            total_tasks=total,
            cfg=cfg,
            color_cache=color_cache,
        )

    print("\n全部任务处理完毕。")


if __name__ == "__main__":
    main()
