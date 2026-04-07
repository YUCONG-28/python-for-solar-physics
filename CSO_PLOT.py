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
#  ★ CONFIGURATION PARAMETERS - MODIFY ONLY HERE ★
# ============================================================
@dataclass
class PlotConfig:
    """Configuration class for CSO spectrogram plotting parameters."""
    
    # File path
    file_path: str = (
        r'D:\spike_topping_type_III\2024\20240110'
        r'\OROCH_MWRS01_SRSP_L1_05M_20240110064840_V01.01.fits'
    )

    # Time range (UTC)
    t_start: datetime.datetime = field(
        default_factory=lambda: datetime.datetime(2024, 1, 10, 6, 48, 0))
    t_end:   datetime.datetime = field(
        default_factory=lambda: datetime.datetime(2024, 1, 10, 6, 50, 0))

    # Frequency range (MHz)
    f_start: float = 0.0
    f_end:   float = 600.0

    # Target number of grid points after downsampling (time / frequency axes)
    # Larger values produce finer plots but are slower; None = no downsampling
    rebin_t_target: int = 1000
    rebin_f_target: int = 1000

    # Peak memory limit per chunk during block reading (MB)
    # Lower values reduce memory pressure further
    chunk_mem_mb: int = 28

    # Plot toggles
    plot_ll:    bool = False
    plot_rr:    bool = False
    plot_sum:   bool = True
    plot_ratio: bool = True

    # Color scale percentile clipping
    vmin_pct:     float = 0.1
    vmax_pct:     float = 99.9
    sum_vmin_pct: float = 0.1
    sum_vmax_pct: float = 99.9

    # Figure dimensions
    fig_width:      float = 12.0
    fig_height_per: float = 3.0   # Height per subplot (inches)

    # Time axis tick intervals (seconds)
    major_tick_interval: int = 10
    minor_tick_interval: int = 2

    # Save path (empty for display only)
    save_path: str = r'D:\spike_topping_type_III\2024\20240110'
    dpi:       int = 300
    
    # List of frequencies to highlight (MHz)
    highlight_freqs: Optional[List[float]] = field(default_factory=lambda: [149, 164, 190, 205, 223, 238, 285, 300])


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
    """Calculate polarization ratio (R-L)/(R+L) with safe division."""
    denom = Z_r + Z_l
    denom[denom == 0] = np.float32(1e-10)
    return (Z_r - Z_l) / denom


def _safe_log10(arr: np.ndarray) -> np.ndarray:
    """Compute base-10 logarithm safely, handling non-positive values."""
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.log10(np.where(arr > 0, arr, np.nan))


# ============================================================
#  MAIN PROCESSING AND PLOTTING
# ============================================================

@timing_decorator
def process_and_plot(cfg: PlotConfig, data_list: list):
    """Main processing pipeline: read data, compute derived quantities, and generate plots."""
    # Extract LL and RR polarization data
    cso_l = next((d for d in data_list if 'LL' in d.polar), None)
    cso_r = next((d for d in data_list if 'RR' in d.polar), None)
    if cso_l is None or cso_r is None:
        raise ValueError("Complete LL and RR data not found")

    # Pre-calculate bin sizes based on actual slice range
    t_bin, f_bin = calc_bin_sizes(cso_l, cfg)

    # Parallel reading with downsampling
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

    # Compute derived quantities
    Z_sum = Z_l + Z_r
    ratio = calc_polarization_ratio(Z_r, Z_l)

    # Prepare time axis for plotting
    epoch       = np.datetime64(cso_l.dt_base)
    datetime_tt = epoch + (tt * 1e6).astype('timedelta64[us]')
    dt_list     = datetime_tt.astype('datetime64[ms]').astype(datetime.datetime)
    xx, yy      = np.meshgrid(mdates.date2num(dt_list), freq)

    # Assemble plot items based on configuration
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

    # Create figure and subplots
    n = len(items)
    fig, axs = plt.subplots(n, 1,
                             figsize=(cfg.fig_width, cfg.fig_height_per * n),
                             sharex=True, sharey=True)
    fig.subplots_adjust(hspace=0.15)
    if n == 1:
        axs = [axs]

    # Plot each item
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
        
        # Add frequency highlight lines if specified
        if cfg.highlight_freqs is not None:
            for freq in cfg.highlight_freqs:
                if cfg.f_start <= freq <= cfg.f_end:
                    # Add horizontal line
                    ax.axhline(y=freq, color='red', linestyle='--', linewidth=2, alpha=0.8)
                    # Add text label
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

    # Configure time axis
    axs[-1].set_xlabel('Time (UT)', fontsize=10)
    for ax in axs:
        ax.xaxis.set_major_locator(
            mdates.SecondLocator(interval=cfg.major_tick_interval))
        ax.xaxis.set_minor_locator(
            mdates.SecondLocator(interval=cfg.minor_tick_interval))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))

    plt.tight_layout()

    # Save or display the figure
    if cfg.save_path:
        save_path = cfg.save_path
        if os.path.isdir(save_path):
            date_str = cso_l.dateobs[:10].replace('-', '')
            f_start_str = int(cfg.f_start)
            f_end_str = int(cfg.f_end)
            filename = f"CSO_spectrogram_{date_str}_{f_start_str}_{f_end_str}.png"
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

if __name__ == '__main__':
    # Initialize configuration with default parameters
    cfg = PlotConfig()
    
    # ============================================================
    #  USER CUSTOMIZATION AREA - MODIFY AS NEEDED
    # ============================================================
    
    # Example 1: Use manual color scale limits (e.g., 0-10)
    # cfg.use_percentile_clipping = False
    # cfg.manual_vmin = 0.0
    # cfg.manual_vmax = 10.0
    # cfg.manual_sum_vmin = 0.0
    # cfg.manual_sum_vmax = 10.0
    
    # Example 2: Adjust CPU core usage
    # cfg.max_workers = 1  # Use single core for memory conservation
    # cfg.max_workers = None  # Auto-detect based on available memory
    
    # Example 3: Customize highlight frequencies
    # cfg.highlight_freqs = [149.0, 164.0, 190.0, 205.0, 223.0, 238.0, 285.0, 300.0]
    
    # Example 4: Adjust memory usage
    # cfg.chunk_mem_mb = 50  # Increase chunk size for faster processing
    # cfg.chunk_mem_mb = 10  # Decrease chunk size for memory-constrained systems
    
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
        print(f"  Manual limits - LL/RR: [{cfg.manual_vmin}, {cfg.manual_vmax}]")
        print(f"  Manual limits - Sum: [{cfg.manual_sum_vmin}, {cfg.manual_sum_vmax}]")
    else:
        print(f"  Percentile clipping - LL/RR: [{cfg.vmin_pct}%, {cfg.vmax_pct}%]")
        print(f"  Percentile clipping - Sum: [{cfg.sum_vmin_pct}%, {cfg.sum_vmax_pct}%]")
    
    # Display memory information
    total_gb, available_gb, usage_percent = get_system_memory_info()
    if total_gb > 0:
        print(f"System memory: {total_gb:.1f} GB total, {available_gb:.1f} GB available ({usage_percent:.1f}% used)")
    
    print(f"Memory configuration:")
    print(f"  - Chunk memory: {cfg.chunk_mem_mb} MB")
    print(f"  - Max workers: {cfg.max_workers if cfg.max_workers is not None else 'Auto-detect'}")
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
