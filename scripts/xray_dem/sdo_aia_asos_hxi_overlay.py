# -*- coding: utf-8 -*-
# 模块用途: 在 SDO/AIA EUV 图像上叠加 ASO-S/HXI 硬 X 射线轮廓。
# 主要输入: AIA FITS 图像、HXI FITS 图像和等值线参数。
# 主要输出/运行说明: 输出 AIA-HXI 叠加图，用于比较耀斑热/非热辐射源位置。
"""
Created on Sun May 18 20:19:49 2025

@author: 李
"""

from datetime import datetime
from pathlib import Path

import astropy.units as u
import matplotlib.colors as colors
import matplotlib.pyplot as plt
import numpy as np
import sunpy.map
from astropy.coordinates import SkyCoord
from astropy.io import fits

from solar_toolkit.path_config import load_script_config


def convert_date(date_str):
    try:
        return datetime.strptime(date_str, "%d-%b-%y %H:%M:%S.%f").strftime(
            "%Y-%m-%dT%H:%M:%S.%f"
        )[:-3]
    except ValueError:
        return date_str  # 如果转换失败，则返回原始字符串，避免崩溃


if __name__ == "__main__":

    vmin = 1  # 最小值（对数尺度）

    path_config = load_script_config(
        "sdo_aia_asos_hxi_overlay",
        {
            "input_dir_AIA": "D:/Flare/JSOCdata/AIA_304/fits/44/",
            "output_dir": "D:/hxidata/HXI_CLEAN/25_4_24/plot/all_pro/304/",
            "hxi_file_path": "D:/hxidata/HXI_CLEAN/25_4_24/10-20.fits",
            "hxi_file_path_pro": "D:/hxidata/HXI_CLEAN/25_4_24/20-30.fits",
        },
    )
    input_dir_AIA = Path(path_config["input_dir_AIA"])
    output_dir = Path(path_config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    AIA_file_paths = [p for p in input_dir_AIA.iterdir() if p.suffix == ".fits"]
    aia_sequence = sunpy.map.Map(AIA_file_paths, sequence=True)

    aia_my_map = sunpy.map.Map(aia_sequence[1])

    hxi_file_path = path_config["hxi_file_path"]
    hxi_file_path_pro = path_config["hxi_file_path_pro"]
    hdul = fits.open(hxi_file_path)
    hdul_pro = fits.open(hxi_file_path_pro)

    # 确保 i 不会超过 hdul 的长度
    for i in range(0, min(len(aia_sequence), len(hdul))):
        header = hdul[i].header
        print(header)
        header["CUNIT1"] = "arcsec"
        header["CUNIT2"] = "arcsec"
        if "WAVELNTH" in header:
            del header["WAVELNTH"]
        if "DATE_OBS" in header:
            header["DATE_OBS"] = convert_date(header["DATE_OBS"])

        if "DATE-OBS" in header:
            header["DATE-OBS"] = convert_date(header["DATE-OBS"])
        header["crpix1"] = 9 + header["crpix1"]  # 右
        header["crpix2"] = 1 + header["crpix2"]  # 上
        hximap = sunpy.map.Map(hdul[i].data, header)

        header_pro = hdul_pro[i].header
        print(header_pro)
        header_pro["CUNIT1"] = "arcsec"
        header_pro["CUNIT2"] = "arcsec"
        if "WAVELNTH" in header_pro:
            del header_pro["WAVELNTH"]
        if "DATE_OBS" in header_pro:
            header_pro["DATE_OBS"] = convert_date(header_pro["DATE_OBS"])

        if "DATE-OBS" in header_pro:
            header_pro["DATE-OBS"] = convert_date(header_pro["DATE-OBS"])
        header_pro["crpix1"] = 9 + header_pro["crpix1"]  # 右
        header_pro["crpix2"] = 1 + header_pro["crpix2"]  # 上
        hximap_pro = sunpy.map.Map(hdul_pro[i].data, header_pro)

        # 确保 i + j 不会超过 aia_sequence 的长度
        for j in range(4):
            if i + j < len(aia_sequence):
                AIA_1600_IMAGE = aia_sequence[4 * i + j]
                my_map = sunpy.map.Map(AIA_1600_IMAGE)
                roi_bottom_left = SkyCoord(
                    Tx=180 * u.arcsec, Ty=-340 * u.arcsec, frame=my_map.coordinate_frame
                )
                roi_top_right = SkyCoord(
                    Tx=520 * u.arcsec, Ty=20 * u.arcsec, frame=my_map.coordinate_frame
                )
                my_submap = my_map.submap(roi_bottom_left, top_right=roi_top_right)

                fig = plt.figure(figsize=(8, 8))

                ax = fig.add_subplot(projection=my_submap)
                my_submap.plot(
                    axes=ax,
                    norm=colors.LogNorm(vmin=vmin, vmax=0.1 * np.max(my_submap.data)),
                )
                my_submap.draw_grid(axes=ax)

                levels = np.array([0.1]) * hximap.data.max()
                bounds = ax.axis()
                cset = hximap.draw_contours(levels, axes=ax, colors=["green"])
                plt.text(10, 550, "10-20-green", color="white", fontsize=16)

                levels_pro = np.array([0.1]) * hximap_pro.data.max()
                bounds_pro = ax.axis()
                cset = hximap_pro.draw_contours(levels_pro, axes=ax, colors=["red"])
                plt.text(10, 500, "20-30-red", color="white", fontsize=16)

                path = AIA_file_paths[4 * i + j]
                base_name = path.stem
                output_path = output_dir / f"{base_name}.png"
                plt.savefig(output_path, dpi=200, bbox_inches="tight")

                plt.show()
