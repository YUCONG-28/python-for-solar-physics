# -*- coding: utf-8 -*-
"""
Created on Sun Mar 16 20:03:16 2025

@author: 李
"""

import os
import sunpy.map

import matplotlib.pyplot as plt
import astropy.units as u
import matplotlib.colors as colors

from astropy.coordinates import SkyCoord
from sunpy.coordinates import propagate_with_solar_surface

vmin = 1  # 最小值（对数尺度）
vmax = 2000  # 最大值（对数尺度）
norm = colors.LogNorm(vmin=vmin, vmax=vmax)

data_dir = 'D:/Flare/JSOCdata/AIA_304/fits'
file_paths = [os.path.join(data_dir, f) for f in os.listdir(data_dir) if f.endswith('.fits')]
aia_sequence = sunpy.map.Map(file_paths, sequence=True)
output_dir = 'D:/Flare/JSOCdata/AIA_304/plot_offset/'
os.makedirs(output_dir, exist_ok=True)

my_map = sunpy.map.Map(aia_sequence[1])
roi_bottom_left = SkyCoord(Tx=180 * u.arcsec, Ty=-340 * u.arcsec, frame=my_map.coordinate_frame)
roi_top_right = SkyCoord(Tx=520 * u.arcsec, Ty=20 * u.arcsec, frame=my_map.coordinate_frame)
cutout_map = my_map.submap(roi_bottom_left, top_right=roi_top_right)

# fig = plt.figure()
# ax = fig.add_subplot(projection=cutout_map)
# cutout_map.plot(axes=ax,norm=norm)

normalized_sequence = []
for m in aia_sequence:
    normalized_map = sunpy.map.Map(m.data / m.exposure_time, m.meta)
    normalized_sequence.append(normalized_map)
aia_sequence_normalized = sunpy.map.Map(normalized_sequence, sequence=True)

with propagate_with_solar_surface():
    aia_sequence_aligned = sunpy.map.Map([m.reproject_to(cutout_map.wcs) for m in aia_sequence_normalized], sequence=True)

for i in range(200):  # 从 0 到 4
    fig = plt.figure()
    ax = fig.add_subplot(projection=aia_sequence_aligned[i])
    ani = aia_sequence_aligned[i].plot(axes=ax, cmap='sdoaia304', norm=norm)
    
    original_file_path = file_paths[i]
    base_name = os.path.basename(original_file_path)
    output_path = os.path.join(output_dir, base_name + '.png')
    
    parts = base_name.split('.')
    time_str = parts[2]
    plt.title(time_str)
    
    plt.savefig(output_path, dpi=200, bbox_inches='tight')
    
    plt.show()
