# -*- coding: utf-8 -*-
"""
Created on Mon Mar 17 11:38:28 2025

@author: 李
"""

import sunpy.map
import numpy as np
import astropy.units as u
import matplotlib.pyplot as plt
from astropy.coordinates import SkyCoord

HMI_LOS_IMAGE='<DATA_ROOT>/JSOCdata/HMI/hmi.M_45s.20240808_192230_TAI.2.magnetogram.fits'
AIA_171_IMAGE='<DATA_ROOT>/aia.lev1_euv_12s.2024-08-08T192310Z.171.image_lev1.fits'

aia, hmi = sunpy.map.Map(AIA_171_IMAGE, HMI_LOS_IMAGE)
scipy_map = hmi.rotate(method='scipy')

bottom_left = SkyCoord(300* u.arcsec, -290* u.arcsec, frame=aia.coordinate_frame)
top_right = SkyCoord(500* u.arcsec, -90* u.arcsec, frame=aia.coordinate_frame)

sub_aia = aia.submap(bottom_left, top_right=top_right)
sub_hmi = scipy_map.submap(bottom_left, top_right=top_right)

fig = plt.figure(figsize=(8, 8))

ax = fig.add_subplot(projection=sub_aia)
sub_aia.plot(axes=ax, clip_interval=(1, 99.99)*u.percent)
sub_aia.draw_grid(axes=ax)

ax.set_title("AIA 171 with HMI magnetic field strength contours", y=1.1)

levels = [ 100, 150, 300, 500, 1000] * u.Gauss

levels = np.concatenate((-1 * levels[::-1], levels))

bounds = ax.axis()

cset = sub_hmi.draw_contours(levels, axes=ax, cmap='seismic', alpha=0.5)
ax.axis(bounds)

plt.colorbar(cset,
              label=f"Magnetic Field Strength [{sub_hmi.unit}]",
              ticks=list(levels.value) + [0],
              shrink=0.8,
              pad=0.17)

plt.show()