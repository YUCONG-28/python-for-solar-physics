# -*- coding: utf-8 -*-
# 模块用途: 读取多个 SDO/AIA 波段图像并绘制六联图概览。
# 主要输入: 多波段 AIA FITS 文件。
# 主要输出/运行说明: 输出统一视场和标注的多波段 EUV 面板图。

"""
Created on Sun Dec  7 21:30:04 2025
read and plot aia images in 6 panels
Jan 31 2026
@author: ningh
"""
import glob
import json
import logging
import re
from pathlib import Path

import astropy.units as u
import matplotlib.colors as colors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from astropy.coordinates import SkyCoord
from sunpy.map import Map
from sunpy.time import parse_time

labelsz = 14


def mk_dir(path):
    """
    根据模板和波长变量创建输出目录。
    """
    obj_path = Path(path)
    obj_path.mkdir(parents=True, exist_ok=True)
    print(f"Directory created or already exists: {obj_path}")
    return obj_path


def organize_aia_files(data_directory):
    """
    从指定目录读取所有 FITS 文件，并按波长分类 (基于文件名模式匹配)。

    参数:
        data_directory (str): 包含 AIA FITS 文件的目录路径。
    返回:
        dict: 键为波长 (例如 '171 Angstrom')，值为文件路径列表。
    """
    WAVELENGTH_REGEX = re.compile(r"\.([0-9]+)\.image_lev1\.fits$")

    classified_files = {}

    for filepath in Path(data_directory).rglob("*.fits"):
        filename = filepath.name
        match = WAVELENGTH_REGEX.search(filename)
        if match:
            wavelength_str = match.group(1)
            wave_int = int(wavelength_str)
            key = wave_int
            if key not in classified_files:
                classified_files[key] = []
            classified_files[key].append(str(filepath))

    for key in classified_files:
        classified_files[key].sort()

    return classified_files


def process_aia(
    outdir,
    file_list,
    log_scale=True,
    global_vmin=None,
    global_vmax=None,
    auto_range=True,
    percentile_range=(1, 99.9),
    return_stats=True,
):

    if not file_list:
        if return_stats:
            return None, None
        return

    calculated_vmin, calculated_vmax = None, None

    if auto_range and (global_vmin is None or global_vmax is None):
        all_data = []

        for fil in file_list[::20]:
            try:
                current_map = Map(fil)
                exposure_time = current_map.exposure_time
                normalized_map = current_map / exposure_time

                roi_bottom_left = SkyCoord(
                    Tx=650 * u.arcsec,
                    Ty=100 * u.arcsec,
                    frame=current_map.coordinate_frame,
                )
                roi_top_right = SkyCoord(
                    Tx=1050 * u.arcsec,
                    Ty=-300 * u.arcsec,
                    frame=current_map.coordinate_frame,
                )
                cropped_map = normalized_map.submap(
                    roi_bottom_left, top_right=roi_top_right
                )

                data = cropped_map.data
                data_valid = data[np.isfinite(data)]
                data_valid = data_valid[data_valid > 0]
                if data_valid.size > 0:
                    all_data.append(data_valid)

            except Exception as e:
                print(f"处理文件 {fil} 时出错: {e}")
                continue

        if all_data:
            all_data_combined = np.concatenate(all_data)
            calculated_vmin = np.percentile(all_data_combined, percentile_range[0])
            calculated_vmax = np.percentile(all_data_combined, percentile_range[1])

            calculated_vmin = max(calculated_vmin, 0.1)
            calculated_vmax = np.percentile(all_data_combined, 99.99)

            print(
                f"wave display range: vmin={calculated_vmin:.2f}, vmax={calculated_vmax:.2f}"
            )
        else:
            calculated_vmin, calculated_vmax = None, None

    if return_stats:
        return calculated_vmin, calculated_vmax


def get_multi_wave_df(all_classified_files, target_waves=[94, 131, 171, 193, 211, 304]):
    wave_dfs = {}
    time_pattern = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{6})")

    for wl in target_waves:
        files = all_classified_files.get(wl, [])
        records = []
        for f in files:
            fname = Path(f).name
            match = time_pattern.search(fname)
            if match:
                t_obj = parse_time(match.group(1))
                records.append({"path": str(f), "abs_sec": t_obj.unix})
        if records:
            wave_dfs[wl] = (
                pd.DataFrame(records).sort_values("abs_sec").reset_index(drop=True)
            )
        else:
            print(f"波段 {wl} 没有找到有效文件记录。")

    base_wave = 171
    if base_wave not in wave_dfs:
        return []

    base_df = wave_dfs[base_wave]
    synced_list = []

    for idx, row in base_df.iterrows():
        base_sec = row["abs_sec"]
        current_group = {base_wave: row["path"], "time_unix": row["abs_sec"]}
        match_success = True

        for wl in target_waves:
            if wl == base_wave:
                continue

            df_target = wave_dfs.get(wl)
            if df_target is None or df_target.empty:
                match_success = False
                break

            diff = (df_target["abs_sec"] - base_sec).abs()
            if diff.empty:
                match_success = False
                break

            idx_min_diff = diff.idxmin()

            if diff[idx_min_diff] <= 6:  # 6秒容差
                current_group[wl] = df_target.loc[idx_min_diff, "path"]
            else:
                match_success = False
                break

        if match_success:
            synced_list.append(current_group)

    return synced_list


def save_ranges(ranges, filename="aia_ranges.json"):
    """将计算好的范围保存到本地"""
    with open(filename, "w") as f:
        json.dump(ranges, f, indent=4)
    print(f"wave display range saved in : {filename}")


def load_ranges(filename="aia_ranges.json"):
    """从本地读取范围，如果文件不存在则返回 None"""
    file_path = Path(filename)
    if file_path.exists():
        with file_path.open("r") as f:
            data = json.load(f)
            return {int(k): v for k, v in data.items()}
    return None


def plot_synced_aia(
    synced_data, outdir, wave_display_ranges, target_waves=[94, 131, 171, 193, 211, 304]
):
    """

    参数:
    ----------
    synced_data : list
        由 get_multi_wave_df 返回的对齐后的数据列表。
        每个元素是一个字典，包含所有波段的文件路径和时间戳。
    outdir : str
        输出目录路径。
    wave_display_ranges : dict
        每个波段的 vmin/vmax 字典。
    target_waves : list, optional
        要绘制的波段列表及顺序。
    """
    mk_dir(outdir)

    for i, item in enumerate(synced_data):
        try:
            obs_time = parse_time(item["time_unix"], format="unix")
            print(obs_time)
            fig = plt.figure(figsize=(18, 12))

            print(f"{obs_time.strftime('%Y-%m-%d %H:%M:%S')} image ")

            for j, wl in enumerate(target_waves):

                if wl in item:
                    file_path = item[wl]

                    m = Map(file_path)
                    m_norm = m / m.exposure_time

                    roi_bottom_left = SkyCoord(
                        Tx=650 * u.arcsec,
                        Ty=100 * u.arcsec,
                        frame=m_norm.coordinate_frame,
                    )
                    roi_top_right = SkyCoord(
                        Tx=1050 * u.arcsec,
                        Ty=-300 * u.arcsec,
                        frame=m_norm.coordinate_frame,
                    )

                    m_crop = m_norm.submap(roi_bottom_left, top_right=roi_top_right)
                    ax = fig.add_subplot(2, 3, j + 1, projection=m_crop.wcs)
                    vmin_val = wave_display_ranges.get(wl, {}).get("vmin", 0.1)
                    vmax_val = wave_display_ranges.get(wl, {}).get(
                        "vmax",
                        np.nanpercentile(m_crop.data[np.isfinite(m_crop.data)], 99.9),
                    )

                    plot_data = m_crop.data.copy()
                    plot_data[plot_data <= 0] = np.nan

                    im = m_crop.plot(
                        axes=ax,
                        title=f"",
                        norm=colors.LogNorm(vmin=vmin_val, vmax=vmax_val),
                    )
                    precise_time = m_crop.date.strftime("%H:%M:%S")
                    label_text = f"{wl} Å | {precise_time}"

                    ax.text(
                        0.03,
                        0.96,
                        label_text,
                        transform=ax.transAxes,
                        color="white",
                        fontsize=16,
                        fontweight="bold",
                        verticalalignment="top",
                        bbox=dict(
                            facecolor="black", alpha=0.4, edgecolor="none", pad=2
                        ),
                    )

                    lon = ax.coords[0]  # Solar X
                    lat = ax.coords[1]  # Solar Y
                    if j % 3 != 0:
                        ax.set_ylabel("")
                        lat.set_ticklabel_visible(False)
                    else:
                        ax.set_ylabel("y (arcsec)", fontsize=labelsz)

                    if j < 3:
                        ax.set_xlabel("")
                        lon.set_ticklabel_visible(False)
                    else:
                        ax.set_xlabel("x (arcsec)", fontsize=labelsz)

                    ax.set_anchor("C")
                    ax.set_adjustable("box")

                    ax.tick_params(
                        axis="both",
                        which="both",
                        direction="in",
                        color="white",
                        labelsize=14,
                        pad=2,
                    )
                    lon.display_minor_ticks(True)
                    lat.display_minor_ticks(True)

            plt.subplots_adjust(wspace=0, hspace=0)
            time_str = obs_time.strftime("%Y%m%d_%H%M%S")
            fout_path = Path(outdir) / f"AIA_{time_str}.png"
            # plt.show()
            # plt.close()
            # break
            plt.savefig(fout_path, dpi=200, bbox_inches="tight")
            plt.close(fig)
        except Exception as e:
            plt.close(fig)
            continue


if __name__ == "__main__":
    DATA_DIR = r"/home/ning/data/aia/260105"
    all_classified_files = organize_aia_files(DATA_DIR)
    RANGE_FILE = "aia_ranges_260105.json"

    wave_display_ranges = load_ranges(RANGE_FILE)

    if wave_display_ranges is None:
        wave_display_ranges = {}
        for wl in [94, 131, 171, 193, 211, 304]:
            if wl in all_classified_files:
                vmin, vmax = process_aia(
                    outdir=None,
                    file_list=all_classified_files[wl],
                    auto_range=True,
                    percentile_range=(1, 99.99),
                    return_stats=True,
                )
                wave_display_ranges[wl] = {"vmin": vmin, "vmax": vmax}

        save_ranges(wave_display_ranges, RANGE_FILE)

    target_waves = [94, 131, 171, 193, 211, 304]
    sync_data = get_multi_wave_df(all_classified_files)

    COMBO_OUT = Path.home() / "output/260105/jet/aia/"
    plot_synced_aia(
        sync_data, str(COMBO_OUT), wave_display_ranges, target_waves=target_waves
    )
