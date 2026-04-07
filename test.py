# -*- coding: utf-8 -*-
"""
Created on Sun Nov 23 00:19:30 2025

@author: Severus

"""

import time
import datetime
import os
from dataclasses import dataclass, field
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor
from functools import wraps

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from astropy.io import fits
from tqdm import tqdm


# ============================================================
#  ★ 所有可调参数，只需修改这里 ★
# ============================================================
@dataclass
class PlotConfig:
    # 文件路径
    file_path: str = (
        r'D:\spike_topping_type_III\2025\20250124'
        r'\OROCH_MWRS01_SRSP_L1_05M_20250124044743_V01.01.fits'
    )

    # 时间范围（UTC）
    t_start: datetime.datetime = field(
        default_factory=lambda: datetime.datetime(2025, 1, 24, 4, 46, 0))
    t_end:   datetime.datetime = field(
        default_factory=lambda: datetime.datetime(2025, 1, 24, 4, 48, 30))

    # 频率范围（MHz）
    f_start: float = 0.0
    f_end:   float = 600.0

    # 降采样后的目标格点数（时间 / 频率方向）
    # 越大图越精细但越慢；None = 不降采样
    rebin_t_target: int = 1000
    rebin_f_target: int = 1000

    # 分块读取时单块峰值内存上限（MB），调小可进一步降低内存压力
    chunk_mem_mb: int = 28

    # 绘图开关
    plot_ll:    bool = False
    plot_rr:    bool = False
    plot_sum:   bool = True
    plot_ratio: bool = True

    # 色标百分位裁剪
    vmin_pct:     float = 0.1
    vmax_pct:     float = 99.9
    sum_vmin_pct: float = 0.1
    sum_vmax_pct: float = 99.9

    # 图像尺寸
    fig_width:      float = 12.0
    fig_height_per: float = 3.0   # 每子图高度（英寸）

    # 时间轴刻度（秒）
    major_tick_interval: int = 10
    minor_tick_interval: int = 2

    # 保存路径（留空仅弹窗）
    save_path: str = r'C:\Users\Lee\Desktop'
    dpi:       int = 300
    
    # 需要高亮显示的频率列表（MHz）
    highlight_freqs: Optional[List[float]] = field(default_factory=lambda: [238,285])


# ============================================================
#  工具
# ============================================================

def timing_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        result = func(*args, **kwargs)
        print(f"  [{func.__name__}] {time.perf_counter() - t0:.3f} s")
        return result
    return wrapper


def _find_range(arr: np.ndarray, lo: float, hi: float):
    """Fast range index lookup using searchsorted with boundary protection.
    
    Args:
        arr: Sorted 1D numpy array
        lo: Lower bound
        hi: Upper bound
        
    Returns:
        Tuple of (start_index, end_index)
        
    Raises:
        ValueError: If arr is empty
    """
    if len(arr) == 0:
        raise ValueError("Input array cannot be empty")
    
    if lo > hi:
        lo, hi = hi, lo
    
    # Ensure array is sorted for searchsorted to work correctly
    if not np.all(np.diff(arr) >= 0):
        raise ValueError("Input array must be sorted in non-decreasing order")
    
    i0 = int(np.clip(np.searchsorted(arr, lo, side='left'), 0, len(arr)-1))
    i1 = int(np.clip(np.searchsorted(arr, hi, side='right')-1, 0, len(arr)-1))
    return i0, max(i0, i1)


# ============================================================
#  惰性频谱容器
# ============================================================

class LazySpectrogram:
    """
    只持有 FITS memmap 引用 + 元数据，不具化大数组。
    read_slice_rebinned() 边读边降采样，峰值内存极低。
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
        分块从 memmap 读取并立即做 block-mean，峰值内存 ≈ chunk_mem_mb。

        流程：
          1. 计算索引并对齐到 bin 整数倍
          2. 每次读 chunk_cols_raw 列（≈chunk_mem_mb / freq行数）
          3. 每块做 reshape+mean 得到降采样结果，写入输出数组
        """
        t1s = (t1 - self.dt_base).total_seconds()
        t2s = (t2 - self.dt_base).total_seconds()

        ti0, ti1 = _find_range(self.time, t1s, t2s)
        fi0, fi1 = _find_range(self.freq, f1,  f2)

        n_freq_raw = fi1 - fi0 + 1
        n_time_raw = ti1 - ti0 + 1

        # 对齐到 bin 整数倍
        n_freq_trim = (n_freq_raw // f_bin) * f_bin
        n_time_trim = (n_time_raw // t_bin) * t_bin
        n_freq_out  = n_freq_trim // f_bin
        n_time_out  = n_time_trim // t_bin

        raw_mb = n_freq_raw * n_time_raw * 4 / 1e6
        out_mb = n_freq_out * n_time_out  * 4 / 1e6
        print(f"    [{self.polar}] 原始: {n_freq_raw}×{n_time_raw} "
              f"({raw_mb:.0f} MB)  ->  输出: {n_freq_out}×{n_time_out} "
              f"({out_mb:.1f} MB)")

        # 每次读取的列数：使内存 ≈ chunk_mem_mb，且必须是 t_bin 整数倍
        cols_per_chunk = max(t_bin,
                             (int(chunk_mem_mb * 1e6 / (n_freq_trim * 4))
                              // t_bin) * t_bin)

        Z_out = np.empty((n_freq_out, n_time_out), dtype=np.float32)
        out_col = 0

        for col0 in tqdm(range(0, n_time_trim, cols_per_chunk),
                         desc=f"    读取{self.polar}", leave=False):
            col1   = min(col0 + cols_per_chunk, n_time_trim)
            n_cols = ((col1 - col0) // t_bin) * t_bin   # 对齐
            if n_cols == 0:
                continue

            # 触发实际磁盘 I/O，立即 copy 为 float32
            chunk = np.array(
                self._raw[fi0 : fi0 + n_freq_trim,
                          ti0 + col0 : ti0 + col0 + n_cols],
                dtype=np.float32
            )   # (n_freq_trim, n_cols)

            # 同时做 freq 和 time 的 block-mean
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
#  数据读取
# ============================================================

@timing_decorator
def read_cso_fits(fn: str):
    """
    打开 FITS，读取元数据，返回 (LazySpectrogram列表, hdu句柄)。
    hdu 须在所有 read_slice_rebinned() 完成后关闭。
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
            print(f"  单偏振: {polars}  尺寸: {raw.shape}  "
                  f"({raw.nbytes/1e9:.2f} GB，未载入内存)")
        elif raw.ndim == 3:
            for ii in range(raw.shape[0]):
                polar = polars[ii] * 2
                results.append(LazySpectrogram(
                    raw[ii], time_, freq_, polar, dateobs, unit, dt_base))
            print(f"  Dual polarization  Full: {raw.shape}  "
                  f"({raw.nbytes/1e9:.2f} GB, not loaded into memory)")

        return results, hdu

    except Exception:
        hdu.close()
        raise


# ============================================================
#  Helper: Pre-calculate bin sizes
# ============================================================

def calc_bin_sizes(spec: LazySpectrogram, cfg: PlotConfig):
    """Calculate t_bin / f_bin based on actual slice range and target point count.
    
    Args:
        spec: LazySpectrogram instance
        cfg: PlotConfig instance
        
    Returns:
        Tuple of (t_bin, f_bin)
        
    Raises:
        ValueError: If rebin targets are invalid or no data in range
    """
    # Validate time range
    if cfg.t_start >= cfg.t_end:
        raise ValueError(f"t_start ({cfg.t_start}) must be earlier than t_end ({cfg.t_end})")
    
    if cfg.f_start >= cfg.f_end:
        raise ValueError(f"f_start ({cfg.f_start}) must be less than f_end ({cfg.f_end})")
    
    t1s = (cfg.t_start - spec.dt_base).total_seconds()
    t2s = (cfg.t_end   - spec.dt_base).total_seconds()
    
    ti0, ti1 = _find_range(spec.time, t1s, t2s)
    fi0, fi1 = _find_range(spec.freq, cfg.f_start, cfg.f_end)
    
    n_t = ti1 - ti0 + 1
    n_f = fi1 - fi0 + 1
    
    if n_t <= 0 or n_f <= 0:
        raise ValueError(f"No data in specified range: time points={n_t}, freq points={n_f}")
    
    # Handle rebin targets safely
    if cfg.rebin_t_target is not None and cfg.rebin_t_target <= 0:
        raise ValueError(f"rebin_t_target must be positive, got {cfg.rebin_t_target}")
    
    if cfg.rebin_f_target is not None and cfg.rebin_f_target <= 0:
        raise ValueError(f"rebin_f_target must be positive, got {cfg.rebin_f_target}")
    
    t_bin = max(1, n_t // cfg.rebin_t_target) if cfg.rebin_t_target else 1
    f_bin = max(1, n_f // cfg.rebin_f_target) if cfg.rebin_f_target else 1
    
    return t_bin, f_bin


# ============================================================
#  Polarization ratio & log10
# ============================================================

def calc_polarization_ratio(Z_r: np.ndarray, Z_l: np.ndarray) -> np.ndarray:
    denom = Z_r + Z_l
    denom[denom == 0] = np.float32(1e-10)
    return (Z_r - Z_l) / denom


def _safe_log10(arr: np.ndarray) -> np.ndarray:
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.log10(np.where(arr > 0, arr, np.nan))


# ============================================================
#  Main process
# ============================================================

@timing_decorator
def process_and_plot(cfg: PlotConfig, data_list: list):
    cso_l = next((d for d in data_list if 'LL' in d.polar), None)
    cso_r = next((d for d in data_list if 'RR' in d.polar), None)
    if cso_l is None or cso_r is None:
        raise ValueError("Complete LL and RR data not found")

    # Pre-calculate bin (based on actual slice range)
    t_bin, f_bin = calc_bin_sizes(cso_l, cfg)

    # Parallel reading + downsampling
    print("Block reading + downsampling (parallel)...")
    kwargs = dict(t1=cfg.t_start, t2=cfg.t_end,
                  f1=cfg.f_start, f2=cfg.f_end,
                  t_bin=t_bin, f_bin=f_bin,
                  chunk_mem_mb=cfg.chunk_mem_mb)

    with ThreadPoolExecutor(max_workers=2) as exe:
        fut_l = exe.submit(cso_l.read_slice_rebinned, **kwargs)
        fut_r = exe.submit(cso_r.read_slice_rebinned, **kwargs)
        Z_l, tt, freq = fut_l.result()
        Z_r, _,  _    = fut_r.result()

    # Derived quantities
    Z_sum = Z_l + Z_r
    ratio = calc_polarization_ratio(Z_r, Z_l)

    # Time axis vectorized conversion
    epoch       = np.datetime64(cso_l.dt_base)
    datetime_tt = epoch + (tt * 1e6).astype('timedelta64[us]')
    dt_list     = datetime_tt.astype('datetime64[ms]').astype(datetime.datetime)
    xx, yy      = np.meshgrid(mdates.date2num(dt_list), freq)

    # Assemble subplots
    items    = []
    date_str = cso_l.dateobs[:10]

    if cfg.plot_ll:
        Z_log = _safe_log10(Z_l)
        items.append(dict(data=Z_log,
                          title=f'CSO/CBSm {cso_l.polar} {date_str}',
                          cmap='jet',
                          vmin=np.nanpercentile(Z_log, cfg.vmin_pct),
                          vmax=np.nanpercentile(Z_log, cfg.vmax_pct),
                          cbar_label=r'log$_{10}$ Brightness Temp (K)'))

    if cfg.plot_rr:
        Z_log = _safe_log10(Z_r)
        items.append(dict(data=Z_log,
                          title=f'CSO/CBSm {cso_r.polar} {date_str}',
                          cmap='jet',
                          vmin=np.nanpercentile(Z_log, cfg.vmin_pct),
                          vmax=np.nanpercentile(Z_log, cfg.vmax_pct),
                          cbar_label=r'log$_{10}$ Brightness Temp (K)'))

    if cfg.plot_sum:
        Z_log = _safe_log10(Z_sum)
        items.append(dict(data=Z_log,
                          title=f'CSO/CBSm LL+RR {date_str}',
                          cmap='jet',
                          vmin=np.nanpercentile(Z_log, cfg.sum_vmin_pct),
                          vmax=np.nanpercentile(Z_log, cfg.sum_vmax_pct),
                          cbar_label=r'log$_{10}$ Brightness Temp (K)'))

    if cfg.plot_ratio:
        items.append(dict(data=ratio,
                          title='CSO/CBSm Polarization (R-L)/(R+L)',
                          cmap='bwr', vmin=-1, vmax=1,
                          cbar_label='Polarization Ratio'))

    if not items:
        print("No plot items selected, exiting")
        return

    n = len(items)
    fig, axs = plt.subplots(n, 1,
                             figsize=(cfg.fig_width, cfg.fig_height_per * n),
                             sharex=True, sharey=True)
    fig.subplots_adjust(hspace=0.15)
    if n == 1:
        axs = [axs]

    for ax, item in zip(axs, items):
        im = ax.pcolormesh(xx, yy, item['data'][:-1, :-1],
                           shading='flat',
                           cmap=item['cmap'],
                           vmin=item['vmin'], vmax=item['vmax'])
        ax.set_title(item['title'], fontsize=12)
        ax.set_ylabel('Frequency (MHz)', fontsize=10)
        cbar = fig.colorbar(im, ax=ax, pad=0.01)
        cbar.set_label(item['cbar_label'], fontsize=9)
        ax.tick_params(axis='x', labelsize=8, rotation=0)
        ax.tick_params(axis='y', labelsize=8)
        
        # If frequencies to highlight are specified, add horizontal lines
        if cfg.highlight_freqs is not None:
            for freq in cfg.highlight_freqs:
                # Ensure frequency is within display range
                if cfg.f_start <= freq <= cfg.f_end:
                    # Add horizontal line
                    ax.axhline(y=freq, color='red', linestyle='--', linewidth=2, alpha=0.8)
                    # Add text label
                    # Use the minimum value of time axis as x position
                    x_min = mdates.date2num(dt_list[0])
                    x_max = mdates.date2num(dt_list[-1])
                    x_pos = x_min + 0.01 * (x_max - x_min)
                    ax.text(
                        x_pos,
                        freq + 0.01 * (cfg.f_end - cfg.f_start),
                        f'{freq} MHz',
                        color='red',
                        fontsize=9,
                        verticalalignment='bottom',
                        horizontalalignment='left',
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='yellow', alpha=0.5)
                    )
                else:
                    print(f"Warning: Frequency {freq} MHz is not within display range [{cfg.f_start}, {cfg.f_end}], skipping.")

    axs[-1].set_xlabel('Time (UT)', fontsize=10)
    for ax in axs:
        ax.xaxis.set_major_locator(
            mdates.SecondLocator(interval=cfg.major_tick_interval))
        ax.xaxis.set_minor_locator(
            mdates.SecondLocator(interval=cfg.minor_tick_interval))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))

    plt.tight_layout()

    if cfg.save_path:
        # Ensure save path is a complete file path
        save_path = cfg.save_path
        # If path is a directory, generate default filename
        if os.path.isdir(save_path):
            # Use date and frequency range to generate filename
            date_str = cso_l.dateobs[:10].replace('-', '')
            f_start_str = int(cfg.f_start)
            f_end_str = int(cfg.f_end)
            filename = f"CSO_spectrogram_{date_str}_{f_start_str}_{f_end_str}.png"
            save_path = os.path.join(save_path, filename)
        # Ensure directory exists
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        fig.savefig(save_path, dpi=cfg.dpi, bbox_inches='tight')
        print(f"Image saved: {save_path}")
    else:
        print("No save path specified, only displaying graph")

    # Display graph
    plt.show()


# ============================================================
#  Entry point
# ============================================================

if __name__ == '__main__':
    cfg = PlotConfig()   # All parameters are defined uniformly in PlotConfig
    # If you need to highlight specific frequencies, you can set them here
    # For example: cfg.highlight_freqs = [238.0, 300.0]

    t0 = time.perf_counter()
    data_list, hdu = read_cso_fits(cfg.file_path)
    try:
        process_and_plot(cfg, data_list)
    finally:
        hdu.close()

    print(f"\nTotal time: {time.perf_counter() - t0:.2f} s")
