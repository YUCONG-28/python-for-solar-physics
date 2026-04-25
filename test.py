# -*- coding: utf-8 -*-
"""
AIA_RS_HMI.py  –  AIA、射电和 HMI 数据叠加绘图脚本
======================================================
功能：将射电等值线叠加到 AIA 171Å 图像上，可选叠加 HMI 磁图等值线。

赤经赤纬坐标图文件说明
-----------------------
每个射电频率目录下配套两个辅助 FITS 文件：
    <freq>MHz_RightAscensionDegree.fits   -- 赤经坐标图（度）
    <freq>MHz_DeclinationDegree.fits      -- 赤纬坐标图（度）

它们与射电图像像素一一对应，记录每个像素在天球 ICRS 坐标系中的赤经/赤纬值，
是精确坐标转换（ICRS → HPC）的核心依据，使射电等值线能正确叠加到太阳图像上。
若未找到这两个文件，程序将自动回退到基于太阳半径缩放的简化投影法。

新增功能: 左右旋数据加和（可配置加权平均）
==========================================
支持三种偏振模式：
1. "RR": 仅使用右旋圆偏振数据
2. "LL": 仅使用左旋圆偏振数据
3. "RR+LL": 右旋和左旋数据合并（加权平均或简单相加）
"""

# ============================================================
# 1. 基础库导入
# ============================================================
import gc
import glob
import os
import re
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import lru_cache, partial
from typing import Dict, List, Optional, Tuple

# ============================================================
# 2. 科学计算和天文库导入
# ============================================================
import astropy.units as u
import matplotlib

matplotlib.use("Agg")  # 非交互后端，子进程安全，节省内存
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import psutil
import sunpy.coordinates
import sunpy.map
from astropy.constants import R_sun
from astropy.convolution import Gaussian2DKernel
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS
from matplotlib.lines import Line2D
from matplotlib.patches import Ellipse
from scipy.interpolate import RegularGridInterpolator  # 提前导入，避免函数内重复导入
from scipy.ndimage import gaussian_filter
from scipy.optimize import curve_fit
from sunpy.coordinates import frames

warnings.filterwarnings("ignore")

# ============================================================
# 3. 全局配置和常量
# ============================================================

# 字体设置
plt.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

# 正则表达式常量（全部预编译，避免运行时重复编译）
_RE_MHZ = re.compile(r"(\d+\.?\d*)\s*MHz", re.IGNORECASE)
_RE_BAND_SORTED = re.compile(r"(\d+\.?\d*)MHz")
_RE_AIA_PATS = [
    re.compile(r"aia\.lev1_euv_12s\.(\d{4}-\d{2}-\d{2}T\d{6}Z)\.\d+\.image_lev1\.fits"),
    re.compile(r"aia\.lev1_euv_12s\.(\d{4}-\d{2}-\d{2}T\d{6}Z)"),
    re.compile(r"(\d{4}-\d{2}-\d{2}T\d{6}Z)"),
    re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)"),
    re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"),
    re.compile(r"(\d{4}\d{2}\d{2}T\d{2}\d{2}\d{2})"),
]
_RE_HMI_PAT = re.compile(r"(\d{8})_(\d{6})")
_RE_RADIO_PAT_YYYYJJJ = re.compile(r"(\d{7})_(\d{6})_(\d{1,3})")
_RE_RADIO_PAT_YYYYMMDD = re.compile(r"(\d{8})_(\d{6})")
_RE_AIA_NEW_PAT = re.compile(
    r"aia\.lev1_euv_12s\.(\d{4}-\d{2}-\d{2}T\d{6}Z)\.\d+\.image_lev1\.fits"
)
_RE_HMI_NEW_PAT = re.compile(r"hmi\.M_45s\.(\d{8})_(\d{6})_TAI")

# 时间格式常量（按命中频率粗略排序，减少无效尝试次数）
_DATETIME_FMTS = [
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y%m%dT%H%M%SZ",
    "%Y%m%dT%H%M%S",
    "%Y%m%d_%H%M%S",
    "%Y-%m-%dT%H%M%S",
    "%Y-%m-%dT%H%M%S.%f",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H%M%S.%fZ",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H%M%S",
    "%Y-%m-%d %H%M%S.%f",
    "%Y%m%dT%H%M%S.%f",
    "%Y%m%d%H%M%S",
    "%Y%m%d%H%M%S.%f",
    "%d/%m/%YT%H:%M:%S",
    "%d/%m/%YT%H:%M:%S.%f",
    "%d-%b-%YT%H:%M:%S",
    "%d-%b-%YT%H:%M:%S.%f",
    "%Y%j%H%M%S",
    "%Y%j%H%M%S.%f",
]

# ============================================================
# 4. 配置类
# ============================================================


@dataclass
class CanvasStyle:
    """
    画布与坐标轴颜色配置
    --------------------
    修改此处即可一键调整图像整体配色风格，不需要改动绘图逻辑。
    """

    # 背景色
    figure_bg: str = "white"  # 整幅图背景
    axes_bg: str = "black"  # 绘图区背景

    # 坐标轴
    tick_color: str = "black"  # 刻度颜色
    spine_color: str = "white"  # 轴边框颜色
    xlabel_color: str = "black"  # X 轴标签颜色
    ylabel_color: str = "black"  # Y 轴标签颜色
    title_color: str = "black"  # 标题颜色

    # 图例
    legend_face: str = "white"  # 图例背景
    legend_text: str = "black"  # 图例文字颜色
    legend_alpha: float = 0.6  # 图例背景透明度

    # 日面边缘
    limb_color: str = "gray"
    limb_lw: float = 1.0
    limb_alpha: float = 0.6

    # HMI 等值线
    hmi_pos_color: str = "red"  # 正极性等值线
    hmi_neg_color: str = "blue"  # 负极性等值线
    hmi_lw: float = 0.8
    hmi_alpha: float = 0.7


@dataclass
class Config:
    """主要配置参数类"""

    # ── 目录配置 ──────────────────────────────────────────────
    radio_base_dir: str = r"D:\spike_topping_type_III\2025\20250124\RS_0447-0450"
    aia_base_dir: str = r"D:\spike_topping_type_III\2025\20250124\AIA\171\1"
    hmi_base_dir: str = r"D:\spike_topping_type_III\2025\20250124\AIA\hmi\1"
    output_dir: str = (
        r"D:\spike_topping_type_III\2025\20250124\AIA_RS_HMI\RR+LL_peak mode_0.75"
    )

    # ── 文件处理配置 ───────────────────────────────────────────
    save_figure: bool = True
    dpi: int = 300
    aia_file_start_idx: int = 392
    aia_file_end_idx: Optional[int] = 396

    # ── 射电波段配置 ───────────────────────────────────────────
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

    # 偏振模式配置
    # "RR": 仅使用右旋圆偏振数据
    # "LL": 仅使用左旋圆偏振数据
    # "RR+LL": 右旋和左旋数据合并
    polarization_mode: str = "RR+LL"

    # ── 左右旋数据加和配置 ─────────────────────────────────────
    combine_polarizations: bool = True  # 是否启用左右旋数据加和功能
    rr_dir_suffix: str = "RR"  # 右旋数据目录后缀
    ll_dir_suffix: str = "LL"  # 左旋数据目录后缀
    weighted_average: bool = False  # 是否使用加权平均（True）或简单相加（False）
    rr_weight: float = 0.5  # 右旋权重（加权平均时使用）
    ll_weight: float = 0.5  # 左旋权重（加权平均时使用）
    # 同时保存功能暂未实现
    save_individual_pols: bool = False  # 是否同时保存单独的RR、LL图像
    time_tolerance_seconds: float = 0.01  # 时间对齐容差（秒）

    radio_time_threshold: int = 6  # 射电与 AIA 时间匹配阈值（秒）
    max_radio_per_band: int = 28

    # ── 等值线配置 ─────────────────────────────────────────────
    normalization_mode: str = "peak"
    contour_levels_peak: List[float] = field(default_factory=lambda: [0.75])
    rms_sigma_levels: List[float] = field(default_factory=lambda: [20.0])
    rms_box_fraction: float = 0.05
    contour_linewidths: List[float] = field(default_factory=lambda: [2.0])
    contour_alpha: float = 0.90
    contour_smooth_sigma: float = 0

    # ── 显示配置 ───────────────────────────────────────────────
    show_beam: bool = True
    beam_inset_fraction: float = 0.12
    overlay_hmi: bool = True
    hmi_time_threshold: int = 24  # HMI 与 AIA 时间匹配阈值（小时）
    hmi_threshold_gauss: float = 0.0
    hmi_sigma: int = 2
    hmi_levels_gauss: List[float] = field(default_factory=lambda: [100.0])

    # ── AIA 图像配置 ───────────────────────────────────────────
    aia_vmin: float = 16
    aia_vmax: float = 6666
    aia_cmap: str = "sdoaia171"
    roi_bottom_left: List[float] = field(default_factory=lambda: [600, -800])
    roi_top_right: List[float] = field(default_factory=lambda: [1600, 200])

    # ── 画布颜色配置 ───────────────────────────────────────────
    style: CanvasStyle = field(default_factory=CanvasStyle)

    # ── 射电波段颜色配置 ───────────────────────────────────────
    band_colors_dict: dict = field(
        default_factory=lambda: {
            "149.0MHz": ("dodgerblue", "navy"),  # 深蓝系（清晰）
            "164.0MHz": ("orange", "darkorange"),  # 橙色（强对比）
            "190.0MHz": ("crimson", "darkred"),  # 红色（最醒目）
            "205.0MHz": ("mediumorchid", "purple"),  # 紫色（区别红）
            "223.0MHz": ("gold", "goldenrod"),  # 金色（对AIA很好）
            "238.0MHz": ("teal", "darkslategray"),  # 青绿偏暗（避开背景）
        }
    )
    default_colors: List[Tuple] = field(
        default_factory=lambda: [
            ("dodgerblue", "navy"),
            ("orange", "darkorange"),
            ("crimson", "darkred"),
            ("mediumorchid", "purple"),
            ("gold", "goldenrod"),
            ("teal", "darkslategray"),
            ("deeppink", "hotpink"),  # 额外增强区分
            ("royalblue", "midnightblue"),  # 更深蓝备选
        ]
    )

    # ── 性能配置 ───────────────────────────────────────────────
    num_workers: int = 8
    memory_limit_pct: float = 90
    radio_use_float32: bool = True

    # ── 处理选项 ───────────────────────────────────────────────
    apply_background_subtraction: bool = False
    debug_mode: bool = True

    # ── 坐标处理配置 ───────────────────────────────────────────
    coordinate_search_radius: float = 3.0
    quick_test: bool = False
    test_file_limit: int = 5

    # ── 坐标图配置 ─────────────────────────────────────────────
    use_radec_maps: bool = True  # 是否使用赤经赤纬坐标
    radio_to_solar_scale_factor: float = 0.05
    auto_adjust_scale_factor: bool = True
    min_pixels_in_view: int = 100
    max_scale_factor_adjustments: int = 3


# ============================================================
# 5. 工具函数 – 时间处理
# ============================================================


def _parse_flexible_datetime(date_str: str) -> Optional[datetime]:
    """灵活解析各种时间字符串格式，返回 datetime 或 None"""
    date_str = date_str.strip()

    # ── 17 位纯数字格式（YYYYMMDDHHMMSSmmm）─────────────────
    if len(date_str) == 17 and date_str.isdigit():
        try:
            return datetime(
                int(date_str[0:4]),
                int(date_str[4:6]),
                int(date_str[6:8]),
                int(date_str[8:10]),
                int(date_str[10:12]),
                int(date_str[12:14]),
                int(date_str[14:17]) * 1000,
            )
        except Exception:
            pass

    # ── 下划线分隔格式（YYYYJJJ_HHMMSS_SSS 或 YYYYmDD_HHMMSS）──
    if "_" in date_str:
        parts = date_str.split("_")
        if len(parts) >= 2:
            date_part, time_part = parts[0], parts[1]
            if len(date_part) == 7:
                year = int(date_part[:4])
                parsed_date = None
                try:
                    parsed_date = datetime(
                        year, int(date_part[4:5]), int(date_part[5:7])
                    )
                except ValueError:
                    pass
                if parsed_date is None:
                    try:
                        parsed_date = datetime(year, 1, 1) + timedelta(
                            days=int(date_part[4:]) - 1
                        )
                    except Exception:
                        pass
                if parsed_date is not None and len(time_part) == 6:
                    microsecond = 0
                    if len(parts) > 2 and parts[2]:
                        microsecond = int(parts[2].strip().ljust(3, "0")[:3]) * 1000
                    return datetime(
                        parsed_date.year,
                        parsed_date.month,
                        parsed_date.day,
                        int(time_part[0:2]),
                        int(time_part[2:4]),
                        int(time_part[4:6]),
                        microsecond,
                    )

    # ── 规范化小数部分 ────────────────────────────────────────
    if "." in date_str:
        integer_part, decimal_part = date_str.split(".", 1)
        date_str = f"{integer_part}.{decimal_part.ljust(6, '0')[:6]}"

    # ── 逐一尝试标准格式 ──────────────────────────────────────
    for fmt in _DATETIME_FMTS:
        try:
            s = date_str
            if ".%f" in fmt and "." not in s:
                s = s + ".0"
            if "." in s and ".%f" in fmt:
                ip, dp = s.split(".", 1)
                s = f"{ip}.{dp.ljust(6, '0')[:6]}"
            return datetime.strptime(s, fmt)
        except ValueError:
            continue

    # ── 14+ 位纯数字兜底 ──────────────────────────────────────
    if len(date_str) >= 14 and date_str[:14].isdigit():
        try:
            microsecond = 0
            remaining = date_str[14:]
            if remaining.startswith("."):
                microsecond = int(remaining[1:].ljust(6, "0")[:6])
            elif remaining.isdigit():
                if len(remaining) == 3:
                    microsecond = int(remaining) * 1000
                else:
                    microsecond = int(remaining.ljust(6, "0")[:6])
            return datetime(
                int(date_str[0:4]),
                int(date_str[4:6]),
                int(date_str[6:8]),
                int(date_str[8:10]),
                int(date_str[10:12]),
                int(date_str[12:14]),
                microsecond,
            )
        except Exception:
            pass

    return None


def parse_radio_time_from_filename(filename: str) -> Optional[datetime]:
    """从射电文件名提取观测时间"""
    basename = os.path.basename(filename)

    m = _RE_RADIO_PAT_YYYYJJJ.search(basename)
    if m:
        t = _parse_flexible_datetime(f"{m.group(1)}_{m.group(2)}_{m.group(3)}")
        if t:
            return t

    m = _RE_RADIO_PAT_YYYYMMDD.search(basename)
    if m:
        t = _parse_flexible_datetime(f"{m.group(1)}_{m.group(2)}")
        if t:
            return t

    try:
        if os.path.exists(filename):
            date_obs = str(fits.getheader(filename, 0).get("DATE-OBS", "")).strip()
            if date_obs:
                return _parse_flexible_datetime(date_obs)
    except Exception:
        pass

    return None


def parse_aia_time_from_filename(filename: str) -> Optional[datetime]:
    """从 AIA 文件名或头文件提取观测时间"""
    basename = os.path.basename(filename)

    try:
        if os.path.exists(filename):
            date_obs = str(fits.getheader(filename, 0).get("DATE-OBS", "")).strip()
            if date_obs:
                t = _parse_flexible_datetime(date_obs)
                if t:
                    return t
    except Exception:
        pass

    m = _RE_AIA_NEW_PAT.search(basename)
    if m:
        t = _parse_flexible_datetime(m.group(1).rstrip("Z"))
        if t:
            return t

    for pat in _RE_AIA_PATS:
        m = pat.search(basename)
        if m:
            t = _parse_flexible_datetime(m.group(1).rstrip("Z"))
            if t:
                return t

    for digits in re.findall(r"\d{4,}", basename):
        if len(digits) >= 8:
            t = _parse_flexible_datetime(digits)
            if t:
                return t

    return None


def parse_hmi_time_from_filename(filename: str) -> Optional[datetime]:
    """从 HMI 文件名提取观测时间"""
    basename = os.path.basename(filename)

    m = _RE_HMI_NEW_PAT.search(basename)
    if m:
        try:
            return datetime.strptime(f"{m.group(1)}_{m.group(2)}", "%Y%m%d_%H%M%S")
        except ValueError:
            pass

    m = _RE_HMI_PAT.search(basename)
    if m:
        try:
            return datetime.strptime(f"{m.group(1)}_{m.group(2)}", "%Y%m%d_%H%M%S")
        except ValueError:
            pass

    return None


def parse_radio_time_from_header(header: fits.Header) -> Optional[datetime]:
    """从 FITS 头解析射电观测时间"""
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
        if key not in header:
            continue
        date_str = str(header[key]).strip()
        if not date_str:
            continue
        if "  " in date_str:
            date_str = " ".join(date_str.split())
        if " " in date_str:
            parts = date_str.split(" ")
            if len(parts) == 2:
                date_str = f"{parts[0]}.{parts[1].ljust(3, '0')[:3]}"
        t = _parse_flexible_datetime(date_str.rstrip("Z"))
        if t:
            return t
    return None


def _parse_time_from_filename(filename: str) -> Optional[Tuple[str, int]]:
    """
    从文件名中解析时间信息（精确到毫秒），用于时间对齐匹配。

    文件名格式: 149MHz_2025124_043739_681.fits
      - 日期部分:   2025124  (YYYYDDD，7~8位)
      - 时间部分:   043739   (HHMMSS，6位)
      - 毫秒部分:   681      (1~3位，不足3位按实际值处理)

    返回: (date_str, total_ms) 或 None
      - date_str  : 日期字符串，用于跨天判断
      - total_ms  : 当天从0点起的毫秒数，用于数值比较
    """
    # 匹配: _日期(7-8位)_时间(6位)_毫秒(1-3位)
    pattern = r"_(\d{7,8})_(\d{6})_(\d{1,3})"
    match = re.search(pattern, filename)
    if match:
        date_part = match.group(1)  # e.g. "2025124"
        time_part = match.group(2)  # e.g. "043739"
        ms_str = match.group(3)  # e.g. "681"

        hh = int(time_part[0:2])
        mm = int(time_part[2:4])
        ss = int(time_part[4:6])
        # 对齐到毫秒：不足3位的补零到3位再取整数
        ms = int(ms_str.ljust(3, "0"))

        total_ms = (hh * 3600 + mm * 60 + ss) * 1000 + ms
        return (date_part, total_ms)

    # 降级：仅匹配 _日期_时间（无毫秒字段）
    pattern_no_ms = r"_(\d{7,8})_(\d{6})"
    match2 = re.search(pattern_no_ms, filename)
    if match2:
        date_part = match2.group(1)
        time_part = match2.group(2)
        hh = int(time_part[0:2])
        mm = int(time_part[2:4])
        ss = int(time_part[4:6])
        total_ms = (hh * 3600 + mm * 60 + ss) * 1000
        return (date_part, total_ms)

    return None


def _match_rr_ll_by_time(
    rr_files: list, ll_files: list, tolerance_ms: float = 10.0
) -> List[Tuple[str, str]]:
    """
    根据文件名时间戳将RR与LL文件逐一配对（毫秒级精度）。

    算法:
      1. 解析所有LL文件的时间戳，建立 {(date, ms): path} 索引。
      2. 遍历每个RR文件，先精确匹配，再在容差范围内找最近邻。
      3. 返回已匹配的 [(rr_path, ll_path), ...] 列表，并报告未匹配数量。

    Parameters
    ----------
    rr_files      : RR文件路径列表（已排序）
    ll_files      : LL文件路径列表（已排序）
    tolerance_ms  : 时间匹配容差（毫秒），默认10ms

    Returns
    -------
    matched_pairs : list of (rr_path, ll_path)
    """
    # 构建LL时间索引: {(date, total_ms): ll_path}
    ll_index: Dict[Tuple[str, int], str] = {}
    ll_no_parse: List[str] = []
    for ll_path in ll_files:
        parsed = _parse_time_from_filename(os.path.basename(ll_path))
        if parsed is None:
            ll_no_parse.append(ll_path)
        else:
            key = parsed  # (date_str, total_ms)
            if key not in ll_index:
                ll_index[key] = ll_path

    if ll_no_parse:
        warnings.warn(f"有 {len(ll_no_parse)} 个LL文件无法从文件名解析时间，将被跳过。")

    matched_pairs: List[Tuple[str, str]] = []
    unmatched_rr: List[str] = []

    # 将LL索引按日期分组，加速搜索
    from collections import defaultdict

    ll_by_date: Dict[str, List[Tuple[int, str]]] = defaultdict(
        list
    )  # {date_str: [(total_ms, ll_path), ...]}
    for (date_str, total_ms), ll_path in ll_index.items():
        ll_by_date[date_str].append((total_ms, ll_path))
    # 每个日期内按ms排序，以便未来二分查找（当前数据量不大，线性也可）
    for date_str in ll_by_date:
        ll_by_date[date_str].sort(key=lambda x: x[0])

    for rr_path in rr_files:
        parsed = _parse_time_from_filename(os.path.basename(rr_path))
        if parsed is None:
            unmatched_rr.append(rr_path)
            warnings.warn(f"RR文件 {os.path.basename(rr_path)} 无法解析时间，跳过。")
            continue

        rr_date, rr_ms = parsed

        # ① 精确匹配
        if (rr_date, rr_ms) in ll_index:
            matched_pairs.append((rr_path, ll_index[(rr_date, rr_ms)]))
            continue

        # ② 容差范围内最近邻匹配
        candidates = ll_by_date.get(rr_date, [])
        best_ll_path = None
        best_diff = float("inf")
        for ll_ms, ll_path in candidates:
            diff = abs(rr_ms - ll_ms)
            if diff < best_diff:
                best_diff = diff
                best_ll_path = ll_path

        if best_ll_path is not None and best_diff <= tolerance_ms:
            matched_pairs.append((rr_path, best_ll_path))
        else:
            unmatched_rr.append(rr_path)
            if best_diff != float("inf"):
                warnings.warn(
                    f"RR文件 {os.path.basename(rr_path)} 找不到时间匹配的LL文件 "
                    f"(最近差值={best_diff:.1f}ms > 容差={tolerance_ms:.1f}ms)，跳过。"
                )
            else:
                warnings.warn(
                    f"RR文件 {os.path.basename(rr_path)} 在LL目录中找不到同日期文件，跳过。"
                )

    if unmatched_rr:
        print(
            f"  时间匹配结果: 成功 {len(matched_pairs)} 对，"
            f"RR未匹配 {len(unmatched_rr)} 个。"
        )
    else:
        print(f"  时间匹配结果: 全部 {len(matched_pairs)} 对成功匹配。")

    return matched_pairs


def _combine_polarization_data(
    rr_data: np.ndarray, ll_data: np.ndarray, cfg: Config
) -> np.ndarray:
    """组合RR和LL数据（加权平均或简单相加）"""
    if cfg.weighted_average:
        combined_data = rr_data * cfg.rr_weight + ll_data * cfg.ll_weight
    else:
        combined_data = rr_data + ll_data
    return combined_data


# ============================================================
# 6. 工具函数 – 坐标处理
# ============================================================


def get_sun_center_and_radius(header) -> Tuple:
    """从 FITS 头获取太阳中心坐标和可视半径"""
    try:
        crpix1 = header.get("CRPIX1", 0)
        crpix2 = header.get("CRPIX2", 0)
        crval1 = header.get("CRVAL1", 0)
        crval2 = header.get("CRVAL2", 0)
        cdelt1 = header.get("CDELT1", 1)
        cdelt2 = header.get("CDELT2", 1)

        if "RSUN_OBS" in header:
            rsun_obs = header["RSUN_OBS"]
        elif "R_SUN" in header and "CDELT1" in header:
            rsun_obs = abs(header["R_SUN"] * header["CDELT1"])
        else:
            rsun_obs = 960.0

        return crpix1, crpix2, crval1, crval2, cdelt1, cdelt2, rsun_obs
    except Exception as e:
        print(f"获取太阳信息时出错: {e}")
        return 0, 0, 0, 0, 1, 1, 960.0


def calculate_image_extent(data_shape, crpix1, crpix2, crval1, crval2, cdelt1, cdelt2):
    """计算图像完整空间范围（角秒）"""
    nx, ny = data_shape[1], data_shape[0]
    x_min = crval1 + (1 - crpix1) * cdelt1
    x_max = crval1 + (nx - crpix1) * cdelt1
    y_min = crval2 + (1 - crpix2) * cdelt2
    y_max = crval2 + (ny - crpix2) * cdelt2

    x_extent = [x_min, x_max] if cdelt1 > 0 else [x_max, x_min]
    y_extent = [y_min, y_max] if cdelt2 > 0 else [y_max, y_min]
    return x_extent, y_extent


def get_solar_position(obs_time: datetime) -> Tuple[float, float]:
    """计算观测时刻太阳中心在 ICRS 坐标系中的位置（RA, Dec，单位度）"""
    try:
        from astropy.coordinates import get_sun
        from astropy.time import Time

        sun_coord = get_sun(Time(obs_time, format="datetime", scale="utc"))
        return sun_coord.ra.deg, sun_coord.dec.deg
    except Exception as e:
        print(f"    [警告] 使用 astropy 计算太阳位置失败: {e}")
        return 306.413395, -19.231661


# ============================================================
# 7. 工具函数 – 数据读取与处理
# ============================================================

# 坐标文件缓存：key = (search_dir, freq_value, 'ra'/'dec')
_radec_file_cache: Dict[Tuple[str, str, str], Optional[str]] = {}


def _find_radec_file(
    search_dirs: List[str], freq_value: str, kind: str
) -> Optional[str]:
    """
    查找赤经（kind='ra'）或赤纬（kind='dec'）坐标文件，结果缓存避免重复搜索。
    """
    if kind == "ra":
        patterns = [
            f"{freq_value}MHz_RightAscensionDegree.fits",
            f"{freq_value}MHz_RA.fits",
            f"*{freq_value}*RightAscension*.fits",
            f"*{freq_value}*RA*.fits",
        ]
    else:
        patterns = [
            f"{freq_value}MHz_DeclinationDegree.fits",
            f"{freq_value}MHz_Dec.fits",
            f"*{freq_value}*Declination*.fits",
            f"*{freq_value}*Dec*.fits",
        ]

    for sd in search_dirs:
        # 使用绝对路径作为缓存 key，避免相对路径引发的歧义
        abs_sd = os.path.abspath(sd)
        cache_key = (abs_sd, freq_value, kind)

        # ─── 修复核心逻辑 ──────────────────────────────
        if cache_key in _radec_file_cache:
            if _radec_file_cache[cache_key] is not None:
                return _radec_file_cache[cache_key]  # 找到了，直接返回
            else:
                continue  # 缓存显示当前目录没有，继续去下一个目录找！

        if not os.path.isdir(abs_sd):
            _radec_file_cache[cache_key] = None
            continue

        found = None
        for pat in patterns:
            matches = glob.glob(os.path.join(abs_sd, pat))
            if matches:
                found = matches[0]
                break

        _radec_file_cache[cache_key] = found
        if found:
            return found

    return None


def _load_fits_2d(path: str, use_float32: bool) -> Optional[np.ndarray]:
    """读取 FITS 并压缩到 2D，失败返回 None"""
    try:
        with fits.open(path) as hdu:
            data = hdu[0].data
            while data.ndim > 2:
                data = data[0]
            data = np.squeeze(data)
            return data.astype(np.float32 if use_float32 else np.float64)
    except Exception:
        return None


def extract_radio_2d_data(
    fits_path: str,
    use_float32: bool = True,
    cfg: Optional[Config] = None,
) -> Tuple[
    Optional[np.ndarray],
    Optional[np.ndarray],
    Optional[np.ndarray],
    Optional[fits.Header],
    None,
]:
    """
    提取射电强度数据及配套的赤经赤纬坐标图。

    返回
    ----
    (radio_data_2d, ra_map, dec_map, header, None)

    赤经赤纬坐标图（ra_map / dec_map）：
        与 radio_data_2d 像素一一对应的坐标映射图，
        每个像素存储该点天球 ICRS 赤经/赤纬值（度）。
        用于后续精确坐标变换（ICRS → HPC）。
    """
    try:
        with fits.open(fits_path) as hdu:
            data = hdu[0].data
            while data.ndim > 2:
                data = data[0]
            data = np.squeeze(data)
            header = hdu[0].header.copy()

        dtype = np.float32 if use_float32 else np.float64
        data = data.astype(dtype)

        ra_map = dec_map = None

        if cfg is not None and cfg.use_radec_maps:
            base_dir = os.path.dirname(fits_path)
            base_name = os.path.basename(fits_path)

            # 提取频率值
            m = re.search(r"(\d+)MHz", base_name, re.IGNORECASE)
            if not m:
                m = re.search(r"(\d+)MHz", os.path.basename(base_dir), re.IGNORECASE)
            freq_value = m.group(1) if m else None

            if freq_value:
                search_dirs = [
                    base_dir,
                    os.path.dirname(base_dir),
                    os.path.join(os.path.dirname(base_dir), ".."),
                ]
                ra_path = _find_radec_file(search_dirs, freq_value, "ra")
                dec_path = _find_radec_file(search_dirs, freq_value, "dec")

                if ra_path:
                    ra_map = _load_fits_2d(ra_path, use_float32)
                    if cfg.debug_mode and ra_map is not None:
                        print(
                            f"    [坐标图] 已加载 RA 文件: {os.path.basename(ra_path)}"
                        )
                if dec_path:
                    dec_map = _load_fits_2d(dec_path, use_float32)
                    if cfg.debug_mode and dec_map is not None:
                        print(
                            f"    [坐标图] 已加载 Dec 文件: {os.path.basename(dec_path)}"
                        )

                if cfg.debug_mode:
                    if ra_map is not None and dec_map is not None:
                        print("    [坐标图] 成功加载赤经赤纬坐标图")

                        ra_valid = ra_map[np.isfinite(ra_map)]
                        dec_valid = dec_map[np.isfinite(dec_map)]
                        if len(ra_valid) > 0:
                            print("\n" + "=" * 30)
                            print("【坐标原始数值探针 - 诊断用】")
                            print(
                                f"RA 范围:  {np.nanmin(ra_valid):.4f} 至 {np.nanmax(ra_valid):.4f}"
                            )
                            print(
                                f"Dec 范围: {np.nanmin(dec_valid):.4f} 至 {np.nanmax(dec_valid):.4f}"
                            )
                            print(f"检测到为 0 的异常像素数: {np.sum(ra_map == 0)}")
                            print("=" * 30 + "\n")
                    else:
                        print("    [坐标图] 警告: 未找到完整的坐标图文件")

        return data, ra_map, dec_map, header, None

    except Exception as e:
        print(f"读取 FITS 文件失败 {fits_path}: {e}")
        return None, None, None, None, None


def estimate_rms_noise(data: np.ndarray, box_fraction: float = 0.15) -> float:
    """通过图像四角估算背景 RMS 噪声"""
    ny, nx = data.shape
    bx = max(int(nx * box_fraction), 5)
    by = max(int(ny * box_fraction), 5)

    corners = [data[:by, :bx], data[:by, -bx:], data[-by:, :bx], data[-by:, -bx:]]
    pixels = np.concatenate([c.ravel() for c in corners])
    pixels = pixels[np.isfinite(pixels)]

    if len(pixels) < 10:
        edges = np.concatenate(
            [
                data[:by].ravel(),
                data[-by:].ravel(),
                data[:, :bx].ravel(),
                data[:, -bx:].ravel(),
            ]
        )
        pixels = edges[np.isfinite(edges)]

    if len(pixels) == 0:
        val = np.nanstd(data)
        if not np.isfinite(val):
            return 0.0  # ✅ 不要返回 None
        return float(val * 0.1)

    median = np.median(pixels)
    mad = np.median(np.abs(pixels - median))
    std_est = mad * 1.4826
    filtered = pixels[np.abs(pixels - median) < 3 * std_est]
    return float(np.std(filtered)) if len(filtered) > 0 else float(std_est)


def compute_contour_levels(data: np.ndarray, cfg: Config) -> List[float]:
    """根据归一化模式计算等值线级别"""
    finite = data[np.isfinite(data)]
    if len(finite) == 0:
        return []
    peak = float(np.nanmax(finite))

    if cfg.normalization_mode == "rms":
        rms = estimate_rms_noise(data, cfg.rms_box_fraction)
        if rms is None or not np.isfinite(rms) or rms <= 0:
            return []
        levels = [s * rms for s in cfg.rms_sigma_levels if 0 < s * rms < peak]
    else:
        levels = [f * peak for f in cfg.contour_levels_peak]

    return levels


# ============================================================
# 8. 椭圆高斯拟合函数（从 01.py 复制）
# ============================================================


def elliptical_gaussian_2d(xy, A, x0, y0, sigma_x, sigma_y, theta):
    """
    二维椭圆高斯函数
    参数：
        A      : 峰值振幅
        x0, y0 : 中心位置（质心）
        sigma_x, sigma_y : 沿长轴和短轴的 rms 宽度
        theta  : 长轴相对于 x 轴的角度（弧度）
    返回：对应坐标的高斯值
    """
    x, y = xy
    cos_t = np.cos(theta)
    sin_t = np.sin(theta)
    x_rot = (x - x0) * cos_t + (y - y0) * sin_t
    y_rot = -(x - x0) * sin_t + (y - y0) * cos_t
    exponent = (x_rot**2) / (2 * sigma_x**2) + (y_rot**2) / (2 * sigma_y**2)
    return A * np.exp(-exponent)


def fit_elliptical_gaussian(data, x, y, initial_guess=None):
    """
    拟合二维椭圆高斯到图像数据

    输入：
        data : 2D numpy数组，图像强度
        x    : 1D numpy数组，x坐标（长度 = data.shape[1]）
        y    : 1D numpy数组，y坐标（长度 = data.shape[0]）
        initial_guess : 可选，初始参数 (A, x0, y0, sigma_x, sigma_y, theta)

    输出：
        popt : 拟合参数 [A, x0, y0, sigma_x, sigma_y, theta]
        pcov : 协方差矩阵
    """
    X, Y = np.meshgrid(x, y)
    x_flat = X.ravel()
    y_flat = Y.ravel()
    data_flat = data.ravel()

    # 如果没有提供初始猜测，自动估计
    if initial_guess is None:
        max_idx = np.unravel_index(np.argmax(data), data.shape)
        init_x0 = x[max_idx[1]]
        init_y0 = y[max_idx[0]]
        init_A = np.max(data)

        # 粗略估计 sigma（通过半高宽）
        half_max = init_A / 2.0
        # x方向
        row_max = data[max_idx[0], :]
        indices = np.where(row_max >= half_max)[0]
        if len(indices) > 1:
            init_sigma_x = (x[indices[-1]] - x[indices[0]]) / (2.355)  # FWHM -> sigma
        else:
            init_sigma_x = (x[-1] - x[0]) / 10.0
        # y方向
        col_max = data[:, max_idx[1]]
        indices_y = np.where(col_max >= half_max)[0]
        if len(indices_y) > 1:
            init_sigma_y = (y[indices_y[-1]] - y[indices_y[0]]) / (2.355)
        else:
            init_sigma_y = (y[-1] - y[0]) / 10.0
        init_theta = 0.0
        initial_guess = (init_A, init_x0, init_y0, init_sigma_x, init_sigma_y, init_theta)

    # 参数边界
    bounds = ([0, -np.inf, -np.inf, 1e-3, 1e-3, -np.pi/2],
              [np.inf, np.inf, np.inf, np.inf, np.inf, np.pi/2])

    popt, pcov = curve_fit(elliptical_gaussian_2d, (x_flat, y_flat), data_flat,
                           p0=initial_guess, bounds=bounds, maxfev=5000)
    return popt, pcov


# ============================================================
# 9. 主投影函数（基于椭圆高斯拟合）
# ============================================================


def reproject_radio_via_gaussian_fit(
    radio_data: np.ndarray,
    ra_map: Optional[np.ndarray],
    dec_map: Optional[np.ndarray],
    aia_cutout_map: sunpy.map.GenericMap,
    cfg: Config,
    radio_header: Optional[fits.Header] = None,
) -> Optional[np.ndarray]:
    """
    通过二维椭圆高斯拟合将射电源投影到 AIA 图像。
    返回与 AIA 图像尺寸相同的模型图像数组（float32），
    用于后续等值线绘制。
    """
    ny_a, nx_a = aia_cutout_map.data.shape
    ny_r, nx_r = radio_data.shape
    x_pix = np.arange(nx_r, dtype=float)
    y_pix = np.arange(ny_r, dtype=float)

    # ---------- 1. 二维椭圆高斯拟合 ----------
    try:
        popt, _ = fit_elliptical_gaussian(radio_data, x_pix, y_pix)
    except Exception as e:
        if cfg.debug_mode:
            print(f"    [高斯拟合] 失败: {e}")
        return None

    A_fit, x0_pix, y0_pix, sigma_x_pix, sigma_y_pix, theta = popt

    # ---------- 2. 获取质心坐标（RA/Dec 或直接角度） ----------
    use_radec = cfg.use_radec_maps and ra_map is not None and dec_map is not None

    if use_radec:
        # ---- 2a. 使用坐标图 ----
        # 获取质心处 RA/Dec
        interp_ra = RegularGridInterpolator(
            (y_pix, x_pix), ra_map, bounds_error=False, fill_value=np.nan
        )
        interp_dec = RegularGridInterpolator(
            (y_pix, x_pix), dec_map, bounds_error=False, fill_value=np.nan
        )
        ra_center = float(interp_ra((y0_pix, x0_pix)))
        dec_center = float(interp_dec((y0_pix, x0_pix)))
        if np.isnan(ra_center) or np.isnan(dec_center):
            # 降级到最近邻
            iy, ix = int(round(y0_pix)), int(round(x0_pix))
            iy = np.clip(iy, 0, ny_r - 1)
            ix = np.clip(ix, 0, nx_r - 1)
            ra_center = ra_map[iy, ix]
            dec_center = dec_map[iy, ix]
            if np.isnan(ra_center) or np.isnan(dec_center):
                return None

        # 估算原始图像像素角尺度（度/像素）
        if nx_r > 1 and ny_r > 1:
            d_ra_dx = np.nanmedian(np.abs(np.diff(ra_map, axis=1)))   # 度/像素
            d_dec_dy = np.nanmedian(np.abs(np.diff(dec_map, axis=0)))
        else:
            d_ra_dx = 0.001   # 兜底值
            d_dec_dy = 0.001

        arcsec_per_pix_x = d_ra_dx * 3600.0
        arcsec_per_pix_y = d_dec_dy * 3600.0

        # 将 RA/Dec 转换到 AIA HPC 像素
        try:
            coord_icrs = SkyCoord(ra_center * u.deg, dec_center * u.deg, frame='icrs')
            coord_hpc = coord_icrs.transform_to(aia_cutout_map.coordinate_frame)
            px, py = aia_cutout_map.wcs.world_to_pixel(coord_hpc)
            x0_aia = float(px)
            y0_aia = float(py)
        except Exception as e:
            if cfg.debug_mode:
                print(f"    [坐标转换] 失败: {e}")
            return None

    else:
        # ---- 2b. 不使用坐标图，从头文件获取角度信息 ----
        if radio_header is None:
            return None
        try:
            crpix1 = radio_header.get('CRPIX1', 0)
            crpix2 = radio_header.get('CRPIX2', 0)
            crval1 = radio_header.get('CRVAL1', 0)
            crval2 = radio_header.get('CRVAL2', 0)
            cdelt1 = radio_header.get('CDELT1', 1)
            cdelt2 = radio_header.get('CDELT2', 1)
        except:
            return None

        # 质心对应的角度（单位：度，若 CDELT 是度）
        x_angle = crval1 + (x0_pix + 1 - crpix1) * cdelt1
        y_angle = crval2 + (y0_pix + 1 - crpix2) * cdelt2

        arcsec_per_pix_x = abs(cdelt1 * 3600.0) if cdelt1 != 0 else 1.0
        arcsec_per_pix_y = abs(cdelt2 * 3600.0) if cdelt2 != 0 else 1.0

        # 假设 x_angle, y_angle 已经是 HPC 坐标（角秒）
        try:
            coord_hpc = SkyCoord(
                Tx=x_angle * u.arcsec, Ty=y_angle * u.arcsec,
                frame=aia_cutout_map.coordinate_frame
            )
            px, py = aia_cutout_map.wcs.world_to_pixel(coord_hpc)
            x0_aia = float(px)
            y0_aia = float(py)
        except Exception as e:
            if cfg.debug_mode:
                print(f"    [无坐标图坐标转换] 失败: {e}")
            return None

    # ---------- 3. 转换高斯半宽到 AIA 像素 ----------
    aia_scale_x = abs(aia_cutout_map.scale.axis1.to(u.arcsec / u.pix).value)
    aia_scale_y = abs(aia_cutout_map.scale.axis2.to(u.arcsec / u.pix).value)

    sigma_arcsec_x = sigma_x_pix * arcsec_per_pix_x
    sigma_arcsec_y = sigma_y_pix * arcsec_per_pix_y

    sigma_aia_x = sigma_arcsec_x / aia_scale_x
    sigma_aia_y = sigma_arcsec_y / aia_scale_y
    theta_aia = theta   # 方向角保持不变（可调）

    # ---------- 4. 生成 AIA 尺寸的高斯模型图像 ----------
    Y_aia, X_aia = np.mgrid[0:ny_a, 0:nx_a]
    model = elliptical_gaussian_2d(
        (X_aia, Y_aia),
        A_fit, x0_aia, y0_aia,
        sigma_aia_x, sigma_aia_y, theta_aia
    )
    model = np.maximum(model, 0)       # 确保非负
    return model.astype(np.float32)


# ============================================================
# 10. 工具函数 – 绘图辅助
# ============================================================


def smooth_for_contour(data: np.ndarray, sigma: float) -> np.ndarray:
    """对等值线数据做加权高斯平滑（保留 NaN 边界）"""
    if sigma <= 0:
        return data
    nan_mask = np.isnan(data)
    filled = np.where(nan_mask, 0.0, data)
    weights = (~nan_mask).astype(np.float64)
    sm_d = gaussian_filter(filled, sigma=sigma)
    sm_w = gaussian_filter(weights, sigma=sigma)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(sm_w > 1e-6, sm_d / sm_w, np.nan)


def _get_padded_aia_map(
    aia_map: sunpy.map.GenericMap, cfg: Config
) -> sunpy.map.GenericMap:
    """
    若 ROI 超出原图视场，先扩充画布再裁剪，
    避免射电数据在图像边缘被截断。
    """
    bl = SkyCoord(
        cfg.roi_bottom_left[0] * u.arcsec,
        cfg.roi_bottom_left[1] * u.arcsec,
        frame=aia_map.coordinate_frame,
    )
    tr = SkyCoord(
        cfg.roi_top_right[0] * u.arcsec,
        cfg.roi_top_right[1] * u.arcsec,
        frame=aia_map.coordinate_frame,
    )

    px_bl = aia_map.wcs.world_to_pixel(bl)
    px_tr = aia_map.wcs.world_to_pixel(tr)
    x0, y0 = int(np.floor(float(px_bl[0]))), int(np.floor(float(px_bl[1])))
    x1, y1 = int(np.ceil(float(px_tr[0]))), int(np.ceil(float(px_tr[1])))

    # 确保裁剪区域在图像范围内
    ny, nx = aia_map.data.shape
    x0 = max(0, x0)
    y0 = max(0, y0)
    x1 = min(nx, x1)
    y1 = min(ny, y1)

    # 如果裁剪区域完全在图像内，直接裁剪
    if x0 >= 0 and y0 >= 0 and x1 <= nx and y1 <= ny:
        submap = aia_map.submap(
            bl,
            top_right=tr,
        )
        return submap

    # 否则需要扩充画布
    # 计算需要扩充的像素数
    pad_left = max(0, -x0)
    pad_right = max(0, x1 - nx)
    pad_bottom = max(0, -y0)
    pad_top = max(0, y1 - ny)

    # 使用 NaN 填充
    data = aia_map.data
    padded_data = np.pad(
        data,
        ((pad_bottom, pad_top), (pad_left, pad_right)),
        mode='constant',
        constant_values=np.nan,
    )

    # 更新 WCS
    wcs = aia_map.wcs
    wcs.wcs.crpix[0] += pad_left
    wcs.wcs.crpix[1] += pad_bottom

    # 创建新的 map
    from sunpy.map import Map
    padded_map = Map(padded_data, wcs)

    # 裁剪到 ROI
    submap = padded_map.submap(
        bl,
        top_right=tr,
    )
    return submap
