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
是精确坐标转换（ICRS → 日面 HPC）的核心依据，使射电等值线能正确叠加到太阳图像上。
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
    radio_base_dir: str = r"<PROJECT_ROOT>\2025\20250124\RS_0447-0450"
    aia_base_dir: str = r"<PROJECT_ROOT>\2025\20250124\AIA\171\1"
    hmi_base_dir: str = r"<PROJECT_ROOT>\2025\20250124\AIA\hmi\1"
    output_dir: str = (
        r"<PROJECT_ROOT>\2025\20250124\AIA_RS_HMI\RR+LL_rms mode_5"
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
    normalization_mode: str = "rms"
    contour_levels_peak: List[float] = field(default_factory=lambda: [0.90])
    rms_sigma_levels: List[float] = field(default_factory=lambda: [5.0])
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


def _preprocess_radec_maps(
    ra_map: np.ndarray,
    dec_map: np.ndarray,
    radio_header: Optional[fits.Header],
    cfg: Config,
) -> Tuple[np.ndarray, np.ndarray, bool]:
    """
    修正版坐标预处理：精准保留太阳半径偏移，并过滤背景填充值
    """
    if not cfg.use_radec_maps:
        return ra_map, dec_map, True

    ra = ra_map.copy().astype(np.float64)
    dec = dec_map.copy().astype(np.float64)

    # 【修复 1】：精准击杀背景幽灵！
    # 探针检测到背景填充区使用了精确的 0.0，把它们设为 NaN，防止堆积在日心
    invalid_mask = (ra == 0.0) & (dec == 0.0)
    ra[invalid_mask] = np.nan
    dec[invalid_mask] = np.nan

    # （彻底删除了原有的 np.mod 取模逻辑，防止坐标系左半边被撕裂）

    return ra, dec, False


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
# 8. 工具函数 – 重投影
# ============================================================


def reproject_radio_simple_scale(
    radio_data: np.ndarray,
    radio_header: fits.Header,
    aia_cutout_map,
    cfg: Config,
) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """
    简化投影法（无坐标图时的后备方案）：
    按太阳半径比例缩放射电图像，插值到 AIA 网格。
    """
    try:
        (
            radio_crpix1,
            radio_crpix2,
            radio_crval1,
            radio_crval2,
            radio_cdelt1,
            radio_cdelt2,
            radio_rsun,
        ) = get_sun_center_and_radius(radio_header)

        (
            aia_crpix1,
            aia_crpix2,
            aia_crval1,
            aia_crval2,
            aia_cdelt1,
            aia_cdelt2,
            aia_rsun,
        ) = get_sun_center_and_radius(aia_cutout_map.meta)

        if cfg.debug_mode:
            print(
                f'    [简单投影] AIA 太阳半径: {aia_rsun:.1f}"  射电太阳半径: {radio_rsun:.1f}"'
            )

        scale = aia_rsun / radio_rsun

        radio_x_ext, radio_y_ext = calculate_image_extent(
            radio_data.shape,
            radio_crpix1,
            radio_crpix2,
            radio_crval1,
            radio_crval2,
            radio_cdelt1,
            radio_cdelt2,
        )

        cx, cy = radio_crval1, radio_crval2
        sx_min = cx + (radio_x_ext[0] - cx) * scale
        sx_max = cx + (radio_x_ext[1] - cx) * scale
        sy_min = cy + (radio_y_ext[0] - cy) * scale
        sy_max = cy + (radio_y_ext[1] - cy) * scale
        scaled_ext = [
            min(sx_min, sx_max),
            max(sx_min, sx_max),
            min(sy_min, sy_max),
            max(sy_min, sy_max),
        ]

        ny, nx = radio_data.shape
        x_radio = np.linspace(scaled_ext[0], scaled_ext[1], nx)
        y_radio = np.linspace(scaled_ext[2], scaled_ext[3], ny)

        interpolator = RegularGridInterpolator(
            (y_radio, x_radio),
            np.nan_to_num(radio_data, nan=0.0),
            method="linear",
            bounds_error=False,
            fill_value=0.0,
        )

        aia_x_ext, aia_y_ext = calculate_image_extent(
            aia_cutout_map.data.shape,
            aia_crpix1,
            aia_crpix2,
            aia_crval1,
            aia_crval2,
            aia_cdelt1,
            aia_cdelt2,
        )
        aia_ext = [
            min(aia_x_ext[0], aia_x_ext[1]),
            max(aia_x_ext[0], aia_x_ext[1]),
            min(aia_y_ext[0], aia_y_ext[1]),
            max(aia_y_ext[0], aia_y_ext[1]),
        ]

        ny_a, nx_a = aia_cutout_map.data.shape
        x_aia = np.linspace(aia_ext[0], aia_ext[1], nx_a)
        y_aia = np.linspace(aia_ext[2], aia_ext[3], ny_a)
        X_aia, Y_aia = np.meshgrid(x_aia, y_aia)

        reprojected = interpolator(
            np.column_stack([Y_aia.ravel(), X_aia.ravel()])
        ).reshape(ny_a, nx_a)

        if cfg.debug_mode:
            print(
                f"    [简单投影] 有效像素: {np.sum(~np.isnan(reprojected))}/{ny_a*nx_a}"
            )

        return reprojected, X_aia, Y_aia

    except Exception as e:
        if cfg.debug_mode:
            print(f"    [简单投影] 异常: {e}")
        return None


def reproject_radio_forward_paste(
    radio_data: np.ndarray,
    ra_map: np.ndarray,
    dec_map: np.ndarray,
    aia_cutout_map,
    cfg: Config,
    radio_header: Optional[fits.Header] = None,
) -> Optional[np.ndarray]:
    """前向投影贴图法（终极真理版：正确比例 + 动态网格桥接）"""
    if ra_map is None or dec_map is None:
        return None

    ra_abs, dec_abs, _ = _preprocess_radec_maps(ra_map, dec_map, radio_header, cfg)

    # ── 1. 有效点严格筛选 ─────────────────────────────────────────
    valid_mask = np.isfinite(ra_abs) & np.isfinite(dec_abs) & np.isfinite(radio_data)

    n_valid = int(np.sum(valid_mask))
    if n_valid < 9:
        return None

    ra_valid = ra_abs[valid_mask]
    dec_valid = dec_abs[valid_mask]
    v_vals_fin = radio_data[valid_mask].astype(np.float64)

    # ── 2. 坐标转换 (Degree → Arcsec) ──────────────
    try:
        import astropy.units as u
        from astropy.coordinates import SkyCoord

        # 真实单位是度 (Degree)，必须乘 3600 才能归位到太阳边缘
        tx_arcsec = ra_valid * 3600.0
        ty_arcsec = dec_valid * 3600.0

        radio_hpc = SkyCoord(
            Tx=tx_arcsec * u.arcsec,
            Ty=ty_arcsec * u.arcsec,
            frame=aia_cutout_map.coordinate_frame,
        )

        px_f, py_f = aia_cutout_map.wcs.world_to_pixel(radio_hpc)

    except Exception as e:
        if cfg.debug_mode:
            print(f"    [警告] 坐标映射失败: {e}")
        return None

    # ── 3. 映射并散射到输出网格 ───────────────────────────────────
    px_f = np.asarray(px_f, dtype=np.float64)
    py_f = np.asarray(py_f, dtype=np.float64)

    fin_pix = np.isfinite(px_f) & np.isfinite(py_f)
    px_i = np.round(px_f[fin_pix]).astype(int)
    py_i = np.round(py_f[fin_pix]).astype(int)
    v_vals_mapped = v_vals_fin[fin_pix]

    ny_a, nx_a = aia_cutout_map.data.shape
    in_bounds = (px_i >= 0) & (px_i < nx_a) & (py_i >= 0) & (py_i < ny_a)

    if not np.any(in_bounds):
        return None

    acc = np.full((ny_a, nx_a), -np.inf, dtype=np.float64)
    np.maximum.at(acc, (py_i[in_bounds], px_i[in_bounds]), v_vals_mapped[in_bounds])
    output = np.where(acc > -np.inf, acc, np.nan).astype(np.float32)

    # ── 4. 间隙填充（动态高斯扩散 - 解决钉板消失效应）─────────────
    nan_mask = np.isnan(output)
    if nan_mask.any():
        try:
            # 估算射电图原有的像素度数分辨率
            deg_per_pix = np.sqrt(
                (np.nanmax(ra_valid) - np.nanmin(ra_valid))
                * (np.nanmax(dec_valid) - np.nanmin(dec_valid))
                / n_valid
            )
            # 转换为 AIA 像素间距
            aia_scale = abs(aia_cutout_map.scale.axis1.value)
            gap_pixels = (deg_per_pix * 3600.0) / aia_scale
            # 动态调整 Sigma：保证平滑半径足够大以桥接拉伸后的缝隙
            dynamic_sigma = float(max(15.0, gap_pixels * 0.6))
        except Exception:
            dynamic_sigma = 50.0  # 兜底值

        if cfg.debug_mode:
            print(f"    [投影] 动态平滑 Sigma: {dynamic_sigma:.1f}")

        filled = np.where(nan_mask, 0.0, output)
        weights = (~nan_mask).astype(np.float64)

        from scipy.ndimage import gaussian_filter

        sm_d = gaussian_filter(filled.astype(np.float64), sigma=dynamic_sigma)
        sm_w = gaussian_filter(weights, sigma=dynamic_sigma)

        with np.errstate(invalid="ignore", divide="ignore"):
            diffused = np.where(sm_w > 1e-6, sm_d / sm_w, np.nan)
        output = np.where(nan_mask, diffused.astype(np.float32), output)

    return output


def parse_freq(band_str):
    return float(band_str.replace("MHz", ""))


def freq_to_height(freq_mhz):
    """
    针对你 150–324 MHz 优化
    """
    return 1.05 + (300 / freq_mhz) ** 0.5 * 0.08


def reproject_radio_with_height(
    radio_data,
    ra_map,
    dec_map,
    aia_map,
    cfg,
    height_rsun=1.1,
):
    mask = np.isfinite(ra_map) & np.isfinite(dec_map) & np.isfinite(radio_data)
    if np.sum(mask) < 10:
        return None

    x = ra_map[mask]
    y = dec_map[mask]
    vals = radio_data[mask]

    # 🔑 关键：Rsun → arcsec
    rsun_arcsec = aia_map.meta.get("RSUN_OBS", 960.0)

    Tx = x * rsun_arcsec * u.arcsec
    Ty = y * rsun_arcsec * u.arcsec

    # 🌟 加入高度（核心升级）
    distance = height_rsun * R_sun

    hpc_3d = SkyCoord(
        Tx=Tx,
        Ty=Ty,
        distance=distance,
        frame=frames.Helioprojective,
        observer=aia_map.observer_coordinate,
        obstime=aia_map.date,
    )

    px, py = aia_map.wcs.world_to_pixel(hpc_3d)

    out = np.full(aia_map.data.shape, np.nan, dtype=np.float32)

    px = np.round(px).astype(int)
    py = np.round(py).astype(int)

    valid = (px >= 0) & (px < out.shape[1]) & (py >= 0) & (py < out.shape[0])

    np.maximum.at(out, (py[valid], px[valid]), vals[valid])

    return out


def reproject_radio_auto_height(
    radio_data,
    ra_map,
    dec_map,
    aia_map,
    freq_mhz,
    cfg,
):
    height = freq_to_height(freq_mhz)

    if cfg.debug_mode:
        print(f"{freq_mhz} MHz → {height:.3f} Rsun")

    return reproject_radio_with_height(
        radio_data, ra_map, dec_map, aia_map, cfg, height_rsun=height
    )


def reproject_radio_to_aia(
    radio_data,
    radio_header,
    ra_map,
    dec_map,
    aia_cutout_map,
    cfg,
):
    # 🎯 模式1：使用 RA/Dec（高精度）
    if cfg.use_radec_maps and ra_map is not None and dec_map is not None:
        return reproject_radio_forward_paste(
            radio_data, ra_map, dec_map, aia_cutout_map, cfg, radio_header
        )

    # 🎯 模式2：简单投影（fallback）
    if cfg.debug_mode:
        print("    使用简单投影模式")

    result = reproject_radio_simple_scale(radio_data, radio_header, aia_cutout_map, cfg)

    if result is None:
        return None

    reprojected, _, _ = result
    return reprojected


# ============================================================
# 9. 工具函数 – 绘图辅助
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
    if x0 > x1:
        x0, x1 = x1, x0
    if y0 > y1:
        y0, y1 = y1, y0

    ny, nx = aia_map.data.shape
    min_x, min_y = min(0, x0), min(0, y0)
    max_x, max_y = max(nx, x1), max(ny, y1)

    # ROI 完全在原图内，直接裁剪
    if min_x == 0 and min_y == 0 and max_x == nx and max_y == ny:
        return aia_map.submap(bl, top_right=tr)

    # 创建扩充画布并嵌入原图
    new_data = np.full((max_y - min_y, max_x - min_x), np.nan, dtype=aia_map.data.dtype)
    ox, oy = -min_x, -min_y
    new_data[oy : oy + ny, ox : ox + nx] = aia_map.data

    new_meta = aia_map.meta.copy()
    new_meta["CRPIX1"] += ox
    new_meta["CRPIX2"] += oy
    new_meta["NAXIS1"] = max_x - min_x
    new_meta["NAXIS2"] = max_y - min_y

    return sunpy.map.Map(new_data, new_meta).submap(bl, top_right=tr)


def get_beam_params_from_header(header: fits.Header) -> Optional[Dict]:
    """从 FITS 头提取综合波束椭圆参数（BMAJ/BMIN/BPA）"""
    bmaj = header.get("BMAJ", None)
    bmin = header.get("BMIN", None)
    if bmaj is None or bmin is None:
        return None
    return {
        "bmaj_arcsec": float(bmaj) * 3600.0,
        "bmin_arcsec": float(bmin) * 3600.0,
        "bpa_deg": float(header.get("BPA", 0.0)),
    }


def draw_beam_ellipse_pixel(
    ax, beam: Dict, aia_cutout_map: sunpy.map.GenericMap, color: str = "white"
):
    """在图像左下角绘制综合波束椭圆"""
    cdelt = abs(aia_cutout_map.scale.axis1.to(u.arcsec / u.pix).value)
    bmaj_px = beam["bmaj_arcsec"] / cdelt
    bmin_px = beam["bmin_arcsec"] / cdelt
    ny, nx = aia_cutout_map.data.shape
    cx_px, cy_px = nx * 0.08, ny * 0.08

    ax.add_patch(
        Ellipse(
            xy=(cx_px, cy_px),
            width=bmin_px,
            height=bmaj_px,
            angle=beam["bpa_deg"],
            linewidth=1.5,
            edgecolor=color,
            facecolor="none",
            alpha=0.85,
        )
    )
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


def _build_band_color_cache(cfg: Config) -> List[Tuple[float, Tuple]]:
    """构建波段频率→颜色的查找缓存"""
    return [
        (float(_RE_MHZ.search(k).group(1)), v)
        for k, v in cfg.band_colors_dict.items()
        if _RE_MHZ.search(k)
    ]


def get_band_color(
    band_label: str, band_idx: int, cfg: Config, color_cache: Optional[List] = None
) -> Tuple[str, str]:
    """根据波段标签返回（主色，暗色）颜色对"""
    m = _RE_MHZ.search(band_label)
    if m and color_cache is not None:
        mhz = float(m.group(1))
        for key_mhz, val in color_cache:
            if abs(key_mhz - mhz) < 0.5:
                return val
    return cfg.default_colors[band_idx % len(cfg.default_colors)]


def process_hmi_for_overlay(
    hmi_file: str, target_wcs, cfg: Config
) -> Optional[sunpy.map.GenericMap]:
    """重投影 HMI 磁图到 AIA WCS，并做高斯平滑和阈值处理"""
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
# 10. 工具函数 – 系统辅助
# ============================================================


def check_memory_usage(limit: float = 90.0):
    """若内存超限则强制 GC 并等待恢复"""
    mem = psutil.virtual_memory().percent
    if mem >= limit:
        print(f"\n[警告] 内存占用 {mem:.0f}% ≥ {limit:.0f}%，正在清理...")
        while psutil.virtual_memory().percent >= limit:
            gc.collect()
            time.sleep(1.0)
        print(f"[恢复] 内存占用降至 {psutil.virtual_memory().percent:.0f}%")


@lru_cache(maxsize=16)
def _make_gaussian_kernel(sigma: float) -> Gaussian2DKernel:
    """缓存 Gaussian2DKernel，避免重复构建"""
    return Gaussian2DKernel(x_stddev=sigma)


def _worker_init():
    """子进程初始化（确保使用非交互后端）"""
    matplotlib.use("Agg")
    warnings.filterwarnings("ignore")


# ============================================================
# 11. 核心处理函数
# ============================================================


def _read_one_radio_header(
    rf: str, selected_bands: Tuple[str, ...], pol: str, cfg: Config
) -> Optional[Dict]:
    """（线程安全）读取单个射电文件的波段/时间信息"""
    # 检查是否包含任何波段信息
    band_found = next((b for b in selected_bands if b in rf), None)
    if not band_found:
        return None

    try:
        r_time = parse_radio_time_from_filename(rf)
        if r_time:
            return {"path": rf, "band": band_found, "pol": pol, "time": r_time}

        hdr = fits.getheader(rf)
        r_time = parse_radio_time_from_header(hdr)
        if r_time:
            return {"path": rf, "band": band_found, "pol": pol, "time": r_time}

        if cfg.debug_mode:
            print(f"    警告: 无法解析射电文件时间: {os.path.basename(rf)}")

    except Exception as e:
        if cfg.debug_mode:
            print(
                f"    读取射电文件头出错: {os.path.basename(rf)}, 错误: {str(e)[:100]}"
            )

    return None


def build_matched_pairs(cfg: Config) -> List[Tuple[str, Optional[str], List]]:
    """扫描目录，构建 (AIA文件, HMI文件, 切片任务列表) 三元组列表"""
    print("=" * 60)
    print("正在扫描并进行横向切片匹配，请稍候...")

    aia_files = sorted(glob.glob(os.path.join(cfg.aia_base_dir, "*.fits")))
    hmi_files = sorted(glob.glob(os.path.join(cfg.hmi_base_dir, "*.fits")))

    if not aia_files:
        print("[错误] 找不到 AIA 文件，请检查 cfg.aia_base_dir")
        return []

    if cfg.quick_test:
        print("[快速测试模式] 只处理前几个文件")
        aia_files = aia_files[: min(5, len(aia_files))]

    # 解析 HMI 时间
    hmi_times = [
        (hf, t)
        for hf in hmi_files
        for t in [parse_hmi_time_from_filename(os.path.basename(hf))]
        if t
    ]

    # 收集射电文件（排除坐标图文件）
    pol = cfg.polarization_mode

    # 检查是否启用左右旋合并
    if cfg.combine_polarizations and pol == "RR+LL":
        print(f"启用左右旋数据合并模式: {cfg.rr_dir_suffix} + {cfg.ll_dir_suffix}")

        # 分别收集RR和LL文件
        rr_files = set()
        ll_files = set()

        # 收集RR文件
        rr_raw = set(
            glob.glob(
                os.path.join(cfg.radio_base_dir, "**", cfg.rr_dir_suffix, "*.fits"),
                recursive=True,
            )
            + glob.glob(
                os.path.join(cfg.radio_base_dir, "**", f"*{cfg.rr_dir_suffix}*.fits"),
                recursive=True,
            )
        )
        rr_files = [
            f
            for f in rr_raw
            if "_RightAscensionDegree.fits" not in f
            and "_DeclinationDegree.fits" not in f
        ]

        # 收集LL文件
        ll_raw = set(
            glob.glob(
                os.path.join(cfg.radio_base_dir, "**", cfg.ll_dir_suffix, "*.fits"),
                recursive=True,
            )
            + glob.glob(
                os.path.join(cfg.radio_base_dir, "**", f"*{cfg.ll_dir_suffix}*.fits"),
                recursive=True,
            )
        )
        ll_files = [
            f
            for f in ll_raw
            if "_RightAscensionDegree.fits" not in f
            and "_DeclinationDegree.fits" not in f
        ]

        if cfg.quick_test:
            rr_files = rr_files[: min(10, len(rr_files))]
            ll_files = ll_files[: min(10, len(ll_files))]

        print(
            f"成功锁定 {len(rr_files)} 个 {cfg.rr_dir_suffix} 和 {len(ll_files)} 个 {cfg.ll_dir_suffix} 射电数据文件。"
        )

        # 按波段和文件名匹配RR和LL文件
        print("正在匹配RR和LL文件...")
        matched_pairs_by_band = {}

        # 按波段分组
        for band in cfg.selected_bands:
            # 获取该波段的RR和LL文件
            band_rr_files = [f for f in rr_files if band in f]
            band_ll_files = [f for f in ll_files if band in f]

            if not band_rr_files or not band_ll_files:
                print(f"  波段 {band}: 缺少RR或LL文件，跳过")
                continue

            # 按时间匹配
            tolerance_ms = cfg.time_tolerance_seconds * 1000
            band_matched_pairs = _match_rr_ll_by_time(
                band_rr_files, band_ll_files, tolerance_ms
            )

            if band_matched_pairs:
                matched_pairs_by_band[band] = band_matched_pairs
                print(f"  波段 {band}: 成功匹配 {len(band_matched_pairs)} 对文件")
            else:
                print(f"  波段 {band}: 无法匹配RR和LL文件")

        # 将匹配对转换为文件列表，供后续处理
        radio_cache = []
        for band, pairs in matched_pairs_by_band.items():
            for rr_path, ll_path in pairs:
                # 使用RR文件的时间作为参考时间
                try:
                    r_time = parse_radio_time_from_filename(rr_path)
                    if not r_time:
                        hdr = fits.getheader(rr_path)
                        r_time = parse_radio_time_from_header(hdr)

                    if r_time:
                        # 存储为元组，表示这是一对文件
                        radio_cache.append(
                            {
                                "path": (rr_path, ll_path),  # 存储为元组
                                "band": band,
                                "pol": "RR+LL",
                                "time": r_time,
                            }
                        )
                except Exception as e:
                    if cfg.debug_mode:
                        print(
                            f"    读取射电文件头出错: {os.path.basename(rr_path)}, 错误: {str(e)[:100]}"
                        )

        print(f"  读取完毕，有效射电观测记录（RR+LL对）: {len(radio_cache)} 条")

    else:
        # 原模式：仅收集指定偏振的文件
        radio_raw = set(
            glob.glob(
                os.path.join(cfg.radio_base_dir, "**", pol, "*.fits"), recursive=True
            )
            + glob.glob(
                os.path.join(cfg.radio_base_dir, "**", f"*{pol}*.fits"), recursive=True
            )
        )
        radio_files = [
            f
            for f in radio_raw
            if "_RightAscensionDegree.fits" not in f
            and "_DeclinationDegree.fits" not in f
        ]
        if cfg.quick_test:
            radio_files = radio_files[: min(10, len(radio_files))]

        print(
            f"成功锁定 {len(radio_files)} 个 {pol} 射电数据文件。正在并发提取观测时间..."
        )

        # 并发读取头文件
        max_threads = min(32, (os.cpu_count() or 4) * 2, max(1, len(radio_files)))
        _read_fn = partial(
            _read_one_radio_header,
            selected_bands=tuple(cfg.selected_bands),
            pol=pol,
            cfg=cfg,
        )
        with ThreadPoolExecutor(max_workers=max_threads) as ex:
            radio_cache = [r for r in ex.map(_read_fn, radio_files) if r is not None]

        print(f"  读取完毕，有效射电观测记录: {len(radio_cache)} 条")

    start_idx = cfg.aia_file_start_idx if cfg.aia_file_start_idx is not None else 0
    end_idx = (
        cfg.aia_file_end_idx if cfg.aia_file_end_idx is not None else len(aia_files)
    )
    hmi_thresh_sec = cfg.hmi_time_threshold * 3600
    grouped_tasks = []
    stats = {"processed": 0, "matched": 0, "slices": 0}

    for aia_file in aia_files[start_idx:end_idx]:
        stats["processed"] += 1
        aia_time = parse_aia_time_from_filename(os.path.basename(aia_file))
        if not aia_time:
            print(f"  警告: 无法解析 AIA 文件时间: {os.path.basename(aia_file)}")
            continue

        # 寻找最近 HMI 文件
        best_hmi = None
        if hmi_times:
            valid_hmi = [
                x
                for x in hmi_times
                if abs((x[1] - aia_time).total_seconds()) <= hmi_thresh_sec
            ]
            if valid_hmi:
                best_hmi = min(
                    valid_hmi, key=lambda x: abs((x[1] - aia_time).total_seconds())
                )[0]

        # 按波段分组时间窗内的射电文件
        band_groups: Dict[str, list] = {}
        for rc in radio_cache:
            dt = abs((rc["time"] - aia_time).total_seconds())
            if dt <= cfg.radio_time_threshold:
                band_groups.setdefault(rc["band"], []).append(
                    (rc["path"], rc["pol"], rc["time"], dt)
                )

        if not band_groups:
            if cfg.debug_mode:
                print(f"  AIA {aia_time}: 无射电数据匹配")
            continue

        stats["matched"] += 1

        # 每波段按时间差排序并截断
        for band in band_groups:
            band_groups[band].sort(key=lambda x: x[2])
            band_groups[band] = band_groups[band][: cfg.max_radio_per_band]

        # 构建横向切片任务
        min_count = min(len(v) for v in band_groups.values())
        if min_count == 0:
            continue

        tasks_for_aia = []
        for idx in range(min_count):
            slc = {
                band: [band_groups[band][idx][:3]]
                for band in band_groups
                if idx < len(band_groups[band])
            }
            if slc:
                tasks_for_aia.append((idx, slc))
                stats["slices"] += 1

        if tasks_for_aia:
            grouped_tasks.append((aia_file, best_hmi, tasks_for_aia))

    print(f"\n匹配结果统计:")
    print(f"  处理的 AIA 文件 : {stats['processed']}")
    print(f"  成功匹配的 AIA  : {stats['matched']}")
    print(f"  创建的切片总数  : {stats['slices']}")
    print(f"  任务组总数      : {len(grouped_tasks)}")
    print("=" * 60)
    return grouped_tasks


def process_aia_group(
    aia_file: str,
    hmi_file: Optional[str],
    sub_tasks: List[Tuple[int, Dict]],
    task_index: int,
    total_tasks: int,
    cfg: Config,
    color_cache: List,
):
    """处理单个 AIA 文件组，逐切片绘图并保存"""
    check_memory_usage(limit=cfg.memory_limit_pct)
    print(f"\n[{task_index}/{total_tasks}] 加载 AIA: {os.path.basename(aia_file)}")

    sty = cfg.style  # 画布颜色快捷引用
    selected_bands_idx = {b: i for i, b in enumerate(cfg.selected_bands)}
    aia_cmap_name = cfg.aia_cmap if cfg.aia_cmap in plt.colormaps() else "hot"

    # 预先构建等值线线宽列表（避免在循环内重复创建）
    _max_lev = max(len(cfg.rms_sigma_levels), len(cfg.contour_levels_peak), 1)
    _lw_lut = [
        cfg.contour_linewidths[min(i, len(cfg.contour_linewidths) - 1)]
        for i in range(_max_lev)
    ]

    aia_map = cutout_aia = hmi_processed = None

    try:
        aia_map = sunpy.map.Map(aia_file)
        cutout_aia = _get_padded_aia_map(aia_map, cfg)
        hmi_processed = (
            process_hmi_for_overlay(hmi_file, cutout_aia.wcs, cfg)
            if cfg.overlay_hmi and hmi_file
            else None
        )

        # 输出目录只需创建一次
        if cfg.save_figure:
            os.makedirs(cfg.output_dir, exist_ok=True)

        for sub_index, single_slice_bands in sub_tasks:
            check_memory_usage(limit=cfg.memory_limit_pct)
            print(f"  -> 绘制序列帧 {sub_index + 1}/{len(sub_tasks)}")

            fig = plt.figure(figsize=(12, 10))
            ax = fig.add_subplot(111, projection=cutout_aia.wcs)

            # ── AIA 底图 ──────────────────────────────────────
            cutout_aia.plot(
                axes=ax,
                norm=mcolors.LogNorm(vmin=cfg.aia_vmin, vmax=cfg.aia_vmax),
                cmap=aia_cmap_name,
                title=False,
            )
            ax.coords.grid(False)
            ax.autoscale(False)
            ax.set_xlim(0, cutout_aia.data.shape[1] - 1)
            ax.set_ylim(0, cutout_aia.data.shape[0] - 1)

            legend_handles = []
            first_radio_time = None
            collected_beams: Dict[str, Dict] = {}

            # ── HMI 磁场等值线 ────────────────────────────────
            if hmi_processed is not None:
                max_hmi = float(np.nanmax(hmi_processed.data))
                min_hmi = float(np.nanmin(hmi_processed.data))

                pos_levels = [lv for lv in cfg.hmi_levels_gauss if lv < max_hmi]
                neg_levels = [-lv for lv in cfg.hmi_levels_gauss if -lv > min_hmi]

                if pos_levels:
                    ax.contour(
                        hmi_processed.data,
                        levels=pos_levels,
                        colors=[sty.hmi_pos_color],
                        linewidths=sty.hmi_lw,
                        alpha=sty.hmi_alpha,
                    )
                if neg_levels:
                    ax.contour(
                        hmi_processed.data,
                        levels=neg_levels,
                        colors=[sty.hmi_neg_color],
                        linewidths=sty.hmi_lw,
                        alpha=sty.hmi_alpha,
                    )

                # 仅当真正画了线才添加图例
                if pos_levels:
                    legend_handles.append(
                        Line2D(
                            [0],
                            [0],
                            color=sty.hmi_pos_color,
                            lw=sty.hmi_lw,
                            label=f"+{pos_levels[0]:.0f}G",
                        )
                    )
                if neg_levels:
                    legend_handles.append(
                        Line2D(
                            [0],
                            [0],
                            color=sty.hmi_neg_color,
                            lw=sty.hmi_lw,
                            label=f"-{-neg_levels[0]:.0f}G",
                        )
                    )

            # ── 按频率排序波段 ────────────────────────────────
            def _band_freq(item):
                m = _RE_BAND_SORTED.search(item[0])  # 每个 item 只搜索一次
                return float(m.group(1)) if m else 0.0

            sorted_bands = sorted(single_slice_bands.items(), key=_band_freq)

            # ── 射电等值线叠加 ────────────────────────────────
            for band_idx, (band_label, file_list) in enumerate(sorted_bands):
                orig_idx = selected_bands_idx.get(band_label, band_idx)
                main_color, dark_color = get_band_color(
                    band_label, orig_idx, cfg, color_cache
                )
                drawn_any = False

                for file_item, polarization, radio_time in file_list:
                    # 检查是否启用左右旋合并
                    if (
                        cfg.combine_polarizations
                        and polarization == "RR+LL"
                        and isinstance(file_item, tuple)
                    ):
                        # file_item 是 (rr_path, ll_path) 元组
                        rr_path, ll_path = file_item

                        try:
                            # 读取RR数据
                            rr_data, rr_ra_map, rr_dec_map, rr_header, _ = (
                                extract_radio_2d_data(
                                    rr_path, use_float32=cfg.radio_use_float32, cfg=cfg
                                )
                            )
                            # 读取LL数据
                            ll_data, ll_ra_map, ll_dec_map, ll_header, _ = (
                                extract_radio_2d_data(
                                    ll_path, use_float32=cfg.radio_use_float32, cfg=cfg
                                )
                            )

                            if rr_data is None or ll_data is None:
                                continue

                            # 合并左右旋数据
                            radio_data_2d = _combine_polarization_data(
                                rr_data, ll_data, cfg
                            )

                            # 使用RR文件的坐标图和头文件
                            ra_map = rr_ra_map
                            dec_map = rr_dec_map
                            radio_header_2d = rr_header

                        except Exception as e:
                            if cfg.debug_mode:
                                print(f"    合并左右旋数据时出错: {e}")
                            continue

                    else:
                        # 原模式：单个文件
                        if (
                            cfg.polarization_mode != "BOTH"
                            and polarization != cfg.polarization_mode
                        ):
                            continue

                        try:
                            radio_data_2d, ra_map, dec_map, radio_header_2d, _ = (
                                extract_radio_2d_data(
                                    file_item,
                                    use_float32=cfg.radio_use_float32,
                                    cfg=cfg,
                                )
                            )
                        except Exception:
                            continue

                    if radio_data_2d is None or radio_data_2d.size == 0:
                        continue

                    beam = get_beam_params_from_header(radio_header_2d)
                    if beam and band_label not in collected_beams:
                        collected_beams[band_label] = beam

                    # === 修复后的智能投影路由 ===
                    reprojected = None
                    if (
                        cfg.use_radec_maps
                        and ra_map is not None
                        and dec_map is not None
                    ):
                        # 使用赤经赤纬前向投影
                        reprojected = reproject_radio_forward_paste(
                            radio_data_2d,
                            ra_map,
                            dec_map,
                            cutout_aia,
                            cfg,
                            radio_header_2d,
                        )
                    else:
                        # 缺失坐标图时，回退到简单缩放投影
                        result = reproject_radio_simple_scale(
                            radio_data_2d, radio_header_2d, cutout_aia, cfg
                        )
                        if result is not None:
                            reprojected = result[0]

                    if reprojected is None:
                        continue
                    # ==========================
                    # ==========================
                    if np.isnan(np.nanmax(reprojected)) or np.nanmax(reprojected) <= 0:
                        continue

                    display_data = smooth_for_contour(
                        reprojected, cfg.contour_smooth_sigma
                    )
                    levels = compute_contour_levels(display_data, cfg)
                    if not levels:
                        continue

                    n_lev = len(levels)
                    lws = _lw_lut[:n_lev]
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

                if drawn_any:
                    # 在图例中显示偏振信息
                    if cfg.combine_polarizations and cfg.polarization_mode == "RR+LL":
                        if cfg.weighted_average:
                            label = f"{band_label} (RR+LL, w={cfg.rr_weight:.1f}:{cfg.ll_weight:.1f})"
                        else:
                            label = f"{band_label} (RR+LL sum)"
                    else:
                        label = f"{band_label} ({polarization})"

                    legend_handles.append(
                        Line2D([0], [0], color=main_color, linewidth=2.0, label=label)
                    )

            # ── 波束椭圆 ───────────────────────────────────────
            if cfg.show_beam and collected_beams:
                for b_idx, (b_label, beam) in enumerate(collected_beams.items()):
                    b_color, _ = get_band_color(b_label, b_idx, cfg, color_cache)
                    draw_beam_ellipse_pixel(ax, beam, cutout_aia, color=b_color)

            # ── 日面边缘 ───────────────────────────────────────
            try:
                cutout_aia.draw_limb(
                    axes=ax,
                    color=sty.limb_color,
                    linewidth=sty.limb_lw,
                    linestyle="--",
                    alpha=sty.limb_alpha,
                    label="Solar limb",
                )
            except Exception as e:
                if cfg.debug_mode:
                    print(f"    [警告] 绘制日面边缘失败，可能不在当前视场内: {e}")

            # ── 标题与图例 ─────────────────────────────────────
            title_time = (
                first_radio_time.strftime("%Y-%m-%d %H:%M:%S") + " UT"
                if first_radio_time
                else os.path.basename(aia_file)
            )

            # 在标题中显示偏振信息
            if cfg.combine_polarizations and cfg.polarization_mode == "RR+LL":
                if cfg.weighted_average:
                    polar_display = f"RR+LL (weighted: RR={cfg.rr_weight:.1f}, LL={cfg.ll_weight:.1f})"
                else:
                    polar_display = "RR+LL (sum)"
            else:
                polar_display = cfg.polarization_mode

            ax.set_title(
                f"AIA 171Å + Radio ({polar_display}) + HMI\n{title_time}",
                fontsize=12,
                pad=10,
                color=sty.title_color,
            )
            ax.legend(
                handles=legend_handles,
                loc="upper right",
                fontsize=9,
                framealpha=sty.legend_alpha,
                facecolor=sty.legend_face,
                labelcolor=sty.legend_text,
            )

            # ── 画布与坐标轴样式（使用 CanvasStyle）─────────────
            fig.patch.set_facecolor(sty.figure_bg)
            ax.set_facecolor(sty.axes_bg)
            ax.tick_params(colors=sty.tick_color, direction="in")
            for spine in ax.spines.values():
                spine.set_edgecolor(sty.spine_color)
            ax.coords[0].set_axislabel("Solar X (arcsec)", color=sty.xlabel_color)
            ax.coords[1].set_axislabel("Solar Y (arcsec)", color=sty.ylabel_color)

            # ── 保存 ──────────────────────────────────────────
            if cfg.save_figure:
                ts_str = (
                    first_radio_time.strftime("%Y%m%d_%H%M%S")
                    if first_radio_time
                    else f"unknown_{sub_index}"
                )

                # 在文件名中包含偏振信息
                if cfg.combine_polarizations and cfg.polarization_mode == "RR+LL":
                    if cfg.weighted_average:
                        polar_suffix = f"RR{cfg.rr_weight:.1f}_LL{cfg.ll_weight:.1f}"
                    else:
                        polar_suffix = "RR_LL_sum"
                else:
                    polar_suffix = cfg.polarization_mode

                out_name = f"{ts_str}_{polar_suffix}_seq{sub_index + 1:02d}.png"
                plt.savefig(
                    os.path.join(cfg.output_dir, out_name),
                    dpi=cfg.dpi,
                    bbox_inches="tight",
                    facecolor=sty.figure_bg,
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
# 12. 主函数
# ============================================================


def test_time_parsing():
    """调试用：验证时间解析是否正常"""
    cases = [
        "20250124045940760",
        "20250124044317 38",
        "2025124_044317_038",
        "2025-01-24T04:43:17.038Z",
    ]
    print("测试时间解析:")
    for s in cases:
        r = _parse_flexible_datetime(s)
        print(f"  '{s}' -> {r if r else '解析失败'}")


def main():
    """主入口"""
    cfg = Config()

    # 如果启用左右旋合并但偏振模式不是RR+LL，自动调整
    if cfg.combine_polarizations and cfg.polarization_mode != "RR+LL":
        print(
            f"注意: combine_polarizations=True 但 polarization_mode='{cfg.polarization_mode}'"
        )
        print("自动将 polarization_mode 设置为 'RR+LL'")
        cfg.polarization_mode = "RR+LL"

    # 打印左右旋合并配置信息
    if cfg.combine_polarizations:
        print("=" * 60)
        print("左右旋数据加和功能已启用")
        print(f"  偏振模式: {cfg.polarization_mode}")
        print(f"  RR目录后缀: {cfg.rr_dir_suffix}")
        print(f"  LL目录后缀: {cfg.ll_dir_suffix}")
        print(f"  时间对齐容差: {cfg.time_tolerance_seconds} 秒")

        if cfg.weighted_average:
            print(
                f"  组合方式: 加权平均 (RR权重={cfg.rr_weight}, LL权重={cfg.ll_weight})"
            )
        else:
            print("  组合方式: 简单相加")

        if cfg.save_individual_pols:
            print("  同时保存单独的RR、LL图像: 是")
        else:
            print("  同时保存单独的RR、LL图像: 否")
        print("=" * 60)

    # ── 可在此处修改画布颜色，例如浅色主题 ─────────────────────
    # cfg.style.figure_bg    = "white"
    # cfg.style.axes_bg      = "whitesmoke"
    # cfg.style.tick_color   = "black"
    # cfg.style.spine_color  = "black"
    # cfg.style.xlabel_color = "black"
    # cfg.style.ylabel_color = "black"
    # cfg.style.title_color  = "black"
    # cfg.style.limb_color   = "dimgray"
    # cfg.style.legend_face  = "white"
    # cfg.style.legend_text  = "black"
    # cfg.style.hmi_pos_color = "crimson"
    # cfg.style.hmi_neg_color = "navy"

    if cfg.debug_mode:
        test_time_parsing()
        print("\n测试太阳位置计算:")
        t = datetime(2025, 1, 24, 4, 43, 17)
        try:
            ra, dec = get_solar_position(t)
            print(f"  时间: {t}  RA={ra:.6f}°  Dec={dec:.6f}°")
        except Exception as e:
            print(f"  失败: {e}")

    color_cache = _build_band_color_cache(cfg)
    grouped_tasks = build_matched_pairs(cfg)

    if not grouped_tasks:
        print("[提示] 没有找到匹配的数据对。请检查时间阈值或路径设置。")
        return

    total = len(grouped_tasks)
    print(f"[模式] 单进程，共 {total} 组任务")

    for idx, (aia_file, hmi_file, sub_tasks) in enumerate(grouped_tasks):
        process_aia_group(
            aia_file=aia_file,
            hmi_file=hmi_file,
            sub_tasks=sub_tasks,
            task_index=idx + 1,
            total_tasks=total,
            cfg=cfg,
            color_cache=color_cache,
        )

    print("\n全部任务处理完毕。")


if __name__ == "__main__":
    main()
