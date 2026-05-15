# -*- coding: utf-8 -*-
# 模块用途: 读取并绘制 SDO/HMI 磁图数据。
# 主要输入: HMI magnetogram FITS 文件。
# 主要输出/运行说明: 输出磁场背景图，为耀斑/活动区分析提供磁场环境。
"""
Created on Sat Apr  5 14:39:30 2025

@author: 李
"""

from pathlib import Path

import astropy.units as u
import matplotlib.colors as colors
import matplotlib.pyplot as plt
import sunpy.map
from astropy.coordinates import SkyCoord
from sunpy.coordinates import propagate_with_solar_surface

from solar_toolkit.path_config import load_script_config

# vmin = 10  # 最小值（对数尺度）
# vmax = 2000  # 最大值（对数尺度）
# norm = colors.LogNorm(vmin=vmin, vmax=vmax)

PATH_CONFIG = load_script_config(
    "sdo_hmi_magnetogram_plot",
    {
        "data_dir": "D:/Flare/JSOCdata/HMI/",
        "output_dir": "D:/Flare/JSOCdata/HMI/plot_offset",
        "show_plot": False,
    },
)
data_dir = Path(PATH_CONFIG["data_dir"])
file_paths = sorted(p for p in data_dir.iterdir() if p.suffix.lower() == ".fits")
aia_sequence = sunpy.map.Map(file_paths, sequence=True)
output_dir = Path(PATH_CONFIG["output_dir"])
output_dir.mkdir(parents=True, exist_ok=True)
show_plot = bool(PATH_CONFIG.get("show_plot", False))

my_map = sunpy.map.Map(aia_sequence[1])
roi_bottom_left = SkyCoord(
    Tx=180 * u.arcsec, Ty=-340 * u.arcsec, frame=my_map.coordinate_frame
)
roi_top_right = SkyCoord(
    Tx=520 * u.arcsec, Ty=20 * u.arcsec, frame=my_map.coordinate_frame
)
cutout_map = my_map.submap(roi_bottom_left, top_right=roi_top_right)

# fig = plt.figure()
# ax = fig.add_subplot(projection=cutout_map)
# cutout_map.plot(axes=ax,norm=norm)

with propagate_with_solar_surface():
    aia_sequence_aligned = sunpy.map.Map(
        [m.reproject_to(cutout_map.wcs) for m in aia_sequence], sequence=True
    )

for i in range(1):  # 从 0 到 4
    fig = plt.figure()
    ax = fig.add_subplot(projection=aia_sequence_aligned[i])
    ani = aia_sequence_aligned[i].plot(axes=ax)  # norm=norm)

    base_name = file_paths[i].name
    output_path = output_dir / (base_name + ".png")

    parts = base_name.split(".")
    time_str = parts[2]
    plt.title(time_str)

    plt.savefig(output_path, dpi=200, bbox_inches="tight")

    if show_plot:
        plt.show()
    plt.close(fig)
