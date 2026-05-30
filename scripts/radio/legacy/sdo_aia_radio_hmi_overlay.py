# 模块用途: 生成 AIA、射电源和可选 HMI 的多仪器叠加图。
# 主要输入: AIA/HMI FITS 图像、射电源数据、偏振信息和配准参数。
# 主要输出/运行说明: 输出带等值线和偏振标记的综合诊断图，适合耀斑源区对比。
# ruff: noqa: E402, I001
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
import math  # noqa: E402
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
    find_objects,
    gaussian_filter,
    label,
)
from scipy.optimize import curve_fit  # noqa: E402

from scripts.radio.core.radio_coordinates import (
    normalize_roi_bounds_arcsec,
)  # noqa: E402
from solar_toolkit.path_config import apply_config_to_object  # noqa: E402

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
    radio_base_dir: str = r"<PROJECT_ROOT>\2025\20250124\RS_0447-0450"
    aia_base_dir: str = r"<PROJECT_ROOT>\2025\20250124\AIA\171\1"
    hmi_base_dir: str = r"<PROJECT_ROOT>\2025\20250124\AIA\hmi\1"
    output_dir: str = r"<PROJECT_ROOT>\2025\20250124\AIA_RS_HMI\test"
    aia_wavelength: str = "171"

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

    # ── 高斯拟合稳健性配置 ─────────────────────────────────────
    enable_gaussian_overlay: bool = True
    draw_low_quality_gaussian_contours: bool = False

    fit_use_source_mask: bool = True
    fit_snr_threshold: float = 5.0
    fit_grow_snr_threshold: float = 3.0
    fit_peak_fraction_threshold: float = 0.40
    fit_grow_peak_fraction_threshold: float = 0.22
    fit_mask_target_min_pixels: int = 18
    fit_mask_target_max_pixels: int = 260
    fit_peak_fraction_threshold_min: float = 0.25
    fit_peak_fraction_threshold_max: float = 0.62
    fit_peak_fraction_threshold_step: float = 0.03
    fit_min_mask_pixels: int = 12
    fit_mask_dilation_pixels: int = 1

    gaussian_fit_use_roi: bool = True
    gaussian_fit_roi_padding_pixels: int = 4
    gaussian_fit_max_pixels: int = 400
    gaussian_fit_normalize_data: bool = True
    gaussian_fit_fallback_to_moment: bool = True
    gaussian_fit_maxfev: int = 8000
    gaussian_fit_verbose: bool = False

    fit_background_model: str = "constant"  # "none", "constant", "plane"
    max_sigma_fraction: float = 0.18
    max_fwhm_arcsec: float = 1800.0
    max_center_peak_distance_arcsec: float = 300.0
    gaussian_max_center_peak_distance_fraction_of_fwhm: float = 0.5

    gaussian_valid_only_for_overlay: bool = True
    gaussian_valid_only_for_trajectory: bool = True
    gaussian_allow_moment_fallback_for_trajectory: bool = False

    background_use_for_mask: bool = True
    background_mesh_size: int = 96
    background_mesh_step: int = 48
    background_sigma_clip: float = 3.0
    background_sigma_clip_iters: int = 3
    background_min_valid_pixels: int = 20
    background_rms_floor: float = 1e-12

    save_gaussian_diagnostics: bool = True
    gaussian_diagnostics_csv: str = "aia_radio_gaussian_fit_diagnostics.csv"

    gaussian_quality_requirements: dict = field(
        default_factory=lambda: {
            "require_quality_ok": True,
            "max_fwhm_arcsec": 1800.0,
            "max_center_peak_distance_arcsec": 300.0,
            "min_snr": 5.0,
            "max_residual_rms_fraction": 0.8,
        }
    )

    gaussian_per_band_params: dict = field(
        default_factory=lambda: {
            "149MHz": {
                "fit_peak_fraction_threshold": 0.38,
                "fit_peak_fraction_threshold_min": 0.25,
                "fit_peak_fraction_threshold_max": 0.55,
                "fit_mask_target_min_pixels": 18,
                "fit_mask_target_max_pixels": 180,
                "gaussian_fit_roi_padding_pixels": 4,
                "gaussian_fit_max_pixels": 350,
                "max_sigma_fraction": 0.17,
                "fit_background_model": "constant",
                "fit_mask_dilation_pixels": 1,
            },
            "164MHz": {
                "fit_peak_fraction_threshold": 0.38,
                "fit_peak_fraction_threshold_min": 0.25,
                "fit_peak_fraction_threshold_max": 0.55,
                "fit_mask_target_min_pixels": 18,
                "fit_mask_target_max_pixels": 180,
                "gaussian_fit_roi_padding_pixels": 4,
                "gaussian_fit_max_pixels": 350,
                "max_sigma_fraction": 0.17,
                "fit_background_model": "constant",
                "fit_mask_dilation_pixels": 1,
            },
            "190MHz": {
                "fit_peak_fraction_threshold": 0.40,
                "fit_peak_fraction_threshold_min": 0.25,
                "fit_peak_fraction_threshold_max": 0.60,
                "fit_mask_target_min_pixels": 18,
                "fit_mask_target_max_pixels": 220,
                "gaussian_fit_roi_padding_pixels": 4,
                "gaussian_fit_max_pixels": 400,
                "max_sigma_fraction": 0.18,
                "fit_background_model": "constant",
                "fit_mask_dilation_pixels": 1,
            },
            "205MHz": {
                "fit_peak_fraction_threshold": 0.40,
                "fit_peak_fraction_threshold_min": 0.25,
                "fit_peak_fraction_threshold_max": 0.60,
                "fit_mask_target_min_pixels": 18,
                "fit_mask_target_max_pixels": 240,
                "gaussian_fit_roi_padding_pixels": 4,
                "gaussian_fit_max_pixels": 400,
                "max_sigma_fraction": 0.18,
                "fit_background_model": "constant",
                "fit_mask_dilation_pixels": 1,
            },
            "223MHz": {
                "fit_peak_fraction_threshold": 0.42,
                "fit_peak_fraction_threshold_min": 0.25,
                "fit_peak_fraction_threshold_max": 0.65,
                "fit_mask_target_min_pixels": 16,
                "fit_mask_target_max_pixels": 180,
                "gaussian_fit_roi_padding_pixels": 3,
                "gaussian_fit_max_pixels": 320,
                "max_sigma_fraction": 0.16,
                "fit_background_model": "plane",
                "fit_mask_dilation_pixels": 1,
            },
            "238MHz": {
                "fit_peak_fraction_threshold": 0.42,
                "fit_peak_fraction_threshold_min": 0.25,
                "fit_peak_fraction_threshold_max": 0.65,
                "fit_mask_target_min_pixels": 16,
                "fit_mask_target_max_pixels": 180,
                "gaussian_fit_roi_padding_pixels": 3,
                "gaussian_fit_max_pixels": 320,
                "max_sigma_fraction": 0.16,
                "fit_background_model": "plane",
                "fit_mask_dilation_pixels": 1,
            },
        }
    )

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
    roi_bounds_arcsec: dict | None = None
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

    def __post_init__(self):
        apply_config_to_object(self, "sdo_aia_radio_hmi_overlay")


def _apply_values_to_config(cfg: Config, values: dict | None) -> Config:
    for key, value in (values or {}).items():
        if key == "style" and isinstance(value, dict):
            for style_key, style_value in value.items():
                if hasattr(cfg.style, style_key):
                    setattr(cfg.style, style_key, style_value)
        elif hasattr(cfg, key):
            setattr(cfg, key, value)
    return cfg


def apply_aia_radio_hmi_user_config(cfg: Config, user_config: dict | None) -> Config:
    """Apply grouped user config to the legacy Config dataclass."""
    if not user_config:
        return cfg
    for section in (
        "paths",
        "aia",
        "hmi",
        "radio",
        "wcs_reproject",
        "gaussian",
        "display",
        "output",
        "runtime",
    ):
        _apply_values_to_config(cfg, user_config.get(section))
    _apply_values_to_config(
        cfg,
        {
            key: value
            for key, value in user_config.items()
            if not isinstance(value, dict)
        },
    )
    return cfg


@dataclass
class GaussianFitResult:
    model: np.ndarray
    gaussian_only_model: np.ndarray
    center_pixel: tuple[float, float]
    center_arcsec: tuple[float, float]
    sigma_pixel: tuple[float, float]
    theta_rad: float
    amplitude: float
    background_level: float | None
    noise_sigma: float | None
    snr: float | None
    residual_rms: float | None
    quality_flag: str
    covariance: np.ndarray | None
    mask_pixel_count: int
    source_file: str | None = None


@dataclass
class GaussianReprojectResult:
    model: np.ndarray
    center_pixel: tuple[float, float]
    center_arcsec: tuple[float, float]
    sigma_pixel: tuple[float, float]
    theta_rad: float
    amplitude: float
    covariance: np.ndarray | None
    quality_flag: str = "ok"
    quality_flag_detail: str = ""
    overlay_valid: bool = True
    trajectory_valid: bool = True
    snr: float | None = None
    residual_rms: float | None = None
    mask_pixel_count: int = 0
    fwhm_major_arcsec: float | None = None
    fwhm_minor_arcsec: float | None = None
    center_peak_distance_arcsec: float | None = None
    source_file: str | None = None
    radio_fit_result: GaussianFitResult | None = None


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


def _unravel_2d_index(
    flat_index: int | np.integer, shape: tuple[int, ...]
) -> tuple[int, int]:
    coords = np.asarray(np.unravel_index(int(flat_index), shape), dtype=np.intp)
    return int(coords[0]), int(coords[1])


def _true_indices(mask: np.ndarray) -> IntArray:
    mask_bool = np.asarray(mask, dtype=np.bool_)
    return np.asarray(np.nonzero(mask_bool)[0], dtype=np.intp)


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
    return elliptical_gaussian_2d(xy, A, x0, y0, sigma_x, sigma_y, theta) + b0


def elliptical_gaussian_2d_with_plane_bg(
    xy, A, x0, y0, sigma_x, sigma_y, theta, b0, bx, by
):
    x, y = xy
    return (
        elliptical_gaussian_2d(xy, A, x0, y0, sigma_x, sigma_y, theta)
        + b0
        + bx * x
        + by * y
    )


def gaussian_only_from_popt(xy, popt, background_model):
    return elliptical_gaussian_2d(xy, *popt[:6])


def estimate_background_noise(data, source_exclusion_mask=None):
    work = np.asarray(data, dtype=np.float64)
    valid_mask = np.isfinite(work)
    if source_exclusion_mask is not None:
        valid_mask &= ~np.asarray(source_exclusion_mask, dtype=np.bool_)
    finite_data = work[valid_mask]
    if finite_data.size == 0:
        return np.nan, np.nan
    background_level = float(np.nanmedian(finite_data))
    mad = float(np.nanmedian(np.abs(finite_data - background_level)))
    noise_sigma = 1.4826 * mad
    if not np.isfinite(noise_sigma) or noise_sigma <= 0:
        noise_sigma = float(np.nanstd(finite_data))
    return background_level, noise_sigma


def _robust_median_mad(values):
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return np.nan, np.nan
    med = float(np.nanmedian(arr))
    mad = float(np.nanmedian(np.abs(arr - med)))
    rms = 1.4826 * mad
    if not np.isfinite(rms) or rms <= 0:
        rms = float(np.nanstd(arr))
    return med, rms


def _sigma_clip_values(values, sigma=3.0, iters=3):
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return arr
    for _ in range(max(int(iters), 0)):
        med, rms = _robust_median_mad(arr)
        if not np.isfinite(med) or not np.isfinite(rms) or rms <= 0:
            break
        keep = np.abs(arr - med) <= float(sigma) * rms
        if np.count_nonzero(keep) == arr.size:
            break
        arr = arr[keep]
        if arr.size == 0:
            break
    return arr


def _safe_rms_map(rms_map):
    safe = np.asarray(rms_map, dtype=np.float64).copy()
    finite_positive = safe[np.isfinite(safe) & (safe > 0)]
    fallback = float(np.nanmedian(finite_positive)) if finite_positive.size else 1.0
    if not np.isfinite(fallback) or fallback <= 0:
        fallback = 1.0
    safe[~np.isfinite(safe) | (safe <= 0)] = fallback
    return np.maximum(safe, 1e-12)


def _mesh_values_to_map(mesh_y, mesh_x, mesh_values, shape, fill_value):
    ny, nx = shape
    if len(mesh_values) == 0:
        return np.full(shape, fill_value, dtype=np.float64)
    mesh_y = np.asarray(mesh_y, dtype=np.float64)
    mesh_x = np.asarray(mesh_x, dtype=np.float64)
    values = np.asarray(mesh_values, dtype=np.float64)
    valid = np.isfinite(mesh_y) & np.isfinite(mesh_x) & np.isfinite(values)
    mesh_y = mesh_y[valid]
    mesh_x = mesh_x[valid]
    values = values[valid]
    if values.size == 0:
        return np.full(shape, fill_value, dtype=np.float64)
    y_unique = np.unique(mesh_y)
    x_unique = np.unique(mesh_x)
    grid = np.full((len(y_unique), len(x_unique)), np.nan, dtype=np.float64)
    y_lookup = {v: i for i, v in enumerate(y_unique)}
    x_lookup = {v: i for i, v in enumerate(x_unique)}
    for yv, xv, val in zip(mesh_y, mesh_x, values, strict=False):
        grid[y_lookup[yv], x_lookup[xv]] = val
    global_fill = float(np.nanmedian(values)) if values.size else fill_value
    if not np.isfinite(global_fill):
        global_fill = fill_value
    grid = np.where(np.isfinite(grid), grid, global_fill)
    x_pixels = np.arange(nx, dtype=np.float64)
    y_pixels = np.arange(ny, dtype=np.float64)
    row_interp = np.empty((grid.shape[0], nx), dtype=np.float64)
    for i in range(grid.shape[0]):
        row_interp[i, :] = np.interp(x_pixels, x_unique, grid[i, :])
    out = np.empty((ny, nx), dtype=np.float64)
    for j in range(nx):
        out[:, j] = np.interp(y_pixels, y_unique, row_interp[:, j])
    return out


def estimate_background_rms_mesh(data, cfg, source_mask=None):
    work = np.asarray(data, dtype=np.float64)
    finite = np.isfinite(work)
    finite_values = work[finite]
    global_bg, global_rms = _robust_median_mad(finite_values)
    if not np.isfinite(global_bg):
        global_bg = 0.0
    if not np.isfinite(global_rms) or global_rms <= 0:
        global_rms = 1.0
    mesh_size = max(int(cfg.get("background_mesh_size", 96)), 1)
    mesh_step = max(int(cfg.get("background_mesh_step", mesh_size)), 1)
    min_valid = max(int(cfg.get("background_min_valid_pixels", 20)), 1)
    exclude = np.zeros(work.shape, dtype=np.bool_)
    if source_mask is not None and np.asarray(source_mask).shape == work.shape:
        exclude = np.asarray(source_mask, dtype=np.bool_)
    diagnostics = {
        "background_rms_median": np.nan,
        "background_level_median": np.nan,
        "finite_pixel_count": int(np.count_nonzero(finite)),
        "mesh_count": 0,
        "warning": "",
    }
    if work.ndim != 2 or finite_values.size == 0:
        diagnostics["warning"] = "non_finite_data"
        bg = np.full_like(work, global_bg, dtype=np.float64)
        rms = np.full_like(work, global_rms, dtype=np.float64)
        return bg, _safe_rms_map(rms), diagnostics
    ny, nx = work.shape
    mesh_y, mesh_x, bg_values, rms_values = [], [], [], []
    for y0 in range(0, ny, mesh_step):
        y1 = min(y0 + mesh_size, ny)
        for x0 in range(0, nx, mesh_step):
            x1 = min(x0 + mesh_size, nx)
            box = work[y0:y1, x0:x1]
            valid = np.isfinite(box) & ~exclude[y0:y1, x0:x1]
            clipped = _sigma_clip_values(
                box[valid],
                sigma=float(cfg.get("background_sigma_clip", 3.0)),
                iters=int(cfg.get("background_sigma_clip_iters", 3)),
            )
            if clipped.size < min_valid:
                continue
            bg, rms = _robust_median_mad(clipped)
            if not np.isfinite(bg) or not np.isfinite(rms) or rms <= 0:
                continue
            mesh_y.append(0.5 * (y0 + y1 - 1))
            mesh_x.append(0.5 * (x0 + x1 - 1))
            bg_values.append(bg)
            rms_values.append(rms)
    if not bg_values:
        diagnostics["warning"] = "mesh_insufficient; fallback_global_median_mad"
        background_map = np.full_like(work, global_bg, dtype=np.float64)
        rms_map = np.full_like(work, global_rms, dtype=np.float64)
    else:
        background_map = _mesh_values_to_map(
            mesh_y, mesh_x, bg_values, work.shape, global_bg
        )
        rms_map = _mesh_values_to_map(
            mesh_y, mesh_x, rms_values, work.shape, global_rms
        )
    rms_map = np.maximum(
        _safe_rms_map(rms_map), float(cfg.get("background_rms_floor", 1e-12))
    )
    diagnostics.update(
        {
            "background_rms_median": float(np.nanmedian(rms_map[np.isfinite(rms_map)])),
            "background_level_median": float(
                np.nanmedian(background_map[np.isfinite(background_map)])
            ),
            "mesh_count": int(len(bg_values)),
        }
    )
    return background_map, rms_map, diagnostics


def _select_peak_connected_mask(
    source_mask_bool,
    grow_mask,
    peak_y,
    peak_x,
    use_snr=False,
    snr_map=None,
    work=None,
):
    labeled, _ = label(source_mask_bool)
    peak_label = labeled[peak_y, peak_x]
    if peak_label == 0:
        object_slices = find_objects(labeled)
        if not object_slices:
            main_mask = source_mask_bool
        else:
            labels = np.arange(1, int(labeled.max()) + 1)
            scores = []
            for lab in labels:
                component = labeled == lab
                score_map = snr_map if use_snr and snr_map is not None else work
                score = float(np.nanmax(np.where(component, score_map, np.nan)))
                if not np.isfinite(score):
                    score = float(np.count_nonzero(component))
                scores.append(score)
            peak_label = int(labels[int(np.argmax(scores))]) if scores else 0
            main_mask = np.asarray(labeled == peak_label, dtype=np.bool_)
    else:
        main_mask = np.asarray(labeled == peak_label, dtype=np.bool_)
    if use_snr:
        grown_labels, _ = label(grow_mask)
        grow_label = grown_labels[peak_y, peak_x]
        if grow_label == 0 and peak_label > 0:
            overlap = grown_labels[main_mask]
            overlap = overlap[overlap > 0]
            if overlap.size:
                grow_label = int(np.bincount(overlap).argmax())
        if grow_label > 0:
            main_mask = np.asarray(grown_labels == grow_label, dtype=np.bool_)
    return np.asarray(main_mask, dtype=np.bool_)


def create_source_mask(data, cfg, background_map=None, rms_map=None):
    work = np.asarray(data, dtype=np.float64)
    finite_data = work[np.isfinite(work)]
    diagnostics = {
        "quality_flag": "ok",
        "background_level": np.nan,
        "noise_sigma": np.nan,
        "threshold": np.nan,
        "peak": np.nan,
        "mask_pixel_count": 0,
        "source_snr_peak": np.nan,
        "source_snr_mean": np.nan,
        "background_rms_median": np.nan,
        "background_level_median": np.nan,
        "mask_method": "raw_threshold",
        "fit_peak_fraction_threshold_used": np.nan,
        "fit_peak_fraction_candidate_counts": "",
    }
    if finite_data.size == 0:
        diagnostics["quality_flag"] = "non_finite_data"
        return None, diagnostics
    peak = float(np.max(finite_data))
    if not np.isfinite(peak):
        diagnostics["quality_flag"] = "non_finite_data"
        return None, diagnostics
    use_snr = False
    snr_map = None
    if (
        cfg.get("background_use_for_mask", True)
        and background_map is not None
        and rms_map is not None
    ):
        bg = np.asarray(background_map, dtype=np.float64)
        rms = _safe_rms_map(rms_map)
        use_snr = bg.shape == work.shape and rms.shape == work.shape
    else:
        bg = rms = None
    finite_peak_work = np.where(np.isfinite(work), work, -np.inf)
    peak_y, peak_x = _unravel_2d_index(int(np.argmax(finite_peak_work)), work.shape)
    base_peak_fraction = float(cfg.get("fit_peak_fraction_threshold", 0.40))
    grow_peak_fraction = float(cfg.get("fit_grow_peak_fraction_threshold", 0.22))
    min_peak_fraction = float(
        cfg.get("fit_peak_fraction_threshold_min", base_peak_fraction)
    )
    max_peak_fraction = float(
        cfg.get("fit_peak_fraction_threshold_max", base_peak_fraction)
    )
    step_peak_fraction = abs(float(cfg.get("fit_peak_fraction_threshold_step", 0.03)))
    min_peak_fraction, max_peak_fraction = sorted(
        (min_peak_fraction, max_peak_fraction)
    )
    base_peak_fraction = min(
        max(base_peak_fraction, min_peak_fraction), max_peak_fraction
    )
    grow_peak_fraction = min(max(grow_peak_fraction, 0.0), base_peak_fraction)
    target_min_pixels = int(cfg.get("fit_mask_target_min_pixels", 18))
    target_max_pixels = int(cfg.get("fit_mask_target_max_pixels", 260))
    if target_max_pixels < target_min_pixels:
        target_min_pixels, target_max_pixels = target_max_pixels, target_min_pixels
    if use_snr:
        snr_map = (work - bg) / rms
        fit_threshold = float(cfg.get("fit_snr_threshold", 5.0))
        grow_threshold = float(cfg.get("fit_grow_snr_threshold", 3.0))
        diagnostics.update(
            {
                "background_level": float(np.nanmedian(bg[np.isfinite(bg)])),
                "noise_sigma": float(np.nanmedian(rms[np.isfinite(rms) & (rms > 0)])),
                "threshold": fit_threshold,
                "background_rms_median": float(
                    np.nanmedian(rms[np.isfinite(rms) & (rms > 0)])
                ),
                "background_level_median": float(np.nanmedian(bg[np.isfinite(bg)])),
                "mask_method": "snr_mesh",
            }
        )
    else:
        background_level, noise_sigma = estimate_background_noise(work)
        if not np.isfinite(noise_sigma) or noise_sigma <= 0:
            noise_sigma = max(float(np.std(finite_data)), 1e-12)
        diagnostics.update(
            {
                "background_level": background_level,
                "noise_sigma": noise_sigma,
                "background_rms_median": noise_sigma,
                "background_level_median": background_level,
                "mask_method": "raw_threshold",
            }
        )

    def build_mask_for_peak_fraction(peak_fraction):
        intensity_threshold = float(peak_fraction * peak)
        grow_intensity_threshold = float(grow_peak_fraction * peak)
        if use_snr:
            core_mask = (
                np.isfinite(snr_map)
                & (snr_map >= fit_threshold)
                & np.isfinite(work)
                & (work > intensity_threshold)
            )
            grow_mask_local = (
                np.isfinite(snr_map)
                & (snr_map >= grow_threshold)
                & np.isfinite(work)
                & (work > grow_intensity_threshold)
            )
            threshold_used = fit_threshold
        else:
            noise_sigma = diagnostics["noise_sigma"]
            threshold_used = max(
                float(cfg.get("fit_snr_threshold", 5.0)) * noise_sigma,
                intensity_threshold,
            )
            core_mask = np.isfinite(work) & (work > threshold_used)
            grow_threshold_used = max(
                float(cfg.get("fit_grow_snr_threshold", 3.0)) * noise_sigma,
                grow_intensity_threshold,
            )
            grow_mask_local = np.isfinite(work) & (work > grow_threshold_used)
        if not np.any(core_mask):
            return None, 0, threshold_used
        candidate_mask = _select_peak_connected_mask(
            core_mask,
            grow_mask_local,
            peak_y,
            peak_x,
            use_snr=use_snr,
            snr_map=snr_map,
            work=work,
        )
        dilation_pixels = int(cfg.get("fit_mask_dilation_pixels", 1))
        if dilation_pixels > 0:
            candidate_mask = binary_dilation(candidate_mask, iterations=dilation_pixels)
        return (
            np.asarray(candidate_mask, dtype=np.bool_),
            int(np.count_nonzero(candidate_mask)),
            threshold_used,
        )

    if step_peak_fraction <= 0:
        candidate_fractions = [base_peak_fraction]
    else:
        candidate_fractions = []
        frac = min_peak_fraction
        while frac <= max_peak_fraction + 1e-12:
            candidate_fractions.append(round(frac, 10))
            frac += step_peak_fraction
        if candidate_fractions[-1] < max_peak_fraction - 1e-12:
            candidate_fractions.append(max_peak_fraction)
    candidates = []
    for candidate_fraction in sorted(set(candidate_fractions)):
        candidate_mask, candidate_count, candidate_threshold = (
            build_mask_for_peak_fraction(candidate_fraction)
        )
        candidates.append(
            {
                "fraction": float(candidate_fraction),
                "mask": candidate_mask,
                "count": int(candidate_count),
                "threshold": float(candidate_threshold),
            }
        )
    target_mid_pixels = 0.5 * (target_min_pixels + target_max_pixels)
    in_target_candidates = [
        item
        for item in candidates
        if item["mask"] is not None
        and target_min_pixels <= item["count"] <= target_max_pixels
    ]
    usable_candidates = [
        item
        for item in candidates
        if item["mask"] is not None
        and item["count"] >= int(cfg.get("fit_min_mask_pixels", 12))
    ]
    nonempty_candidates = [
        item for item in candidates if item["mask"] is not None and item["count"] > 0
    ]
    if in_target_candidates:
        selected = min(
            in_target_candidates,
            key=lambda item: (
                abs(item["count"] - target_mid_pixels),
                abs(item["fraction"] - base_peak_fraction),
            ),
        )
    elif usable_candidates:
        selected = min(
            usable_candidates,
            key=lambda item: (
                abs(item["count"] - target_min_pixels),
                abs(item["fraction"] - base_peak_fraction),
            ),
        )
    elif nonempty_candidates:
        selected = max(nonempty_candidates, key=lambda item: item["count"])
    else:
        selected = {
            "fraction": base_peak_fraction,
            "mask": None,
            "count": 0,
            "threshold": np.nan,
        }
    diagnostics.update(
        {
            "fit_peak_fraction_threshold_used": float(selected["fraction"]),
            "fit_peak_fraction_candidate_counts": ";".join(
                f"{item['fraction']:.3f}:{item['count']}" for item in candidates
            ),
            "threshold": selected["threshold"],
            "peak": peak,
            "mask_pixel_count": int(selected["count"]),
        }
    )
    main_mask = selected["mask"]
    if main_mask is None or not np.any(main_mask):
        diagnostics["quality_flag"] = "mask_too_small"
        return None, diagnostics
    if use_snr and snr_map is not None:
        source_snr = snr_map[main_mask & np.isfinite(snr_map)]
        diagnostics["source_snr_peak"] = (
            float(np.nanmax(source_snr)) if source_snr.size else np.nan
        )
        diagnostics["source_snr_mean"] = (
            float(np.nanmean(source_snr)) if source_snr.size else np.nan
        )
    if int(selected["count"]) < int(cfg.get("fit_min_mask_pixels", 12)):
        diagnostics["quality_flag"] = "mask_too_small"
    return np.asarray(main_mask, dtype=np.bool_), diagnostics


def _gaussian_fit_diag_defaults(cfg):
    return {
        "gaussian_fit_method": "skipped",
        "roi_used": False,
        "roi_shape": "",
        "fit_pixel_count_before_limit": 0,
        "fit_pixel_count_after_limit": 0,
        "maxfev": int(cfg.get("gaussian_fit_maxfev", 8000)),
        "initial_center_pixel": "",
        "initial_sigma_x_pixel": np.nan,
        "initial_sigma_y_pixel": np.nan,
        "normalization_scale": np.nan,
    }


def _roi_slices_from_mask(mask, shape, padding):
    if mask is None or not np.any(mask):
        return slice(0, shape[0]), slice(0, shape[1]), False
    ys, xs = np.nonzero(mask)
    if ys.size == 0 or xs.size == 0:
        return slice(0, shape[0]), slice(0, shape[1]), False
    pad = max(int(padding), 0)
    y0 = max(int(np.min(ys)) - pad, 0)
    y1 = min(int(np.max(ys)) + pad + 1, shape[0])
    x0 = max(int(np.min(xs)) - pad, 0)
    x1 = min(int(np.max(xs)) + pad + 1, shape[1])
    roi_used = (y0 > 0) or (x0 > 0) or (y1 < shape[0]) or (x1 < shape[1])
    return slice(y0, y1), slice(x0, x1), roi_used


def _weighted_moment_initial_guess(x, y, z, bg, nx, ny, peak_x, peak_y, cfg):
    weights = np.asarray(z, dtype=np.float64) - bg
    finite = np.isfinite(weights) & np.isfinite(x) & np.isfinite(y)
    weights = np.where(finite & (weights > 0), weights, 0.0)
    total = float(np.sum(weights))
    sigma_min = 1.0
    sigma_max = max(2.0, float(cfg.get("max_sigma_fraction", 0.18)) * max(nx, ny))
    if total > 0:
        cx = float(np.sum(x * weights) / total)
        cy = float(np.sum(y * weights) / total)
        var_x = float(np.sum(((x - cx) ** 2) * weights) / total)
        var_y = float(np.sum(((y - cy) ** 2) * weights) / total)
        sigma_x = math.sqrt(max(var_x, sigma_min**2))
        sigma_y = math.sqrt(max(var_y, sigma_min**2))
    else:
        cx, cy = float(peak_x), float(peak_y)
        sigma_x = max(min(nx, ny) / 12.0, sigma_min)
        sigma_y = sigma_x
    sigma_x = float(np.clip(sigma_x, sigma_min, sigma_max))
    sigma_y = float(np.clip(sigma_y, sigma_min, sigma_max))
    if not np.isfinite(cx) or not np.isfinite(cy):
        cx, cy = float(peak_x), float(peak_y)
    return cx, cy, sigma_x, sigma_y


def _limit_fit_pixels(x, y, z, peak_x, peak_y, max_pixels):
    count = int(z.size)
    max_pixels = int(max_pixels or 0)
    if max_pixels <= 0 or count <= max_pixels:
        return x, y, z, count, count
    intensity_rank = np.asarray(z, dtype=np.float64)
    finite_intensity = intensity_rank[np.isfinite(intensity_rank)]
    fill = float(np.nanmin(finite_intensity)) if finite_intensity.size else 0.0
    intensity_rank = np.where(np.isfinite(intensity_rank), intensity_rank, fill)
    dist2 = (x - peak_x) ** 2 + (y - peak_y) ** 2
    order = np.lexsort((dist2, -intensity_rank))
    keep = np.sort(order[:max_pixels])
    return x[keep], y[keep], z[keep], count, int(keep.size)


def _gaussian_quality_config(cfg):
    quality_cfg = dict(cfg.get("gaussian_quality_requirements", {}) or {})
    quality_cfg.setdefault("require_quality_ok", True)
    quality_cfg.setdefault("max_fwhm_arcsec", cfg.get("max_fwhm_arcsec", 1800.0))
    quality_cfg.setdefault(
        "max_center_peak_distance_arcsec",
        cfg.get("max_center_peak_distance_arcsec", 300.0),
    )
    quality_cfg.setdefault("min_snr", cfg.get("fit_snr_threshold", 5.0))
    quality_cfg.setdefault("max_residual_rms_fraction", 0.8)
    return quality_cfg


def _set_gaussian_failure_diag(
    cfg: dict, source_file, reason: str, mask_diag: dict | None = None, **extra
) -> None:
    mask_diag = mask_diag or {}
    cfg["_last_gaussian_failure_diag"] = {
        "source_file": source_file or "",
        "reason": reason,
        "quality_flag": reason,
        "quality_flag_detail": extra.get("quality_flag_detail", ""),
        "finite_pixel_count": extra.get("finite_pixel_count", ""),
        "mask_pixel_count": mask_diag.get(
            "mask_pixel_count", extra.get("mask_pixel_count", 0)
        ),
        "background_rms_median": mask_diag.get("background_rms_median", np.nan),
        "background_level_median": mask_diag.get("background_level_median", np.nan),
        "fit_peak_fraction_threshold_used": mask_diag.get(
            "fit_peak_fraction_threshold_used",
            extra.get("fit_peak_fraction_threshold_used", np.nan),
        ),
        "fit_peak_fraction_candidate_counts": mask_diag.get(
            "fit_peak_fraction_candidate_counts",
            extra.get("fit_peak_fraction_candidate_counts", ""),
        ),
        "gaussian_fit_method": extra.get("gaussian_fit_method", "skipped"),
        "roi_used": extra.get("roi_used", False),
        "roi_shape": extra.get("roi_shape", ""),
    }


def _fit_failure_warning(source_file, quality_flag, detail=""):
    name = os.path.basename(source_file) if source_file else "radio image"
    suffix = f" / {detail}" if detail else ""
    if detail or str(quality_flag) not in {"mask_too_small", "low_snr"}:
        warnings.warn(
            f"Gaussian fit skipped for {name}: reason={quality_flag}{suffix}",
            stacklevel=2,
        )


def pixel_to_data_coord(
    x_pix, y_pix, extent, shape, origin="upper"
) -> tuple[float, float]:
    left, right, bottom, top = map(float, extent)
    ny, nx = shape
    dx = (right - left) / max(float(nx), 1.0)
    dy = (top - bottom) / max(float(ny), 1.0)
    x_arcsec = left + (float(x_pix) + 0.5) * dx
    if origin == "upper":
        y_arcsec = top - (float(y_pix) + 0.5) * dy
    elif origin == "lower":
        y_arcsec = bottom + (float(y_pix) + 0.5) * dy
    else:
        raise ValueError(f"Unsupported image origin: {origin}")
    return float(x_arcsec), float(y_arcsec)


def data_coord_to_pixel(
    x_arcsec, y_arcsec, extent, shape, origin="upper"
) -> tuple[float, float]:
    left, right, bottom, top = map(float, extent)
    ny, nx = shape
    dx = (right - left) / max(float(nx), 1.0)
    dy = (top - bottom) / max(float(ny), 1.0)
    x_pix = (float(x_arcsec) - left) / dx - 0.5
    if origin == "upper":
        y_pix = (top - float(y_arcsec)) / dy - 0.5
    elif origin == "lower":
        y_pix = (float(y_arcsec) - bottom) / dy - 0.5
    else:
        raise ValueError(f"Unsupported image origin: {origin}")
    return float(x_pix), float(y_pix)


def coordinate_roundtrip_error_pixel(
    x_pix, y_pix, extent, shape, origin="upper"
) -> float:
    x_arcsec, y_arcsec = pixel_to_data_coord(x_pix, y_pix, extent, shape, origin)
    x_back, y_back = data_coord_to_pixel(x_arcsec, y_arcsec, extent, shape, origin)
    return float(math.hypot(float(x_pix) - x_back, float(y_pix) - y_back))


def _attach_gaussian_fit_metadata(result, cfg, mask_diag, fit_input_type, fit_meta):
    result.fit_input_type = fit_input_type
    result.background_rms_median = mask_diag.get("background_rms_median", np.nan)
    result.background_level_median = mask_diag.get("background_level_median", np.nan)
    result.fit_peak_fraction_threshold_used = mask_diag.get(
        "fit_peak_fraction_threshold_used", np.nan
    )
    result.fit_peak_fraction_candidate_counts = mask_diag.get(
        "fit_peak_fraction_candidate_counts", ""
    )
    result.source_snr_peak = mask_diag.get("source_snr_peak", np.nan)
    result.source_snr_mean = mask_diag.get("source_snr_mean", np.nan)
    for key, value in fit_meta.items():
        setattr(result, key, value)
    return result


def _update_gaussian_quality(fit_result, extent, img_shape, cfg):
    ny, nx = img_shape
    dx = abs((extent[1] - extent[0]) / max(nx, 1))
    dy = abs((extent[3] - extent[2]) / max(ny, 1))
    width = 2.355 * fit_result.sigma_pixel[0] * dx
    height = 2.355 * fit_result.sigma_pixel[1] * dy
    fit_result.fwhm_major_arcsec = float(max(width, height))
    fit_result.fwhm_minor_arcsec = float(min(width, height))
    raw_center = getattr(fit_result, "raw_center_arcsec", None)
    fit_result.center_peak_distance_arcsec = np.nan
    if raw_center is not None:
        cx, cy = fit_result.center_arcsec
        rx, ry = raw_center
        fit_result.center_peak_distance_arcsec = float(math.hypot(cx - rx, cy - ry))
    quality_cfg = _gaussian_quality_config(cfg)
    is_moment_fallback = fit_result.quality_flag == "moment_fallback"
    detail = getattr(fit_result, "quality_flag_detail", "")
    valid = True
    if fit_result.fwhm_major_arcsec > float(quality_cfg.get("max_fwhm_arcsec", 1800.0)):
        fit_result.quality_flag = "unphysical_size"
        detail = "skipped_large_fwhm"
        valid = False
    max_dist = float(quality_cfg.get("max_center_peak_distance_arcsec", 300.0))
    if np.isfinite(fit_result.center_peak_distance_arcsec):
        max_dist = min(
            max_dist,
            float(cfg.get("gaussian_max_center_peak_distance_fraction_of_fwhm", 0.5))
            * fit_result.fwhm_minor_arcsec,
        )
        if fit_result.center_peak_distance_arcsec > max_dist:
            fit_result.quality_flag = "center_far_from_peak"
            detail = "center_far_from_peak"
            valid = False
    min_snr = float(quality_cfg.get("min_snr", cfg.get("fit_snr_threshold", 5.0)))
    if (
        fit_result.snr is not None
        and np.isfinite(fit_result.snr)
        and fit_result.snr < min_snr
    ):
        if not is_moment_fallback:
            fit_result.quality_flag = "low_snr"
        detail = "low_snr"
        valid = False
    max_resid = float(quality_cfg.get("max_residual_rms_fraction", 0.8))
    if (
        fit_result.residual_rms is not None
        and np.isfinite(fit_result.residual_rms)
        and np.isfinite(fit_result.amplitude)
        and abs(fit_result.amplitude) > 0
        and fit_result.residual_rms / abs(fit_result.amplitude) > max_resid
    ):
        fit_result.quality_flag = "high_residual"
        detail = "high_residual"
        valid = False
    if is_moment_fallback and quality_cfg.get("require_quality_ok", True):
        valid = False
        detail = detail or "moment_fallback"
    if quality_cfg.get("require_quality_ok", True) and fit_result.quality_flag != "ok":
        valid = False
    fit_result.quality_flag_detail = detail
    fit_result.overlay_valid = (
        bool(valid) if cfg.get("gaussian_valid_only_for_overlay", True) else True
    )
    fit_result.trajectory_valid = (
        bool(valid) if cfg.get("gaussian_valid_only_for_trajectory", True) else True
    )
    if is_moment_fallback and not cfg.get(
        "gaussian_allow_moment_fallback_for_trajectory", False
    ):
        fit_result.trajectory_valid = False
    return bool(fit_result.overlay_valid)


def fit_elliptical_gaussian_on_radio_image(
    data,
    extent,
    cfg,
    source_file=None,
    background_map=None,
    rms_map=None,
    fit_input_type="raw",
    image_origin=None,
):
    work = np.asarray(data, dtype=np.float64)
    image_origin = image_origin or cfg.get("_current_radio_image_origin", "upper")
    cfg.pop("_last_gaussian_failure_diag", None)
    fit_meta = _gaussian_fit_diag_defaults(cfg)
    if work.ndim != 2 or not np.any(np.isfinite(work)):
        _set_gaussian_failure_diag(cfg, source_file, "non_finite_data", **fit_meta)
        _fit_failure_warning(source_file, "non_finite_data")
        return None
    finite_work = work[np.isfinite(work)]
    ny, nx = work.shape
    X, Y = np.meshgrid(np.arange(nx, dtype=np.float64), np.arange(ny, dtype=np.float64))
    source_mask, mask_diag = create_source_mask(
        work, cfg, background_map=background_map, rms_map=rms_map
    )
    if cfg.get("fit_use_source_mask", True) and source_mask is None:
        reason = mask_diag.get("quality_flag", "mask_too_small")
        _set_gaussian_failure_diag(
            cfg,
            source_file,
            reason,
            mask_diag,
            finite_pixel_count=finite_work.size,
            **fit_meta,
        )
        _fit_failure_warning(source_file, reason)
        return None
    fit_mask = (
        np.asarray(source_mask, dtype=np.bool_) & np.isfinite(work)
        if cfg.get("fit_use_source_mask", True)
        else np.isfinite(work)
    )
    if cfg.get("gaussian_fit_use_roi", True):
        y_slice, x_slice, roi_used = _roi_slices_from_mask(
            source_mask if source_mask is not None else fit_mask,
            work.shape,
            cfg.get("gaussian_fit_roi_padding_pixels", 4),
        )
    else:
        y_slice, x_slice, roi_used = slice(0, ny), slice(0, nx), False
    x_offset = int(x_slice.start or 0)
    y_offset = int(y_slice.start or 0)
    roi_work = work[y_slice, x_slice]
    roi_fit_mask = fit_mask[y_slice, x_slice]
    roi_ny, roi_nx = roi_work.shape
    fit_meta["roi_used"] = bool(roi_used)
    fit_meta["roi_shape"] = f"{roi_ny}x{roi_nx}"
    X_roi, Y_roi = np.meshgrid(
        np.arange(roi_nx, dtype=np.float64),
        np.arange(roi_ny, dtype=np.float64),
    )
    xy_fit = (X_roi[roi_fit_mask].ravel(), Y_roi[roi_fit_mask].ravel())
    z_fit = roi_work[roi_fit_mask].ravel()
    finite = np.isfinite(z_fit) & np.isfinite(xy_fit[0]) & np.isfinite(xy_fit[1])
    xy_fit = (xy_fit[0][finite], xy_fit[1][finite])
    z_fit = z_fit[finite]
    if z_fit.size < int(cfg.get("fit_min_mask_pixels", 12)):
        _set_gaussian_failure_diag(
            cfg, source_file, "mask_too_small", mask_diag, **fit_meta
        )
        _fit_failure_warning(source_file, "mask_too_small")
        return None
    local_bg = float(mask_diag.get("background_level", np.nan))
    if not np.isfinite(local_bg):
        local_bg = float(np.nanmedian(z_fit))
    local_peak = float(np.nanmax(z_fit))
    local_peak_idx = int(np.nanargmax(z_fit))
    peak_x = float(xy_fit[0][local_peak_idx])
    peak_y = float(xy_fit[1][local_peak_idx])
    xy_x, xy_y, z_fit, before_limit, after_limit = _limit_fit_pixels(
        xy_fit[0],
        xy_fit[1],
        z_fit,
        peak_x,
        peak_y,
        cfg.get("gaussian_fit_max_pixels", 400),
    )
    xy_fit = (xy_x, xy_y)
    fit_meta["fit_pixel_count_before_limit"] = int(before_limit)
    fit_meta["fit_pixel_count_after_limit"] = int(after_limit)
    mask_diag["mask_pixel_count"] = int(after_limit)
    if z_fit.size < int(cfg.get("fit_min_mask_pixels", 12)):
        _set_gaussian_failure_diag(
            cfg, source_file, "mask_too_small", mask_diag, **fit_meta
        )
        _fit_failure_warning(source_file, "mask_too_small")
        return None
    A0 = max(local_peak - local_bg, 1e-12)
    cx0, cy0, sigma_x0, sigma_y0 = _weighted_moment_initial_guess(
        xy_fit[0], xy_fit[1], z_fit, local_bg, roi_nx, roi_ny, peak_x, peak_y, cfg
    )
    fit_meta["initial_center_pixel"] = f"{cx0 + x_offset:.3f},{cy0 + y_offset:.3f}"
    fit_meta["initial_sigma_x_pixel"] = float(sigma_x0)
    fit_meta["initial_sigma_y_pixel"] = float(sigma_y0)
    if cfg.get("gaussian_fit_normalize_data", True):
        centered = z_fit - local_bg
        finite_centered = centered[np.isfinite(centered)]
        norm_scale = (
            float(np.nanpercentile(np.abs(finite_centered), 99))
            if finite_centered.size
            else np.nan
        )
        if not np.isfinite(norm_scale) or norm_scale <= 0:
            norm_scale = max(abs(A0), 1.0)
        z_curve = centered / norm_scale
        A0_curve = max(A0 / norm_scale, 1e-6)
        bg0_curve = 0.0
        bg_abs_limit = 10.0
    else:
        norm_scale = 1.0
        z_curve = z_fit
        A0_curve = A0
        bg0_curve = local_bg
        bg_abs_limit = max(abs(local_peak) * 10.0, abs(local_bg) * 10.0, 1.0)
    fit_meta["normalization_scale"] = float(norm_scale)
    background_model = cfg.get("fit_background_model", "constant")
    model_map = {
        "none": elliptical_gaussian_2d,
        "constant": elliptical_gaussian_2d_with_constant_bg,
        "plane": elliptical_gaussian_2d_with_plane_bg,
    }
    if background_model not in model_map:
        background_model = "constant"
    model_func = model_map[background_model]
    sigma_upper = max(
        2.0, float(cfg.get("max_sigma_fraction", 0.18)) * max(roi_nx, roi_ny)
    )
    amp_upper = max(abs(A0_curve) * 10.0, 2.0)
    slope_limit = bg_abs_limit / max(roi_nx, roi_ny, 1)
    p0 = [A0_curve, float(cx0), float(cy0), sigma_x0, sigma_y0, 0.0]
    lower = [0.0, 0.0, 0.0, 0.5, 0.5, -np.pi / 2]
    upper = [amp_upper, roi_nx - 1, roi_ny - 1, sigma_upper, sigma_upper, np.pi / 2]
    if background_model == "constant":
        p0 += [bg0_curve]
        lower += [-bg_abs_limit]
        upper += [bg_abs_limit]
    elif background_model == "plane":
        p0 += [bg0_curve, 0.0, 0.0]
        lower += [-bg_abs_limit, -slope_limit, -slope_limit]
        upper += [bg_abs_limit, slope_limit, slope_limit]
    p0_arr = np.minimum(
        np.maximum(np.asarray(p0, dtype=float), np.asarray(lower, dtype=float)),
        np.asarray(upper, dtype=float),
    )
    maxfev = int(cfg.get("gaussian_fit_maxfev", 8000))
    fit_meta["maxfev"] = maxfev
    fit_exception = None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            popt, pcov = curve_fit(
                model_func,
                xy_fit,
                z_curve,
                p0=p0_arr,
                bounds=(np.asarray(lower, dtype=float), np.asarray(upper, dtype=float)),
                maxfev=maxfev,
            )
        fit_meta["gaussian_fit_method"] = "curve_fit"
    except Exception as exc:
        fit_exception = exc
        if not cfg.get("gaussian_fit_fallback_to_moment", True):
            _set_gaussian_failure_diag(
                cfg,
                source_file,
                "fit_failed_no_fallback",
                mask_diag,
                quality_flag_detail=str(exc),
                **fit_meta,
            )
            _fit_failure_warning(source_file, "fit_failed_no_fallback", str(exc))
            return None
        popt = p0_arr.copy()
        pcov = None
        fit_meta["gaussian_fit_method"] = "moment_fallback"
    X_local_full = X - x_offset
    Y_local_full = Y - y_offset
    model_curve = model_func((X_local_full, Y_local_full), *popt).reshape(work.shape)
    model_total = (
        model_curve * norm_scale + local_bg
        if cfg.get("gaussian_fit_normalize_data", True)
        else model_curve
    )
    gaussian_curve = gaussian_only_from_popt(
        (X_local_full, Y_local_full), popt, background_model
    ).reshape(work.shape)
    gaussian_only_model = (
        gaussian_curve * norm_scale
        if cfg.get("gaussian_fit_normalize_data", True)
        else gaussian_curve
    )
    if not np.all(np.isfinite(model_total[fit_mask])):
        _set_gaussian_failure_diag(
            cfg, source_file, "non_finite_fit_result", mask_diag, **fit_meta
        )
        _fit_failure_warning(source_file, "non_finite_fit_result")
        return None
    x0_fit, y0_fit = float(popt[1]) + x_offset, float(popt[2]) + y_offset
    sigma_x, sigma_y = abs(float(popt[3])), abs(float(popt[4]))
    center_arcsec = pixel_to_data_coord(
        x0_fit, y0_fit, extent, work.shape, origin=image_origin
    )
    raw_peak_arcsec = pixel_to_data_coord(
        peak_x + x_offset, peak_y + y_offset, extent, work.shape, origin=image_origin
    )
    residual = work[fit_mask] - model_total[fit_mask]
    residual_rms = float(np.sqrt(np.nanmean(residual**2))) if residual.size else np.nan
    if (
        cfg.get("background_use_for_mask", True)
        and rms_map is not None
        and np.asarray(rms_map).shape == work.shape
    ):
        safe_rms = _safe_rms_map(rms_map)
        noise_values = safe_rms[fit_mask & np.isfinite(safe_rms)]
        noise_sigma = float(np.nanmedian(noise_values)) if noise_values.size else np.nan
    else:
        _, noise_sigma = estimate_background_noise(work, fit_mask)
    if not np.isfinite(noise_sigma) or noise_sigma <= 0:
        noise_sigma = mask_diag.get("noise_sigma", np.nan)
    amplitude_curve = float(popt[0])
    amplitude_original = (
        amplitude_curve * norm_scale
        if cfg.get("gaussian_fit_normalize_data", True)
        else amplitude_curve
    )
    snr = (
        float(amplitude_original / noise_sigma)
        if np.isfinite(noise_sigma) and noise_sigma > 0
        else np.nan
    )
    quality_flag = (
        "moment_fallback"
        if fit_meta["gaussian_fit_method"] == "moment_fallback"
        else "ok"
    )
    result = GaussianFitResult(
        model=model_total,
        gaussian_only_model=gaussian_only_model,
        center_pixel=(x0_fit, y0_fit),
        center_arcsec=center_arcsec,
        sigma_pixel=(sigma_x, sigma_y),
        theta_rad=float(popt[5]),
        amplitude=amplitude_original,
        background_level=(
            float(local_bg + popt[6] * norm_scale)
            if len(popt) >= 7 and cfg.get("gaussian_fit_normalize_data", True)
            else (float(popt[6]) if len(popt) >= 7 else None)
        ),
        noise_sigma=float(noise_sigma) if np.isfinite(noise_sigma) else None,
        snr=snr if np.isfinite(snr) else None,
        residual_rms=residual_rms if np.isfinite(residual_rms) else None,
        quality_flag=quality_flag,
        covariance=pcov,
        mask_pixel_count=int(after_limit),
        source_file=source_file,
    )
    result.source_mask = source_mask
    result.image_origin = image_origin
    result.image_extent = extent
    result.raw_center_arcsec = raw_peak_arcsec
    result.coordinate_roundtrip_error_pixel = coordinate_roundtrip_error_pixel(
        x0_fit, y0_fit, extent, work.shape, origin=image_origin
    )
    if fit_meta["gaussian_fit_method"] == "moment_fallback":
        result.reason = "fit_failed_moment_fallback"
        result.quality_flag_detail = str(fit_exception or "curve_fit_failed")
    result = _attach_gaussian_fit_metadata(
        result, cfg, mask_diag, fit_input_type, fit_meta
    )
    _update_gaussian_quality(result, extent, work.shape, cfg)
    return result


def _normalise_band_key(band_label) -> str:
    text = str(band_label or "").strip()
    if not text:
        return ""
    if text.endswith("MHz"):
        return text
    try:
        value = float(text)
        if abs(value - round(value)) < 1e-6:
            return f"{int(round(value))}MHz"
        return f"{value:g}MHz"
    except Exception:
        return text


def config_for_gaussian_band(cfg: Config, band_label=None) -> dict:
    base = dict(vars(cfg))
    per_band = getattr(cfg, "gaussian_per_band_params", {}) or {}
    candidates = []
    key = _normalise_band_key(band_label)
    if key:
        candidates.append(key)
        candidates.append(key.replace(".0MHz", "MHz"))
        candidates.append(key.replace("MHz", ""))
    for candidate in candidates:
        if candidate in per_band and isinstance(per_band[candidate], dict):
            base.update(per_band[candidate])
            break
    base["_gaussian_band_label"] = band_label
    return base


GAUSSIAN_DIAGNOSTIC_FIELDS = [
    "source_file",
    "time",
    "band",
    "polarization",
    "quality_flag",
    "quality_flag_detail",
    "center_x_arcsec",
    "center_y_arcsec",
    "center_x_pixel",
    "center_y_pixel",
    "sigma_x_pixel",
    "sigma_y_pixel",
    "fwhm_major_arcsec",
    "fwhm_minor_arcsec",
    "amplitude",
    "snr",
    "residual_rms",
    "mask_pixel_count",
    "fit_peak_fraction_threshold_used",
    "fit_peak_fraction_candidate_counts",
    "background_rms_median",
    "background_level_median",
    "gaussian_fit_method",
    "roi_used",
    "roi_shape",
]


def save_gaussian_diagnostics_row(row, output_dir, cfg):
    try:
        os.makedirs(output_dir, exist_ok=True)
        csv_path = os.path.join(
            output_dir,
            getattr(
                cfg,
                "gaussian_diagnostics_csv",
                "aia_radio_gaussian_fit_diagnostics.csv",
            ),
        )
        write_header = not os.path.exists(csv_path)
        with open(csv_path, "a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=GAUSSIAN_DIAGNOSTIC_FIELDS,
                extrasaction="ignore",
            )
            if write_header:
                writer.writeheader()
            writer.writerow(
                {name: row.get(name, "") for name in GAUSSIAN_DIAGNOSTIC_FIELDS}
            )
    except Exception as exc:
        if getattr(cfg, "debug_mode", False):
            print(f"    [高斯诊断] CSV 写入失败: {exc}")


def _gaussian_diagnostics_row(
    fit_result,
    cfg_dict,
    source_file=None,
    band=None,
    polarization=None,
    radio_time=None,
    bg_diag=None,
):
    bg_diag = bg_diag or {}
    time_str = (
        radio_time.isoformat()
        if hasattr(radio_time, "isoformat")
        else (radio_time or "")
    )
    if fit_result is None:
        fail = cfg_dict.get("_last_gaussian_failure_diag", {})
        return {
            "source_file": source_file or fail.get("source_file", ""),
            "time": time_str,
            "band": band or "",
            "polarization": polarization or "",
            "quality_flag": fail.get("quality_flag", fail.get("reason", "fit_failed")),
            "quality_flag_detail": fail.get(
                "quality_flag_detail", fail.get("reason", "")
            ),
            "mask_pixel_count": fail.get("mask_pixel_count", 0),
            "fit_peak_fraction_threshold_used": fail.get(
                "fit_peak_fraction_threshold_used", ""
            ),
            "fit_peak_fraction_candidate_counts": fail.get(
                "fit_peak_fraction_candidate_counts", ""
            ),
            "background_rms_median": bg_diag.get(
                "background_rms_median", fail.get("background_rms_median", "")
            ),
            "background_level_median": bg_diag.get(
                "background_level_median", fail.get("background_level_median", "")
            ),
            "gaussian_fit_method": fail.get("gaussian_fit_method", "skipped"),
            "roi_used": fail.get("roi_used", ""),
            "roi_shape": fail.get("roi_shape", ""),
        }
    return {
        "source_file": source_file or getattr(fit_result, "source_file", ""),
        "time": time_str,
        "band": band or "",
        "polarization": polarization or "",
        "quality_flag": getattr(fit_result, "quality_flag", ""),
        "quality_flag_detail": getattr(fit_result, "quality_flag_detail", ""),
        "center_x_arcsec": fit_result.center_arcsec[0],
        "center_y_arcsec": fit_result.center_arcsec[1],
        "center_x_pixel": fit_result.center_pixel[0],
        "center_y_pixel": fit_result.center_pixel[1],
        "sigma_x_pixel": fit_result.sigma_pixel[0],
        "sigma_y_pixel": fit_result.sigma_pixel[1],
        "fwhm_major_arcsec": getattr(fit_result, "fwhm_major_arcsec", ""),
        "fwhm_minor_arcsec": getattr(fit_result, "fwhm_minor_arcsec", ""),
        "amplitude": getattr(fit_result, "amplitude", ""),
        "snr": getattr(fit_result, "snr", ""),
        "residual_rms": getattr(fit_result, "residual_rms", ""),
        "mask_pixel_count": getattr(fit_result, "mask_pixel_count", ""),
        "fit_peak_fraction_threshold_used": getattr(
            fit_result, "fit_peak_fraction_threshold_used", ""
        ),
        "fit_peak_fraction_candidate_counts": getattr(
            fit_result, "fit_peak_fraction_candidate_counts", ""
        ),
        "background_rms_median": bg_diag.get(
            "background_rms_median", getattr(fit_result, "background_rms_median", "")
        ),
        "background_level_median": bg_diag.get(
            "background_level_median",
            getattr(fit_result, "background_level_median", ""),
        ),
        "gaussian_fit_method": getattr(fit_result, "gaussian_fit_method", ""),
        "roi_used": getattr(fit_result, "roi_used", ""),
        "roi_shape": getattr(fit_result, "roi_shape", ""),
    }


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
    source_file: str | None = None,
    band_label: str | None = None,
    polarization: str | None = None,
    radio_time: datetime | None = None,
) -> GaussianReprojectResult | None:
    ny_a, nx_a = aia_cutout_map.data.shape
    ny_r, nx_r = radio_data.shape
    x_pix = np.arange(nx_r, dtype=float)
    y_pix = np.arange(ny_r, dtype=float)

    gaussian_cfg = config_for_gaussian_band(cfg, band_label)
    background_map, rms_map, bg_diag = estimate_background_rms_mesh(
        radio_data, gaussian_cfg
    )
    radio_fit = fit_elliptical_gaussian_on_radio_image(
        radio_data,
        extent=[0, nx_r - 1, 0, ny_r - 1],
        cfg=gaussian_cfg,
        source_file=source_file,
        background_map=background_map,
        rms_map=rms_map,
        fit_input_type="raw",
        image_origin="lower",
    )
    if radio_fit is None:
        if getattr(cfg, "save_gaussian_diagnostics", True):
            save_gaussian_diagnostics_row(
                _gaussian_diagnostics_row(
                    None,
                    gaussian_cfg,
                    source_file=source_file,
                    band=band_label,
                    polarization=polarization,
                    radio_time=radio_time,
                    bg_diag=bg_diag,
                ),
                cfg.output_dir,
                cfg,
            )
        if cfg.debug_mode:
            print(f"    [高斯拟合] 失败或质量不足: {source_file}")
        return None
    if (
        not getattr(radio_fit, "overlay_valid", True)
        and not cfg.draw_low_quality_gaussian_contours
    ):
        if getattr(cfg, "save_gaussian_diagnostics", True):
            save_gaussian_diagnostics_row(
                _gaussian_diagnostics_row(
                    radio_fit,
                    gaussian_cfg,
                    source_file=source_file,
                    band=band_label,
                    polarization=polarization,
                    radio_time=radio_time,
                    bg_diag=bg_diag,
                ),
                cfg.output_dir,
                cfg,
            )
        if cfg.debug_mode:
            print(
                f"    [高斯拟合] 跳过低质量结果: "
                f"quality={radio_fit.quality_flag}, "
                f"detail={getattr(radio_fit, 'quality_flag_detail', '')}"
            )
        return None

    # ---------- 1. 在射电域进行二维椭圆高斯拟合 ----------
    try:
        popt = (
            radio_fit.amplitude,
            radio_fit.center_pixel[0],
            radio_fit.center_pixel[1],
            radio_fit.sigma_pixel[0],
            radio_fit.sigma_pixel[1],
            radio_fit.theta_rad,
        )
        pcov = radio_fit.covariance
    except Exception as e:
        if cfg.debug_mode:
            print(f"    [高斯拟合] 失败: {e}")
        return None

    A_fit, x0_pix, y0_pix, sigma_x_pix, sigma_y_pix, theta_pix = popt
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

    if getattr(cfg, "save_gaussian_diagnostics", True):
        save_gaussian_diagnostics_row(
            _gaussian_diagnostics_row(
                radio_fit,
                gaussian_cfg,
                source_file=source_file,
                band=band_label,
                polarization=polarization,
                radio_time=radio_time,
                bg_diag=bg_diag,
            ),
            cfg.output_dir,
            cfg,
        )

    return GaussianReprojectResult(
        model=model.astype(np.float32),
        center_pixel=(float(c_aia_x), float(c_aia_y)),
        center_arcsec=(
            float(center_world.Tx.to_value(u.arcsec)),
            float(center_world.Ty.to_value(u.arcsec)),
        ),
        sigma_pixel=(float(sigma_aia_x), float(sigma_aia_y)),
        theta_rad=float(theta_aia),
        amplitude=float(A_fit),
        covariance=None if pcov is None else np.asarray(pcov),
        quality_flag=getattr(radio_fit, "quality_flag", "ok"),
        quality_flag_detail=getattr(radio_fit, "quality_flag_detail", ""),
        overlay_valid=getattr(radio_fit, "overlay_valid", True),
        trajectory_valid=getattr(radio_fit, "trajectory_valid", True),
        snr=getattr(radio_fit, "snr", None),
        residual_rms=getattr(radio_fit, "residual_rms", None),
        mask_pixel_count=getattr(radio_fit, "mask_pixel_count", 0),
        fwhm_major_arcsec=getattr(radio_fit, "fwhm_major_arcsec", None),
        fwhm_minor_arcsec=getattr(radio_fit, "fwhm_minor_arcsec", None),
        center_peak_distance_arcsec=getattr(
            radio_fit, "center_peak_distance_arcsec", None
        ),
        source_file=source_file,
        radio_fit_result=radio_fit,
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


def _get_padded_aia_map(
    aia_map: sunpy.map.GenericMap, cfg: Config
) -> sunpy.map.GenericMap:
    """
    精确截取或扩充画布到用户指定的 ROI 范围，
    彻底解决 sunpy.map.submap 在图像边缘的自动截断问题，
    允许在 AIA 没有数据的外太空区域继续绘制射电和 HMI。
    """
    roi = normalize_roi_bounds_arcsec(cfg)
    bl = SkyCoord(
        roi["left"] * u.arcsec,
        roi["bottom"] * u.arcsec,
        frame=aia_map.coordinate_frame,
    )
    tr = SkyCoord(
        roi["right"] * u.arcsec,
        roi["top"] * u.arcsec,
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
                    radio_data = _combine_polarization_data(rr_data, ll_data, cfg)
                    radio_header2 = rr_header
                else:
                    # 单偏振模式时，file_item 就是单文件的路径（字符串）
                    radio_data, ra_map, dec_map, radio_header2, _ = (
                        extract_radio_2d_data(file_item, cfg.radio_use_float32, cfg)
                    )
                    if radio_data is None:
                        continue

                # 重新投影
                if isinstance(file_item, tuple):
                    source_file_for_fit = f"{file_item[0]}|{file_item[1]}"
                else:
                    source_file_for_fit = str(file_item)

                fit_result = reproject_radio_via_gaussian_fit(
                    radio_data,
                    ra_map,
                    dec_map,
                    aia_cutout,
                    cfg,
                    radio_header2,
                    source_file=source_file_for_fit,
                    band_label=band_label,
                    polarization=polarization,
                    radio_time=radio_time,
                )
                if fit_result is None:
                    continue
                if (
                    not fit_result.overlay_valid
                    and not cfg.draw_low_quality_gaussian_contours
                ):
                    continue
                model_data = fit_result.model

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

                if cfg.mark_radio_center:
                    center_x, center_y = fit_result.center_arcsec
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


def test_gaussian_fit_synthetic_source():
    cfg = Config()
    cfg.fit_snr_threshold = 1.0
    cfg.gaussian_quality_requirements["require_quality_ok"] = False
    shape = (96, 128)
    y, x = np.indices(shape, dtype=np.float64)
    x0, y0 = 70.25, 34.75
    data = 2.0 + 80.0 * np.exp(-0.5 * (((x - x0) / 7.0) ** 2 + ((y - y0) / 5.0) ** 2))
    result = fit_elliptical_gaussian_on_radio_image(
        data,
        extent=[0, shape[1] - 1, 0, shape[0] - 1],
        cfg=dict(vars(cfg)),
        source_file="synthetic.fits",
        image_origin="lower",
    )
    assert result is not None
    assert math.hypot(result.center_pixel[0] - x0, result.center_pixel[1] - y0) < 1.0
    return True


# ============================================================
# 15. 主程序入口
# ============================================================


# ---- 主流程：创建配置、构建匹配任务、串行处理所有 AIA 文件 ----
def main(user_config=None):
    cfg = Config()
    cfg = apply_aia_radio_hmi_user_config(cfg, user_config)
    os.makedirs(cfg.output_dir, exist_ok=True)
    color_cache = []

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
        )


if __name__ == "__main__":
    main()
