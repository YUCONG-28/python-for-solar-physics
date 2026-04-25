# -*- coding: utf-8 -*-
"""
Created on Mon Mar 31 11:06:15 2025

@author: 李
"""
from pathlib import Path

import matplotlib.pyplot as plt
from sunpy.map import Map

input_dir = Path("<DATA_ROOT>/data/")
output_dir = Path("<DATA_ROOT>/plot/")
output_dir.mkdir(parents=True, exist_ok=True)
files = sorted(input_dir.glob("*.jp2"))

for file_path in files:
    lasco_map = Map(file_path)
    fig = plt.figure()
    ax = fig.add_subplot(projection=lasco_map)
    lasco_map.plot(axes=ax)

    base_name = file_path.stem
    output_path = output_dir / f"{base_name}.png"
    plt.savefig(output_path, dpi=200, bbox_inches="tight")

    plt.show()
