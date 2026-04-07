# -*- coding: utf-8 -*-
"""
CSO Spectrogram Plotting Tool

This script processes and visualizes Chinese Solar Radio Telescope (CSO) 
spectrogram data from FITS files. It efficiently handles large datasets 
using memory-mapped I/O and block-wise downsampling to minimize memory usage.

Key features:
- Lazy loading of FITS data using memory mapping
- Parallel reading and downsampling of polarization channels
- Configurable time/frequency ranges and downsampling targets
- Multiple plot types: individual polarizations (LL, RR), total intensity, polarization ratio
- Memory-efficient chunked processing with progress tracking

Author: Severus
Created on: Sun Nov 23 00:19:30 2025
"""

import time
import datetime
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
from functools import wraps

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from astropy.io import fits
from tqdm import tqdm


# ============================================================
#  ★ All adjustable parameters - modify only here ★
# ============================================================
@dataclass
class PlotConfig:
    # File path
    file_path: str = (
        r'D:\spike_topping_type_III\2025\20250124'
        r'\OROCH_MWRS01_SRSP_L1_05M_20250124044743_V01.01.fits'
    )

    # Time range (UTC)
    t_start: datetime.datetime = field(
        default_factory=lambda: datetime.datetime(2025, 1, 24, 4, 46, 0))
    t_end:   datetime.datetime = field(
        default_factory=lambda: datetime.datetime(2025, 1, 24, 4, 48, 30))

    # Frequency range (MHz)
    f_start: float = 0.0
    f_end:   float = 600.0

    # Target number of grid points after downsampling (time / frequency axes)
    # Larger values produce finer plots but are slower; None = no downsampling
    rebin_t_target: int = 10000
    rebin_f_target: int = 10000

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
    save_path: str = r'D:\spike_topping_type_III\2025\20250124\DEM\select_0337\RS'
    dpi:       int = 300


# ============================================================
#  Utilities
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
    """Fast range index lookup using searchsorted with boundary protection"""
    if lo > hi:
        lo, hi = hi, lo
    i0 = int(np.clip(np.searchsorted(arr, lo, side='left'),  0, len(arr)-1))
    i1 = int(np.clip(np.searchsorted(arr, hi, side='right')-1, 0, len(arr)-1))
    return i0, max(i0, i1)


# ============================================================
#  Lazy spectrogram container
# ============================================================

class LazySpectrogram:
    """
    Holds only FITS memmap references and metadata, not the full array.
    read_slice_rebinned() performs on-the-fly downsampling with minimal peak memory.
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
        Peak memory ≈ chunk_mem_mb.

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
#  Data reading
# ============================================================

@timing_decorator
def read_cso_fits(fn: str):
    """
    Open FITS, read metadata, return (list of LazySpectrogram, hdu handle).
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
#  Helper: pre-calculate bin sizes
# ============================================================

def calc_bin_sizes(spec: LazySpectrogram, cfg: PlotConfig):
    """Calculate t_bin / f_bin based on actual slice range and target points"""
    t1s = (cfg.t_start - spec.dt_base).total_seconds()
    t2s = (cfg.t_end   - spec.dt_base).total_seconds()
    ti0, ti1 = _find_range(spec.time, t1s, t2s)
    fi0, fi1 = _find_range(spec.freq, cfg.f_start, cfg.f_end)
    n_t = ti1 - ti0 + 1
    n_f = fi1 - fi0 + 1
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
#  Main processing and plotting
# ============================================================

@timing_decorator
def process_and_plot(cfg: PlotConfig, data_list: list):
    cso_l = next((d for d in data_list if 'LL' in d.polar), None)
    cso_r = next((d for d in data_list if 'RR' in d.polar), None)
    if cso_l is None or cso_r is None:
        raise ValueError("Complete LL and RR data not found")

    # Pre-calculate bins (based on actual slice range)
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

    axs[-1].set_xlabel('Time (UT)', fontsize=10)
    for ax in axs:
        ax.xaxis.set_major_locator(
            mdates.SecondLocator(interval=cfg.major_tick_interval))
        ax.xaxis.set_minor_locator(
            mdates.SecondLocator(interval=cfg.minor_tick_interval))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))

    plt.tight_layout()

    if cfg.save_path:
        fig.savefig(cfg.save_path, dpi=cfg.dpi, bbox_inches='tight')
        print(f"Image saved: {cfg.save_path}")

    plt.show()


# ============================================================
#  Entry point
# ============================================================

if __name__ == '__main__':
    cfg = PlotConfig()   # All parameters are defined in PlotConfig

    t0 = time.perf_counter()
    data_list, hdu = read_cso_fits(cfg.file_path)
    try:
        process_and_plot(cfg, data_list)
    finally:
        hdu.close()

    print(f"\nTotal time: {time.perf_counter() - t0:.2f} s")
