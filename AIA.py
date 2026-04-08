# -*- coding: utf-8 -*-
"""
Created on Sun Nov 23 00:19:30 2025
@author: Severus

"""

import gc
import time
import multiprocessing
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
import math
from pathlib import Path
from typing import List, Optional, Tuple

import matplotlib
matplotlib.use('Agg')  # 强制非交互式后端，多进程安全且防内存泄漏
import matplotlib.patheffects as mpath_effects
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import astropy.units as u
from astropy.coordinates import SkyCoord
from sunpy.coordinates import propagate_with_solar_surface
import sunpy.map
from tqdm import tqdm


# ==============================================================================
# 全局配置
# ==============================================================================
AIA_CONFIG: dict = {
    94:  {'cmap': 'sdoaia94','vmin':0.4, 'vmax': 6666},
    131: {'cmap': 'sdoaia131','vmin':0.7, 'vmax': 6666},
    171: {'cmap': 'sdoaia171','vmin':16, 'vmax': 6666},
    193: {'cmap': 'sdoaia193','vmin':42, 'vmax': 6666},
    211: {'cmap': 'sdoaia211','vmin':18, 'vmax': 6666},
    304: {'cmap': 'sdoaia304','vmin':0.9, 'vmax': 2222},
    335: {'cmap': 'sdoaia335'},
}


@dataclass
class AIAConfig:
    data_path:  str           = r'<PROJECT_ROOT>\2025\20250428\AIA'
    output_dir: Optional[str] = None
    start_idx: int            = 0
    end_idx:   Optional[int]  = None
    roi_bounds: Tuple[float, float, float, float] = (-1100, -900, 0, 200) # (xmin, xmax, ymin, ymax)
    user_vmin: Optional[float] = None
    user_vmax: Optional[float] = None
    user_cmap: Optional[str]   = None
    
    # 动态 figsize 的基础宽度（英寸），高度会自动按比例计算
    base_fig_width: float = 8.0 
    dpi:           int  = 300
    show_limb:     bool = False  # 如果开启，需将 limb 颜色改为黑色
    show_grid:     bool = True   # 默认开启以匹配参考图
    show_colorbar: bool = False
    save_image:       bool = True
    show_image:       bool = False
    use_band_subdirs: bool = True
    
    max_workers: Optional[int] = 16

    # 多波段同图：False 时与原先一致（逐文件单图）；True 时按各波段目录内时间排序后的第 k 个文件对齐到同一画布
    multi_band_composite: bool = False
    multi_band_wavelengths: Optional[Tuple[int, ...]] = None  # 六波段参考排布为 (94,131,171,193,211,304) 对应 2×3 上行 94–131–171、下行 193–211–304；None 时按数字子目录名排序（通常即此顺序）
    multi_band_output_subdir: str = "multi_band"
    multi_band_merge_axes: bool = True  # 保留字段以兼容旧配置；拼图模式固定为无缝拼接，仅角标显示波段与时间
    # 仅当 multi_band_composite=True 时有效：拼图完成后是否仍按原逻辑导出各 FITS 对应的单波段 PNG
    multi_band_also_save_single: bool = False
    # 拼图子图间距（matplotlib 中为相对子图宽/高的比例，约 0.03–0.1 可见缝）
    multi_band_wspace: float = 0.06
    multi_band_hspace: float = 0.06
    # 保存时画布四周的绝对留白（英寸）；单图与拼图共用
    figure_pad_inches: float = 0.15
    # 主标题（日期 YYYY-MM-DD）字号；单图与拼图共用
    figure_suptitle_fontsize: float = 34
    # 单图模式下子图顶部的时间标题字号（位于主标题下方）
    single_map_title_fontsize: float = 13

    def __post_init__(self):
        if self.output_dir is None:
            self.output_dir = self.data_path


# ==============================================================================
# 内部工具函数
# ==============================================================================
def _resolve_files(input_path: Path, start_idx: int, end_idx: Optional[int]) -> list:
    if input_path.is_file():
        file_list = [input_path]
    elif input_path.is_dir():
        # 按时间字符串（而非路径字符串）升序排列，保证单图模式下输出顺序与观测时间一致
        file_list = sorted(input_path.rglob('*.fits'), key=lambda p: _parse_timestr(p))
    else:
        raise ValueError(f"无效的路径: {input_path}")

    total = len(file_list)
    if total == 0:
        raise ValueError("数据目录或其子目录中没有找到 FITS 文件！")

    end = total if end_idx is None else min(end_idx, total)
    selected = file_list[start_idx:end]
    print(f"共发现 {total} 个文件，已选择处理 {len(selected)} 个（索引: {start_idx} ~ {end - 1}）")
    return selected


def _parse_timestr(file_path: Path) -> str:
    """精准提取格式类似于 2025-01-24T033001Z 的时间字符串"""
    # 尝试正则匹配标准的 ISO 时间格式
    match = re.search(r'\d{4}-\d{2}-\d{2}T\d{6}Z', file_path.name)
    if match:
        return match.group(0)
    
    # 备选方案
    parts = file_path.name.split('.')
    for part in parts:
        if 'T' in part and 'Z' in part:
            return part
    return file_path.stem


def _resolve_display_params(
    current_map: sunpy.map.GenericMap,
    user_cmap:   Optional[str],
    user_vmin:   Optional[float],
    user_vmax:   Optional[float],
) -> Tuple[str, mcolors.Normalize]:
    wave_val = int(current_map.wavelength.value)
    config = AIA_CONFIG.get(wave_val, {})
    sunpy_norm = current_map.plot_settings['norm']
    sunpy_cmap = current_map.plot_settings['cmap']

    final_cmap = user_cmap or config.get('cmap', sunpy_cmap)
    final_vmin = user_vmin if user_vmin is not None else config.get('vmin', sunpy_norm.vmin)
    final_vmax = user_vmax if user_vmax is not None else config.get('vmax', sunpy_norm.vmax)

    if not (final_vmin and final_vmax and final_vmin > 0 and final_vmax > final_vmin):
        final_vmin, final_vmax = 1.0, 1e4

    return final_cmap, mcolors.LogNorm(vmin=final_vmin, vmax=final_vmax)


def _layout_grid(n: int) -> Tuple[int, int]:
    if n <= 0:
        return 1, 1
    ncol = max(1, math.ceil(math.sqrt(n)))
    nrow = max(1, math.ceil(n / ncol))
    return nrow, ncol


def _layout_mosaic_grid(n: int) -> Tuple[int, int]:
    """与常见 SDO 六波段拼图一致：2 行 × 3 列；其余数量仍用近似方阵。"""
    if n == 6:
        return 2, 3
    return _layout_grid(n)


def _discover_wavelength_dirs(data_path: Path) -> Tuple[int, ...]:
    found: List[int] = []
    digit_dirs = [p for p in data_path.iterdir() if p.is_dir() and p.name.isdigit()]
    for p in sorted(digit_dirs, key=lambda x: int(x.name)):
        found.append(int(p.name))
    if not found:
        raise ValueError(
            f"未在 {data_path} 下发现数字波段子目录；请设置 multi_band_wavelengths 或检查 use_band_subdirs / 路径。"
        )
    return tuple(found)


def _sorted_fits_for_band(data_path: Path, wave: int, use_band_subdirs: bool) -> List[Path]:
    band_dir = (data_path / str(wave)) if use_band_subdirs else data_path
    if not band_dir.is_dir():
        raise ValueError(f"波段目录不存在: {band_dir}")
    files = sorted(band_dir.rglob("*.fits"), key=lambda p: _parse_timestr(p))
    return files


def _slice_band_files(files: List[Path], start_idx: int, end_idx: Optional[int]) -> List[Path]:
    total = len(files)
    if total == 0:
        return []
    end = total if end_idx is None else min(end_idx, total)
    return files[start_idx:end]


def _build_multi_band_slots(cfg: AIAConfig, wavelengths: Tuple[int, ...]) -> List[Tuple[Path, ...]]:
    data_path = Path(cfg.data_path)
    per_band: List[List[Path]] = []
    for w in wavelengths:
        all_f = _sorted_fits_for_band(data_path, w, cfg.use_band_subdirs)
        # 双保险：对切片前的完整列表再次按时间字符串升序排列，
        # 确保无论文件系统返回顺序如何，各波段文件均严格按观测时间从小到大排列。
        all_f = sorted(all_f, key=lambda p: _parse_timestr(p))
        sliced = _slice_band_files(all_f, cfg.start_idx, cfg.end_idx)
        if not sliced:
            raise ValueError(f"波段 {w} 在索引范围 [{cfg.start_idx}, {cfg.end_idx}) 内没有 FITS 文件")
        # 切片后再排一次，防止 start_idx/end_idx 引入乱序（理论上不会，但作为防御性编程）
        sliced = sorted(sliced, key=lambda p: _parse_timestr(p))
        per_band.append(sliced)
    m = min(len(x) for x in per_band)
    if any(len(x) != m for x in per_band):
        print(
            f"提示: 各波段可用文件数不同，已按时间排序后取最短长度 {m} 帧对齐（第 k 帧拼到同一张图）。"
        )
    # 构造槽位：slot[i] = (band0的第i个时间文件, band1的第i个时间文件, ...)
    # 从第 1 张拼图到第 m 张拼图，每个波段的文件均按时间从小到大递进。
    return [tuple(band[i] for band in per_band) for i in range(m)]


def _obs_time_isot_label(aia_map: sunpy.map.GenericMap, fallback_path: Path) -> str:
    """与参考图一致：ISO 时间 + 可选毫秒，如 2025-04-28T02:48:11.121。"""
    try:
        return str(aia_map.date.isot)
    except Exception:
        s = _parse_timestr(fallback_path).strip()
        return s[:-1] if s.endswith("Z") else s


def _hide_wcs_frame_for_seamless(ax) -> None:
    """去掉坐标刻度与轴名，子图边界无留白缝，便于多波段像素对齐拼接。"""
    lon, lat = ax.coords
    lon.set_ticks_visible(False)
    lat.set_ticks_visible(False)
    lon.set_ticklabel_visible(False)
    lat.set_ticklabel_visible(False)
    lon.set_axislabel("")
    lat.set_axislabel("")
    ax.set_frame_on(False)


def _silence_heliographic_overlay(overlay) -> None:
    """去掉 draw_grid 产生的 Stonyhurst/Carrington 轴名与刻度（保留网格线）。"""
    if overlay is None:
        return
    try:
        o0, o1 = overlay[0], overlay[1]
        o0.set_axislabel("")
        o1.set_axislabel("")
        o0.set_ticklabel_visible(False)
        o1.set_ticklabel_visible(False)
        o0.set_ticks_visible(False)
        o1.set_ticks_visible(False)
    except (TypeError, KeyError, IndexError, AttributeError):
        pass


def _purge_stonyhurst_text_artists(ax) -> None:
    """隐藏误留在图上的含 Stonyhurst/Carrington 字样的文字对象。"""
    for txt in ax.texts:
        t = txt.get_text().lower()
        if "stonyhurst" in t or "carrington" in t:
            txt.set_visible(False)


def _obs_date_ymd(aia_map: sunpy.map.GenericMap, fallback_path: Optional[Path] = None) -> str:
    """主标题用：FITS/图中观测日期，仅年月日 YYYY-MM-DD。"""
    try:
        dt = aia_map.date.to_datetime()
        return f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d}"
    except Exception:
        if fallback_path is not None:
            s = _parse_timestr(fallback_path)
            m = re.search(r"\d{4}-\d{2}-\d{2}", s)
            if m:
                return m.group(0)
        return ""


# ==============================================================================
# 单文件处理核心函数
# ==============================================================================
def _process_single_worker(file_path: Path, cfg: AIAConfig) -> Tuple[bool, str]:
    current_map = None
    raw_cutout = None
    cutout_map = None
    fig = None
    
    try:
        current_map = sunpy.map.Map(file_path)
        wave_val = int(current_map.wavelength.value)
        exp_time = current_map.exposure_time.to_value(u.s)
        
        if exp_time <= 0:
            return False, f"{file_path.name}: 曝光时间异常 ({exp_time}s)"

        # 1. 坐标与裁剪边界解析
        tx1, tx2, ty1, ty2 = cfg.roi_bounds
        roi_bl_tx, roi_bl_ty = tx1 * u.arcsec, ty1 * u.arcsec
        roi_tr_tx, roi_tr_ty = tx2 * u.arcsec, ty2 * u.arcsec

        # 2. 计算自适应 figsize (高度根据物理比例计算)
        dx = abs(tx2 - tx1)
        dy = abs(ty2 - ty1)
        aspect_ratio = dy / dx if dx != 0 else 1.0
        fig_width = cfg.base_fig_width
        fig_height = fig_width * aspect_ratio

        # 3. 裁剪处理
        with propagate_with_solar_surface():
            frame = current_map.coordinate_frame
            bl = SkyCoord(Tx=roi_bl_tx, Ty=roi_bl_ty, frame=frame)
            tr = SkyCoord(Tx=roi_tr_tx, Ty=roi_tr_ty, frame=frame)
            raw_cutout = current_map.submap(bl, top_right=tr)

        normalized_data = raw_cutout.data / exp_time
        cutout_map = sunpy.map.Map(normalized_data, raw_cutout.meta)

        final_cmap, final_norm = _resolve_display_params(
            current_map, cfg.user_cmap, cfg.user_vmin, cfg.user_vmax
        )
        time_str = _parse_timestr(file_path)

        # 4. 画图设置 (核心修改：设置背景为白色)
        # 显式设置 figure 的 facecolor 为白色
        fig = plt.figure(figsize=(fig_width, fig_height), facecolor='white')
        ax = fig.add_subplot(projection=cutout_map)
        # 设置 axes 的 facecolor（绘图区域内部）为白色
        ax.set_facecolor('white')

        im = cutout_map.plot(axes=ax, cmap=final_cmap, norm=final_norm, annotate=False)

        if cfg.show_limb:
            # 白色背景下，Limb 颜色改为黑色
            current_map.draw_limb(axes=ax, color='black', linewidth=0.8, alpha=0.6)

        if cfg.show_grid:
            # annotate=False：不绘制 Stonyhurst 经纬网轴名/刻度；再强制清空覆盖层文字
            hg_ov = cutout_map.draw_grid(
                axes=ax,
                color="black",
                linewidth=0.3,
                alpha=0.3,
                linestyle="--",
                annotate=False,
            )
            _silence_heliographic_overlay(hg_ov)
            _purge_stonyhurst_text_artists(ax)

        if cfg.show_colorbar:
            cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
            cbar.set_label('Intensity (DN/s)', fontsize=10)
            cbar.ax.tick_params(labelsize=9)

        # 5. UI 细节精调 (匹配参考图布局)
        lon, lat = ax.coords
        lon.set_axislabel('Helioprojective Longitude (Solar-X)', fontsize=10)
        lat.set_axislabel('Helioprojective Latitude (Solar-Y)', fontsize=10)
        
        # 刻度线和标签（默认已经是黑色，在白色背景下清晰）
        
        # 刻度线向内，且四面均显示
        lon.set_ticks(direction='in')
        lat.set_ticks(direction='in')
        lon.set_ticks_position('tb')
        lat.set_ticks_position('lr')

        # 设置标题仅为时间（字号略小于主标题）
        ax.set_title(f"{time_str}", fontsize=cfg.single_map_title_fontsize, pad=22)

        # 单波段模式：不需要主标题（日期），只保留子标题（具体时间）
        # 调整子图位置，为轴标签与刻度留足空间
        fig.subplots_adjust(left=0.13, right=0.95, top=0.93, bottom=0.11)

        # 6. 保存图片 (文件名直接用时间)
        if cfg.save_image and cfg.output_dir:
            save_dir = Path(cfg.output_dir) / str(wave_val) if cfg.use_band_subdirs else Path(cfg.output_dir)
            save_dir.mkdir(parents=True, exist_ok=True)
            # 输出名字：时间字符串.png (如果你需要jpg，这里改成.jpg即可)
            save_path = save_dir / f"{time_str}.png"
            fig.savefig(save_path, dpi=cfg.dpi, bbox_inches='tight', facecolor='white',
                        pad_inches=cfg.figure_pad_inches)
        
        return True, ""

    except Exception as e:
        return False, f"{file_path.name} -> {str(e)}"

    finally:
        if fig is not None:
            plt.close(fig)
        del current_map, raw_cutout, cutout_map
        gc.collect()


def _process_multi_band_worker(
    slot_idx: int,
    paths: Tuple[Path, ...],
    wavelengths: Tuple[int, ...],
    cfg: AIAConfig,
) -> Tuple[bool, str]:
    fig = None
    cutout_maps = []
    current_maps = []
    panel_meta: List[Tuple[str, int, str, mcolors.Normalize]] = []

    try:
        if len(paths) != len(wavelengths):
            return False, "内部错误: paths 与 wavelengths 长度不一致"

        tx1, tx2, ty1, ty2 = cfg.roi_bounds
        roi_bl_tx, roi_bl_ty = tx1 * u.arcsec, ty1 * u.arcsec
        roi_tr_tx, roi_tr_ty = tx2 * u.arcsec, ty2 * u.arcsec
        dx = abs(tx2 - tx1)
        dy = abs(ty2 - ty1)
        aspect_ratio = dy / dx if dx != 0 else 1.0

        for path, expect_w in zip(paths, wavelengths):
            current_map = sunpy.map.Map(path)
            wave_val = int(current_map.wavelength.value)
            if wave_val != expect_w:
                return False, f"{path.name}: 波长 {wave_val} 与期望波段 {expect_w} 不符"
            exp_time = current_map.exposure_time.to_value(u.s)
            if exp_time <= 0:
                return False, f"{path.name}: 曝光时间异常 ({exp_time}s)"
            with propagate_with_solar_surface():
                frame = current_map.coordinate_frame
                bl = SkyCoord(Tx=roi_bl_tx, Ty=roi_bl_ty, frame=frame)
                tr = SkyCoord(Tx=roi_tr_tx, Ty=roi_tr_ty, frame=frame)
                raw_cutout = current_map.submap(bl, top_right=tr)
            normalized_data = raw_cutout.data / exp_time
            cutout_map = sunpy.map.Map(normalized_data, raw_cutout.meta)
            final_cmap, final_norm = _resolve_display_params(
                current_map, cfg.user_cmap, cfg.user_vmin, cfg.user_vmax
            )
            iso_t = _obs_time_isot_label(current_map, path)
            cutout_maps.append(cutout_map)
            current_maps.append(current_map)
            panel_meta.append((final_cmap, wave_val, iso_t, final_norm))

        n = len(cutout_maps)
        nrow, ncol = _layout_mosaic_grid(n)
        fig_width = cfg.base_fig_width * ncol
        panel_w = fig_width / ncol
        fig_height = panel_w * aspect_ratio * nrow

        fig = plt.figure(figsize=(fig_width, fig_height), facecolor="white")
        gs = fig.add_gridspec(
            nrow,
            ncol,
            figure=fig,
            wspace=cfg.multi_band_wspace,
            hspace=cfg.multi_band_hspace,
        )
        for idx in range(n):
            row, col = divmod(idx, ncol)
            ax = fig.add_subplot(gs[row, col], projection=cutout_maps[idx])
            ax.set_facecolor("white")
            cmap, wave_val, iso_t, norm = panel_meta[idx]
            im = cutout_maps[idx].plot(axes=ax, cmap=cmap, norm=norm, annotate=False)
            if cfg.show_limb:
                current_maps[idx].draw_limb(axes=ax, color="black", linewidth=0.8, alpha=0.6)
            if cfg.show_grid:
                hg_ov = cutout_maps[idx].draw_grid(
                    axes=ax,
                    color="black",
                    linewidth=0.3,
                    alpha=0.3,
                    linestyle="--",
                    annotate=False,
                )
                _silence_heliographic_overlay(hg_ov)
                _purge_stonyhurst_text_artists(ax)
            if cfg.show_colorbar:
                fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02).set_label(
                    "DN/s", fontsize=8
                )
            _hide_wcs_frame_for_seamless(ax)
            ax.text(
                0.02,
                0.03,
                f"{iso_t} AIA {wave_val}",
                transform=ax.transAxes,
                fontsize=13,
                va="bottom",
                ha="left",
                color="white",
                path_effects=[
                    mpath_effects.withStroke(linewidth=2.2, foreground="black", alpha=0.65)
                ],
            )

        for j in range(n, nrow * ncol):
            er, ec = divmod(j, ncol)
            ax_empty = fig.add_subplot(gs[er, ec])
            ax_empty.set_visible(False)

        slot_label = f"{slot_idx + 1:04d}"
        date_ymd = _obs_date_ymd(current_maps[0], paths[0])
        
        # 多波段模式：添加主标题（日期）
        if date_ymd:
            fig.suptitle(
                date_ymd,
                fontsize=cfg.figure_suptitle_fontsize,
                y=0.97,  # 调整主标题垂直位置
                fontweight="medium",
            )
        
        # 根据是否有主标题调整子图位置
        if date_ymd:
            # 有主标题：顶部留出标题高度，底部和两侧留出适当空间
            fig.subplots_adjust(
                left=0.04,
                right=0.96,
                top=0.89,  # 为标题留出空间
                bottom=0.04,
            )
        else:
            # 无主标题：均匀分布
            fig.subplots_adjust(
                left=0.04,
                right=0.96,
                top=0.95,
                bottom=0.04,
            )

        if cfg.save_image and cfg.output_dir:
            save_dir = Path(cfg.output_dir) / cfg.multi_band_output_subdir
            save_dir.mkdir(parents=True, exist_ok=True)
            save_path = save_dir / f"multi_{slot_label}.png"
            fig.savefig(
                save_path,
                dpi=cfg.dpi,
                bbox_inches="tight",
                facecolor="white",
                pad_inches=cfg.figure_pad_inches,
            )

        return True, ""

    except Exception as e:
        return False, f"multi-band slot {slot_idx} -> {str(e)}"

    finally:
        if fig is not None:
            plt.close(fig)
        del cutout_maps, current_maps
        gc.collect()


# ==============================================================================
# 批量执行入口
# ==============================================================================
def process_aia_fits(cfg: AIAConfig):
    if cfg.multi_band_composite:
        if not cfg.use_band_subdirs:
            raise ValueError("多波段拼图要求数据按波段分子目录（use_band_subdirs=True）。")
        waves = cfg.multi_band_wavelengths
        if waves is None:
            waves = _discover_wavelength_dirs(Path(cfg.data_path))
        print(f"多波段拼图模式: 波段 {waves}")
        slots = _build_multi_band_slots(cfg, waves)
        print(f"共 {len(slots)} 个时间槽位（每槽 {len(waves)} 个波段同画布）")

        start_time = time.time()
        success_cnt = 0
        error_cnt = 0
        workers = cfg.max_workers or max(1, multiprocessing.cpu_count() - 1)
        print(f"启动多进程处理拼图，分配核心数: {workers} ...")

        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_process_multi_band_worker, i, slots[i], waves, cfg): i
                for i in range(len(slots))
            }
            for future in tqdm(
                as_completed(futures), total=len(slots), desc="Multi-band", unit="slot"
            ):
                success, msg = future.result()
                if success:
                    success_cnt += 1
                else:
                    error_cnt += 1
                    tqdm.write(f"\n  [失败] {msg}")

        elapsed = time.time() - start_time
        print(
            f"\n多波段拼图完成！成功: {success_cnt}，失败: {error_cnt}，总耗时 {elapsed:.2f} 秒"
        )
        if not cfg.multi_band_also_save_single:
            return
        print("\n--- 继续导出各波段单张图（multi_band_also_save_single=True）---")

    input_path = Path(cfg.data_path)
    selected_files = _resolve_files(input_path, cfg.start_idx, cfg.end_idx)

    start_time = time.time()
    success_cnt = 0
    error_cnt = 0

    workers = cfg.max_workers or max(1, multiprocessing.cpu_count() - 1)
    print(f"启动多进程处理，分配核心数: {workers} ...")

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_process_single_worker, f, cfg): f for f in selected_files}
        
        for future in tqdm(as_completed(futures), total=len(selected_files), desc="Processing", unit="file"):
            success, msg = future.result()
            if success:
                success_cnt += 1
            else:
                error_cnt += 1
                tqdm.write(f"\n  [失败] {msg}")

    elapsed = time.time() - start_time
    print(f"\n处理完成！成功: {success_cnt}，失败: {error_cnt}，总耗时 {elapsed:.2f} 秒")


if __name__ == "__main__":
    # 默认：单文件单图（与原先一致）
    cfg = AIAConfig(show_image=False, show_grid=True)
    # 多波段同画布：multi_band_composite=True；若还要单波段 PNG：multi_band_also_save_single=True
    print("--- 开始极速批量处理 AIA 数据 (白色背景版) ---")
    process_aia_fits(cfg)
