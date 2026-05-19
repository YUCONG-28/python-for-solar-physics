# 模块用途: 读取 ASO-S/HXI FITS 产品并绘制硬 X 射线图像。
# 主要输入: HXI FITS 图像或 map 数据。
# 主要输出/运行说明: 输出硬 X 射线图像/等值线图，用于高能源区定位。
"""
Created on Mon Mar 17 10:48:46 2025

@author: 李
"""

from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import sunpy.map
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
    path_config = load_script_config(
        "asos_hxi_image_plot",
        {
            "file_path": (
                "D:/hxidata/HXI_CLEAN/"
                "hxi_imgcube_04e09t_20240808_192000_HXI_CLEAN.fits"
            )
        },
    )
    file_path = Path(path_config["file_path"])
    hdul = fits.open(file_path)

    for i in range(1):  # i=14,18,22
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
        hximap = sunpy.map.Map(hdul[i].data, header)
        hximap.plot()
        plt.text(10, 80, header["ENERGY_H"], color="white")
        plt.show()
