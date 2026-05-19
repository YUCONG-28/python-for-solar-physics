# 模块用途: 使用 SunPy 绘制基础 SOHO/LASCO 日冕仪图像。
# 主要输入: LASCO FITS 文件。
# 主要输出/运行说明: 输出单帧 LASCO 图像；文件名中的 LOSCO 为历史拼写。
"""
Created on Mon Mar 31 11:06:15 2025

@author: 李
"""

from pathlib import Path

import matplotlib.pyplot as plt
from sunpy.map import Map

from solar_toolkit.path_config import load_script_config

PATH_CONFIG = load_script_config(
    "soho_lasco_image_plot",
    {
        "input_dir": "D:/LASCO/data/",
        "output_dir": "D:/LASCO/plot/",
        "show_plot": False,
    },
)
input_dir = Path(PATH_CONFIG["input_dir"])
output_dir = Path(PATH_CONFIG["output_dir"])
output_dir.mkdir(parents=True, exist_ok=True)
show_plot = bool(PATH_CONFIG.get("show_plot", False))
files = sorted(input_dir.glob("*.jp2"))

for file_path in files:
    lasco_map = Map(file_path)
    fig = plt.figure()
    ax = fig.add_subplot(projection=lasco_map)
    lasco_map.plot(axes=ax)

    base_name = file_path.stem
    output_path = output_dir / f"{base_name}.png"
    plt.savefig(output_path, dpi=200, bbox_inches="tight")

    if show_plot:
        plt.show()
    plt.close(fig)
