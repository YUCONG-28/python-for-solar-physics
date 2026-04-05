# -*- coding: utf-8 -*-
"""
Created on Sun Mar 23 21:21:44 2025

@author: 李
"""

import sunpy.map

import numpy as np
import astropy.units as u
import matplotlib.pyplot as plt
import matplotlib.colors as colors

from matplotlib.colors import Normalize
from astropy.coordinates import SkyCoord
from skimage.measure import label, regionprops

vmin = 10  # 最小值（对数尺度）
vmax = 2000  # 最大值（对数尺度）
norm = colors.LogNorm(vmin=vmin, vmax=vmax)

AIA_171_IMAGE = '<DATA_ROOT>/JSOCdata/AIA_171/aia.lev1_euv_12s.2024-08-08T192234Z.171.image_lev1.fits'
my_map = sunpy.map.Map(AIA_171_IMAGE)
roi_bottom_left = SkyCoord(Tx=180*u.arcsec, Ty=-340*u.arcsec, frame=my_map.coordinate_frame)
roi_top_right = SkyCoord(Tx=520*u.arcsec, Ty=20*u.arcsec, frame=my_map.coordinate_frame)
my_submap = my_map.submap(roi_bottom_left, top_right=roi_top_right)
normalized_map = sunpy.map.Map(my_submap.data/my_submap.exposure_time, my_submap.meta)

HMI_IMAGE='<DATA_ROOT>/JSOCdata/HMI/hmi.M_45s.20240808_192230_TAI.2.magnetogram.fits'
hmi = sunpy.map.Map(HMI_IMAGE)
hmi = hmi.submap(roi_bottom_left, top_right=roi_top_right)

aia = normalized_map.reproject_to(hmi.wcs)
aia.nickname = 'AIA'

segmented = aia.data > 520
labeled = label(segmented)
regions = regionprops(labeled, hmi.data)
regions = sorted(regions, key=lambda r: r.area, reverse=True)

fig = plt.figure()
ax = fig.add_subplot(projection=aia)
aia.plot(axes=ax)
aia.draw_contours(axes=ax, levels=180, colors="r")
for i in range(7):
    plt.text(*np.flip(regions[i].centroid), str(i), color="w", ha="center", va="center")
    
fig = plt.figure()
ax = fig.add_subplot(projection=hmi)
im = hmi.plot(axes=ax, cmap="hmimag", norm=Normalize(-1400, 1400))
aia.draw_contours(axes=ax, levels=180, colors="r")
fig.colorbar(im)
    
bbox = regions[0].bbox
mask = np.ones_like(hmi.data, dtype=bool)
mask[bbox[0]: bbox[2], bbox[1]: bbox[3]] = ~regions[0].image
hmi_masked = sunpy.map.Map((hmi.data, hmi.meta), mask=mask)
fig = plt.figure()
ax = fig.add_subplot(projection=hmi_masked)
im = hmi_masked.plot(axes=ax, cmap="hmimag", norm=Normalize(-1300, 1300))
fig.colorbar(im)

plt.show()
