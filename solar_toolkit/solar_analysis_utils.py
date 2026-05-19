from __future__ import annotations

# 模块用途: 提供太阳物理数据处理的共享工具函数。
# 主要输入: 文件名、FITS 路径、配置参数、SunPy/AstroPy 坐标对象等。
# 主要输出/运行说明: 供其他脚本复用时间解析、文件排序、内存管理和坐标转换能力。
"""
太阳物理数据处理共享工具模块

提供以下核心功能：
1. 时间处理：从文件名提取时间、时间格式转换
2. 文件管理：FITS文件排序、文件匹配
3. 内存管理：智能垃圾回收、内存监控
4. 配置管理：统一参数管理
5. 可视化辅助：颜色映射、坐标转换

作者: Severus
创建时间: 2025-11-23
"""

import datetime  # noqa: E402
import gc  # noqa: E402
import re  # noqa: E402
import time  # noqa: E402
import warnings  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import TYPE_CHECKING, Any  # noqa: E402

if TYPE_CHECKING:
    import astropy.units as u
    import sunpy.map

# ==============================================================================
# 时间处理函数
# ==============================================================================


def extract_time_from_filename(filename: str) -> datetime.datetime:
    """
    从文件名提取时间信息，支持多种格式

    支持格式:
    1. HMI格式: YYYYMMDD_HHMMSS_TAI
    2. AIA格式: YYYY-MM-DDTHH:MM:SSZ 或 YYYY-MM-DDTHHMMSSZ
    3. AIA备选格式: YYYYMMDDTHHMMSS
    4. CSO格式: YYYYMMDDHHMMSS

    Args:
        filename: 文件名

    Returns:
        datetime.datetime: 提取到的时间

    Raises:
        ValueError: 无法从文件名提取时间
    """
    # HMI格式: YYYYMMDD_HHMMSS_TAI
    hmi_match = re.search(r"(\d{8}_\d{6})_TAI", filename)
    if hmi_match:
        time_str = hmi_match.group(1)
        return datetime.datetime.strptime(time_str, "%Y%m%d_%H%M%S")

    # AIA格式1: YYYY-MM-DDTHH:MM:SSZ
    aia_match1 = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)", filename)
    if aia_match1:
        time_str = aia_match1.group(1)
        return datetime.datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ")

    # AIA格式2: YYYY-MM-DDTHHMMSSZ
    aia_match2 = re.search(r"(\d{4}-\d{2}-\d{2}T\d{6}Z)", filename)
    if aia_match2:
        time_str = aia_match2.group(1)
        return datetime.datetime.strptime(time_str, "%Y-%m-%dT%H%M%SZ")

    # AIA备选格式: YYYYMMDDTHHMMSS
    aia_alt_match = re.search(r"(\d{8})T(\d{6})", filename)
    if aia_alt_match:
        time_str = f"{aia_alt_match.group(1)}_{aia_alt_match.group(2)}"
        return datetime.datetime.strptime(time_str, "%Y%m%d_%H%M%S")

    # CSO格式: YYYYMMDDHHMMSS
    cso_match = re.search(r"(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})", filename)
    if cso_match:
        year, month, day, hour, minute, second = cso_match.groups()
        return datetime.datetime(
            int(year), int(month), int(day), int(hour), int(minute), int(second)
        )

    # 通用尝试: 查找任何看起来像时间戳的部分
    time_patterns = [
        (r"(\d{4}-\d{2}-\d{2})", "%Y-%m-%d"),
        (r"(\d{8})", "%Y%m%d"),
    ]

    for pattern, fmt in time_patterns:
        match = re.search(pattern, filename)
        if match:
            try:
                return datetime.datetime.strptime(match.group(1), fmt)
            except ValueError:
                continue

    raise ValueError(f"无法从文件名提取时间：{filename}")


def parse_isot_time(time_str: str) -> datetime.datetime:
    """
    解析ISO格式时间字符串

    Args:
        time_str: ISO格式时间字符串，如 "2024-08-08T19:00:00"

    Returns:
        datetime.datetime: 解析后的时间
    """
    # 支持T分隔或空格分隔
    normalized = time_str.replace("T", " ")
    return datetime.datetime.fromisoformat(normalized)


def format_time_for_display(dt: datetime.datetime) -> str:
    """
    格式化时间为显示格式

    Args:
        dt: 时间对象

    Returns:
        str: 格式化后的时间字符串
    """
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_time_for_filename(dt: datetime.datetime) -> str:
    """
    格式化时间为文件名格式

    Args:
        dt: 时间对象

    Returns:
        str: 文件名格式的时间字符串
    """
    return dt.strftime("%Y%m%d_%H%M%S")


# ==============================================================================
# 文件管理函数
# ==============================================================================


def get_sorted_fits_files(
    input_dir: str, min_size_kb: int = 1
) -> list[tuple[Path, datetime.datetime]]:
    """
    获取目录下所有FITS文件并按时间排序

    Args:
        input_dir: 输入目录路径
        min_size_kb: 最小文件大小（KB），小于此值的文件将被跳过

    Returns:
        List[Tuple[Path, datetime.datetime]]: 排序后的文件列表，每个元素为(文件路径, 时间)
    """
    files = []
    input_path = Path(input_dir)
    for f in input_path.iterdir():
        if f.suffix.lower() == ".fits":
            try:
                if f.stat().st_size < min_size_kb * 1024:
                    warnings.warn(f"跳过空/小文件：{f.name}", stacklevel=2)
                    continue
                file_time = extract_time_from_filename(f.name)
                files.append((f, file_time))
            except ValueError as e:
                warnings.warn(f"跳过文件（时间提取失败：{e}）：{f.name}", stacklevel=2)
            except Exception as e:
                warnings.warn(f"处理文件时出错：{f.name}，错误：{e}", stacklevel=2)

    return sorted(files, key=lambda x: x[1])


def find_closest_file_by_time(
    target_time: datetime.datetime,
    file_list: list[tuple[str, datetime.datetime]],
    max_diff_seconds: float = 3600,
) -> tuple[str, datetime.datetime] | None:
    """
    在文件列表中找到时间最接近目标时间的文件

    Args:
        target_time: 目标时间
        file_list: 文件列表，每个元素为(文件路径, 时间)
        max_diff_seconds: 最大时间差（秒），超过此值返回None

    Returns:
        Optional[Tuple[str, datetime.datetime]]: 最接近的文件，如果无匹配则返回None
    """
    if not file_list:
        return None

    closest_file = min(
        file_list, key=lambda x: abs((x[1] - target_time).total_seconds())
    )
    time_diff = abs((closest_file[1] - target_time).total_seconds())

    if time_diff > max_diff_seconds:
        return None

    return closest_file


def filter_files_by_time_range(
    file_list: list[tuple[str, datetime.datetime]],
    start_time: datetime.datetime,
    end_time: datetime.datetime,
) -> list[tuple[str, datetime.datetime]]:
    """
    按时间范围筛选文件

    Args:
        file_list: 文件列表，每个元素为(文件路径, 时间)
        start_time: 开始时间
        end_time: 结束时间

    Returns:
        List[Tuple[str, datetime.datetime]]: 筛选后的文件列表
    """
    return [(path, time) for path, time in file_list if start_time <= time <= end_time]


# ==============================================================================
# 内存管理函数
# ==============================================================================


def optimized_gc_collect():
    """
    优化的垃圾回收函数

    在适当的时候调用垃圾回收，避免频繁调用导致的性能下降
    """
    if gc.isenabled():
        # 只在内存使用较高时执行完整回收
        import psutil

        memory_percent = psutil.virtual_memory().percent

        if memory_percent > 70:
            gc.collect()
        elif memory_percent > 50 and gc.get_count()[0] > 700:
            # 如果第0代垃圾数量较多，也执行回收
            gc.collect(0)


def safe_delete(variable_names: list[str], locals_dict: dict):
    """
    安全删除变量并立即回收内存

    Args:
        variable_names: 要删除的变量名列表
        locals_dict: 局部变量字典（通常使用locals()）
    """
    for var_name in variable_names:
        if var_name in locals_dict:
            del locals_dict[var_name]

    optimized_gc_collect()


def monitor_memory_usage(description: str = "") -> dict[str, float]:
    """
    监控内存使用情况

    Args:
        description: 描述信息，用于输出

    Returns:
        Dict[str, float]: 内存使用信息
    """
    try:
        import os

        import psutil

        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()

        result = {
            "rss_mb": memory_info.rss / 1024 / 1024,  # 驻留内存
            "vms_mb": memory_info.vms / 1024 / 1024,  # 虚拟内存
            "percent": process.memory_percent(),
        }

        if description:
            print(
                f"{description}: RSS={result['rss_mb']:.1f}MB, "
                f"VMS={result['vms_mb']:.1f}MB, {result['percent']:.1f}%"
            )

        return result
    except ImportError:
        warnings.warn("psutil未安装，无法监控内存使用", stacklevel=2)
        return {}


# ==============================================================================
# AIA数据处理辅助函数
# ==============================================================================


def create_aia_submap(
    aia_map: sunpy.map.GenericMap, roi_bounds: tuple[float, float, float, float]
) -> sunpy.map.GenericMap:
    """
    创建AIA数据的子图区域

    Args:
        aia_map: AIA地图对象
        roi_bounds: 区域边界 (xmin, xmax, ymin, ymax)，单位：角秒

    Returns:
        sunpy.map.GenericMap: 裁剪后的地图
    """
    import astropy.units as u
    from astropy.coordinates import SkyCoord
    from sunpy.coordinates import propagate_with_solar_surface

    tx1, tx2, ty1, ty2 = roi_bounds
    roi_bl_tx, roi_bl_ty = tx1 * u.arcsec, ty1 * u.arcsec
    roi_tr_tx, _unused_roi_tr_ty = tx2 * u.arcsec, ty2 * u.arcsec

    with propagate_with_solar_surface():
        frame = aia_map.coordinate_frame
        bl = SkyCoord(Tx=roi_bl_tx, Ty=roi_bl_ty, frame=frame)
        tr = SkyCoord(Tx=roi_tr_tx, Ty=roi_bl_ty, frame=frame)
        cutout_map = aia_map.submap(bl, top_right=tr)

    return cutout_map


def normalize_aia_exposure(aia_map: sunpy.map.GenericMap) -> sunpy.map.GenericMap:
    """
    归一化AIA数据的曝光时间

    Args:
        aia_map: AIA地图对象

    Returns:
        sunpy.map.GenericMap: 曝光归一化后的地图
    """
    import sunpy.map

    exp_time = aia_map.exposure_time
    if exp_time is not None and exp_time.value > 0:
        normalized_data = aia_map.data / exp_time.value
        return sunpy.map.Map(normalized_data, aia_map.meta)
    else:
        warnings.warn(f"曝光时间无效: {exp_time}，跳过归一化", stacklevel=2)
        return aia_map


def get_aia_wavelength_config(wavelength: int) -> dict[str, Any]:
    """
    获取AIA波段的显示配置

    Args:
        wavelength: 波长值（94, 131, 171, 193, 211, 304）

    Returns:
        Dict[str, Any]: 配置字典，包含cmap, vmin, vmax等
    """
    configs = {
        94: {"cmap": "sdoaia94", "vmin": 0.4, "vmax": 6666},
        131: {"cmap": "sdoaia131", "vmin": 0.7, "vmax": 6666},
        171: {"cmap": "sdoaia171", "vmin": 16, "vmax": 6666},
        193: {"cmap": "sdoaia193", "vmin": 42, "vmax": 6666},
        211: {"cmap": "sdoaia211", "vmin": 18, "vmax": 6666},
        304: {"cmap": "sdoaia304", "vmin": 0.9, "vmax": 2222},
    }

    return configs.get(wavelength, {"cmap": "sdoaia94", "vmin": 1.0, "vmax": 1e4})


def align_maps_to_reference(
    source_map: sunpy.map.GenericMap, target_wcs
) -> sunpy.map.GenericMap:
    """
    将源地图重投影到目标坐标系

    Args:
        source_map: 源地图对象
        target_wcs: 目标坐标系

    Returns:
        sunpy.map.GenericMap: 重投影后的地图
    """
    from sunpy.coordinates import propagate_with_solar_surface

    with propagate_with_solar_surface():
        aligned_map = source_map.reproject_to(target_wcs)
    return aligned_map


# ==============================================================================
# HMI数据处理辅助函数
# ==============================================================================


def process_hmi_magnetic_field(
    hmi_map: sunpy.map.GenericMap, threshold: u.Quantity | None = None, sigma: float = 3
) -> sunpy.map.GenericMap:
    """
    处理HMI磁场数据：应用阈值和高斯滤波

    Args:
        hmi_map: HMI地图对象
        threshold: 磁场阈值，小于此值的设为零
        sigma: 高斯滤波标准差

    Returns:
        sunpy.map.GenericMap: 处理后的磁场地图
    """
    import astropy.units as u
    import numpy as np
    import sunpy.map
    from scipy.ndimage import gaussian_filter

    if threshold is None:
        threshold = 0 * u.Gauss

    # 确保单位存在
    if hmi_map.unit is None:
        hmi_map.meta["bunit"] = "G"
        hmi_unit = u.Gauss
    else:
        hmi_unit = hmi_map.unit

    # 应用阈值
    hmi_data = hmi_map.data * hmi_unit
    hmi_data[np.abs(hmi_data) < threshold] = 0 * u.Gauss

    # 高斯滤波
    smoothed_data = gaussian_filter(hmi_data.value, sigma=sigma) * hmi_data.unit
    hmi_smoothed = sunpy.map.Map(smoothed_data, hmi_map.meta)

    return hmi_smoothed


def create_magnetic_contour_levels(base_level: u.Quantity | None = None) -> u.Quantity:
    """
    创建磁场等值线层级

    Args:
        base_level: 基础层级

    Returns:
        u.Quantity: 等值线层级数组
    """
    import astropy.units as u

    if base_level is None:
        base_level = 50 * u.Gauss
    return u.Quantity([-base_level.value, base_level.value], base_level.unit)


# ==============================================================================
# 可视化辅助函数
# ==============================================================================


def setup_chinese_font():
    """
    设置中文字体，解决中文显示问题
    """
    import matplotlib.pyplot as plt

    # 修改字体设置部分
    plt.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示问题


def create_figure_with_white_background(figsize: tuple[float, float] = (10, 8)):
    """
    创建白色背景的图形

    Args:
        figsize: 图形尺寸

    Returns:
        Tuple[plt.Figure, plt.Axes]: 图形和坐标轴对象
    """
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=figsize, facecolor="white")
    ax = fig.add_subplot(111)
    ax.set_facecolor("white")

    return fig, ax


def add_frequency_highlight_lines(
    ax,
    frequencies: list[float],
    freq_range: tuple[float, float],
    time_range: tuple[datetime.datetime, datetime.datetime],
    color: str = "red",
):
    """
    在频谱图上添加频率高亮线

    Args:
        ax: 坐标轴对象
        frequencies: 要高亮的频率列表（MHz）
        freq_range: 频率范围 (f_start, f_end)
        time_range: 时间范围 (t_start, t_end)
        color: 线条颜色
    """
    import matplotlib.dates as mdates

    f_start, f_end = freq_range
    t_start, t_end = time_range

    for freq in frequencies:
        if f_start <= freq <= f_end:
            # 添加水平线
            ax.axhline(y=freq, color=color, linestyle="--", linewidth=1.3, alpha=0.6)
            # 添加文本标签
            x_min = mdates.date2num(t_start)
            x_max = mdates.date2num(t_end)
            x_pos = x_min + 0.01 * (x_max - x_min)

            ax.text(
                x_pos,
                freq + 0.01 * (f_end - f_start),
                f"{freq} MHz",
                color=color,
                fontsize=8,
                verticalalignment="bottom",
                horizontalalignment="left",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="yellow", alpha=0.3),
            )


# ==============================================================================
# 性能计时装饰器
# ==============================================================================


def timing_decorator(func):
    """
    函数执行时间测量装饰器
    """
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        print(f"[{func.__name__}] 执行时间: {end_time - start_time:.3f} 秒")
        return result

    return wrapper


# ==============================================================================
# 数据验证函数
# ==============================================================================


def validate_time_range(
    start_time: datetime.datetime, end_time: datetime.datetime
) -> bool:
    """
    验证时间范围是否有效

    Args:
        start_time: 开始时间
        end_time: 结束时间

    Returns:
        bool: 是否有效

    Raises:
        ValueError: 时间范围无效
    """
    if start_time >= end_time:
        raise ValueError(f"开始时间 ({start_time}) 必须早于结束时间 ({end_time})")

    time_diff = (end_time - start_time).total_seconds()
    if time_diff <= 0:
        raise ValueError(f"时间差必须为正，实际为 {time_diff} 秒")

    return True


def validate_frequency_range(f_start: float, f_end: float) -> bool:
    """
    验证频率范围是否有效

    Args:
        f_start: 起始频率（MHz）
        f_end: 结束频率（MHz）

    Returns:
        bool: 是否有效

    Raises:
        ValueError: 频率范围无效
    """
    if f_start >= f_end:
        raise ValueError(f"起始频率 ({f_start} MHz) 必须小于结束频率 ({f_end} MHz)")

    if f_start < 0 or f_end < 0:
        raise ValueError(f"频率必须为正数，实际为 {f_start} - {f_end} MHz")

    return True


# ==============================================================================
# 配置管理
# ==============================================================================


class SolarDataConfig:
    """
    太阳数据处理的统一配置类
    """

    def __init__(self, config_dict: dict[str, Any] | None = None):
        """
        初始化配置

        Args:
            config_dict: 配置字典，如果为None则使用默认值
        """
        # 默认配置
        self.defaults = {
            "data_dir": "D:/solar_data",
            "output_dir": "D:/solar_data/output",
            "roi_bounds": (-700, -100, -100, 400),  # (xmin, xmax, ymin, ymax)
            "dpi": 300,
            "fig_width": 10.0,
            "use_parallel": True,
            "max_workers": None,  # None表示自动检测
            "chunk_mem_mb": 50,
            "save_images": True,
            "show_images": False,
        }

        # 更新用户配置
        if config_dict:
            self.defaults.update(config_dict)

        # 设置属性
        for key, value in self.defaults.items():
            setattr(self, key, value)

    def to_dict(self) -> dict[str, Any]:
        """
        将配置转换为字典

        Returns:
            Dict[str, Any]: 配置字典
        """
        return {key: getattr(self, key) for key in self.defaults.keys()}

    def save_to_file(self, filepath: str):
        """
        保存配置到文件

        Args:
            filepath: 文件路径，支持.json或.yaml格式
        """
        import json

        import yaml

        config_dict = self.to_dict()

        if filepath.endswith(".json"):
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
        elif filepath.endswith(".yaml") or filepath.endswith(".yml"):
            with open(filepath, "w", encoding="utf-8") as f:
                yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
        else:
            raise ValueError(f"不支持的配置文件格式: {filepath}")

    @classmethod
    def load_from_file(cls, filepath: str) -> SolarDataConfig:
        """
        从文件加载配置

        Args:
            filepath: 文件路径，支持.json或.yaml格式

        Returns:
            SolarDataConfig: 配置对象
        """
        import json

        import yaml

        if filepath.endswith(".json"):
            with open(filepath, encoding="utf-8") as f:
                config_dict = json.load(f)
        elif filepath.endswith(".yaml") or filepath.endswith(".yml"):
            with open(filepath, encoding="utf-8") as f:
                config_dict = yaml.safe_load(f)
        else:
            raise ValueError(f"不支持的配置文件格式: {filepath}")

        return cls(config_dict)


# ==============================================================================
# 日志记录
# ==============================================================================


class SolarLogger:
    """
    太阳数据处理日志记录器
    """

    def __init__(self, log_file: str | None = None, level: str = "INFO"):
        """
        初始化日志记录器

        Args:
            log_file: 日志文件路径，如果为None则只输出到控制台
            level: 日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        """
        import logging

        self.logger = logging.getLogger("solar_data_processing")
        self.logger.setLevel(getattr(logging, level))

        # 清除现有处理器
        self.logger.handlers.clear()

        # 创建格式器
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # 文件处理器
        if log_file:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def debug(self, msg: str):
        """记录调试信息"""
        self.logger.debug(msg)

    def info(self, msg: str):
        """记录一般信息"""
        self.logger.info(msg)

    def warning(self, msg: str):
        """记录警告信息"""
        self.logger.warning(msg)

    def error(self, msg: str):
        """记录错误信息"""
        self.logger.error(msg)

    def critical(self, msg: str):
        """记录严重错误信息"""
        self.logger.critical(msg)


# ==============================================================================
# 主程序示例
# ==============================================================================

if __name__ == "__main__":
    # 示例用法
    print("太阳物理数据处理共享工具模块")
    print("=" * 50)

    # 测试时间提取
    test_filenames = [
        "aia_2024-08-08T19:22:30Z.fits",
        "hmi_20250124_041219_TAI.fits",
        "OROCH_MWRS01_SRSP_L1_05M_20250124041219_V01.01.fits",
    ]

    for filename in test_filenames:
        try:
            dt = extract_time_from_filename(filename)
            print(f"文件名: {filename}")
            print(f"  提取时间: {format_time_for_display(dt)}")
            print(f"  文件名格式: {format_time_for_filename(dt)}")
        except ValueError as e:
            print(f"文件名: {filename}")
            print(f"  错误: {e}")

    print("\n" + "=" * 50)

    # 测试配置管理
    config = SolarDataConfig(
        {
            "data_dir": "D:/my_solar_data",
            "output_dir": "D:/my_solar_data/output",
            "roi_bounds": (-500, 500, -500, 500),
        }
    )

    print("配置示例:")
    print(f"  数据目录: {config.data_dir}")
    print(f"  输出目录: {config.output_dir}")
    print(f"  ROI边界: {config.roi_bounds}")
