"""背景扣除实验版：在原 AIA/Radio/HMI 叠加基础上，增加射电背景扣除、SNR 源区掩膜、带背景项的椭圆高斯拟合与中心诊断输出。"""

# 模块用途: 生成 AIA、射电源和可选 HMI 的多仪器叠加图。
# 主要输入: AIA/HMI FITS 图像、射电源数据、偏振信息和配准参数。
# 主要输出/运行说明: 输出带等值线和偏振标记的综合诊断图，适合耀斑源区对比。
"""
Created on Sat Apr 25 19:57:54 2026

@author: Lee
"""

"""
AIA_RS.py – 射电、AIA 与 HMI 数据叠加绘图模块

功能：
- 根据配置文件处理 AIA、射电（含偏振组合）、HMI 数据
- 通过椭圆高斯拟合将射电数据重投影到 AIA 坐标系
- 生成带等值线叠加的最终图像并保存
"""

# ============================================================
# 1. 基础库导入
# ============================================================
import csv  # noqa: E402
import glob  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import warnings  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402

# ============================================================
# 2. 科学计算和天文库导入
# ============================================================
import astropy.units as u  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")  # 非交互后端，子进程安全，节省内存
import matplotlib.colors as mcolors  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import sunpy.coordinates  # noqa: E402
import sunpy.map  # noqa: E402
from astropy.coordinates import SkyCoord  # noqa: E402
from astropy.io import fits  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from numpy.typing import NDArray  # noqa: E402
from scipy.interpolate import RegularGridInterpolator  # noqa: E402
from scipy.ndimage import (  # noqa: E402
    binary_dilation,
    gaussian_filter,
    label,
    median_filter,
)
from scipy.optimize import curve_fit  # noqa: E402

from solar_toolkit.path_config import apply_config_to_object  # noqa: E402

BoolArray = NDArray[np.bool_]
FloatArray = NDArray[np.float64]
IntArray = NDArray[np.intp]

warnings.filterwarnings("ignore")

# ============================================================
# 3. 全局配置和常量
# ============================================================

# 字体设置
plt.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

# 正则表达式常量（全部预编译，避免运行时重复编译）
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
        r"D:\spike_topping_type_III\2025\20250124\AIA_RS_HMI\test_bgcorrected"
    )

    # ── 文件处理配置 ───────────────────────────────────────────
    save_figure: bool = True
    dpi: int = 300
    aia_file_start_idx: int = 392
    aia_file_end_idx: int | None = 396

    # ── 射电波段配置 ───────────────────────────────────────────
    selected_bands: list[str] = field(
        default_factory=lambda: [
            "149MHz",
            "164MHz",
            "190MHz",
            "205MHz",
            "223MHz",
            "238MHz",
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
    show_radio_contours: bool = False
    contour_levels_peak: list[float] = field(default_factory=lambda: [0.90])
    contour_linewidths: list[float] = field(default_factory=lambda: [2.0])
    contour_alpha: float = 0.90
    contour_smooth_sigma: float = 0
    mark_radio_center: bool = True
    radio_center_marker: str = "x"
    radio_center_size: float = 50
    radio_center_linewidth: float = 1.8
    label_radio_center: bool = False

    # ── 显示配置 ───────────────────────────────────────────────
    overlay_hmi: bool = True
    hmi_time_threshold: int = 24  # HMI 与 AIA 时间匹配阈值（小时）
    hmi_threshold_gauss: float = 0.0
    hmi_sigma: int = 2
    hmi_levels_gauss: list[float] = field(default_factory=lambda: [100.0])

    # ── AIA 图像配置 ───────────────────────────────────────────
    aia_vmin: float = 16
    aia_vmax: float = 6666
    aia_cmap: str = "sdoaia171"
    roi_bottom_left: list[float] = field(default_factory=lambda: [600, -800])
    roi_top_right: list[float] = field(default_factory=lambda: [1600, 200])

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
    default_colors: list[tuple] = field(
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
    radio_use_float32: bool = True

    # ── 处理选项 ───────────────────────────────────────────────
    debug_mode: bool = True

    # ── 坐标图配置 ─────────────────────────────────────────────
    use_radec_maps: bool = True  # 是否使用赤经赤纬坐标

    radio_background_mode: str = "pre_event_median"
    background_pre_event_seconds: float = 60.0
    background_min_frames: int = 5
    background_local_median_size: int = 31
    background_scale_mode: str = "offsource_median"
    clip_negative_after_background: bool = True

    fit_use_source_mask: bool = True
    fit_snr_threshold: float = 5.0
    fit_peak_fraction_threshold: float = 0.30
    fit_min_mask_pixels: int = 20
    fit_mask_dilation_pixels: int = 3
    fit_background_model: str = "plane"

    save_fit_diagnostics: bool = True
    draw_raw_vs_bg_center_shift: bool = False

    def __post_init__(self):
        apply_config_to_object(self, "sdo_aia_radio_hmi_overlay_bgcorrected")


@dataclass
class GaussianReprojectResult:
    model: np.ndarray
    center_pixel: tuple[float, float]
    center_pixel_raw: tuple[float, float] | None
    center_pixel_bgsub: tuple[float, float] | None
    center_arcsec: tuple[float, float]
    sigma_pixel: tuple[float, float]
    theta_rad: float
    amplitude: float
    covariance: np.ndarray
    noise_sigma: float | None
    snr: float | None
    background_level: float | None
    residual_rms: float | None
    quality_flag: str


# ============================================================
# 5. 工具函数 – 时间处理
# ============================================================


def _parse_flexible_datetime(date_str: str) -> datetime | None:
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


def parse_radio_time_from_filename(filename: str) -> datetime | None:
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


def parse_aia_time_from_filename(filename: str) -> datetime | None:
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


def parse_hmi_time_from_filename(filename: str) -> datetime | None:
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


def _parse_time_from_filename(filename: str) -> tuple[str, int] | None:
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
) -> list[tuple[str, str]]:
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
    ll_index: dict[tuple[str, int], str] = {}
    ll_no_parse: list[str] = []
    for ll_path in ll_files:
        parsed = _parse_time_from_filename(os.path.basename(ll_path))
        if parsed is None:
            ll_no_parse.append(ll_path)
        else:
            key = parsed  # (date_str, total_ms)
            if key not in ll_index:
                ll_index[key] = ll_path

    if ll_no_parse:
        warnings.warn(
            f"有 {len(ll_no_parse)} 个LL文件无法从文件名解析时间，将被跳过。",
            stacklevel=2,
        )

    matched_pairs: list[tuple[str, str]] = []
    unmatched_rr: list[str] = []

    # 将LL索引按日期分组，加速搜索
    from collections import defaultdict

    ll_by_date: dict[str, list[tuple[int, str]]] = defaultdict(
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
            warnings.warn(
                f"RR文件 {os.path.basename(rr_path)} 无法解析时间，跳过。", stacklevel=2
            )
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
                    f"(最近差值={best_diff:.1f}ms > 容差={tolerance_ms:.1f}ms)，跳过。",
                    stacklevel=2,
                )
            else:
                warnings.warn(
                    f"RR文件 {os.path.basename(rr_path)} 在LL目录中找不到同日期文件，跳过。",
                    stacklevel=2,
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


def find_background_files_for_current_radio(
    current_radio_file: str,
    band: str | None,
    polarization: str | None,
    cfg: Config,
) -> list[str]:
    """Find pre-event FITS frames in the same directory for the same band/polarization."""
    if cfg.radio_background_mode != "pre_event_median":
        return []
    current_time = parse_radio_time_from_filename(current_radio_file)
    if current_time is None:
        return []

    directory = os.path.dirname(current_radio_file)
    current_abs = os.path.abspath(current_radio_file)
    band_key = (band or "").replace(".0MHz", "MHz")
    candidates = sorted(glob.glob(os.path.join(directory, "*.fits")))
    out: list[str] = []
    for path in candidates:
        if os.path.abspath(path) == current_abs:
            continue
        name = os.path.basename(path)
        if (
            band_key
            and band_key not in name
            and band_key.replace("MHz", ".0MHz") not in name
        ):
            continue
        if polarization and polarization not in {"RR+LL", ""}:
            parent = os.path.basename(os.path.dirname(path)).upper()
            if (
                polarization.upper() not in parent
                and polarization.upper() not in name.upper()
            ):
                continue
        t = parse_radio_time_from_filename(path)
        if t is None:
            continue
        dt = (current_time - t).total_seconds()
        if 0 < dt <= cfg.background_pre_event_seconds:
            out.append(path)
    return out


def build_radio_background_map(
    background_files: list[str], cfg: Config
) -> np.ndarray | None:
    """Build a median background map from compatible pre-event frames."""
    frames = []
    target_shape = None
    for path in background_files:
        data = _load_fits_2d(path, cfg.radio_use_float32)
        if data is None:
            continue
        if target_shape is None:
            target_shape = data.shape
        if data.shape != target_shape:
            continue
        frames.append(np.asarray(data, dtype=np.float64))
    if len(frames) < cfg.background_min_frames:
        return None
    return np.nanmedian(np.stack(frames, axis=0), axis=0)


def _estimate_local_background(data: np.ndarray, cfg: Config) -> np.ndarray | None:
    size = int(cfg.background_local_median_size)
    if size < 3:
        return None
    if size % 2 == 0:
        size += 1
    try:
        return median_filter(
            np.asarray(data, dtype=np.float64), size=size, mode="nearest"
        )
    except Exception:
        return None


def subtract_radio_background(
    radio_data: np.ndarray, background_map: np.ndarray | None, cfg: Config
) -> tuple[np.ndarray, dict]:
    """Subtract radio background with fallbacks and keep diagnostics."""
    diagnostics = {
        "background_mode_used": cfg.radio_background_mode,
        "background_scale": 1.0,
        "background_level": None,
        "warning": None,
    }
    raw = np.asarray(radio_data, dtype=np.float64)
    bg = background_map

    if cfg.radio_background_mode == "none":
        diagnostics["background_mode_used"] = "none"
        return raw.copy(), diagnostics
    if bg is None and cfg.radio_background_mode in {"pre_event_median", "local_median"}:
        bg = _estimate_local_background(raw, cfg)
        diagnostics["background_mode_used"] = (
            "local_median" if bg is not None else "plane_only"
        )
        if bg is None:
            diagnostics["warning"] = (
                "background fallback: local_median failed; using fit background only"
            )
            return raw.copy(), diagnostics
    if bg is None:
        diagnostics["background_mode_used"] = "plane_only"
        return raw.copy(), diagnostics

    bg = np.asarray(bg, dtype=np.float64)
    if bg.shape != raw.shape:
        diagnostics["background_mode_used"] = "plane_only"
        diagnostics["warning"] = "background shape mismatch; using fit background only"
        return raw.copy(), diagnostics

    scale = 1.0
    if cfg.background_scale_mode == "offsource_median":
        raw_level, _ = estimate_background_noise(raw)
        bg_level, _ = estimate_background_noise(bg)
        if np.isfinite(raw_level) and np.isfinite(bg_level) and abs(bg_level) > 1e-12:
            scale = raw_level / bg_level
    diagnostics["background_scale"] = float(scale)
    diagnostics["background_level"] = float(np.nanmedian(bg * scale))
    sub = raw - scale * bg
    if cfg.clip_negative_after_background:
        sub = np.where(sub < 0, 0.0, sub)
    return sub, diagnostics


# ============================================================
# 6. 工具函数 – 坐标处理
# ============================================================


def get_solar_position(obs_time: datetime) -> tuple[float, float]:
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
_radec_file_cache: dict[tuple[str, str, str], str | None] = {}


def _find_radec_file(search_dirs: list[str], freq_value: str, kind: str) -> str | None:
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


def _load_fits_2d(path: str, use_float32: bool) -> np.ndarray | None:
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
    cfg: Config | None = None,
) -> tuple[
    np.ndarray | None,
    np.ndarray | None,
    np.ndarray | None,
    fits.Header | None,
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


def compute_contour_levels(data: np.ndarray, cfg: Config) -> list[float]:
    """直接基于高斯模型的峰值计算等值线级别"""
    finite = data[np.isfinite(data)]
    if len(finite) == 0:
        return []
    peak = float(np.nanmax(finite))
    # 直接返回峰值的百分比（例如 90%）
    return [f * peak for f in cfg.contour_levels_peak]


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
        max_y, max_x = _unravel_2d_index(int(np.argmax(data)), data.shape)
        init_x0 = x[max_x]
        init_y0 = y[max_y]
        init_A = np.max(data)

        # 粗略估计 sigma（通过半高宽）
        half_max = init_A / 2.0
        # x方向
        row_max = data[max_y, :]
        indices = _true_indices(row_max >= half_max)
        if len(indices) > 1:
            init_sigma_x = (x[indices[-1]] - x[indices[0]]) / (2.355)  # FWHM -> sigma
        else:
            init_sigma_x = (x[-1] - x[0]) / 10.0
        # y方向
        col_max = data[:, max_x]
        indices_y = _true_indices(col_max >= half_max)
        if len(indices_y) > 1:
            init_sigma_y = (y[indices_y[-1]] - y[indices_y[0]]) / (2.355)
        else:
            init_sigma_y = (y[-1] - y[0]) / 10.0
        init_theta = 0.0
        initial_guess = (
            init_A,
            init_x0,
            init_y0,
            init_sigma_x,
            init_sigma_y,
            init_theta,
        )

    # 参数边界
    bounds = (
        [0, -np.inf, -np.inf, 1e-3, 1e-3, -np.pi / 2],
        [np.inf, np.inf, np.inf, np.inf, np.inf, np.pi / 2],
    )

    popt, pcov = curve_fit(
        elliptical_gaussian_2d,
        (x_flat, y_flat),
        data_flat,
        p0=initial_guess,
        bounds=bounds,
        maxfev=5000,
    )
    return popt, pcov


def elliptical_gaussian_2d_with_constant_bg(xy, A, x0, y0, sigma_x, sigma_y, theta, b0):
    """Elliptical Gaussian plus a constant background."""
    return elliptical_gaussian_2d(xy, A, x0, y0, sigma_x, sigma_y, theta) + b0


def elliptical_gaussian_2d_with_plane_bg(
    xy, A, x0, y0, sigma_x, sigma_y, theta, b0, bx, by
):
    """Elliptical Gaussian plus a tilted plane background."""
    x, y = xy
    return (
        elliptical_gaussian_2d(xy, A, x0, y0, sigma_x, sigma_y, theta)
        + b0
        + bx * x
        + by * y
    )


def _unravel_2d_index(
    flat_index: int | np.integer, shape: tuple[int, ...]
) -> tuple[int, int]:
    coords = np.asarray(np.unravel_index(int(flat_index), shape), dtype=np.intp)
    return int(coords[0]), int(coords[1])


def _true_indices(mask: np.ndarray) -> IntArray:
    mask_bool = np.asarray(mask, dtype=np.bool_)
    return np.asarray(np.nonzero(mask_bool)[0], dtype=np.intp)


def estimate_background_noise(
    data: np.ndarray, source_exclusion_mask: np.ndarray | None = None
) -> tuple[float, float]:
    """Estimate background level and sigma via median and MAD."""
    values = np.asarray(data, dtype=np.float64)
    finite = np.isfinite(values)
    if source_exclusion_mask is not None:
        finite &= ~source_exclusion_mask
    sample = values[finite]
    if sample.size == 0:
        sample = values[np.isfinite(values)]
    if sample.size == 0:
        return 0.0, 0.0
    med = float(np.nanmedian(sample))
    mad = float(np.nanmedian(np.abs(sample - med)))
    sigma = 1.4826 * mad
    if not np.isfinite(sigma) or sigma <= 0:
        sigma = float(np.nanstd(sample))
    if not np.isfinite(sigma):
        sigma = 0.0
    return med, sigma


def create_source_mask(
    data: FloatArray | np.ndarray, cfg: Config
) -> tuple[BoolArray | None, dict]:
    """Create an SNR/peak-fraction mask, keeping only the peak-connected source."""
    work = np.asarray(data, dtype=np.float64)
    finite = np.isfinite(work)
    diagnostics = {
        "noise_sigma": None,
        "snr": None,
        "background_level": None,
        "mask_pixel_count": 0,
        "quality_flag": "ok",
    }
    if not np.any(finite):
        diagnostics["quality_flag"] = "fit_failed"
        return None, diagnostics

    peak = float(np.nanmax(work))
    peak_y, peak_x = _unravel_2d_index(int(np.nanargmax(work)), work.shape)
    initial_source: BoolArray = np.asarray(
        work > max(float(np.nanmedian(work)), cfg.fit_peak_fraction_threshold * peak),
        dtype=np.bool_,
    )
    background_level, noise_sigma = estimate_background_noise(work, initial_source)
    snr = (peak - background_level) / noise_sigma if noise_sigma > 0 else np.inf
    threshold = max(
        cfg.fit_snr_threshold * noise_sigma,
        cfg.fit_peak_fraction_threshold * peak,
    )
    source_mask_bool: BoolArray = np.asarray(
        finite & (work > threshold), dtype=np.bool_
    )

    labeled, n_labels = label(source_mask_bool)
    peak_label = int(labeled[peak_y, peak_x])
    if n_labels == 0 or peak_label == 0:
        diagnostics.update(
            {
                "noise_sigma": noise_sigma,
                "snr": snr,
                "background_level": background_level,
                "quality_flag": "mask_too_small",
            }
        )
        return None, diagnostics

    main_mask: BoolArray = np.asarray(labeled == peak_label, dtype=np.bool_)
    if cfg.fit_mask_dilation_pixels > 0:
        main_mask = np.asarray(
            binary_dilation(main_mask, iterations=cfg.fit_mask_dilation_pixels),
            dtype=np.bool_,
        )
        main_mask &= finite

    mask_count = int(np.sum(main_mask))
    quality_flag = "ok"
    if mask_count < cfg.fit_min_mask_pixels:
        quality_flag = "mask_too_small"
    elif np.isfinite(snr) and snr < cfg.fit_snr_threshold:
        quality_flag = "low_snr"

    diagnostics.update(
        {
            "noise_sigma": noise_sigma,
            "snr": snr,
            "background_level": background_level,
            "mask_pixel_count": mask_count,
            "quality_flag": quality_flag,
        }
    )
    if quality_flag == "mask_too_small":
        return None, diagnostics
    return np.asarray(main_mask, dtype=np.bool_), diagnostics


def _initial_gaussian_guess(data: np.ndarray, x: np.ndarray, y: np.ndarray):
    clean = np.asarray(data, dtype=np.float64)
    background_level, _ = estimate_background_noise(clean)
    peak_y, peak_x = _unravel_2d_index(int(np.nanargmax(clean)), clean.shape)
    peak = float(clean[peak_y, peak_x])
    amp = max(peak - background_level, peak, 1e-6)
    return (
        amp,
        float(x[peak_x]),
        float(y[peak_y]),
        max((x[-1] - x[0]) / 10.0, 1.0),
        max((y[-1] - y[0]) / 10.0, 1.0),
        0.0,
    )


def fit_elliptical_gaussian_robust(
    data: np.ndarray, x: np.ndarray, y: np.ndarray, cfg: Config
) -> tuple[np.ndarray | None, np.ndarray | None, dict]:
    """Fit an elliptical Gaussian with optional mask and background terms."""
    diagnostics = {
        "noise_sigma": None,
        "snr": None,
        "background_level": None,
        "residual_rms": None,
        "quality_flag": "ok",
        "mask_pixel_count": int(np.isfinite(data).sum()),
    }
    fit_data = np.asarray(data, dtype=np.float64)
    finite = np.isfinite(fit_data)
    source_mask: BoolArray | None = None

    if cfg.fit_use_source_mask:
        source_mask, mask_diag = create_source_mask(fit_data, cfg)
        diagnostics.update(mask_diag)
        if mask_diag["quality_flag"] == "mask_too_small":
            return None, None, diagnostics
        fit_mask = np.asarray(source_mask, dtype=np.bool_)
    else:
        background_level, noise_sigma = estimate_background_noise(fit_data)
        peak = float(np.nanmax(fit_data)) if np.any(finite) else 0.0
        snr = (peak - background_level) / noise_sigma if noise_sigma > 0 else np.inf
        diagnostics.update(
            {
                "noise_sigma": noise_sigma,
                "snr": snr,
                "background_level": background_level,
                "quality_flag": "low_snr" if snr < cfg.fit_snr_threshold else "ok",
            }
        )
        fit_mask = finite

    X, Y = np.meshgrid(x, y)
    fit_mask = np.asarray(fit_mask, dtype=np.bool_) & finite
    if int(np.sum(fit_mask)) < cfg.fit_min_mask_pixels:
        diagnostics["quality_flag"] = "mask_too_small"
        diagnostics["mask_pixel_count"] = int(np.sum(fit_mask))
        return None, None, diagnostics

    x_flat = X[fit_mask].ravel()
    y_flat = Y[fit_mask].ravel()
    data_flat = fit_data[fit_mask].ravel()
    p0_base = _initial_gaussian_guess(np.where(finite, fit_data, np.nan), x, y)
    ny, nx = fit_data.shape
    common_bounds = (
        [0, 0, 0, 1e-3, 1e-3, -np.pi / 2],
        [np.inf, nx - 1, ny - 1, nx, ny, np.pi / 2],
    )

    model_name = cfg.fit_background_model.lower()
    if model_name == "constant":
        model_func = elliptical_gaussian_2d_with_constant_bg
        p0 = (*p0_base, diagnostics.get("background_level") or 0.0)
        bounds = ((*common_bounds[0], -np.inf), (*common_bounds[1], np.inf))
    elif model_name == "plane":
        model_func = elliptical_gaussian_2d_with_plane_bg
        p0 = (*p0_base, diagnostics.get("background_level") or 0.0, 0.0, 0.0)
        bounds = (
            (*common_bounds[0], -np.inf, -np.inf, -np.inf),
            (*common_bounds[1], np.inf, np.inf, np.inf),
        )
    else:
        model_func = elliptical_gaussian_2d
        p0 = p0_base
        bounds = common_bounds

    try:
        popt, pcov = curve_fit(
            model_func,
            (x_flat, y_flat),
            data_flat,
            p0=p0,
            bounds=bounds,
            maxfev=10000,
        )
    except Exception as exc:
        diagnostics["quality_flag"] = "fit_failed"
        diagnostics["fit_error"] = str(exc)
        return None, None, diagnostics

    model_values = model_func((x_flat, y_flat), *popt)
    residual = data_flat - model_values
    diagnostics["residual_rms"] = float(np.sqrt(np.nanmean(residual**2)))
    diagnostics["mask_pixel_count"] = int(np.sum(fit_mask))
    sx, sy = float(popt[3]), float(popt[4])
    if sx > nx / 2 or sy > ny / 2:
        diagnostics["quality_flag"] = "unphysical_size"
    elif diagnostics.get("quality_flag") not in {"low_snr"}:
        diagnostics["quality_flag"] = "ok"
    return np.asarray(popt), np.asarray(pcov), diagnostics


# ============================================================
# 9. 主投影函数（基于椭圆高斯拟合与关键点映射）
# ============================================================


def reproject_radio_via_gaussian_fit(
    radio_data: np.ndarray,
    ra_map: np.ndarray | None,
    dec_map: np.ndarray | None,
    aia_cutout_map: sunpy.map.GenericMap,
    cfg: Config,
    radio_header: fits.Header | None = None,
    radio_fit_data: np.ndarray | None = None,
    fit_label: str | None = None,
) -> GaussianReprojectResult | None:
    ny_a, nx_a = aia_cutout_map.data.shape
    ny_r, nx_r = radio_data.shape
    x_pix = np.arange(nx_r, dtype=float)
    y_pix = np.arange(ny_r, dtype=float)
    fit_data = radio_fit_data if radio_fit_data is not None else radio_data

    # ---------- 1. 在射电域进行二维椭圆高斯拟合 ----------
    popt, pcov, diagnostics = fit_elliptical_gaussian_robust(
        fit_data, x_pix, y_pix, cfg
    )
    if popt is None or pcov is None:
        if cfg.debug_mode:
            label_text = f" ({fit_label})" if fit_label else ""
            print(
                f"    [鲁棒高斯拟合{label_text}] 跳过: "
                f"{diagnostics.get('quality_flag', 'fit_failed')}"
            )
        return None

    A_fit, x0_pix, y0_pix, sigma_x_pix, sigma_y_pix, theta_pix = popt[:6]
    raw_center_radio: tuple[float, float] | None = None
    if cfg.draw_raw_vs_bg_center_shift and radio_fit_data is not None:
        try:
            raw_popt, _ = fit_elliptical_gaussian(radio_data, x_pix, y_pix)
            raw_center_radio = (float(raw_popt[1]), float(raw_popt[2]))
        except Exception as e:
            if cfg.debug_mode:
                print(f"    [原始高斯拟合] 失败: {e}")
    use_radec = cfg.use_radec_maps and (ra_map is not None) and (dec_map is not None)

    if use_radec:
        # 【应用 AIA_RS_HMI.py 的预处理逻辑】
        ra_abs = ra_map.copy().astype(np.float64)
        dec_abs = dec_map.copy().astype(np.float64)

        # 精准过滤背景：将精确为 0.0 的无效区域置为 NaN，防止坐标拉扯
        invalid_mask = (ra_abs == 0.0) & (dec_abs == 0.0)
        ra_abs[invalid_mask] = np.nan
        dec_abs[invalid_mask] = np.nan

        interp_ra = RegularGridInterpolator(
            (y_pix, x_pix), ra_abs, bounds_error=False, fill_value=np.nan
        )
        interp_dec = RegularGridInterpolator(
            (y_pix, x_pix), dec_abs, bounds_error=False, fill_value=np.nan
        )

    elif radio_header is not None:
        crpix1 = radio_header.get("CRPIX1", 0)
        crpix2 = radio_header.get("CRPIX2", 0)
        crval1 = radio_header.get("CRVAL1", 0)
        crval2 = radio_header.get("CRVAL2", 0)
        cdelt1 = radio_header.get("CDELT1", 1)
        cdelt2 = radio_header.get("CDELT2", 1)
    else:
        return None

    # ---------- 2. 映射转换函数（度 -> HPC 角秒） ----------
    def radio_pix_to_aia_pix(xp, yp):
        if use_radec:
            ra_val = float(interp_ra((yp, xp)))
            dec_val = float(interp_dec((yp, xp)))

            # 处理越界或 NaN 值
            if np.isnan(ra_val) or np.isnan(dec_val):
                iy = np.clip(int(round(yp)), 0, ny_r - 1)
                ix = np.clip(int(round(xp)), 0, nx_r - 1)
                ra_val = ra_abs[iy, ix]
                dec_val = dec_abs[iy, ix]
                if np.isnan(ra_val) or np.isnan(dec_val):
                    return np.nan, np.nan

            # 【核心修正】：参照 AIA_RS_HMI.py，真实单位为度，转为角秒必须乘以 3600
            tx_arcsec = ra_val * 3600.0
            ty_arcsec = dec_val * 3600.0

            # 构建 AIA 原生的日面投影坐标系 (HPC)
            coord_target = SkyCoord(
                Tx=tx_arcsec * u.arcsec,
                Ty=ty_arcsec * u.arcsec,
                frame=aia_cutout_map.coordinate_frame,
            )
        else:
            x_angle = crval1 + (xp + 1 - crpix1) * cdelt1
            y_angle = crval2 + (yp + 1 - crpix2) * cdelt2
            coord_target = SkyCoord(
                Tx=x_angle * u.arcsec,
                Ty=y_angle * u.arcsec,
                frame=aia_cutout_map.coordinate_frame,
            )

        px, py = aia_cutout_map.wcs.world_to_pixel(coord_target)
        return float(px), float(py)

    # ---------- 3. 核心：三点映射 ----------
    try:
        c_aia_x, c_aia_y = radio_pix_to_aia_pix(x0_pix, y0_pix)
        if np.isnan(c_aia_x) or np.isnan(c_aia_y):
            return None
        raw_center_aia = None
        if raw_center_radio is not None:
            raw_aia_x, raw_aia_y = radio_pix_to_aia_pix(*raw_center_radio)
            if np.isfinite(raw_aia_x) and np.isfinite(raw_aia_y):
                raw_center_aia = (float(raw_aia_x), float(raw_aia_y))

        p_maj_x = x0_pix + sigma_x_pix * np.cos(theta_pix)
        p_maj_y = y0_pix + sigma_x_pix * np.sin(theta_pix)
        maj_aia_x, maj_aia_y = radio_pix_to_aia_pix(p_maj_x, p_maj_y)

        p_min_x = x0_pix - sigma_y_pix * np.sin(theta_pix)
        p_min_y = y0_pix + sigma_y_pix * np.cos(theta_pix)
        min_aia_x, min_aia_y = radio_pix_to_aia_pix(p_min_x, p_min_y)
    except Exception as e:
        if cfg.debug_mode:
            print(f"    [坐标转换] 映射失败: {e}")
        return None

    dx_maj = maj_aia_x - c_aia_x
    dy_maj = maj_aia_y - c_aia_y
    sigma_aia_x = np.sqrt(dx_maj**2 + dy_maj**2)
    theta_aia = np.arctan2(dy_maj, dx_maj)

    dx_min = min_aia_x - c_aia_x
    dy_min = min_aia_y - c_aia_y
    sigma_aia_y = np.sqrt(dx_min**2 + dy_min**2)

    if not (
        np.isfinite(sigma_aia_x)
        and np.isfinite(sigma_aia_y)
        and sigma_aia_x > 0
        and sigma_aia_y > 0
    ):
        return None

    # ---------- 4. 在 AIA 视场生成最终模型 ----------
    Y_aia, X_aia = np.mgrid[0:ny_a, 0:nx_a]
    model = elliptical_gaussian_2d(
        (X_aia, Y_aia), A_fit, c_aia_x, c_aia_y, sigma_aia_x, sigma_aia_y, theta_aia
    )

    model = np.maximum(model, 0)
    center_world = aia_cutout_map.pixel_to_world(c_aia_x * u.pixel, c_aia_y * u.pixel)

    return GaussianReprojectResult(
        model=model.astype(np.float32),
        center_pixel=(float(c_aia_x), float(c_aia_y)),
        center_pixel_raw=raw_center_aia,
        center_pixel_bgsub=(float(c_aia_x), float(c_aia_y)),
        center_arcsec=(
            float(center_world.Tx.to_value(u.arcsec)),
            float(center_world.Ty.to_value(u.arcsec)),
        ),
        sigma_pixel=(float(sigma_aia_x), float(sigma_aia_y)),
        theta_rad=float(theta_aia),
        amplitude=float(A_fit),
        covariance=np.asarray(pcov),
        noise_sigma=diagnostics.get("noise_sigma"),
        snr=diagnostics.get("snr"),
        background_level=diagnostics.get("background_level"),
        residual_rms=diagnostics.get("residual_rms"),
        quality_flag=str(diagnostics.get("quality_flag", "ok")),
    )


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


def _world_arcsec_from_pixel(
    aia_map: sunpy.map.GenericMap, pixel_xy: tuple[float, float] | None
) -> tuple[float | None, float | None]:
    if pixel_xy is None:
        return None, None
    try:
        world = aia_map.pixel_to_world(pixel_xy[0] * u.pixel, pixel_xy[1] * u.pixel)
        return float(world.Tx.to_value(u.arcsec)), float(world.Ty.to_value(u.arcsec))
    except Exception:
        return None, None


def _diagnostic_row_from_fit(
    fit_result: GaussianReprojectResult,
    aia_map: sunpy.map.GenericMap,
    radio_time: datetime | None,
    band: str,
    polarization: str,
    source_file,
    cfg: Config,
) -> dict:
    raw_arcsec = _world_arcsec_from_pixel(aia_map, fit_result.center_pixel_raw)
    shift_pixel = None
    shift_arcsec = None
    if (
        fit_result.center_pixel_raw is not None
        and fit_result.center_pixel_bgsub is not None
    ):
        dxp = fit_result.center_pixel_bgsub[0] - fit_result.center_pixel_raw[0]
        dyp = fit_result.center_pixel_bgsub[1] - fit_result.center_pixel_raw[1]
        shift_pixel = float(np.hypot(dxp, dyp))
        if raw_arcsec[0] is not None and raw_arcsec[1] is not None:
            dxa = fit_result.center_arcsec[0] - raw_arcsec[0]
            dya = fit_result.center_arcsec[1] - raw_arcsec[1]
            shift_arcsec = float(np.hypot(dxa, dya))

    return {
        "time": radio_time.isoformat() if radio_time else "",
        "band": band,
        "polarization": polarization,
        "source_file": (
            ";".join(source_file)
            if isinstance(source_file, tuple)
            else str(source_file)
        ),
        "center_x_arcsec": fit_result.center_arcsec[0],
        "center_y_arcsec": fit_result.center_arcsec[1],
        "center_x_pixel": (
            fit_result.center_pixel_bgsub[0] if fit_result.center_pixel_bgsub else ""
        ),
        "center_y_pixel": (
            fit_result.center_pixel_bgsub[1] if fit_result.center_pixel_bgsub else ""
        ),
        "sigma_x_pixel": fit_result.sigma_pixel[0],
        "sigma_y_pixel": fit_result.sigma_pixel[1],
        "theta_rad": fit_result.theta_rad,
        "amplitude": fit_result.amplitude,
        "background_level": fit_result.background_level,
        "noise_sigma": fit_result.noise_sigma,
        "snr": fit_result.snr,
        "residual_rms": fit_result.residual_rms,
        "quality_flag": fit_result.quality_flag,
        "background_mode": cfg.radio_background_mode,
        "fit_background_model": cfg.fit_background_model,
        "center_shift_pixel": shift_pixel if shift_pixel is not None else "",
        "center_shift_arcsec": shift_arcsec if shift_arcsec is not None else "",
    }


def write_fit_diagnostics_csv(rows: list[dict], cfg: Config) -> str | None:
    if not cfg.save_fit_diagnostics or not rows:
        return None
    out_path = os.path.join(cfg.output_dir, "radio_fit_centers_bgcorrected.csv")
    fieldnames = [
        "time",
        "band",
        "polarization",
        "source_file",
        "center_x_arcsec",
        "center_y_arcsec",
        "center_x_pixel",
        "center_y_pixel",
        "sigma_x_pixel",
        "sigma_y_pixel",
        "theta_rad",
        "amplitude",
        "background_level",
        "noise_sigma",
        "snr",
        "residual_rms",
        "quality_flag",
        "background_mode",
        "fit_background_model",
        "center_shift_pixel",
        "center_shift_arcsec",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return out_path


def _get_padded_aia_map(
    aia_map: sunpy.map.GenericMap, cfg: Config
) -> sunpy.map.GenericMap:
    """
    精确截取或扩充画布到用户指定的 ROI 范围，
    彻底解决 sunpy.map.submap 在图像边缘的自动截断问题，
    允许在 AIA 没有数据的外太空区域继续绘制射电和 HMI。
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

    # 转换为整数像素边界
    x0, y0 = int(np.floor(float(px_bl[0]))), int(np.floor(float(px_bl[1])))
    x1, y1 = int(np.ceil(float(px_tr[0]))), int(np.ceil(float(px_tr[1])))

    if x0 > x1:
        x0, x1 = x1, x0
    if y0 > y1:
        y0, y1 = y1, y0

    new_nx = x1 - x0
    new_ny = y1 - y0

    # 创建全 NaN 的全新画布（充当深空背景）
    new_data = np.full((new_ny, new_nx), np.nan, dtype=aia_map.data.dtype)

    orig_ny, orig_nx = aia_map.data.shape

    # 计算原图和新画布的重合像素区域
    src_x0 = max(0, x0)
    src_x1 = min(orig_nx, x1)
    src_y0 = max(0, y0)
    src_y1 = min(orig_ny, y1)

    # 如果有重合，则将 AIA 原图的有效部分精准贴入新画布
    if src_x0 < src_x1 and src_y0 < src_y1:
        dst_x0 = src_x0 - x0
        dst_x1 = src_x1 - x0
        dst_y0 = src_y0 - y0
        dst_y1 = src_y1 - y0
        new_data[dst_y0:dst_y1, dst_x0:dst_x1] = aia_map.data[
            src_y0:src_y1, src_x0:src_x1
        ]

    # 更新 WCS 头文件，平移参考坐标原点
    new_meta = aia_map.meta.copy()
    new_meta["CRPIX1"] -= x0
    new_meta["CRPIX2"] -= y0
    new_meta["NAXIS1"] = new_nx
    new_meta["NAXIS2"] = new_ny

    # 返回完全基于用户范围定制的新 Map
    return sunpy.map.Map(new_data, new_meta)


# ============================================================
# 11. 新增函数：build_matched_pairs
# ============================================================


def build_matched_pairs(cfg: Config) -> list[tuple[str, str | None, list]]:
    """
    构建任务列表：将 AIA 文件前后指定时间内的所有射电数据
    按时间顺序切分为一个个独立的“切片”（slice），用于生成序列帧。
    """
    aia_files = sorted(glob.glob(os.path.join(cfg.aia_base_dir, "*.fits")))
    if not aia_files:
        raise FileNotFoundError(f"在 {cfg.aia_base_dir} 中未找到 AIA fits 文件")

    start = cfg.aia_file_start_idx if cfg.aia_file_start_idx is not None else 0
    end = cfg.aia_file_end_idx if cfg.aia_file_end_idx is not None else len(aia_files)
    aia_files = aia_files[start:end]

    hmi_files = (
        sorted(glob.glob(os.path.join(cfg.hmi_base_dir, "*.fits")))
        if cfg.overlay_hmi
        else []
    )

    # 提前缓存并解析所有射电文件的时间
    radio_cache = []
    for band in cfg.selected_bands:
        band_dir = os.path.join(cfg.radio_base_dir, band)
        rr_dir = (
            os.path.join(band_dir, cfg.rr_dir_suffix)
            if cfg.combine_polarizations
            else band_dir
        )
        ll_dir = (
            os.path.join(band_dir, cfg.ll_dir_suffix)
            if cfg.combine_polarizations
            else None
        )

        rr_files = (
            sorted(glob.glob(os.path.join(rr_dir, "*.fits")))
            if os.path.isdir(rr_dir)
            else []
        )
        ll_files = (
            sorted(glob.glob(os.path.join(ll_dir, "*.fits")))
            if ll_dir and os.path.isdir(ll_dir)
            else []
        )

        if cfg.combine_polarizations and rr_files and ll_files:
            pairs = _match_rr_ll_by_time(
                rr_files, ll_files, cfg.time_tolerance_seconds * 1000
            )
            for rr_path, ll_path in pairs:
                t = parse_radio_time_from_filename(rr_path)
                if t:
                    radio_cache.append(
                        {
                            "path": (rr_path, ll_path),
                            "band": band,
                            "pol": "RR+LL",
                            "time": t,
                        }
                    )
        else:
            files = (
                rr_files
                if rr_files
                else (
                    ll_files
                    if ll_files
                    else glob.glob(os.path.join(band_dir, "*.fits"))
                )
            )
            for rf in files:
                t = parse_radio_time_from_filename(rf)
                if t:
                    radio_cache.append(
                        {
                            "path": rf,
                            "band": band,
                            "pol": cfg.polarization_mode,
                            "time": t,
                        }
                    )

    matched_pairs = []
    for aia_file in aia_files:
        aia_time = parse_aia_time_from_filename(os.path.basename(aia_file))
        if not aia_time:
            continue

        # 匹配最近的 HMI
        best_hmi = None
        if cfg.overlay_hmi and hmi_files:
            hmi_diffs = []
            for hf in hmi_files:
                ht = parse_hmi_time_from_filename(hf)
                if ht:
                    hmi_diffs.append((hf, abs((ht - aia_time).total_seconds())))
            valid_hmis = [x for x in hmi_diffs if x[1] <= cfg.hmi_time_threshold * 3600]
            if valid_hmis:
                best_hmi = min(valid_hmis, key=lambda x: x[1])[0]

        # 归类落在这个 AIA 时间窗口内的所有射电帧
        band_groups = {}
        for rc in radio_cache:
            dt = abs((rc["time"] - aia_time).total_seconds())
            if dt <= cfg.radio_time_threshold:
                band_groups.setdefault(rc["band"], []).append(
                    (rc["path"], rc["pol"], rc["time"], dt)
                )

        if not band_groups:
            continue

        for band in band_groups:
            band_groups[band].sort(key=lambda x: x[2])  # 严格按照时间排序
            band_groups[band] = band_groups[band][: cfg.max_radio_per_band]

        min_count = min(len(v) for v in band_groups.values())
        if min_count == 0:
            continue

        # 横向构建切片，生成序列子任务 (切片结构：{ 频段: [(文件, 偏振, 时间)] })
        tasks_for_aia = []
        for idx in range(min_count):
            slc = {
                band: [band_groups[band][idx][:3]]
                for band in band_groups
                if idx < len(band_groups[band])
            }
            if slc:
                tasks_for_aia.append((idx, slc))

        matched_pairs.append((aia_file, best_hmi, tasks_for_aia))

    return matched_pairs


# ============================================================
# 12. 核心处理与绘图逻辑
# ============================================================


def process_aia_group(
    aia_file: str,
    hmi_file: str | None,
    sub_tasks: list[tuple[int, dict]],
    task_index: int,
    total_tasks: int,
    cfg: Config,
    color_cache: list,
    fit_diagnostics_rows: list[dict] | None = None,
):
    """
    处理单个 AIA 文件及其对应的所有时间切片绘图任务。

    参数
    ----------
    aia_file   : str
        AIA FITS 文件完整路径。
    hmi_file   : Optional[str]
        HMI FITS 文件完整路径，若无则传入 None。
    sub_tasks  : List[Tuple[int, Dict]]
        时间切片列表，每个元素为 (索引, {波段: [(文件路径, 偏振, 时间), ...]}).
    task_index : int
        当前任务序号（从 1 开始，用于打印进度）。
    total_tasks: int
        任务总数。
    cfg        : Config
        全局配置对象。
    color_cache: List
        颜色缓存列表，用于图例颜色一致性。

    功能描述
    ----------
    - 加载 AIA 图像并裁剪/扩充到用户设定 ROI。
    - 遍历每个时间切片，对各个射电波段执行：数据提取、高斯拟合、坐标重投影、平滑及等值线绘制。
    - 若启用 HMI，将其重投影到 AIA 坐标系并绘制磁图等值线。
    - 添加图例、标题，保存图像到输出目录。
    """
    print(f"\n处理 AIA 文件 [{task_index}/{total_tasks}]: {os.path.basename(aia_file)}")

    try:
        aia_map = sunpy.map.Map(aia_file)
    except Exception as e:
        print(f"  读取 AIA 失败: {e}")
        return

    aia_cutout = _get_padded_aia_map(aia_map, cfg)
    aia_data = aia_cutout.data
    extent_arcsec = [
        aia_cutout.bottom_left_coord.Tx.value,
        aia_cutout.top_right_coord.Tx.value,
        aia_cutout.bottom_left_coord.Ty.value,
        aia_cutout.top_right_coord.Ty.value,
    ]

    # 【核心：遍历时间切片，每一帧生成一张图】
    for sub_index, single_slice_bands in sub_tasks:
        print(f"  -> 绘制序列帧 {sub_index + 1}/{len(sub_tasks)}")

        fig, ax = plt.subplots(figsize=(10, 10))

        # --- 1. 绘制 AIA 底图 ---
        # 提取当前的 colormap，并强制将无数据的 NaN 区域（即扩充的深空画布）渲染为纯黑
        my_cmap = plt.get_cmap(cfg.aia_cmap).copy()
        my_cmap.set_bad(color="black")

        # 【核心修复】：加入 norm=mcolors.LogNorm(...)，使用对数缩放！
        ax.imshow(
            aia_data,
            cmap=my_cmap,
            norm=mcolors.LogNorm(vmin=cfg.aia_vmin, vmax=cfg.aia_vmax),
            origin="lower",
            extent=extent_arcsec,
        )

        # 同时也把坐标轴的背景底色设为黑，作为双重保险
        ax.set_facecolor("black")

        ax.set_xlabel("Solar X (arcsec)")
        ax.set_ylabel("Solar Y (arcsec)")
        ax.tick_params(colors=cfg.style.tick_color)

        ax.set_xlim([extent_arcsec[0], extent_arcsec[1]])
        ax.set_ylim([extent_arcsec[2], extent_arcsec[3]])

        rsun_pix = aia_cutout.rsun_obs.to(u.arcsec).value
        circle = plt.Circle(
            (aia_cutout.center.Tx.value, aia_cutout.center.Ty.value),
            rsun_pix,
            fill=False,
            color=cfg.style.limb_color,
            lw=cfg.style.limb_lw,
            alpha=cfg.style.limb_alpha,
        )
        ax.add_patch(circle)

        # --- 2. 处理并叠加 HMI ---
        if hmi_file and cfg.overlay_hmi:
            try:
                process_hmi_for_overlay(hmi_file, aia_cutout.wcs, cfg, ax)
            except Exception as e:
                print(f"  处理 HMI 失败: {e}")

        legend_elements = []
        bands_used = set()
        first_radio_time = None

        # --- 3. 提取并遍历当前切片的波段数据 ---
        def _band_freq(item):
            m = re.search(r"(\d+\.?\d*)MHz", item[0])
            return float(m.group(1)) if m else 0.0

        sorted_bands = sorted(single_slice_bands.items(), key=_band_freq)

        for band_label, file_list in sorted_bands:
            band_idx = (
                cfg.selected_bands.index(band_label)
                if band_label in cfg.selected_bands
                else 0
            )
            search_bl = (
                band_label if "." in band_label else band_label.replace("MHz", ".0MHz")
            )
            color_main, _ = get_band_color(search_bl, band_idx, cfg, color_cache)

            # 解析数据结构：(文件路径, 偏振模式, 射电时间)
            for file_item, polarization, radio_time in file_list:
                if first_radio_time is None and radio_time:
                    first_radio_time = radio_time

                # 对应匹配对中的元组和字符串解包
                if (
                    cfg.combine_polarizations
                    and polarization == "RR+LL"
                    and isinstance(file_item, tuple)
                ):
                    rr_path, ll_path = file_item
                    rr_data, ra_map, dec_map, rr_header, _ = extract_radio_2d_data(
                        rr_path, cfg.radio_use_float32, cfg
                    )
                    ll_data, _, _, _, _ = extract_radio_2d_data(
                        ll_path, cfg.radio_use_float32, cfg
                    )
                    if rr_data is None or ll_data is None:
                        continue
                    rr_bg_files = find_background_files_for_current_radio(
                        rr_path, band_label, "RR", cfg
                    )
                    ll_bg_files = find_background_files_for_current_radio(
                        ll_path, band_label, "LL", cfg
                    )
                    rr_bg = build_radio_background_map(rr_bg_files, cfg)
                    ll_bg = build_radio_background_map(ll_bg_files, cfg)
                    rr_sub, rr_bg_diag = subtract_radio_background(rr_data, rr_bg, cfg)
                    ll_sub, ll_bg_diag = subtract_radio_background(ll_data, ll_bg, cfg)
                    if cfg.debug_mode:
                        for bg_diag in (rr_bg_diag, ll_bg_diag):
                            if bg_diag.get("warning"):
                                print(f"    [背景扣除] {bg_diag['warning']}")
                    radio_data = _combine_polarization_data(rr_data, ll_data, cfg)
                    radio_fit_data = _combine_polarization_data(rr_sub, ll_sub, cfg)
                    radio_header2 = rr_header
                    source_file = (rr_path, ll_path)
                else:
                    # 单偏振模式时，file_item 就是单文件的路径（字符串）
                    radio_data, ra_map, dec_map, radio_header2, _ = (
                        extract_radio_2d_data(file_item, cfg.radio_use_float32, cfg)
                    )
                    if radio_data is None:
                        continue
                    bg_files = find_background_files_for_current_radio(
                        file_item, band_label, polarization, cfg
                    )
                    bg_map = build_radio_background_map(bg_files, cfg)
                    radio_fit_data, bg_diag = subtract_radio_background(
                        radio_data, bg_map, cfg
                    )
                    if cfg.debug_mode and bg_diag.get("warning"):
                        print(f"    [背景扣除] {bg_diag['warning']}")
                    source_file = file_item

                # 重新投影
                fit_result = reproject_radio_via_gaussian_fit(
                    radio_data,
                    ra_map,
                    dec_map,
                    aia_cutout,
                    cfg,
                    radio_header2,
                    radio_fit_data=radio_fit_data,
                    fit_label=f"{band_label} {polarization}",
                )
                if fit_result is None:
                    continue
                model_data = fit_result.model
                if fit_diagnostics_rows is not None:
                    fit_diagnostics_rows.append(
                        _diagnostic_row_from_fit(
                            fit_result,
                            aia_cutout,
                            radio_time,
                            band_label,
                            polarization,
                            source_file,
                            cfg,
                        )
                    )

                if cfg.show_radio_contours:
                    contour_data = model_data
                    if cfg.contour_smooth_sigma > 0:
                        contour_data = smooth_for_contour(
                            contour_data, cfg.contour_smooth_sigma
                        )

                    levels = compute_contour_levels(contour_data, cfg)
                    if not levels:
                        continue

                    # 绘制射电等值线
                    ax.contour(
                        contour_data,
                        levels=levels,
                        extent=extent_arcsec,
                        colors=[color_main],
                        linewidths=cfg.contour_linewidths,
                        alpha=cfg.contour_alpha,
                        origin="lower",
                    )

                can_draw_center = fit_result.quality_flag not in {
                    "low_snr",
                    "unphysical_size",
                    "mask_too_small",
                    "fit_failed",
                }
                if cfg.mark_radio_center and can_draw_center:
                    center_x, center_y = fit_result.center_arcsec
                    if (
                        cfg.draw_raw_vs_bg_center_shift
                        and fit_result.center_pixel_raw is not None
                    ):
                        raw_x, raw_y = _world_arcsec_from_pixel(
                            aia_cutout, fit_result.center_pixel_raw
                        )
                        if raw_x is not None and raw_y is not None:
                            ax.scatter(
                                [raw_x],
                                [raw_y],
                                marker=".",
                                s=20,
                                color="lightgray",
                                alpha=0.8,
                            )
                            ax.annotate(
                                "",
                                xy=(center_x, center_y),
                                xytext=(raw_x, raw_y),
                                arrowprops={
                                    "arrowstyle": "->",
                                    "color": "lightgray",
                                    "lw": 0.8,
                                    "alpha": 0.8,
                                },
                            )
                    ax.scatter(
                        [center_x],
                        [center_y],
                        marker=cfg.radio_center_marker,
                        s=cfg.radio_center_size,
                        color=color_main,
                        linewidths=cfg.radio_center_linewidth,
                    )
                    if cfg.label_radio_center:
                        ax.annotate(
                            "Gaussian-fit center",
                            xy=(center_x, center_y),
                            xytext=(4, 0),
                            textcoords="offset points",
                            fontsize=8,
                            color=color_main,
                            va="center",
                            ha="left",
                        )
                elif cfg.debug_mode and fit_result.quality_flag != "ok":
                    print(
                        f"    [质量控制] {band_label} {polarization}: "
                        f"{fit_result.quality_flag}，跳过中心绘制"
                    )

                # 添加图例
                disp_bl = band_label
                if disp_bl not in bands_used:
                    bands_used.add(disp_bl)
                    if cfg.combine_polarizations and cfg.polarization_mode == "RR+LL":
                        lbl = (
                            f"{disp_bl} (RR+LL sum)"
                            if not cfg.weighted_average
                            else f"{disp_bl} (RR+LL)"
                        )
                    else:
                        lbl = f"{disp_bl} ({cfg.polarization_mode})"
                    legend_elements.append(
                        Line2D([0], [0], color=color_main, lw=2, label=lbl)
                    )

        # --- 4. 标题、图例与保存 ---
        if cfg.combine_polarizations and cfg.polarization_mode == "RR+LL":
            polar_display = (
                "RR+LL (sum)"
                if not cfg.weighted_average
                else f"RR+LL (w={cfg.rr_weight}:{cfg.ll_weight})"
            )
        else:
            polar_display = cfg.polarization_mode

        title_time = (
            first_radio_time.strftime("%Y-%m-%d %H:%M:%S") + " UT"
            if first_radio_time
            else "Unknown Time"
        )
        ax.set_title(
            f"AIA 171 Å + Radio ({polar_display}) + HMI\n{title_time}",
            color=cfg.style.title_color,
        )

        if legend_elements:
            ax.legend(
                handles=legend_elements,
                loc="upper right",
                facecolor=cfg.style.legend_face,
                edgecolor="none",
                labelcolor=cfg.style.legend_text,
                framealpha=cfg.style.legend_alpha,
            )

        if cfg.save_figure:
            if first_radio_time:
                ts_str = first_radio_time.strftime("%Y%m%d_%H%M%S")
            else:
                aia_t = parse_aia_time_from_filename(aia_file)
                ts_str = (
                    aia_t.strftime("%Y%m%d_%H%M%S") if aia_t else f"task_{task_index}"
                )

            if cfg.combine_polarizations and cfg.polarization_mode == "RR+LL":
                polar_suffix = (
                    "RR_LL_sum"
                    if not cfg.weighted_average
                    else f"RR{cfg.rr_weight:.1f}_LL{cfg.ll_weight:.1f}"
                )
            else:
                polar_suffix = cfg.polarization_mode

            out_name = f"{ts_str}_{polar_suffix}_seq{sub_index + 1:02d}.png"
            saved_path = os.path.join(cfg.output_dir, out_name)

            plt.savefig(
                saved_path,
                dpi=cfg.dpi,
                bbox_inches="tight",
                facecolor=cfg.style.figure_bg,
            )
            print(f"  保存图像: {saved_path}")

        plt.close(fig)


# ============================================================
# 13. 新增函数：process_hmi_for_overlay
# ============================================================


def process_hmi_for_overlay(hmi_file: str, target_wcs, cfg: Config, ax):
    """读取 HMI 数据，投影到 AIA 坐标系并绘制磁图等值线"""
    try:
        hmi_map = sunpy.map.Map(hmi_file)
    except Exception as e:
        print(f"  读取 HMI 失败: {e}")
        return

    # 重投影到 AIA 网格
    hmi_reprojected = hmi_map.reproject_to(target_wcs)
    hmi_data = hmi_reprojected.data

    # 平滑
    if cfg.hmi_sigma > 0:
        hmi_data = gaussian_filter(hmi_data, sigma=cfg.hmi_sigma)

    # 正负水平
    pos_data = np.where(hmi_data > cfg.hmi_threshold_gauss, hmi_data, 0)
    neg_data = np.where(hmi_data < -cfg.hmi_threshold_gauss, -hmi_data, 0)

    extent = [
        target_wcs.pixel_to_world(0, 0).Tx.value,
        target_wcs.pixel_to_world(target_wcs.array_shape[1], 0).Tx.value,
        target_wcs.pixel_to_world(0, 0).Ty.value,
        target_wcs.pixel_to_world(0, target_wcs.array_shape[0]).Ty.value,
    ]
    if cfg.hmi_levels_gauss:
        # 使用指定级别
        pos_levels = cfg.hmi_levels_gauss
        neg_levels = cfg.hmi_levels_gauss
    else:
        # 自动：最大最小值的百分比
        max_val = np.max(pos_data)
        min_val = np.max(neg_data)
        pos_levels = [max_val * 0.5]
        neg_levels = [min_val * 0.5]

    ax.contour(
        pos_data,
        levels=pos_levels,
        extent=extent,
        colors=cfg.style.hmi_pos_color,
        linewidths=cfg.style.hmi_lw,
        alpha=cfg.style.hmi_alpha,
        origin="lower",
    )
    ax.contour(
        neg_data,
        levels=neg_levels,
        extent=extent,
        colors=cfg.style.hmi_neg_color,
        linewidths=cfg.style.hmi_lw,
        alpha=cfg.style.hmi_alpha,
        origin="lower",
    )


# ============================================================
# 14. 新增函数：波段颜色
# ============================================================


def get_band_color(
    band_label: str, band_idx: int, cfg: Config, color_cache: list | None = None
) -> tuple[str, str]:
    """获取波段主颜色和填充颜色"""
    if cfg.band_colors_dict and band_label in cfg.band_colors_dict:
        return cfg.band_colors_dict[band_label]
    idx = band_idx % len(cfg.default_colors)
    return cfg.default_colors[idx]


# ============================================================
# 15. 主程序入口
# ============================================================

# ---- 主流程：创建配置、构建匹配任务、串行处理所有 AIA 文件 ----
if __name__ == "__main__":
    cfg = Config()
    os.makedirs(cfg.output_dir, exist_ok=True)
    color_cache = []
    fit_diagnostics_rows: list[dict] = []

    # 构建匹配对
    matched = build_matched_pairs(cfg)
    print(f"共构建 {len(matched)} 个 AIA 任务")

    # 串行处理（或可用线程池，但可能导致 FITS 读取冲突）
    for i, (aia_file, hmi_file, sub_tasks) in enumerate(matched):
        process_aia_group(
            aia_file,
            hmi_file,
            sub_tasks,
            i + 1,
            len(matched),
            cfg,
            color_cache,
            fit_diagnostics_rows,
        )
    diagnostics_path = write_fit_diagnostics_csv(fit_diagnostics_rows, cfg)
    if diagnostics_path:
        print(f"保存拟合诊断 CSV: {diagnostics_path}")
