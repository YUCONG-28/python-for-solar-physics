# -*- coding: utf-8 -*-
"""
Created on Sun Mar 16 20:15:09 2025

@author: 李
"""

import os
import glob
import sunpy.map

import matplotlib.pyplot as plt
import astropy.units as u

from astropy.coordinates import SkyCoord

input_dir = '<DATA_ROOT>/JSOCdata/HMI/'
output_dir = '<DATA_ROOT>/JSOCdata/HMI/plot2/'
os.makedirs(output_dir,exist_ok=True)
fits_files = glob.glob(os.path.join(input_dir, "*.fits"))
    
for file_path in fits_files:
    HMI_IMAGE=file_path
    my_map = sunpy.map.Map(HMI_IMAGE)
    roi_bottom_left = SkyCoord(Tx=300*u.arcsec, Ty=-290*u.arcsec, frame=my_map.coordinate_frame)
    roi_top_right = SkyCoord(Tx=500*u.arcsec, Ty=-90*u.arcsec, frame=my_map.coordinate_frame)
    my_submap = my_map.submap(roi_bottom_left, top_right=roi_top_right)
        
    fig = plt.figure()
    ax = fig.add_subplot(122,projection=my_submap)
    my_submap.plot(axes=ax,clip_interval=(0, 500)*u.percent)
        
    output_path = os.path.join(output_dir, 
                         os.path.splitext(os.path.basename(file_path))[0] + '.png')
    plt.savefig(output_path, dpi=200, bbox_inches='tight')