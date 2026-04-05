# -*- coding: utf-8 -*-
"""
Created on Sun Mar 16 20:03:16 2025

@author: 李
"""

import os
import glob
import sunpy.map

import matplotlib.pyplot as plt
import astropy.units as u
from astropy.coordinates import SkyCoord
from sunpy.coordinates import propagate_with_solar_surface

input_dir = 'D:/Flare/JSOCdata/AIA_1600/'
output_dir = 'D:/Flare/JSOCdata/AIA_1600/plot/'
os.makedirs(output_dir, exist_ok=True)
fits_files = glob.glob(os.path.join(input_dir, "*.fits"))#[75:100]

for file_path in fits_files:
    AIA_1600_IMAGE = file_path
    my_map = sunpy.map.Map(AIA_1600_IMAGE)
    roi_bottom_left = SkyCoord(Tx=180 * u.arcsec, Ty=-340 * u.arcsec, frame=my_map.coordinate_frame)
    roi_top_right = SkyCoord(Tx=520 * u.arcsec, Ty=20 * u.arcsec, frame=my_map.coordinate_frame)
    my_submap = my_map.submap(roi_bottom_left, top_right=roi_top_right)

    my_submap.plot_settings['norm'].vmin = 28
    my_submap.plot_settings['norm'].vmax = 1600
    normalized_map = sunpy.map.Map(my_submap.data / my_submap.exposure_time, my_submap.meta)

    with propagate_with_solar_surface():
        aligned_map = normalized_map.reproject_to(my_map.wcs)

    fig = plt.figure()
    ax = fig.add_subplot(projection=my_submap)
    my_submap.plot(axes=ax)

    output_path = os.path.join(output_dir,
                         os.path.splitext(os.path.basename(file_path))[0] + '.png')
    plt.savefig(output_path, dpi=200, bbox_inches='tight')
    #plt.show()