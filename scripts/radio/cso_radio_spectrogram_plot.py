# 模块用途: 从 FITS 数据绘制 CSO 射电动态频谱。
# 主要输入: CSO FITS 文件、偏振通道和降采样配置。
# 主要输出/运行说明: 输出频率-时间谱图，包含内存友好的分块/降采样处理。
"""
Created on Sun Nov 23 00:19:30 2025

@author: Severus

"""

"""
CSO Spectrogram Plotting and Analysis Tool

This script provides a comprehensive solution for processing and visualizing
Chinese Solar Radio Telescope (CSO) spectrogram data from FITS files.
It employs memory-efficient techniques to handle large datasets while
maintaining high performance through parallel processing and intelligent
downsampling.

Key Features:
- Memory-mapped I/O for handling large FITS files without loading entire datasets
- Parallel processing of polarization channels (LL and RR)
- Configurable downsampling to balance resolution and performance
- Multiple visualization options: individual polarizations, total intensity, polarization ratio
- Frequency highlighting with customizable markers
- Flexible output options: display, save to file, or both
"""

import datetime  # noqa: E402
import os  # noqa: E402
import time  # noqa: E402
import warnings  # noqa: E402
from concurrent.futures import ThreadPoolExecutor, as_completed  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from functools import wraps  # noqa: E402

import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from astropy.io import fits  # noqa: E402
from matplotlib.colors import TwoSlopeNorm  # noqa: E402
from tqdm import tqdm  # noqa: E402

from solar_toolkit.path_config import apply_config_to_object  # noqa: E402


# ============================================================
#  ★ CONFIGURATION PARAMETERS - MODIFY ONLY HERE ★
# ============================================================
@dataclass
class PlotConfig:
    """Configuration class for CSO spectrogram plotting parameters."""

    # File path
    # Single-file mode: keep using file_path.
    # Multi-file mode: set file_paths to a list of FITS files ordered or unordered.
    # The program will automatically select the portions overlapping t_start~t_end
    # and concatenate them along the time axis.
    file_path: str = (
        r"D:\spike_topping_type_III\2025\20250124"
        r"\OROCH_MWRS01_SRSP_L1_05M_20250124041219_V01.01.fits"
    )
    # file_paths: list[str] | None = field(default_factory=lambda: [
    #     r"D:\spike_topping_type_III\2026\20260326\OROCH_MWRS01_SRSP_L1_05M_20260326065020_V01.01.fits",
    #     r"D:\spike_topping_type_III\2026\20260326\OROCH_MWRS01_SRSP_L1_05M_20260326065509_V01.01.fits"
    #     ])

    # Time range (UTC)
    t_start: datetime.datetime = field(
        default_factory=lambda: datetime.datetime(2025, 1, 24, 4, 14, 10)
    )
    t_end: datetime.datetime = field(
        default_factory=lambda: datetime.datetime(2025, 1, 24, 4, 15, 20)
    )

    # Frequency range (MHz)
    f_start: float = 80
    f_end: float = 340

    # Target number of grid points after downsampling (time / frequency axes)
    # Larger values produce finer plots but are slower; None = no downsampling
    rebin_t_target: int = 10000
    rebin_f_target: int = 10000

    # Peak memory limit per chunk during block reading (MB)
    # Lower values reduce memory pressure further
    chunk_mem_mb: int = 28

    # Maximum number of CPU cores to use (None = auto-detect, 1 = single core)
    max_workers: int | None = None

    # Plot toggles
    plot_ll: bool = False
    plot_rr: bool = False
    plot_sum: bool = True
    plot_ratio: bool = True

    # Color scale configuration - CHOOSE ONE METHOD:
    # Method 1: Percentile-based clipping (automatic)
    use_percentile_clipping: bool = False  # Set to False to use manual limits
    vmin_pct: float = 0.1
    vmax_pct: float = 99.9
    sum_vmin_pct: float = 0.1
    sum_vmax_pct: float = 99.9
    # For ratio, we need symmetric percentiles since data ranges from -1 to 1
    ratio_vmin_pct: float = 1.0  # Use 1st percentile for negative side
    ratio_vmax_pct: float = 99.0  # Use 99th percentile for positive side

    # Method 2: Manual absolute limits (used when use_percentile_clipping = False)
    # Set these to specific values like 0.0 and 10.0
    # Individual polarization limits
    manual_ll_vmin: float | None = 1.8
    manual_ll_vmax: float | None = 5
    manual_rr_vmin: float | None = 1.8
    manual_rr_vmax: float | None = 5
    # Sum and ratio limits
    manual_sum_vmin: float | None = 2.2
    manual_sum_vmax: float | None = 5.6
    manual_ratio_vmin: float | None = -1.0
    manual_ratio_vmax: float | None = 1.0
    ratio_auto_symmetric_scale: bool = True
    ratio_abs_percentile: float = 99.5
    ratio_min_abs_limit: float = 0.03
    ratio_max_abs_limit: float = 1.0

    # Backward compatibility: if individual limits not set, use these
    manual_vmin: float | None = None
    manual_vmax: float | None = None

    # Figure dimensions
    fig_width: float = 12.0
    fig_height_per: float = 3.0  # Height per subplot (inches)

    # Time axis tick intervals (seconds)
    major_tick_interval: int = 10
    minor_tick_interval: int = 2

    # Save path (empty for display only)
    save_path: str = r"D:\spike_topping_type_III\2025\20250124\CSO_PLOT"
    dpi: int = 300
    show_plot: bool = False
    close_after_save: bool = True

    # List of frequencies to highlight (MHz)
    highlight_freqs: list[float] | None = field(
        default_factory=lambda: [149, 164, 190, 205, 223, 238, 285, 300, 309, 324]
    )
    # [149, 164, 190, 205, 223, 238, 285, 300, 309, 324]

    # 坐标轴显示控制
    show_axis_labels: bool = True  # 是否显示坐标轴标签
    axis_label_rotation: float = 0.0  # 标签旋转角度（度）
    xtick_interval: int | None = None  # X轴刻度间隔（秒），None为自动
    ytick_interval: float | None = None  # Y轴刻度间隔（MHz），None为自动
    xtick_format: str = "%H:%M:%S"  # X轴时间格式
    show_minor_ticks: bool = True  # 是否显示次要刻度

    def __post_init__(self):
        apply_config_to_object(self, "cso_radio_spectrogram_plot")


# ============================================================
#  UTILITY FUNCTIONS
# ============================================================


def timing_decorator(func):
    """Decorator to measure and print function execution time."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        result = func(*args, **kwargs)
        print(f"  [{func.__name__}] {time.perf_counter() - t0:.3f} s")
        return result

    return wrapper


def _find_range(arr: np.ndarray, lo: float, hi: float):
    """Fast range index lookup using searchsorted with boundary protection."""
    if lo > hi:
        lo, hi = hi, lo
    if len(arr) == 0:
        raise ValueError("Cannot search an empty axis")

    if len(arr) > 1 and arr[0] > arr[-1]:
        arr_rev = arr[::-1]
        r0 = int(np.clip(np.searchsorted(arr_rev, lo, side="left"), 0, len(arr) - 1))
        r1 = int(
            np.clip(np.searchsorted(arr_rev, hi, side="right") - 1, 0, len(arr) - 1)
        )
        i0 = len(arr) - 1 - r1
        i1 = len(arr) - 1 - r0
    else:
        i0 = int(np.clip(np.searchsorted(arr, lo, side="left"), 0, len(arr) - 1))
        i1 = int(np.clip(np.searchsorted(arr, hi, side="right") - 1, 0, len(arr) - 1))
    return i0, max(i0, i1)


def _as_datetime(value, name: str) -> datetime.datetime:
    """Accept datetime objects or ISO datetime strings in PlotConfig."""
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, str):
        return datetime.datetime.fromisoformat(value)
    raise TypeError(f"{name} must be datetime.datetime or ISO datetime string")


def _array_stats(name: str, data: np.ndarray) -> None:
    """Print finite-count and basic statistics for diagnostics."""
    finite = data[np.isfinite(data)]
    if finite.size == 0:
        print(f"  {name}: finite_count=0, min=nan, max=nan, mean=nan, std=nan")
        return
    print(
        f"  {name}: finite_count={finite.size}, min={np.nanmin(finite):.6g}, "
        f"max={np.nanmax(finite):.6g}, mean={np.nanmean(finite):.6g}, "
        f"std={np.nanstd(finite):.6g}"
    )


def get_config_file_paths(cfg: PlotConfig) -> list[str]:
    """Return FITS paths from cfg.file_paths, with cfg.file_path kept as fallback."""
    file_paths = getattr(cfg, "file_paths", None)
    if file_paths:
        if isinstance(file_paths, (str, os.PathLike)):
            paths = [str(file_paths)]
        else:
            paths = [str(path) for path in file_paths if str(path).strip()]
    else:
        paths = [str(cfg.file_path)] if str(cfg.file_path).strip() else []

    if not paths:
        raise ValueError(
            "No FITS file path is configured. Set cfg.file_path or cfg.file_paths."
        )

    missing = [path for path in paths if not os.path.exists(path)]
    if missing:
        raise FileNotFoundError("FITS file(s) not found:\n" + "\n".join(missing))

    return paths


def _spec_time_bounds(
    spec: "LazySpectrogram",
) -> tuple[datetime.datetime, datetime.datetime]:
    """Return absolute datetime coverage of one LazySpectrogram."""
    finite_time = spec.time[np.isfinite(spec.time)]
    if finite_time.size == 0:
        raise ValueError(f"{spec.polar} has no finite time samples: {spec.source_path}")
    t_min = float(np.nanmin(finite_time))
    t_max = float(np.nanmax(finite_time))
    return (
        spec.dt_base + datetime.timedelta(seconds=t_min),
        spec.dt_base + datetime.timedelta(seconds=t_max),
    )


def _spec_overlaps_time_range(
    spec: "LazySpectrogram",
    t_start: datetime.datetime,
    t_end: datetime.datetime,
) -> bool:
    """Whether one file has any samples within the requested absolute time range."""
    spec_start, spec_end = _spec_time_bounds(spec)
    return spec_start <= t_end and spec_end >= t_start


def _select_overlapping_specs(
    data_list: list,
    polar_key: str,
    t_start: datetime.datetime,
    t_end: datetime.datetime,
) -> list:
    """Select and time-sort LL/RR spectra that overlap the requested time range."""
    specs = [
        spec
        for spec in data_list
        if polar_key in spec.polar and _spec_overlaps_time_range(spec, t_start, t_end)
    ]
    return sorted(specs, key=lambda spec: _spec_time_bounds(spec)[0])


def _overlap_window(
    spec: "LazySpectrogram",
    t_start: datetime.datetime,
    t_end: datetime.datetime,
) -> tuple[datetime.datetime, datetime.datetime] | None:
    """Return the part of the requested range covered by one file."""
    spec_start, spec_end = _spec_time_bounds(spec)
    overlap_start = max(t_start, spec_start)
    overlap_end = min(t_end, spec_end)
    if overlap_start >= overlap_end:
        return None
    return overlap_start, overlap_end


def _validate_contiguous_time_coverage(
    specs: list,
    t_start: datetime.datetime,
    t_end: datetime.datetime,
    polar_label: str,
    tolerance_seconds: float = 1.0,
) -> None:
    """Raise an explicit error if the requested range is not covered by the files."""
    intervals = []
    for spec in specs:
        window = _overlap_window(spec, t_start, t_end)
        if window is not None:
            intervals.append((*window, spec.source_path))

    if not intervals:
        raise ValueError(f"No {polar_label} file overlaps the requested time range.")

    intervals.sort(key=lambda item: item[0])
    current_end = t_start
    tol = datetime.timedelta(seconds=float(tolerance_seconds))

    for seg_start, seg_end, source_path in intervals:
        if seg_start > current_end + tol:
            raise ValueError(
                f"{polar_label} files do not fully cover the requested time range. "
                f"Gap: {current_end.isoformat()} -> {seg_start.isoformat()}. "
                f"Next file: {source_path}"
            )
        if seg_end > current_end:
            current_end = seg_end
        if current_end >= t_end - tol:
            return

    raise ValueError(
        f"{polar_label} files end before the requested t_end. "
        f"Covered until {current_end.isoformat()}, requested until {t_end.isoformat()}."
    )


def _estimate_raw_selection_mb(
    specs: list,
    cfg: PlotConfig,
    t_start: datetime.datetime,
    t_end: datetime.datetime,
) -> float:
    """Estimate total selected raw data size for one polarization across files."""
    total_points = 0
    for spec in specs:
        window = _overlap_window(spec, t_start, t_end)
        if window is None:
            continue
        t0, t1 = window
        t0s = (t0 - spec.dt_base).total_seconds()
        t1s = (t1 - spec.dt_base).total_seconds()
        ti0, ti1 = _find_range(spec.time, t0s, t1s)
        fi0, fi1 = _find_range(spec.freq, cfg.f_start, cfg.f_end)
        total_points += max(0, ti1 - ti0 + 1) * max(0, fi1 - fi0 + 1)
    return total_points * 4 / (1024 * 1024)


def get_system_memory_info() -> tuple[float, float, float]:
    """
    Get system memory information.

    Returns:
        Tuple of (total_memory_gb, available_memory_gb, memory_usage_percent)
    """
    try:
        import psutil

        memory = psutil.virtual_memory()
        total_gb = memory.total / (1024**3)
        available_gb = memory.available / (1024**3)
        usage_percent = memory.percent
        return total_gb, available_gb, usage_percent
    except ImportError:
        warnings.warn("psutil not installed, cannot get memory info", stacklevel=2)
        return 0.0, 0.0, 0.0


def validate_config(cfg: PlotConfig) -> None:
    """Validate configuration parameters."""
    t_start = _as_datetime(cfg.t_start, "t_start")
    t_end = _as_datetime(cfg.t_end, "t_end")
    if t_start >= t_end:
        raise ValueError(
            f"t_start ({cfg.t_start}) must be earlier than t_end ({cfg.t_end})"
        )

    if cfg.f_start >= cfg.f_end:
        raise ValueError(
            f"f_start ({cfg.f_start}) must be less than f_end ({cfg.f_end})"
        )

    if cfg.rebin_t_target is not None and cfg.rebin_t_target <= 0:
        raise ValueError(f"rebin_t_target must be positive, got {cfg.rebin_t_target}")

    if cfg.rebin_f_target is not None and cfg.rebin_f_target <= 0:
        raise ValueError(f"rebin_f_target must be positive, got {cfg.rebin_f_target}")

    if cfg.chunk_mem_mb <= 0:
        raise ValueError(f"chunk_mem_mb must be positive, got {cfg.chunk_mem_mb}")

    # Check for max_workers attribute (may not exist in older config)
    if hasattr(cfg, "max_workers"):
        if cfg.max_workers is not None and cfg.max_workers <= 0:
            raise ValueError(
                f"max_workers must be positive or None, got {cfg.max_workers}"
            )

    # Check for use_percentile_clipping attribute
    if hasattr(cfg, "use_percentile_clipping"):
        if not cfg.use_percentile_clipping:
            # Check individual polarization limits
            if hasattr(cfg, "manual_ll_vmin") and hasattr(cfg, "manual_ll_vmax"):
                if cfg.manual_ll_vmin is not None and cfg.manual_ll_vmax is not None:
                    if cfg.manual_ll_vmin >= cfg.manual_ll_vmax:
                        raise ValueError(
                            f"manual_ll_vmin ({cfg.manual_ll_vmin}) must be less than manual_ll_vmax ({cfg.manual_ll_vmax})"
                        )

            if hasattr(cfg, "manual_rr_vmin") and hasattr(cfg, "manual_rr_vmax"):
                if cfg.manual_rr_vmin is not None and cfg.manual_rr_vmax is not None:
                    if cfg.manual_rr_vmin >= cfg.manual_rr_vmax:
                        raise ValueError(
                            f"manual_rr_vmin ({cfg.manual_rr_vmin}) must be less than manual_rr_vmax ({cfg.manual_rr_vmax})"
                        )

            # Check backward compatibility limits
            if hasattr(cfg, "manual_vmin") and hasattr(cfg, "manual_vmax"):
                if cfg.manual_vmin is not None and cfg.manual_vmax is not None:
                    if cfg.manual_vmin >= cfg.manual_vmax:
                        raise ValueError(
                            f"manual_vmin ({cfg.manual_vmin}) must be less than manual_vmax ({cfg.manual_vmax})"
                        )

            # Check sum limits
            if hasattr(cfg, "manual_sum_vmin") and hasattr(cfg, "manual_sum_vmax"):
                if cfg.manual_sum_vmin is not None and cfg.manual_sum_vmax is not None:
                    if cfg.manual_sum_vmin >= cfg.manual_sum_vmax:
                        raise ValueError(
                            f"manual_sum_vmin ({cfg.manual_sum_vmin}) must be less than manual_sum_vmax ({cfg.manual_sum_vmax})"
                        )

            # Check ratio limits
            if hasattr(cfg, "manual_ratio_vmin") and hasattr(cfg, "manual_ratio_vmax"):
                if (
                    cfg.manual_ratio_vmin is not None
                    and cfg.manual_ratio_vmax is not None
                ):
                    if cfg.manual_ratio_vmin >= cfg.manual_ratio_vmax:
                        raise ValueError(
                            f"manual_ratio_vmin ({cfg.manual_ratio_vmin}) must be less than manual_ratio_vmax ({cfg.manual_ratio_vmax})"
                        )

    # Warn about potential memory issues
    if (
        hasattr(cfg, "max_workers")
        and cfg.max_workers is not None
        and cfg.max_workers > 2
    ):
        warnings.warn(
            f"max_workers={cfg.max_workers} is set, but only 2 workers are needed for polarization processing",
            stacklevel=2,
        )

    # Check memory configuration
    if cfg.chunk_mem_mb > 500:
        warnings.warn(
            f"chunk_mem_mb={cfg.chunk_mem_mb} MB is quite high. Consider reducing for memory-constrained systems.",
            stacklevel=2,
        )

    # 验证坐标轴配置
    validate_axis_config(cfg)


# ============================================================
#  LAZY SPECTROGRAM CONTAINER
# ============================================================


class LazySpectrogram:
    """
    Container that holds FITS memmap references and metadata without loading
    the full array into memory. The read_slice_rebinned() method performs
    on-the-fly downsampling with minimal peak memory usage.
    """

    __slots__ = (
        "_raw",
        "time",
        "freq",
        "polar",
        "dateobs",
        "unit",
        "dt_base",
        "source_path",
    )

    def __init__(
        self,
        raw_memmap,
        time_arr,
        freq_arr,
        polar,
        dateobs,
        unit,
        dt_base,
        source_path="",
    ):
        self._raw = raw_memmap
        self.time = time_arr.astype(np.float64)
        self.freq = freq_arr.astype(np.float32)
        self.polar = polar
        self.dateobs = dateobs
        self.unit = unit
        self.dt_base = dt_base
        self.source_path = source_path

    def read_slice_rebinned(
        self,
        t1: datetime.datetime,
        t2: datetime.datetime,
        f1: float,
        f2: float,
        t_bin: int,
        f_bin: int,
        chunk_mem_mb: int = 64,
    ):
        """
        Read from memmap in chunks and immediately apply block-mean downsampling.
        Peak memory usage is approximately chunk_mem_mb.

        Process:
          1. Calculate indices and align to bin multiples
          2. Read chunk_cols_raw columns per iteration (≈chunk_mem_mb / freq rows)
          3. Reshape+mean each chunk for downsampling, write to output array
        """
        t1s = (t1 - self.dt_base).total_seconds()
        t2s = (t2 - self.dt_base).total_seconds()

        ti0, ti1 = _find_range(self.time, t1s, t2s)
        fi0, fi1 = _find_range(self.freq, f1, f2)

        n_freq_raw = fi1 - fi0 + 1
        n_time_raw = ti1 - ti0 + 1

        # Align to bin multiples
        n_freq_trim = (n_freq_raw // f_bin) * f_bin
        n_time_trim = (n_time_raw // t_bin) * t_bin
        n_freq_out = n_freq_trim // f_bin
        n_time_out = n_time_trim // t_bin

        if n_freq_out <= 0 or n_time_out <= 0:
            raise ValueError(
                f"Selected range is too short after binning for {self.polar}: "
                f"raw={n_freq_raw}×{n_time_raw}, bin={f_bin}×{t_bin}, "
                f"file={self.source_path}"
            )

        raw_mb = n_freq_raw * n_time_raw * 4 / 1e6
        out_mb = n_freq_out * n_time_out * 4 / 1e6
        print(
            f"    [{self.polar}] Raw: {n_freq_raw}×{n_time_raw} "
            f"({raw_mb:.0f} MB)  ->  Output: {n_freq_out}×{n_time_out} "
            f"({out_mb:.1f} MB)"
        )

        # Columns per chunk: keep memory ≈ chunk_mem_mb, must be multiple of t_bin
        cols_per_chunk = max(
            t_bin, (int(chunk_mem_mb * 1e6 / (n_freq_trim * 4)) // t_bin) * t_bin
        )

        Z_out = np.empty((n_freq_out, n_time_out), dtype=np.float32)
        out_col = 0

        for col0 in tqdm(
            range(0, n_time_trim, cols_per_chunk),
            desc=f"    Reading {self.polar}",
            leave=False,
        ):
            col1 = min(col0 + cols_per_chunk, n_time_trim)
            n_cols = ((col1 - col0) // t_bin) * t_bin  # Alignment
            if n_cols == 0:
                continue

            # Trigger actual disk I/O, immediately copy to float32
            chunk = np.array(
                self._raw[fi0 : fi0 + n_freq_trim, ti0 + col0 : ti0 + col0 + n_cols],
                dtype=np.float32,
            )  # (n_freq_trim, n_cols)

            # Perform block-mean for both frequency and time axes
            n_t_chunk = n_cols // t_bin
            chunk_rb = chunk.reshape(n_freq_out, f_bin, n_t_chunk, t_bin).mean(
                axis=(1, 3), dtype=np.float32
            )

            Z_out[:, out_col : out_col + n_t_chunk] = chunk_rb
            out_col += n_t_chunk

        freq_out = (
            self.freq[fi0 : fi0 + n_freq_trim].reshape(n_freq_out, f_bin).mean(axis=1)
        )
        time_out = (
            self.time[ti0 : ti0 + n_time_trim].reshape(n_time_out, t_bin).mean(axis=1)
        )

        return Z_out, time_out, freq_out


# ============================================================
#  DATA READING FUNCTIONS
# ============================================================


@timing_decorator
def read_cso_fits(fn: str):
    """
    Open FITS file, read metadata, and return (list of LazySpectrogram, hdu handle).
    The hdu must remain open until all read_slice_rebinned() calls complete.
    """
    hdu = fits.open(fn, memmap=True)
    try:
        header = hdu[0].header
        raw = hdu[0].data
        time_ = np.ravel(hdu[1].data["time"])
        freq_ = np.ravel(hdu[1].data["frequency"])

        dateobs = header.get("DATE-OBS") or header.get("DATE_OBS")
        dt_base = datetime.datetime.fromisoformat(dateobs[:10])

        if time_[0] < 0:
            dt_base = dt_base + datetime.timedelta(days=1)
            dateobs = dt_base.isoformat()

        polars = header["POLARIZA"]
        if header["NAXIS"] == 3 and polars == "RCP and LCP":
            polars = "RL"

        unit = header.get("BUNIT") or header.get("QUANTITY", "K")

        results = []
        if raw.ndim == 2:
            results.append(
                LazySpectrogram(raw, time_, freq_, polars, dateobs, unit, dt_base, fn)
            )
            print(
                f"  Single polarization: {polars}  Size: {raw.shape}  "
                f"({raw.nbytes/1e9:.2f} GB, not loaded into memory)"
            )
        elif raw.ndim == 3:
            for ii in range(raw.shape[0]):
                polar = polars[ii] * 2
                results.append(
                    LazySpectrogram(
                        raw[ii], time_, freq_, polar, dateobs, unit, dt_base, fn
                    )
                )
            print(
                f"  Dual polarization  Full size: {raw.shape}  "
                f"({raw.nbytes/1e9:.2f} GB, not loaded into memory)"
            )

        return results, hdu

    except Exception:
        hdu.close()
        raise


def validate_axis_config(cfg: PlotConfig) -> None:
    """验证坐标轴配置参数"""
    if not isinstance(cfg.show_axis_labels, bool):
        raise TypeError(
            f"show_axis_labels must be boolean, got {type(cfg.show_axis_labels)}"
        )

    if not isinstance(cfg.axis_label_rotation, (int, float)):
        raise TypeError(
            f"axis_label_rotation must be numeric, got {type(cfg.axis_label_rotation)}"
        )

    if not (-90 <= cfg.axis_label_rotation <= 90):
        warnings.warn(
            f"axis_label_rotation should be between -90 and 90 degrees, got {cfg.axis_label_rotation}",
            stacklevel=2,
        )
        cfg.axis_label_rotation = np.clip(cfg.axis_label_rotation, -90, 90)

    if cfg.xtick_interval is not None and cfg.xtick_interval <= 0:
        raise ValueError(f"xtick_interval must be positive, got {cfg.xtick_interval}")

    if cfg.ytick_interval is not None and cfg.ytick_interval <= 0:
        raise ValueError(f"ytick_interval must be positive, got {cfg.ytick_interval}")

    if not isinstance(cfg.show_minor_ticks, bool):
        raise TypeError(
            f"show_minor_ticks must be boolean, got {type(cfg.show_minor_ticks)}"
        )


class AxisConfigManager:
    """坐标轴配置管理器，负责处理和优化坐标轴显示"""

    @staticmethod
    def calculate_optimal_ticks(
        data_range: float, num_points: int = None, max_ticks: int = 10
    ) -> float:
        """
        计算最优刻度间隔

        Args:
            data_range: 数据范围
            num_points: 数据点数（可选）
            max_ticks: 最大刻度数

        Returns:
            建议的刻度间隔
        """
        if data_range <= 0:
            return 1.0

        # 基于范围计算基础间隔
        base_intervals = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]
        estimated_ticks = max_ticks

        # 如果提供点数，尝试基于点数调整
        if num_points is not None and num_points > 0:
            points_per_tick = num_points / max_ticks
            if points_per_tick < 1:
                estimated_ticks = min(max_ticks, num_points)

        ideal_interval = data_range / estimated_ticks

        # 找到最接近的理想刻度间隔
        for base in base_intervals:
            for multiplier in [0.1, 0.2, 0.5, 1, 2, 5, 10]:
                interval = base * multiplier
                if interval >= ideal_interval:
                    return interval

        return ideal_interval

    @staticmethod
    def configure_time_axis(
        ax, cfg: PlotConfig, time_values: list[datetime.datetime]
    ) -> None:
        """配置时间轴"""
        if not cfg.show_axis_labels:
            ax.set_xticklabels([])
            ax.set_xlabel("")
        else:
            # 设置主要刻度定位器
            if cfg.xtick_interval is not None:
                major_locator = mdates.SecondLocator(interval=cfg.xtick_interval)
            else:
                # 自动计算：基于时间范围计算最优间隔
                time_range = (time_values[-1] - time_values[0]).total_seconds()
                optimal_interval = AxisConfigManager.calculate_optimal_ticks(
                    time_range, len(time_values), max_ticks=15
                )
                major_locator = mdates.SecondLocator(
                    interval=max(1, int(optimal_interval))
                )

            ax.xaxis.set_major_locator(major_locator)
            ax.xaxis.set_major_formatter(mdates.DateFormatter(cfg.xtick_format))

            # 设置次要刻度
            if cfg.show_minor_ticks:
                if cfg.xtick_interval is not None:
                    minor_interval = max(1, cfg.xtick_interval // 5)
                else:
                    minor_interval = max(1, int(major_locator._interval // 5))
                ax.xaxis.set_minor_locator(
                    mdates.SecondLocator(interval=minor_interval)
                )

            # 设置标签旋转
            if cfg.axis_label_rotation != 0:
                plt.setp(
                    ax.get_xticklabels(),
                    rotation=cfg.axis_label_rotation,
                    ha="right" if cfg.axis_label_rotation > 0 else "left",
                )

    @staticmethod
    def configure_frequency_axis(ax, cfg: PlotConfig, freq_values: np.ndarray) -> None:
        """配置频率轴"""
        f_min = float(np.nanmin(freq_values))
        f_max = float(np.nanmax(freq_values))
        ax.set_ylim(f_min, f_max)
        if not cfg.show_axis_labels:
            ax.set_yticklabels([])
            ax.set_ylabel("")
        else:
            # 设置主要刻度
            if cfg.ytick_interval is not None:
                yticks = np.arange(
                    np.ceil(f_min / cfg.ytick_interval) * cfg.ytick_interval,
                    f_max,
                    cfg.ytick_interval,
                )
                ax.set_yticks(yticks)
            else:
                # 自动计算刻度
                freq_range = f_max - f_min
                optimal_interval = AxisConfigManager.calculate_optimal_ticks(
                    freq_range, len(freq_values), max_ticks=10
                )
                yticks = np.arange(
                    np.ceil(f_min / optimal_interval) * optimal_interval,
                    f_max,
                    optimal_interval,
                )
                ax.set_yticks(yticks)

            # 设置次要刻度
            if cfg.show_minor_ticks:
                from matplotlib.ticker import AutoMinorLocator

                ax.yaxis.set_minor_locator(AutoMinorLocator(5))

            # 设置标签旋转
            if cfg.axis_label_rotation != 0:
                plt.setp(
                    ax.get_yticklabels(), rotation=cfg.axis_label_rotation, va="center"
                )


# ============================================================
#  HELPER FUNCTIONS
# ============================================================


def calc_bin_sizes(spec: LazySpectrogram, cfg: PlotConfig):
    """Calculate t_bin / f_bin based on actual slice range and target point count."""
    t_start = _as_datetime(cfg.t_start, "t_start")
    t_end = _as_datetime(cfg.t_end, "t_end")
    t1s = (t_start - spec.dt_base).total_seconds()
    t2s = (t_end - spec.dt_base).total_seconds()
    ti0, ti1 = _find_range(spec.time, t1s, t2s)
    fi0, fi1 = _find_range(spec.freq, cfg.f_start, cfg.f_end)
    n_t = ti1 - ti0 + 1
    n_f = fi1 - fi0 + 1
    t_bin = max(1, n_t // cfg.rebin_t_target) if cfg.rebin_t_target else 1
    f_bin = max(1, n_f // cfg.rebin_f_target) if cfg.rebin_f_target else 1
    return t_bin, f_bin


def calc_bin_sizes_for_specs(
    specs: list,
    cfg: PlotConfig,
    t_start: datetime.datetime,
    t_end: datetime.datetime,
) -> tuple[int, int]:
    """Calculate common t_bin/f_bin for a requested range spanning one or more files."""
    total_t = 0
    min_t = None
    min_f = None

    for spec in specs:
        window = _overlap_window(spec, t_start, t_end)
        if window is None:
            continue
        t0, t1 = window
        t0s = (t0 - spec.dt_base).total_seconds()
        t1s = (t1 - spec.dt_base).total_seconds()
        ti0, ti1 = _find_range(spec.time, t0s, t1s)
        fi0, fi1 = _find_range(spec.freq, cfg.f_start, cfg.f_end)
        n_t = ti1 - ti0 + 1
        n_f = fi1 - fi0 + 1
        total_t += n_t
        min_t = n_t if min_t is None else min(min_t, n_t)
        min_f = n_f if min_f is None else min(min_f, n_f)

    if total_t <= 0 or min_t is None or min_f is None or min_f <= 0:
        raise ValueError(
            "Requested time/frequency range has no valid samples in the selected files."
        )

    t_bin = max(1, total_t // cfg.rebin_t_target) if cfg.rebin_t_target else 1
    f_bin = max(1, min_f // cfg.rebin_f_target) if cfg.rebin_f_target else 1

    # A short edge segment must not be fully trimmed away by a larger global bin.
    t_bin = min(t_bin, max(1, min_t))
    f_bin = min(f_bin, max(1, min_f))
    return t_bin, f_bin


def _read_polarization_segments_rebinned(
    specs: list,
    cfg: PlotConfig,
    t_start: datetime.datetime,
    t_end: datetime.datetime,
    t_bin: int,
    f_bin: int,
    common_base: datetime.datetime,
    polar_label: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Read all overlapping file segments for one polarization and concatenate in time."""
    z_parts: list[np.ndarray] = []
    t_parts: list[np.ndarray] = []
    freq_ref: np.ndarray | None = None
    last_time = -np.inf

    for spec in specs:
        window = _overlap_window(spec, t_start, t_end)
        if window is None:
            continue
        seg_start, seg_end = window
        print(
            f"  [{polar_label}] using {os.path.basename(spec.source_path)}: "
            f"{seg_start.isoformat()} -> {seg_end.isoformat()}"
        )
        z_seg, tt_seg, freq_seg = spec.read_slice_rebinned(
            t1=seg_start,
            t2=seg_end,
            f1=cfg.f_start,
            f2=cfg.f_end,
            t_bin=t_bin,
            f_bin=f_bin,
            chunk_mem_mb=cfg.chunk_mem_mb,
        )

        # Convert each file's time seconds to seconds relative to one common base.
        base_offset = (spec.dt_base - common_base).total_seconds()
        tt_common = tt_seg.astype(np.float64) + base_offset

        # If two FITS files overlap, keep the earlier file and remove duplicate/backward columns.
        keep = tt_common > last_time
        if not np.any(keep):
            print(
                f"  [{polar_label}] skipped fully overlapping segment: {spec.source_path}"
            )
            continue
        if not np.all(keep):
            removed = int(np.count_nonzero(~keep))
            print(f"  [{polar_label}] removed {removed} overlapping time column(s).")
            z_seg = z_seg[:, keep]
            tt_common = tt_common[keep]

        if freq_ref is None:
            freq_ref = freq_seg
        elif freq_ref.shape != freq_seg.shape or not np.allclose(
            freq_ref, freq_seg, rtol=0.0, atol=1e-3
        ):
            raise ValueError(
                "Frequency axes are inconsistent between FITS files. "
                "Please regrid/interpolate frequency first or use files from the same CSO mode.\n"
                f"Reference: {freq_ref[0]:.6f}~{freq_ref[-1]:.6f} MHz, "
                f"current: {freq_seg[0]:.6f}~{freq_seg[-1]:.6f} MHz, "
                f"file={spec.source_path}"
            )

        z_parts.append(z_seg)
        t_parts.append(tt_common)
        last_time = float(tt_common[-1])

    if not z_parts or freq_ref is None:
        raise ValueError(
            f"No usable {polar_label} segment found in the requested range."
        )

    z_all = np.concatenate(z_parts, axis=1)
    t_all = np.concatenate(t_parts)

    if t_all.size >= 3:
        dt = np.diff(t_all)
        median_dt = float(np.nanmedian(dt))
        if median_dt > 0 and float(np.nanmax(dt)) > 2.5 * median_dt:
            warnings.warn(
                f"Detected a possible time gap in merged {polar_label} data: "
                f"median dt={median_dt:.6g}s, max dt={float(np.nanmax(dt)):.6g}s. "
                "imshow uses a continuous time extent, so inspect the file boundary if the plot looks stretched.",
                stacklevel=2,
            )

    return z_all, t_all, freq_ref


def calc_polarization_ratio(
    Z_r: np.ndarray, Z_l: np.ndarray, eps: float = 1e-30
) -> np.ndarray:
    """
    Calculate polarization ratio (R-L)/(R+L) with safe division.

    Note:
        The result ranges from -1 to 1:
        - Positive values indicate R > L (right-handed dominance)
        - Negative values indicate L > R (left-handed dominance)
        - Zero indicates equal intensity (unpolarized)

    Color mapping:
        - 'bwr' colormap: blue for negative, white for 0, red for positive
        - This ensures correct visual representation of polarization direction
    """
    denom = Z_r + Z_l
    valid = (
        np.isfinite(Z_r) & np.isfinite(Z_l) & np.isfinite(denom) & (np.abs(denom) > eps)
    )
    ratio = np.full_like(Z_r, np.nan, dtype=np.float32)
    ratio[valid] = np.clip(
        (Z_r[valid] - Z_l[valid]) / denom[valid],
        -1.0,
        1.0,
    ).astype(np.float32)
    return ratio


def _safe_log10(arr: np.ndarray) -> np.ndarray:
    """Compute base-10 logarithm safely, handling non-positive values."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.log10(np.where(arr > 0, arr, np.nan))


def get_color_limits(
    data: np.ndarray, cfg: PlotConfig, plot_type: str = "ll"
) -> tuple[float, float]:
    """
    Get color scale limits based on configuration.

    Args:
        data: Input data array
        cfg: Plot configuration
        plot_type: Type of plot - "ll", "rr", "sum", or "ratio"

    Returns:
        Tuple of (vmin, vmax)
    """
    # Check if use_percentile_clipping attribute exists and is enabled
    if hasattr(cfg, "use_percentile_clipping") and not cfg.use_percentile_clipping:
        # Manual limits mode
        vmin = None
        vmax = None

        if plot_type == "ll":
            # Try individual LL limits first
            if hasattr(cfg, "manual_ll_vmin") and cfg.manual_ll_vmin is not None:
                vmin = cfg.manual_ll_vmin
            elif hasattr(cfg, "manual_vmin") and cfg.manual_vmin is not None:
                vmin = cfg.manual_vmin

            if hasattr(cfg, "manual_ll_vmax") and cfg.manual_ll_vmax is not None:
                vmax = cfg.manual_ll_vmax
            elif hasattr(cfg, "manual_vmax") and cfg.manual_vmax is not None:
                vmax = cfg.manual_vmax

        elif plot_type == "rr":
            # Try individual RR limits first
            if hasattr(cfg, "manual_rr_vmin") and cfg.manual_rr_vmin is not None:
                vmin = cfg.manual_rr_vmin
            elif hasattr(cfg, "manual_vmin") and cfg.manual_vmin is not None:
                vmin = cfg.manual_vmin

            if hasattr(cfg, "manual_rr_vmax") and cfg.manual_rr_vmax is not None:
                vmax = cfg.manual_rr_vmax
            elif hasattr(cfg, "manual_vmax") and cfg.manual_vmax is not None:
                vmax = cfg.manual_vmax

        elif plot_type == "sum":
            if hasattr(cfg, "manual_sum_vmin"):
                vmin = cfg.manual_sum_vmin
            if hasattr(cfg, "manual_sum_vmax"):
                vmax = cfg.manual_sum_vmax

        elif plot_type == "ratio":
            if hasattr(cfg, "manual_ratio_vmin"):
                vmin = cfg.manual_ratio_vmin
            if hasattr(cfg, "manual_ratio_vmax"):
                vmax = cfg.manual_ratio_vmax
            # ✅ FIX: Enforce symmetric color scale so that 0 always maps to
            # white in the 'bwr' colormap, regardless of user-supplied limits.
            if vmin is not None and vmax is not None:
                max_abs = max(abs(vmin), abs(vmax))
                vmin = -max_abs
                vmax = max_abs

        # If manual limits are not set, fall back to data range
        if vmin is None or vmax is None:
            valid_data = data[np.isfinite(data)]
            if len(valid_data) > 0:
                vmin = vmin if vmin is not None else np.nanmin(valid_data)
                vmax = vmax if vmax is not None else np.nanmax(valid_data)
            else:
                vmin, vmax = 0.0, 1.0
        return float(vmin), float(vmax)
    else:
        # Percentile-based clipping mode (default)
        if plot_type == "sum":
            vmin = np.nanpercentile(data, cfg.sum_vmin_pct)
            vmax = np.nanpercentile(data, cfg.sum_vmax_pct)
        elif plot_type == "ratio":
            vmin = np.nanpercentile(data, cfg.ratio_vmin_pct)
            vmax = np.nanpercentile(data, cfg.ratio_vmax_pct)
        else:
            # For LL and RR, use the same percentiles
            vmin = np.nanpercentile(data, cfg.vmin_pct)
            vmax = np.nanpercentile(data, cfg.vmax_pct)
        return float(vmin), float(vmax)


def _datetime_list_from_seconds(
    dt_base: datetime.datetime, seconds_array: np.ndarray
) -> list[datetime.datetime]:
    return [
        dt_base + datetime.timedelta(seconds=float(seconds))
        for seconds in seconds_array
    ]


def _prepare_imshow_extent(
    data: np.ndarray,
    time_seconds: np.ndarray,
    freq: np.ndarray,
    dt_base: datetime.datetime,
) -> tuple[np.ndarray, list[float], list[datetime.datetime], np.ndarray, bool]:
    """Prepare image data, datetime x extent, and ascending y extent for imshow."""
    freq_flipped = False
    if freq.size >= 2 and float(freq[0]) > float(freq[-1]):
        data = data[::-1, :].copy()
        freq = freq[::-1].copy()
        freq_flipped = True

    f_min = float(np.nanmin(freq))
    f_max = float(np.nanmax(freq))
    dt_list = _datetime_list_from_seconds(dt_base, time_seconds)
    x_start_num = mdates.date2num(dt_list[0])
    x_end_num = mdates.date2num(dt_list[-1])
    extent = [x_start_num, x_end_num, f_min, f_max]
    return data, extent, dt_list, freq, freq_flipped


def _configure_datetime_axis(
    ax, cfg: PlotConfig, x_start_num: float, x_end_num: float
) -> None:
    ax.xaxis_date()
    if cfg.xtick_interval is not None:
        ax.xaxis.set_major_locator(mdates.SecondLocator(interval=cfg.xtick_interval))
    else:
        span_seconds = max((x_end_num - x_start_num) * 86400.0, 1.0)
        interval = AxisConfigManager.calculate_optimal_ticks(span_seconds, max_ticks=15)
        ax.xaxis.set_major_locator(mdates.SecondLocator(interval=max(1, int(interval))))
    ax.xaxis.set_major_formatter(mdates.DateFormatter(cfg.xtick_format))
    ax.set_xlim(x_start_num, x_end_num)


def _get_ratio_norm_and_limits(ratio: np.ndarray, cfg: PlotConfig):
    finite = ratio[np.isfinite(ratio)]
    if finite.size == 0:
        raise ValueError("Polarization ratio contains no finite values")

    if cfg.ratio_auto_symmetric_scale:
        raw_abs = float(np.nanpercentile(np.abs(finite), cfg.ratio_abs_percentile))
        vmax_abs = float(
            np.clip(raw_abs, cfg.ratio_min_abs_limit, cfg.ratio_max_abs_limit)
        )
        if raw_abs < cfg.ratio_min_abs_limit:
            print(
                "  Ratio is physically close to zero; using enhanced symmetric "
                f"display range +/-{vmax_abs:.4f}."
            )
    else:
        vmin, vmax = get_color_limits(ratio, cfg, "ratio")
        vmax_abs = max(abs(vmin), abs(vmax))

    vmin = -vmax_abs
    vmax = vmax_abs
    return TwoSlopeNorm(vmin=vmin, vcenter=0.0, vmax=vmax), vmin, vmax


def _resolve_output_path(
    cfg: PlotConfig,
    t_start_dt: datetime.datetime,
    t_end_dt: datetime.datetime,
    items: list[dict],
) -> str:
    raw = (cfg.save_path or "").strip()
    if not raw:
        return ""

    tags = [item.get("plot_type", "") for item in items if item.get("plot_type")]
    plot_tags = "_".join(tags) if tags else "spectrogram"
    scale_tag = "auto" if cfg.use_percentile_clipping else "manual"
    auto_name = (
        f"CSO_spectrogram_{t_start_dt:%Y%m%d}_{t_start_dt:%H%M%S}_"
        f"{t_end_dt:%H%M%S}_{int(cfg.f_start)}-{int(cfg.f_end)}MHz_"
        f"{plot_tags}_{scale_tag}.png"
    )

    img_exts = {".png", ".jpg", ".jpeg", ".pdf", ".svg", ".tif", ".tiff"}
    ext = os.path.splitext(raw)[1].lower()
    if ext in img_exts:
        os.makedirs(os.path.dirname(raw) or ".", exist_ok=True)
        return raw
    if os.path.isdir(raw):
        return os.path.join(raw, auto_name)

    os.makedirs(raw, exist_ok=True)
    return os.path.join(raw, auto_name)


def optimize_workers(
    cfg: PlotConfig, data_size_mb: float, chunk_mem_mb: int
) -> tuple[int, float]:
    """
    Optimize number of workers based on available memory, data size, and chunk memory.

    Args:
        cfg: Plot configuration
        data_size_mb: Estimated data size in MB (per polarization)
        chunk_mem_mb: Memory limit per chunk

    Returns:
        Tuple of (optimal_workers, estimated_peak_memory_mb)
    """
    # Maximum workers needed for polarization processing (LL and RR)
    max_needed_workers = 2

    # Get user's worker preference
    user_workers = max_needed_workers
    if hasattr(cfg, "max_workers") and cfg.max_workers is not None:
        user_workers = min(cfg.max_workers, max_needed_workers)

    # Calculate memory requirements more accurately
    # For sequential processing (optimal_workers = 1):
    #   Peak memory = chunk_mem_mb + data_size_mb (one polarization at a time)
    # For parallel processing (optimal_workers = 2):
    #   Peak memory = 2 * chunk_mem_mb + 2 * data_size_mb (both polarizations simultaneously)
    # However, data_size_mb is already per polarization, so we need to adjust

    # Try to get available system memory
    try:
        import psutil

        available_memory = psutil.virtual_memory().available / (1024 * 1024)  # MB

        # Calculate memory for different worker counts
        memory_for_1_worker = chunk_mem_mb + data_size_mb  # Sequential
        memory_for_2_workers = 2 * (chunk_mem_mb + data_size_mb)  # Parallel

        # Determine optimal workers based on memory constraints
        if user_workers == 1:
            # User explicitly wants 1 worker
            optimal_workers = 1
            estimated_peak_memory = memory_for_1_worker
        else:
            # Check if we can afford parallel processing
            if memory_for_2_workers <= available_memory * 0.8:  # 80% safety margin
                optimal_workers = 2
                estimated_peak_memory = memory_for_2_workers
            elif memory_for_1_worker <= available_memory * 0.8:
                # Can't do parallel, but can do sequential
                optimal_workers = 1
                estimated_peak_memory = memory_for_1_worker
                print(
                    "  Note: Insufficient memory for parallel processing. Switching to sequential."
                )
            else:
                # Even sequential processing exceeds memory limits
                raise MemoryError(
                    f"Insufficient memory. Required: {memory_for_1_worker:.1f} MB, "
                    f"Available: {available_memory:.1f} MB. "
                    f"Try reducing chunk_mem_mb or data range."
                )

        # Additional safety check
        if estimated_peak_memory > available_memory * 0.9:
            warnings.warn(
                f"Estimated peak memory ({estimated_peak_memory:.1f} MB) exceeds 90% of "
                f"available memory ({available_memory:.1f} MB). Consider reducing settings.",
                stacklevel=2,
            )

    except ImportError:
        warnings.warn("psutil not installed, using conservative defaults", stacklevel=2)
        # Conservative default: assume limited memory
        optimal_workers = 1
        estimated_peak_memory = chunk_mem_mb + data_size_mb

    # Ensure at least 1 worker
    optimal_workers = max(1, optimal_workers)

    return optimal_workers, estimated_peak_memory


# ============================================================
#  MAIN PROCESSING AND PLOTTING
# ============================================================


@timing_decorator
def process_and_plot(cfg: PlotConfig, data_list: list):
    """Main processing pipeline: read data, compute derived quantities, and generate plots."""
    validate_config(cfg)
    t_start_dt = _as_datetime(cfg.t_start, "t_start")
    t_end_dt = _as_datetime(cfg.t_end, "t_end")

    cso_l_specs = _select_overlapping_specs(data_list, "LL", t_start_dt, t_end_dt)
    cso_r_specs = _select_overlapping_specs(data_list, "RR", t_start_dt, t_end_dt)
    if not cso_l_specs or not cso_r_specs:
        available = []
        for spec in data_list:
            spec_start, spec_end = _spec_time_bounds(spec)
            available.append(
                f"{spec.polar}: {spec_start.isoformat()} -> {spec_end.isoformat()}  "
                f"{spec.source_path}"
            )
        raise ValueError(
            "Complete LL and RR data not found for the requested time range.\n"
            "Available file coverage:\n" + "\n".join(available)
        )

    _validate_contiguous_time_coverage(cso_l_specs, t_start_dt, t_end_dt, "LL")
    _validate_contiguous_time_coverage(cso_r_specs, t_start_dt, t_end_dt, "RR")

    common_base = min(spec.dt_base for spec in [*cso_l_specs, *cso_r_specs])
    t_bin, f_bin = calc_bin_sizes_for_specs(cso_l_specs, cfg, t_start_dt, t_end_dt)

    estimated_data_size_mb = _estimate_raw_selection_mb(
        cso_l_specs, cfg, t_start_dt, t_end_dt
    )
    optimal_workers, estimated_peak_memory = optimize_workers(
        cfg, estimated_data_size_mb, cfg.chunk_mem_mb
    )

    print("Selected FITS coverage:")
    for spec in [*cso_l_specs, *cso_r_specs]:
        spec_start, spec_end = _spec_time_bounds(spec)
        print(
            f"  - {spec.polar}: {spec_start.isoformat()} -> {spec_end.isoformat()} | "
            f"{os.path.basename(spec.source_path)}"
        )
    print(f"Common time base: {common_base.isoformat()}")
    print(f"Common bin size: t_bin={t_bin}, f_bin={f_bin}")

    print("Memory configuration:")
    print(f"  - Chunk memory limit: {cfg.chunk_mem_mb} MB per worker")
    print(f"  - Estimated data size: {estimated_data_size_mb:.1f} MB")
    print(f"  - Optimal workers: {optimal_workers}")
    print(f"  - Estimated peak memory: {estimated_peak_memory:.1f} MB")

    if estimated_peak_memory > 2000:
        print(
            f"Warning: Estimated peak memory ({estimated_peak_memory:.1f} MB) is high."
        )
        print("   Consider reducing chunk_mem_mb or max_workers.")

    print("Block reading + downsampling + multi-file time concatenation...")

    if optimal_workers == 1:
        print("Processing sequentially with 1 worker for memory control...")
        print("  Processing LL polarization...")
        Z_l, tt, freq = _read_polarization_segments_rebinned(
            cso_l_specs,
            cfg,
            t_start_dt,
            t_end_dt,
            t_bin,
            f_bin,
            common_base,
            "LL",
        )
        import gc

        gc.collect()

        print("  Processing RR polarization...")
        Z_r, tt_r, freq_r = _read_polarization_segments_rebinned(
            cso_r_specs,
            cfg,
            t_start_dt,
            t_end_dt,
            t_bin,
            f_bin,
            common_base,
            "RR",
        )
    else:
        print(f"Processing in parallel with {optimal_workers} workers...")
        with ThreadPoolExecutor(max_workers=optimal_workers) as exe:
            future_to_polar = {
                exe.submit(
                    _read_polarization_segments_rebinned,
                    cso_l_specs,
                    cfg,
                    t_start_dt,
                    t_end_dt,
                    t_bin,
                    f_bin,
                    common_base,
                    "LL",
                ): "LL",
                exe.submit(
                    _read_polarization_segments_rebinned,
                    cso_r_specs,
                    cfg,
                    t_start_dt,
                    t_end_dt,
                    t_bin,
                    f_bin,
                    common_base,
                    "RR",
                ): "RR",
            }
            results_dict = {}
            for future in as_completed(future_to_polar):
                polar_key = future_to_polar[future]
                results_dict[polar_key] = future.result()

            Z_l, tt, freq = results_dict["LL"]
            Z_r, tt_r, freq_r = results_dict["RR"]

    if Z_l.shape != Z_r.shape:
        raise ValueError(
            f"LL/RR shape mismatch after merge: LL={Z_l.shape}, RR={Z_r.shape}"
        )
    if tt.shape != tt_r.shape or not np.allclose(tt, tt_r, rtol=0.0, atol=1e-6):
        raise ValueError("LL/RR time axes are inconsistent after multi-file merging.")
    if freq.shape != freq_r.shape or not np.allclose(freq, freq_r, rtol=0.0, atol=1e-3):
        raise ValueError(
            "LL/RR frequency axes are inconsistent after multi-file merging."
        )

    Z_sum = Z_l + Z_r
    ratio = calc_polarization_ratio(Z_r, Z_l)

    dt_list = _datetime_list_from_seconds(common_base, tt)
    print("Axis diagnostics:")
    print(f"  common dt_base: {common_base.isoformat()}")
    print(f"  tt[0], tt[-1]: {float(tt[0]):.6f}, {float(tt[-1]):.6f}")
    print(f"  first displayed datetime: {dt_list[0].isoformat()}")
    print(f"  last displayed datetime: {dt_list[-1].isoformat()}")
    print(f"  freq[0], freq[-1]: {float(freq[0]):.6f}, {float(freq[-1]):.6f}")

    print("Data diagnostics:")
    _array_stats("LL", Z_l)
    _array_stats("RR", Z_r)
    _array_stats("Z_sum", Z_sum)
    _array_stats("ratio", ratio)

    items = []
    date_str = t_start_dt.strftime("%Y-%m-%d")

    def create_plot_item(data, title, cmap, cbar_label, plot_type="ll"):
        vmin, vmax = get_color_limits(data, cfg, plot_type)
        return dict(
            data=data,
            title=title,
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            cbar_label=cbar_label,
            plot_type=plot_type,
        )

    if cfg.plot_ll:
        Z_log = _safe_log10(Z_l)
        items.append(
            create_plot_item(
                Z_log,
                f"CSO/CBSm LL {date_str}",
                "jet",
                r"log$_{10}$ Brightness Temp (K)",
                plot_type="ll",
            )
        )

    if cfg.plot_rr:
        Z_log = _safe_log10(Z_r)
        items.append(
            create_plot_item(
                Z_log,
                f"CSO/CBSm RR {date_str}",
                "jet",
                r"log$_{10}$ Brightness Temp (K)",
                plot_type="rr",
            )
        )

    if cfg.plot_sum:
        Z_log = _safe_log10(Z_sum)
        items.append(
            create_plot_item(
                Z_log,
                f"CSO/CBSm LL+RR {date_str}",
                "jet",
                r"log$_{10}$ Brightness Temp (K)",
                plot_type="sum",
            )
        )

    if cfg.plot_ratio:
        items.append(
            dict(
                data=ratio,
                title="CSO/CBSm Polarization Ratio (R-L)/(R+L)",
                cmap="bwr",
                vmin=cfg.manual_ratio_vmin,
                vmax=cfg.manual_ratio_vmax,
                cbar_label="Polarization Ratio (R-L)/(R+L)",
                plot_type="ratio",
            )
        )

    if not items:
        print("No plot items selected, exiting")
        return

    display_data_list = []
    extent_list = []
    freq_out = None
    freq_flipped = False
    for item in items:
        data_out, extent, dt_list_i, freq_out_i, flipped = _prepare_imshow_extent(
            item["data"], tt, freq, common_base
        )
        display_data_list.append(data_out)
        extent_list.append(extent)
        dt_list = dt_list_i
        freq_out = freq_out_i
        freq_flipped = freq_flipped or flipped

    x_start_num, x_end_num = extent_list[0][0], extent_list[0][1]
    f_min, f_max = extent_list[0][2], extent_list[0][3]
    print(f"  frequency flipped: {freq_flipped}")

    if not cfg.show_plot:
        plt.switch_backend("Agg")

    n = len(items)
    fig, axs = plt.subplots(
        n,
        1,
        figsize=(cfg.fig_width, cfg.fig_height_per * n),
        sharex=True,
        sharey=True,
        constrained_layout=True,  # Better layout management
    )
    fig.subplots_adjust(hspace=0.15)

    if n == 1:
        axs = [axs]

    for idx, (ax, item, display_data, extent) in enumerate(
        zip(axs, items, display_data_list, extent_list, strict=False)
    ):
        if item["plot_type"] == "ratio":
            norm, vmin, vmax = _get_ratio_norm_and_limits(item["data"], cfg)
            print(f"  ratio display limits: vmin={vmin:.6f}, vmax={vmax:.6f}")
            im = ax.imshow(
                display_data,
                extent=extent,
                origin="lower",
                aspect="auto",
                cmap=item["cmap"],
                norm=norm,
            )
        else:
            im = ax.imshow(
                display_data,
                extent=extent,
                origin="lower",
                aspect="auto",
                cmap=item["cmap"],
                vmin=item["vmin"],
                vmax=item["vmax"],
            )
        ax.set_title(item["title"], fontsize=12)

        ax.set_ylim(f_min, f_max)
        AxisConfigManager.configure_frequency_axis(ax, cfg, freq_out)

        if idx == len(items) - 1:
            _configure_datetime_axis(ax, cfg, x_start_num, x_end_num)
            if cfg.show_axis_labels:
                ax.set_xlabel("Time (UT)", fontsize=10)
        else:
            ax.xaxis_date()
            ax.xaxis.set_major_formatter(mdates.DateFormatter(cfg.xtick_format))
            ax.set_xlim(x_start_num, x_end_num)
            ax.tick_params(labelbottom=False)

        cbar = fig.colorbar(im, ax=ax, pad=0.01)
        cbar.set_label(item["cbar_label"], fontsize=9)

        if cfg.highlight_freqs is not None:
            for freq_val in cfg.highlight_freqs:
                if f_min <= freq_val <= f_max:
                    ax.axhline(
                        y=freq_val,
                        color="red",
                        linestyle="--",
                        linewidth=1.3,
                        alpha=0.6,
                    )
                    # 添加文本标签（只在有标签显示时才添加）
                    if cfg.show_axis_labels:
                        x_min = mdates.date2num(dt_list[0])
                        x_max = mdates.date2num(dt_list[-1])
                        x_pos = x_min + 0.01 * (x_max - x_min)
                        ax.text(
                            x_pos,
                            freq_val + 0.01 * (cfg.f_end - cfg.f_start),
                            f"{freq_val} MHz",
                            color="red",
                            fontsize=4,
                            verticalalignment="bottom",
                            horizontalalignment="left",
                            bbox=dict(
                                boxstyle="round,pad=0.2", facecolor="g", alpha=0.3
                            ),
                        )

    save_path = _resolve_output_path(cfg, t_start_dt, t_end_dt, items)
    if save_path:
        fig.savefig(save_path, dpi=cfg.dpi, bbox_inches="tight")
        if not os.path.exists(save_path):
            raise RuntimeError(f"Save failed: file not found at {save_path}")
        if os.path.getsize(save_path) == 0:
            raise RuntimeError(f"Save failed: file is empty at {save_path}")
        print(f"Final save path: {os.path.abspath(save_path)}")

    if cfg.show_plot:
        plt.show()
    if cfg.close_after_save:
        plt.close(fig)


# ============================================================
#  ENTRY POINT
# ============================================================


def test_polarization_formula():
    """Test function to verify polarization ratio calculation."""
    print("\n" + "=" * 60)
    print("Testing Polarization Ratio Formula (R-L)/(R+L)")
    print("=" * 60)

    # Test cases
    test_cases = [
        ("R > L", 10.0, 5.0, (10 - 5) / (10 + 5)),  # Right-handed dominant
        ("L > R", 5.0, 10.0, (5 - 10) / (5 + 10)),  # Left-handed dominant
        ("R = L", 10.0, 10.0, 0.0),  # Unpolarized
        ("R >> L", 100.0, 1.0, (100 - 1) / (100 + 1)),  # Strong right-handed
        ("L >> R", 1.0, 100.0, (1 - 100) / (1 + 100)),  # Strong left-handed
    ]

    for name, r_val, l_val, expected in test_cases:
        ratio = calc_polarization_ratio(
            np.array([r_val], dtype=np.float32), np.array([l_val], dtype=np.float32)
        )[0]
        print(f"{name}: R={r_val}, L={l_val}")
        print(f"  Expected (R-L)/(R+L): {expected:.4f}, Calculated: {ratio:.4f}")
        print(f"  Difference: {abs(ratio - expected):.6f}")
        print()


class ConfigManager:
    """配置管理器，集中处理所有配置逻辑"""

    @staticmethod
    def create_default_config() -> PlotConfig:
        """创建默认配置"""
        return PlotConfig()

    @staticmethod
    def update_config_from_dict(cfg: PlotConfig, config_dict: dict) -> PlotConfig:
        """从字典更新配置"""
        for key, value in config_dict.items():
            if hasattr(cfg, key):
                setattr(cfg, key, value)
        return cfg

    @staticmethod
    def validate_all(cfg: PlotConfig) -> tuple[bool, list[str]]:
        """验证所有配置，返回(是否有效, 错误信息列表)"""
        errors = []

        try:
            validate_config(cfg)
        except Exception as e:
            errors.append(f"基础配置错误: {e}")

        try:
            validate_axis_config(cfg)
        except Exception as e:
            errors.append(f"坐标轴配置错误: {e}")

        return len(errors) == 0, errors


if __name__ == "__main__":
    # Run polarization formula test
    test_polarization_formula()

    # Initialize configuration with default parameters
    cfg = PlotConfig()

    # ============================================================
    #  USER CUSTOMIZATION AREA - MODIFY AS NEEDED
    # ============================================================

    # Example 1: Use manual color scale limits with individual settings
    # cfg.use_percentile_clipping = False
    # # Individual polarization limits
    # cfg.manual_ll_vmin = 0.0
    # cfg.manual_ll_vmax = 8.0
    # cfg.manual_rr_vmin = 0.0
    # cfg.manual_rr_vmax = 10.0
    # # Sum and ratio limits
    # cfg.manual_sum_vmin = 0.0
    # cfg.manual_sum_vmax = 10.0
    # cfg.manual_ratio_vmin = -1.0
    # cfg.manual_ratio_vmax = 1.0
    # # Backward compatibility (optional)
    # cfg.manual_vmin = 0.0
    # cfg.manual_vmax = 10.0

    # Example 2: Adjust CPU core usage
    # cfg.max_workers = 1  # Use single core for memory conservation
    # cfg.max_workers = None  # Auto-detect based on available memory

    # Example 3: Customize highlight frequencies
    # cfg.highlight_freqs = [149.0, 164.0, 190.0, 205.0, 223.0, 238.0, 285.0, 300.0]

    # Example 4: Adjust memory usage
    # cfg.chunk_mem_mb = 50  # Increase chunk size for faster processing
    # cfg.chunk_mem_mb = 10  # Decrease chunk size for memory-constrained systems

    # 示例：使用坐标轴控制功能
    # cfg.show_axis_labels = True  # 显示坐标轴标签
    # cfg.axis_label_rotation = 45  # 旋转45度防止重叠
    # cfg.xtick_interval = 30  # X轴每30秒一个主刻度
    # cfg.ytick_interval = 50  # Y轴每50MHz一个主刻度
    # cfg.xtick_format = "%H:%M"  # 只显示小时和分钟
    # cfg.show_minor_ticks = False  # 不显示次要刻度

    # 验证配置
    is_valid, errors = ConfigManager.validate_all(cfg)
    if not is_valid:
        print("配置错误:", "\n".join(errors))
        exit(1)

    # ============================================================
    #  EXECUTION
    # ============================================================

    print("=" * 60)
    print("CSO Spectrogram Plotting Tool")
    print("=" * 60)
    file_paths = get_config_file_paths(cfg)
    print("Files:")
    for file_path in file_paths:
        print(f"  - {os.path.basename(file_path)}")
    print(f"Time range: {cfg.t_start} to {cfg.t_end}")
    print(f"Frequency range: {cfg.f_start} to {cfg.f_end} MHz")
    print(
        f"Color scale method: {'Manual limits' if not cfg.use_percentile_clipping else 'Percentile clipping'}"
    )
    if not cfg.use_percentile_clipping:
        # Display individual limits if set
        ll_vmin = (
            cfg.manual_ll_vmin
            if hasattr(cfg, "manual_ll_vmin") and cfg.manual_ll_vmin is not None
            else cfg.manual_vmin
        )
        ll_vmax = (
            cfg.manual_ll_vmax
            if hasattr(cfg, "manual_ll_vmax") and cfg.manual_ll_vmax is not None
            else cfg.manual_vmax
        )
        rr_vmin = (
            cfg.manual_rr_vmin
            if hasattr(cfg, "manual_rr_vmin") and cfg.manual_rr_vmin is not None
            else cfg.manual_vmin
        )
        rr_vmax = (
            cfg.manual_rr_vmax
            if hasattr(cfg, "manual_rr_vmax") and cfg.manual_rr_vmax is not None
            else cfg.manual_vmax
        )

        print(f"  Manual limits - LL: [{ll_vmin}, {ll_vmax}]")
        print(f"  Manual limits - RR: [{rr_vmin}, {rr_vmax}]")
        print(f"  Manual limits - Sum: [{cfg.manual_sum_vmin}, {cfg.manual_sum_vmax}]")
        print(
            f"  Manual limits - Ratio: [{cfg.manual_ratio_vmin}, {cfg.manual_ratio_vmax}]"
        )
    else:
        print(f"  Percentile clipping - LL/RR: [{cfg.vmin_pct}%, {cfg.vmax_pct}%]")
        print(
            f"  Percentile clipping - Sum: [{cfg.sum_vmin_pct}%, {cfg.sum_vmax_pct}%]"
        )
        print(
            f"  Percentile clipping - Ratio: [{cfg.ratio_vmin_pct}%, {cfg.ratio_vmax_pct}%]"
        )

    # 显示坐标轴配置
    print("坐标轴配置:")
    print(f"  - 显示标签: {cfg.show_axis_labels}")
    print(f"  - 标签旋转: {cfg.axis_label_rotation} 度")
    print(
        f"  - X轴刻度间隔: {cfg.xtick_interval if cfg.xtick_interval is not None else '自动'}"
    )
    print(
        f"  - Y轴刻度间隔: {cfg.ytick_interval if cfg.ytick_interval is not None else '自动'}"
    )
    print(f"  - X轴格式: {cfg.xtick_format}")
    print(f"  - 显示次要刻度: {cfg.show_minor_ticks}")

    # Display memory information
    total_gb, available_gb, usage_percent = get_system_memory_info()
    if total_gb > 0:
        print(
            f"System memory: {total_gb:.1f} GB total, {available_gb:.1f} GB available ({usage_percent:.1f}% used)"
        )

    print("Memory configuration:")
    print(f"  - Chunk memory: {cfg.chunk_mem_mb} MB")
    # Check if max_workers attribute exists (for backward compatibility)
    if hasattr(cfg, "max_workers"):
        max_workers_display = (
            cfg.max_workers if cfg.max_workers is not None else "Auto-detect"
        )
    else:
        max_workers_display = "Auto-detect (default)"
    print(f"  - Max workers: {max_workers_display}")
    print("=" * 60)

    # Execute processing pipeline
    t0 = time.perf_counter()
    hdus = []
    data_list = []
    try:
        for file_path in file_paths:
            data_part, hdu = read_cso_fits(file_path)
            data_list.extend(data_part)
            hdus.append(hdu)
        process_and_plot(cfg, data_list)
    except Exception as e:
        print(f"Error during processing: {e}")
        import traceback

        traceback.print_exc()
    finally:
        for hdu in hdus:
            hdu.close()

    print(f"\nTotal execution time: {time.perf_counter() - t0:.2f} s")
