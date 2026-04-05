# -*- coding: utf-8 -*-
"""
Created on Thu Mar 13 17:24:04 2025

@author: 李
"""

import matplotlib.pyplot as plt
import astropy.units as u
from astropy.coordinates import SkyCoord
import sunpy.map

HMI_LOS_IMAGE='D:/Flare/hmi.M_45s.20240808_192315_TAI.2.magnetogram.fits'
AIA_171_IMAGE='D:/Flare/aia.lev1_euv_12s.2024-08-08T192310Z.171.image_lev1.fits'
aia, hmi = sunpy.map.Map(AIA_171_IMAGE, HMI_LOS_IMAGE)

fig1 = plt.figure(figsize=(11, 5))
bottom_left = SkyCoord(300* u.arcsec, -290* u.arcsec, frame=aia.coordinate_frame)
top_right = SkyCoord(500* u.arcsec, -90* u.arcsec, frame=aia.coordinate_frame)
sub_aia = aia.submap(bottom_left, top_right=top_right)
ax1 = fig1.add_subplot(122, projection=sub_aia)
sub_aia.plot(axes=ax1,clip_interval=(1, 99.99)*u.percent)

fig2 = plt.figure(figsize=(16, 8))
bottom_left = SkyCoord(300* u.arcsec, -290* u.arcsec, frame=hmi.coordinate_frame)
top_right = SkyCoord(500* u.arcsec, -90* u.arcsec, frame=hmi.coordinate_frame)
sub_hmi = hmi.submap(bottom_left, top_right=top_right)
ax2 = fig2.add_subplot(111, projection=sub_hmi)
sub_hmi.plot(axes=ax2)

plt.colorbar()
plt.show()

