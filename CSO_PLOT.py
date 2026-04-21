# -*- coding: utf-8 -*-
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

import time
import datetime
import os
import warnings
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from astropy.io import fits
from tqdm import tqdm


# ============================================================
#  ★ CONFIGURATION PARAMETERS - MODIFY ONLY HERE ★
# ============================================================
@dataclass
class PlotConfig:
    """Configuration class for CSO spectrogram plotting parameters."""
    
    # File path
    file_path: str = (
        r'D:\spike_topping_type_III\2025\20250503'
        r'\OROCH_MWRS01_SRSP_L1_05M_20250503071510_V01.01.fits'
    )

    # Time range (UTC)
    t_start: datetime.datetime = field(
        default_factory=lambda: datetime.datetime(2025, 5, 3, 7, 14, 0))
    t_end:   datetime.datetime = field(
        default_factory=lambda: datetime.datetime(2025, 5, 3, 7, 21, 0))

    # Frequency range (MHz)
    f_start: float = 80
    f_end:   float = 340

    # Target number of grid points after downsampling (time / frequency axes)
    # Larger values produce finer plots but are slower; None = no downsampling
    rebin_t_target: int = 1000
    rebin_f_target: int = 1000

    # Peak memory limit per chunk during block reading (MB)
    # Lower values reduce memory pressure further
    chunk_mem_mb: int = 28

    # Maximum number of CPU cores to use (None = auto-detect, 1 = single core)
    max_workers: Optional[int] = None

    # Plot toggles
    plot_ll:    bool = False
    plot_rr:    bool = False
    plot_sum:   bool = True
    plot_ratio: bool = True

    # Color scale configuration - CHOOSE ONE METHOD:
    # Method 1: Percentile-based clipping (automatic)
    use_percentile_clipping: bool = False  # Set to False to use manual limits
    vmin_pct:     float = 0.1
    vmax_pct:     float = 99.9
    sum_vmin_pct: float = 0.1
    sum_vmax_pct: float = 99.9
    # For ratio, we need symmetric percentiles since data ranges from -1 to 1
    ratio_vmin_pct: float = 1.0    # Use 1st percentile for negative side
    ratio_vmax_pct: float = 99.0   # Use 99th percentile for positive side
    
    # Method 2: Manual absolute limits (used when use_percentile_clipping = False)
    # Set these to specific values like 0.0 and 10.0
    # Individual polarization limits
    manual_ll_vmin: Optional[float] = 1.8
    manual_ll_vmax: Optional[float] = 5
    manual_rr_vmin: Optional[float] = 1.8
    manual_rr_vmax: Optional[float] = 5
    # Sum and ratio limits
    manual_sum_vmin: Optional[float] = 1.8
    manual_sum_vmax: Optional[float] = 3.2
    manual_ratio_vmin: Optional[float] = -1.0
    manual_ratio_vmax: Optional[float] = 1.0
    
    # Backward compatibility: if individual limits not set, use these
    manual_vmin: Optional[float] = None
    manual_vmax: Optional[float] = None

    # Figure dimensions
    fig_width:      float = 12.0
    fig_height_per: float = 3.0   # Height per subplot (inches)

    # Time axis tick intervals (seconds)
    major_tick_interval: int = 10
    minor_tick_interval: int = 2

    # Save path (empty for display only)
    save_path: str = r'D:\spike_topping_type_III\2025\20250503\CSO_PLOT\3\1'
    dpi:       int = 300
    
    # List of frequencies to highlight (MHz)
    highlight_freqs: Optional[List[float]] = field(default_factory=lambda: None)
    #[149, 164, 190, 205, 223, 238, 285, 300, 309, 324]

    # 坐标轴显示控制
    show_axis_labels: bool = True  # 是否显示坐标轴标签
    axis_label_rotation: float = 0.0  # 标签旋转角度（度）
    xtick_interval: Optional[int] = None  # X轴刻度间隔（秒），None为自动
    ytick_interval: Optional[float] = None  # Y轴刻度间隔（MHz），None为自动
    xtick_format: str = "%H:%M:%S"  # X轴时间格式
    show_minor_ticks: bool = True  # 是否显示次要刻度

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
    i0 = int(np.clip(np.searchsorted(arr, lo, side='left'),  0, len(arr)-1))
    i1 = int(np.clip(np.searchsorted(arr, hi, side='right')-1, 0, len(arr)-1))
    return i0, max(i0, i1)


def get_system_memory_info() -> Tuple[float, float, float]:
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
        warnings.warn("psutil not installed, cannot get memory info")
        return 0.0, 0.0, 0.0


def validate_config(cfg: PlotConfig) -> None:
    """Validate configuration parameters."""
    if cfg.t_start >= cfg.t_end:
        raise ValueError(f"t_start ({cfg.t_start}) must be earlier than t_end ({cfg.t_end})")
    
    if cfg.f_start >= cfg.f_end:
        raise ValueError(f"f_start ({cfg.f_start}) must be less than f_end ({cfg.f_end})")
    
    if cfg.rebin_t_target is not None and cfg.rebin_t_target <= 0:
        raise ValueError(f"rebin_t_target must be positive, got {cfg.rebin_t_target}")
    
    if cfg.rebin_f_target is not None and cfg.rebin_f_target <= 0:
        raise ValueError(f"rebin_f_target must be positive, got {cfg.rebin_f_target}")
    
    if cfg.chunk_mem_mb <= 0:
        raise ValueError(f"chunk_mem_mb must be positive, got {cfg.chunk_mem_mb}")
    
    # Check for max_workers attribute (may not exist in older config)
    if hasattr(cfg, 'max_workers'):
        if cfg.max_workers is not None and cfg.max_workers <= 0:
            raise ValueError(f"max_workers must be positive or None, got {cfg.max_workers}")
    
    # Check for use_percentile_clipping attribute
    if hasattr(cfg, 'use_percentile_clipping'):
        if not cfg.use_percentile_clipping:
            # Check individual polarization limits
            if hasattr(cfg, 'manual_ll_vmin') and hasattr(cfg, 'manual_ll_vmax'):
                if cfg.manual_ll_vmin is not None and cfg.manual_ll_vmax is not None:
                    if cfg.manual_ll_vmin >= cfg.manual_ll_vmax:
                        raise ValueError(f"manual_ll_vmin ({cfg.manual_ll_vmin}) must be less than manual_ll_vmax ({cfg.manual_ll_vmax})")
            
            if hasattr(cfg, 'manual_rr_vmin') and hasattr(cfg, 'manual_rr_vmax'):
                if cfg.manual_rr_vmin is not None and cfg.manual_rr_vmax is not None:
                    if cfg.manual_rr_vmin >= cfg.manual_rr_vmax:
                        raise ValueError(f"manual_rr_vmin ({cfg.manual_rr_vmin}) must be less than manual_rr_vmax ({cfg.manual_rr_vmax})")
            
            # Check backward compatibility limits
            if hasattr(cfg, 'manual_vmin') and hasattr(cfg, 'manual_vmax'):
                if cfg.manual_vmin is not None and cfg.manual_vmax is not None:
                    if cfg.manual_vmin >= cfg.manual_vmax:
                        raise ValueError(f"manual_vmin ({cfg.manual_vmin}) must be less than manual_vmax ({cfg.manual_vmax})")
            
            # Check sum limits
            if hasattr(cfg, 'manual_sum_vmin') and hasattr(cfg, 'manual_sum_vmax'):
                if cfg.manual_sum_vmin is not None and cfg.manual_sum_vmax is not None:
                    if cfg.manual_sum_vmin >= cfg.manual_sum_vmax:
                        raise ValueError(f"manual_sum_vmin ({cfg.manual_sum_vmin}) must be less than manual_sum_vmax ({cfg.manual_sum_vmax})")
            
            # Check ratio limits
            if hasattr(cfg, 'manual_ratio_vmin') and hasattr(cfg, 'manual_ratio_vmax'):
                if cfg.manual_ratio_vmin is not None and cfg.manual_ratio_vmax is not None:
                    if cfg.manual_ratio_vmin >= cfg.manual_ratio_vmax:
                        raise ValueError(f"manual_ratio_vmin ({cfg.manual_ratio_vmin}) must be less than manual_ratio_vmax ({cfg.manual_ratio_vmax})")
    
    # Warn about potential memory issues
    if hasattr(cfg, 'max_workers') and cfg.max_workers is not None and cfg.max_workers > 2:
        warnings.warn(f"max_workers={cfg.max_workers} is set, but only 2 workers are needed for polarization processing")
    
    # Check memory configuration
    if cfg.chunk_mem_mb > 500:
        warnings.warn(f"chunk_mem_mb={cfg.chunk_mem_mb} MB is quite high. Consider reducing for memory-constrained systems.")
    
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
    __slots__ = ('_raw', 'time', 'freq', 'polar', 'dateobs', 'unit', 'dt_base')

    def __init__(self, raw_memmap, time_arr, freq_arr,
                 polar, dateobs, unit, dt_base):
        self._raw    = raw_memmap
        self.time    = time_arr.astype(np.float64)
        self.freq    = freq_arr.astype(np.float32)
        self.polar   = polar
        self.dateobs = dateobs
        self.unit    = unit
        self.dt_base = dt_base

    def read_slice_rebinned(self,
                            t1: datetime.datetime, t2: datetime.datetime,
                            f1: float, f2: float,
                            t_bin: int, f_bin: int,
                            chunk_mem_mb: int = 64):
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
        fi0, fi1 = _find_range(self.freq, f1,  f2)

        n_freq_raw = fi1 - fi0 + 1
        n_time_raw = ti1 - ti0 + 1

        # Align to bin multiples
        n_freq_trim = (n_freq_raw // f_bin) * f_bin
        n_time_trim = (n_time_raw // t_bin) * t_bin
        n_freq_out  = n_freq_trim // f_bin
        n_time_out  = n_time_trim // t_bin

        raw_mb = n_freq_raw * n_time_raw * 4 / 1e6
        out_mb = n_freq_out * n_time_out  * 4 / 1e6
        print(f"    [{self.polar}] Raw: {n_freq_raw}×{n_time_raw} "
              f"({raw_mb:.0f} MB)  ->  Output: {n_freq_out}×{n_time_out} "
              f"({out_mb:.1f} MB)")

        # Columns per chunk: keep memory ≈ chunk_mem_mb, must be multiple of t_bin
        cols_per_chunk = max(t_bin,
                             (int(chunk_mem_mb * 1e6 / (n_freq_trim * 4))
                              // t_bin) * t_bin)

        Z_out = np.empty((n_freq_out, n_time_out), dtype=np.float32)
        out_col = 0

        for col0 in tqdm(range(0, n_time_trim, cols_per_chunk),
                         desc=f"    Reading {self.polar}", leave=False):
            col1   = min(col0 + cols_per_chunk, n_time_trim)
            n_cols = ((col1 - col0) // t_bin) * t_bin   # Alignment
            if n_cols == 0:
                continue

            # Trigger actual disk I/O, immediately copy to float32
            chunk = np.array(
                self._raw[fi0 : fi0 + n_freq_trim,
                          ti0 + col0 : ti0 + col0 + n_cols],
                dtype=np.float32
            )   # (n_freq_trim, n_cols)

            # Perform block-mean for both frequency and time axes
            n_t_chunk = n_cols // t_bin
            chunk_rb = (chunk
                        .reshape(n_freq_out, f_bin, n_t_chunk, t_bin)
                        .mean(axis=(1, 3), dtype=np.float32))

            Z_out[:, out_col : out_col + n_t_chunk] = chunk_rb
            out_col += n_t_chunk

        freq_out = (self.freq[fi0 : fi0 + n_freq_trim]
                    .reshape(n_freq_out, f_bin).mean(axis=1))
        time_out = (self.time[ti0 : ti0 + n_time_trim]
                    .reshape(n_time_out, t_bin).mean(axis=1))

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
        raw    = hdu[0].data
        time_  = np.ravel(hdu[1].data['time'])
        freq_  = np.ravel(hdu[1].data['frequency'])

        dateobs = header.get('DATE-OBS') or header.get('DATE_OBS')
        dt_base = datetime.datetime.fromisoformat(dateobs[:10])

        if time_[0] < 0:
            dt_base = dt_base + datetime.timedelta(days=1)
            dateobs = dt_base.isoformat()

        polars = header['POLARIZA']
        if header['NAXIS'] == 3 and polars == 'RCP and LCP':
            polars = 'RL'

        unit = header.get('BUNIT') or header.get('QUANTITY', 'K')

        results = []
        if raw.ndim == 2:
            results.append(LazySpectrogram(
                raw, time_, freq_, polars, dateobs, unit, dt_base))
            print(f"  Single polarization: {polars}  Size: {raw.shape}  "
                  f"({raw.nbytes/1e9:.2f} GB, not loaded into memory)")
        elif raw.ndim == 3:
            for ii in range(raw.shape[0]):
                polar = polars[ii] * 2
                results.append(LazySpectrogram(
                    raw[ii], time_, freq_, polar, dateobs, unit, dt_base))
            print(f"  Dual polarization  Full size: {raw.shape}  "
                  f"({raw.nbytes/1e9:.2f} GB, not loaded into memory)")

        return results, hdu

    except Exception:
        hdu.close()
        raise


def validate_axis_config(cfg: PlotConfig) -> None:
    """验证坐标轴配置参数"""
    if not isinstance(cfg.show_axis_labels, bool):
        raise TypeError(f"show_axis_labels must be boolean, got {type(cfg.show_axis_labels)}")
    
    if not isinstance(cfg.axis_label_rotation, (int, float)):
        raise TypeError(f"axis_label_rotation must be numeric, got {type(cfg.axis_label_rotation)}")
    
    if not (-90 <= cfg.axis_label_rotation <= 90):
        warnings.warn(f"axis_label_rotation should be between -90 and 90 degrees, got {cfg.axis_label_rotation}")
        cfg.axis_label_rotation = np.clip(cfg.axis_label_rotation, -90, 90)
    
    if cfg.xtick_interval is not None and cfg.xtick_interval <= 0:
        raise ValueError(f"xtick_interval must be positive, got {cfg.xtick_interval}")
    
    if cfg.ytick_interval is not None and cfg.ytick_interval <= 0:
        raise ValueError(f"ytick_interval must be positive, got {cfg.ytick_interval}")
    
    if not isinstance(cfg.show_minor_ticks, bool):
        raise TypeError(f"show_minor_ticks must be boolean, got {type(cfg.show_minor_ticks)}")


class AxisConfigManager:
    """坐标轴配置管理器，负责处理和优化坐标轴显示"""
    
    @staticmethod
    def calculate_optimal_ticks(data_range: float, num_points: int = None, 
                               max_ticks: int = 10) -> float:
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
    def configure_time_axis(ax, cfg: PlotConfig, time_values: List[datetime.datetime]) -> None:
        """配置时间轴"""
        if not cfg.show_axis_labels:
            ax.set_xticklabels([])
            ax.set_xlabel('')
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
                major_locator = mdates.SecondLocator(interval=max(1, int(optimal_interval)))
            
            ax.xaxis.set_major_locator(major_locator)
            ax.xaxis.set_major_formatter(mdates.DateFormatter(cfg.xtick_format))
            
            # 设置次要刻度
            if cfg.show_minor_ticks:
                if cfg.xtick_interval is not None:
                    minor_interval = max(1, cfg.xtick_interval // 5)
                else:
                    minor_interval = max(1, int(major_locator._interval // 5))
                ax.xaxis.set_minor_locator(mdates.SecondLocator(interval=minor_interval))
            
            # 设置标签旋转
            if cfg.axis_label_rotation != 0:
                plt.setp(ax.get_xticklabels(), rotation=cfg.axis_label_rotation, 
                        ha='right' if cfg.axis_label_rotation > 0 else 'left')
    
    @staticmethod
    def configure_frequency_axis(ax, cfg: PlotConfig, freq_values: np.ndarray) -> None:
        """配置频率轴"""
        if not cfg.show_axis_labels:
            ax.set_yticklabels([])
            ax.set_ylabel('')
        else:
            # 设置主要刻度
            if cfg.ytick_interval is not None:
                yticks = np.arange(
                    np.ceil(freq_values[0] / cfg.ytick_interval) * cfg.ytick_interval,
                    freq_values[-1],
                    cfg.ytick_interval
                )
                ax.set_yticks(yticks)
            else:
                # 自动计算刻度
                freq_range = freq_values[-1] - freq_values[0]
                optimal_interval = AxisConfigManager.calculate_optimal_ticks(
                    freq_range, len(freq_values), max_ticks=10
                )
                yticks = np.arange(
                    np.ceil(freq_values[0] / optimal_interval) * optimal_interval,
                    freq_values[-1],
                    optimal_interval
                )
                ax.set_yticks(yticks)
            
            # 设置次要刻度
            if cfg.show_minor_ticks:
                ax.yaxis.set_minor_locator(plt.AutoMinorLocator(5))
            
            # 设置标签旋转
            if cfg.axis_label_rotation != 0:
                plt.setp(ax.get_yticklabels(), rotation=cfg.axis_label_rotation, va='center')


# ============================================================
#  HELPER FUNCTIONS
# ============================================================

def calc_bin_sizes(spec: LazySpectrogram, cfg: PlotConfig):
    """Calculate t_bin / f_bin based on actual slice range and target point count."""
    t1s = (cfg.t_start - spec.dt_base).total_seconds()
    t2s = (cfg.t_end   - spec.dt_base).total_seconds()
    ti0, ti1 = _find_range(spec.time, t1s, t2s)
    fi0, fi1 = _find_range(spec.freq, cfg.f_start, cfg.f_end)
    n_t = ti1 - ti0 + 1
    n_f = fi1 - fi0 + 1
    t_bin = max(1, n_t // cfg.rebin_t_target) if cfg.rebin_t_target else 1
    f_bin = max(1, n_f // cfg.rebin_f_target) if cfg.rebin_f_target else 1
    return t_bin, f_bin


def calc_polarization_ratio(Z_r: np.ndarray, Z_l: np.ndarray) -> np.ndarray:
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
    # Ensure we're working with float32 for consistency
    Z_r = Z_r.astype(np.float32)
    Z_l = Z_l.astype(np.float32)
    
    # Calculate denominator
    denom = Z_r + Z_l
    
    # Handle zero denominator
    zero_mask = denom == 0
    if np.any(zero_mask):
        denom = denom.copy()  # Make a copy to avoid modifying original
        denom[zero_mask] = np.float32(1e-10)
    
    # Calculate ratio (R-L)/(R+L)
    ratio = (Z_r - Z_l) / denom
    
    # Ensure ratio is within [-1, 1] range (numerical stability)
    ratio = np.clip(ratio, -1.0, 1.0)
    
    # Debug information
    print(f"  Polarization ratio (R-L)/(R+L) statistics:")
    print(f"    Min: {np.nanmin(ratio):.4f}, Max: {np.nanmax(ratio):.4f}")
    print(f"    Mean: {np.nanmean(ratio):.4f}, Std: {np.nanstd(ratio):.4f}")
    print(f"    Positive (R>L): {np.sum(ratio > 0.01) / np.sum(np.isfinite(ratio)):.2%}")
    print(f"    Negative (L>R): {np.sum(ratio < -0.01) / np.sum(np.isfinite(ratio)):.2%}")
    print(f"    Near zero (|ratio|<0.01): {np.sum(np.abs(ratio) < 0.01) / np.sum(np.isfinite(ratio)):.2%}")
    
    # Test with simple values to verify formula
    test_r = np.float32(10.0)
    test_l = np.float32(5.0)
    test_ratio = (test_r - test_l) / (test_r + test_l)
    print(f"  Formula test: R={test_r}, L={test_l} => (R-L)/(R+L)={test_ratio:.3f} (should be {(10-5)/(10+5):.3f})")
    
    return ratio


def _safe_log10(arr: np.ndarray) -> np.ndarray:
    """Compute base-10 logarithm safely, handling non-positive values."""
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.log10(np.where(arr > 0, arr, np.nan))


def get_color_limits(data: np.ndarray, cfg: PlotConfig, 
                     plot_type: str = "ll") -> Tuple[float, float]:
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
    if hasattr(cfg, 'use_percentile_clipping') and not cfg.use_percentile_clipping:
        # Manual limits mode
        vmin = None
        vmax = None
        
        if plot_type == "ll":
            # Try individual LL limits first
            if hasattr(cfg, 'manual_ll_vmin') and cfg.manual_ll_vmin is not None:
                vmin = cfg.manual_ll_vmin
            elif hasattr(cfg, 'manual_vmin') and cfg.manual_vmin is not None:
                vmin = cfg.manual_vmin
                
            if hasattr(cfg, 'manual_ll_vmax') and cfg.manual_ll_vmax is not None:
                vmax = cfg.manual_ll_vmax
            elif hasattr(cfg, 'manual_vmax') and cfg.manual_vmax is not None:
                vmax = cfg.manual_vmax
                
        elif plot_type == "rr":
            # Try individual RR limits first
            if hasattr(cfg, 'manual_rr_vmin') and cfg.manual_rr_vmin is not None:
                vmin = cfg.manual_rr_vmin
            elif hasattr(cfg, 'manual_vmin') and cfg.manual_vmin is not None:
                vmin = cfg.manual_vmin
                
            if hasattr(cfg, 'manual_rr_vmax') and cfg.manual_rr_vmax is not None:
                vmax = cfg.manual_rr_vmax
            elif hasattr(cfg, 'manual_vmax') and cfg.manual_vmax is not None:
                vmax = cfg.manual_vmax
                
        elif plot_type == "sum":
            if hasattr(cfg, 'manual_sum_vmin'):
                vmin = cfg.manual_sum_vmin
            if hasattr(cfg, 'manual_sum_vmax'):
                vmax = cfg.manual_sum_vmax
                
        elif plot_type == "ratio":
            if hasattr(cfg, 'manual_ratio_vmin'):
                vmin = cfg.manual_ratio_vmin
            if hasattr(cfg, 'manual_ratio_vmax'):
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


def optimize_workers(cfg: PlotConfig, data_size_mb: float, chunk_mem_mb: int) -> Tuple[int, float]:
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
    if hasattr(cfg, 'max_workers') and cfg.max_workers is not None:
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
                print(f"  Note: Insufficient memory for parallel processing. Switching to sequential.")
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
                f"available memory ({available_memory:.1f} MB). Consider reducing settings."
            )
            
    except ImportError:
        warnings.warn("psutil not installed, using conservative defaults")
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
    # Validate configuration (includes color scale limits validation)
    validate_config(cfg)
    
    # Extract LL and RR polarization data
    cso_l = next((d for d in data_list if 'LL' in d.polar), None)
    cso_r = next((d for d in data_list if 'RR' in d.polar), None)
    if cso_l is None or cso_r is None:
        raise ValueError("Complete LL and RR data not found")

    # Pre-calculate bin sizes based on actual slice range
    t_bin, f_bin = calc_bin_sizes(cso_l, cfg)
    
    # Estimate data size for worker optimization
    t1s = (cfg.t_start - cso_l.dt_base).total_seconds()
    t2s = (cfg.t_end   - cso_l.dt_base).total_seconds()
    ti0, ti1 = _find_range(cso_l.time, t1s, t2s)
    fi0, fi1 = _find_range(cso_l.freq, cfg.f_start, cfg.f_end)
    n_t = ti1 - ti0 + 1
    n_f = fi1 - fi0 + 1
    estimated_data_size_mb = (n_t * n_f * 4) / (1024 * 1024)  # 4 bytes per float32
    
    # Optimize number of workers considering memory constraints
    optimal_workers, estimated_peak_memory = optimize_workers(
        cfg, estimated_data_size_mb, cfg.chunk_mem_mb
    )
    
    print(f"Memory configuration:")
    print(f"  - Chunk memory limit: {cfg.chunk_mem_mb} MB per worker")
    print(f"  - Estimated data size: {estimated_data_size_mb:.1f} MB")
    print(f"  - Optimal workers: {optimal_workers}")
    print(f"  - Estimated peak memory: {estimated_peak_memory:.1f} MB")
    
    # Warn if memory usage might be high
    if estimated_peak_memory > 2000:  # 2GB threshold
        print(f"⚠️  Warning: Estimated peak memory ({estimated_peak_memory:.1f} MB) is high.")
        print(f"   Consider reducing chunk_mem_mb or max_workers.")

    # Parallel reading with downsampling
    print("Block reading + downsampling...")
    kwargs = dict(t1=cfg.t_start, t2=cfg.t_end,
                  f1=cfg.f_start, f2=cfg.f_end,
                  t_bin=t_bin, f_bin=f_bin,
                  chunk_mem_mb=cfg.chunk_mem_mb)

    # Use optimized number of workers
    if optimal_workers == 1:
        print("Processing sequentially with 1 worker for memory control...")
        # Process LL first, then RR
        print("  Processing LL polarization...")
        Z_l, tt, freq = cso_l.read_slice_rebinned(**kwargs)
        # Explicitly delete any intermediate variables if needed
        import gc
        gc.collect()
        
        print("  Processing RR polarization...")
        Z_r, _, _ = cso_r.read_slice_rebinned(**kwargs)
    else:
        print(f"Processing in parallel with {optimal_workers} workers...")
        with ThreadPoolExecutor(max_workers=optimal_workers) as exe:
            # ✅ FIX: Tag each future with its polarization key so results
            # can be correctly identified regardless of completion order.
            future_to_polar = {
                exe.submit(cso_l.read_slice_rebinned, **kwargs): 'LL',
                exe.submit(cso_r.read_slice_rebinned, **kwargs): 'RR',
            }
            results_dict = {}
            for future in as_completed(future_to_polar):
                polar_key = future_to_polar[future]
                results_dict[polar_key] = future.result()

            Z_l, tt, freq = results_dict['LL']
            Z_r, _, _ = results_dict['RR']

    # Debug: Check LL and RR data statistics
    print(f"Data statistics before polarization calculation:")
    print(f"  LL (L): Min={np.nanmin(Z_l):.2f}, Max={np.nanmax(Z_l):.2f}, Mean={np.nanmean(Z_l):.2f}")
    print(f"  RR (R): Min={np.nanmin(Z_r):.2f}, Max={np.nanmax(Z_r):.2f}, Mean={np.nanmean(Z_r):.2f}")
    
    # Check which polarization is stronger
    l_mean = np.nanmean(Z_l)
    r_mean = np.nanmean(Z_r)
    if l_mean > r_mean:
        print(f"  Note: LL (L) is stronger on average (L={l_mean:.2f} vs R={r_mean:.2f})")
    elif r_mean > l_mean:
        print(f"  Note: RR (R) is stronger on average (R={r_mean:.2f} vs L={l_mean:.2f})")
    else:
        print(f"  Note: LL and RR have equal average intensity")
    
    # Compute derived quantities
    Z_sum = Z_l + Z_r
    # Calculate polarization ratio (R-L)/(R+L)
    ratio = calc_polarization_ratio(Z_r, Z_l)

    # Prepare time axis for plotting (optimized)
    epoch = np.datetime64(cso_l.dt_base)
    # Vectorized time conversion
    datetime_tt = epoch + (tt * 1e6).astype('timedelta64[us]')
    dt_list = datetime_tt.astype('datetime64[ms]').astype(datetime.datetime)
    
    # Create meshgrid for plotting
    xx, yy = np.meshgrid(mdates.date2num(dt_list), freq)

    # Assemble plot items based on configuration
    items = []
    date_str = cso_l.dateobs[:10]
    
    # Helper function to create plot item
    def create_plot_item(data, title, cmap, cbar_label, plot_type="ll"):
        vmin, vmax = get_color_limits(data, cfg, plot_type)
        return dict(
            data=data,
            title=title,
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            cbar_label=cbar_label
        )

    if cfg.plot_ll:
        Z_log = _safe_log10(Z_l)
        items.append(create_plot_item(
            Z_log,
            f'CSO/CBSm {cso_l.polar} {date_str}',
            'jet',
            r'log$_{10}$ Brightness Temp (K)',
            plot_type="ll"
        ))

    if cfg.plot_rr:
        Z_log = _safe_log10(Z_r)
        items.append(create_plot_item(
            Z_log,
            f'CSO/CBSm {cso_r.polar} {date_str}',
            'jet',
            r'log$_{10}$ Brightness Temp (K)',
            plot_type="rr"
        ))

    if cfg.plot_sum:
        Z_log = _safe_log10(Z_sum)
        items.append(create_plot_item(
            Z_log,
            f'CSO/CBSm LL+RR {date_str}',
            'jet',
            r'log$_{10}$ Brightness Temp (K)',
            plot_type="sum"
        ))

    if cfg.plot_ratio:
        # Use get_color_limits for both manual and percentile modes
        vmin, vmax = get_color_limits(ratio, cfg, "ratio")
        
        # Ensure symmetric color scale for better visualization
        if cfg.use_percentile_clipping:
            # For percentile mode, ensure symmetric range
            max_abs = max(abs(vmin), abs(vmax))
            vmin = -max_abs
            vmax = max_abs
            print(f"  Adjusted polarization ratio color scale to symmetric: [{vmin:.3f}, {vmax:.3f}]")
        
        # Add title indicating polarization direction
        # mean_ratio = np.nanmean(ratio)
        # if mean_ratio > 0.01:
        #     pol_direction = "(R > L, Right-handed, positive values)"
        # elif mean_ratio < -0.01:
        #     pol_direction = "(L > R, Left-handed, negative values)"
        # else:
        #     pol_direction = "(R ≈ L, Unpolarized)"
        
        # Verify color mapping
        print(f"  Color mapping verification:")
        print(f"    vmin={vmin:.3f} (blue), vmax={vmax:.3f} (red)")
        
        items.append(dict(
            data=ratio,
            title=f'CSO/CBSm Polarization Ratio (R-L)/(R+L)',
            cmap='bwr',  # Blue-White-Red colormap: blue for negative, white for 0, red for positive
            vmin=vmin,
            vmax=vmax,
            cbar_label='Polarization Ratio (R-L)/(R+L)'
        ))

    if not items:
        print("No plot items selected, exiting")
        return

    # Create figure and subplots
    n = len(items)
    fig, axs = plt.subplots(
        n, 1,
        figsize=(cfg.fig_width, cfg.fig_height_per * n),
        sharex=True,
        sharey=True,
        constrained_layout=True  # Better layout management
    )
    fig.subplots_adjust(hspace=0.15)
    
    if n == 1:
        axs = [axs]

    # Plot each item
    for idx, (ax, item) in enumerate(zip(axs, items)):
        im = ax.pcolormesh(
            xx, yy, item['data'][:-1, :-1],
            shading='flat',
            cmap=item['cmap'],
            vmin=item['vmin'],
            vmax=item['vmax']
        )
        ax.set_title(item['title'], fontsize=12)
        
        # 配置Y轴（频率）
        AxisConfigManager.configure_frequency_axis(ax, cfg, freq)
        
        # 配置X轴（时间）- 只在最后一个子图设置标签
        if idx == len(items) - 1:
            AxisConfigManager.configure_time_axis(ax, cfg, dt_list)
            if cfg.show_axis_labels:
                ax.set_xlabel('Time (UT)', fontsize=10)
        else:
            ax.set_xticklabels([])  # 非最后一个子图不显示x轴标签
        
        # 颜色条
        cbar = fig.colorbar(im, ax=ax, pad=0.01)
        cbar.set_label(item['cbar_label'], fontsize=9)
        
        # 添加频率高亮线
        if cfg.highlight_freqs is not None:
            for freq_val in cfg.highlight_freqs:
                if cfg.f_start <= freq_val <= cfg.f_end:
                    ax.axhline(
                        y=freq_val,
                        color='red',
                        linestyle='--',
                        linewidth=1.3,
                        alpha=0.6
                    )
                    # 添加文本标签（只在有标签显示时才添加）
                    if cfg.show_axis_labels:
                        x_min = mdates.date2num(dt_list[0])
                        x_max = mdates.date2num(dt_list[-1])
                        x_pos = x_min + 0.01 * (x_max - x_min)
                        ax.text(
                            x_pos,
                            freq_val + 0.01 * (cfg.f_end - cfg.f_start),
                            f'{freq_val} MHz',
                            color='red',
                            fontsize=4,
                            verticalalignment='bottom',
                            horizontalalignment='left',
                            bbox=dict(
                                boxstyle='round,pad=0.2',
                                facecolor='g',
                                alpha=0.3
                            )
                        )

    # Save or display the figure
    if cfg.save_path:
        save_path = cfg.save_path
        if os.path.isdir(save_path):
            date_str = cso_l.dateobs[:10].replace('-', '')
            f_start_str = int(cfg.f_start)
            f_end_str = int(cfg.f_end)
            # Include color scale method in filename
            scale_method = "manual" if not cfg.use_percentile_clipping else "auto"
            filename = f"CSO_spectrogram_{date_str}_{f_start_str}_{f_end_str}_{scale_method}.png"
            save_path = os.path.join(save_path, filename)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        fig.savefig(save_path, dpi=cfg.dpi, bbox_inches='tight')
        print(f"Image saved: {save_path}")
    else:
        print("No save path specified, only displaying graph")

    plt.show()


# ============================================================
#  ENTRY POINT
# ============================================================

def test_polarization_formula():
    """Test function to verify polarization ratio calculation."""
    print("\n" + "="*60)
    print("Testing Polarization Ratio Formula (R-L)/(R+L)")
    print("="*60)
    
    # Test cases
    test_cases = [
        ("R > L", 10.0, 5.0, (10-5)/(10+5)),  # Right-handed dominant
        ("L > R", 5.0, 10.0, (5-10)/(5+10)),  # Left-handed dominant
        ("R = L", 10.0, 10.0, 0.0),           # Unpolarized
        ("R >> L", 100.0, 1.0, (100-1)/(100+1)),  # Strong right-handed
        ("L >> R", 1.0, 100.0, (1-100)/(1+100)),  # Strong left-handed
    ]
    
    for name, r_val, l_val, expected in test_cases:
        ratio = calc_polarization_ratio(
            np.array([r_val], dtype=np.float32),
            np.array([l_val], dtype=np.float32)
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
    def validate_all(cfg: PlotConfig) -> Tuple[bool, List[str]]:
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


if __name__ == '__main__':
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
    print(f"File: {os.path.basename(cfg.file_path)}")
    print(f"Time range: {cfg.t_start} to {cfg.t_end}")
    print(f"Frequency range: {cfg.f_start} to {cfg.f_end} MHz")
    print(f"Color scale method: {'Manual limits' if not cfg.use_percentile_clipping else 'Percentile clipping'}")
    if not cfg.use_percentile_clipping:
        # Display individual limits if set
        ll_vmin = cfg.manual_ll_vmin if hasattr(cfg, 'manual_ll_vmin') and cfg.manual_ll_vmin is not None else cfg.manual_vmin
        ll_vmax = cfg.manual_ll_vmax if hasattr(cfg, 'manual_ll_vmax') and cfg.manual_ll_vmax is not None else cfg.manual_vmax
        rr_vmin = cfg.manual_rr_vmin if hasattr(cfg, 'manual_rr_vmin') and cfg.manual_rr_vmin is not None else cfg.manual_vmin
        rr_vmax = cfg.manual_rr_vmax if hasattr(cfg, 'manual_rr_vmax') and cfg.manual_rr_vmax is not None else cfg.manual_vmax
        
        print(f"  Manual limits - LL: [{ll_vmin}, {ll_vmax}]")
        print(f"  Manual limits - RR: [{rr_vmin}, {rr_vmax}]")
        print(f"  Manual limits - Sum: [{cfg.manual_sum_vmin}, {cfg.manual_sum_vmax}]")
        print(f"  Manual limits - Ratio: [{cfg.manual_ratio_vmin}, {cfg.manual_ratio_vmax}]")
    else:
        print(f"  Percentile clipping - LL/RR: [{cfg.vmin_pct}%, {cfg.vmax_pct}%]")
        print(f"  Percentile clipping - Sum: [{cfg.sum_vmin_pct}%, {cfg.sum_vmax_pct}%]")
        print(f"  Percentile clipping - Ratio: [{cfg.ratio_vmin_pct}%, {cfg.ratio_vmax_pct}%]")
    
    # 显示坐标轴配置
    print(f"坐标轴配置:")
    print(f"  - 显示标签: {cfg.show_axis_labels}")
    print(f"  - 标签旋转: {cfg.axis_label_rotation} 度")
    print(f"  - X轴刻度间隔: {cfg.xtick_interval if cfg.xtick_interval is not None else '自动'}")
    print(f"  - Y轴刻度间隔: {cfg.ytick_interval if cfg.ytick_interval is not None else '自动'}")
    print(f"  - X轴格式: {cfg.xtick_format}")
    print(f"  - 显示次要刻度: {cfg.show_minor_ticks}")
    
    # Display memory information
    total_gb, available_gb, usage_percent = get_system_memory_info()
    if total_gb > 0:
        print(f"System memory: {total_gb:.1f} GB total, {available_gb:.1f} GB available ({usage_percent:.1f}% used)")
    
    print(f"Memory configuration:")
    print(f"  - Chunk memory: {cfg.chunk_mem_mb} MB")
    # Check if max_workers attribute exists (for backward compatibility)
    if hasattr(cfg, 'max_workers'):
        max_workers_display = cfg.max_workers if cfg.max_workers is not None else 'Auto-detect'
    else:
        max_workers_display = 'Auto-detect (default)'
    print(f"  - Max workers: {max_workers_display}")
    print("=" * 60)
    
    # Execute processing pipeline
    t0 = time.perf_counter()
    data_list, hdu = read_cso_fits(cfg.file_path)
    try:
        process_and_plot(cfg, data_list)
    except Exception as e:
        print(f"Error during processing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        hdu.close()

    print(f"\nTotal execution time: {time.perf_counter() - t0:.2f} s")
