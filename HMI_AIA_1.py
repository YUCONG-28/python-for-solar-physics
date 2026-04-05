# -*- coding: utf-8 -*-
"""
Created on Mon Mar 17 10:39:48 2025

@author: 李
"""

import matplotlib.pyplot as plt
import astropy.units as u
from astropy.coordinates import SkyCoord
import sunpy.map

HMI_LOS_IMAGE='<DATA_ROOT>/JSOCdata/HMI/hmi.M_45s.20240808_192230_TAI.2.magnetogram.fits'
AIA_171_IMAGE='<DATA_ROOT>/aia.lev1_euv_12s.2024-08-08T192310Z.171.image_lev1.fits'
aia, hmi = sunpy.map.Map(AIA_171_IMAGE, HMI_LOS_IMAGE)
scipy_map = hmi.rotate(method='scipy')

bottom_left_1 = SkyCoord(300* u.arcsec, -290* u.arcsec, frame=aia.coordinate_frame)
top_right_1 = SkyCoord(500* u.arcsec, -90* u.arcsec, frame=aia.coordinate_frame)

bottom_left_2 = SkyCoord(300* u.arcsec, -290* u.arcsec, frame=hmi.coordinate_frame)
top_right_2 = SkyCoord(500* u.arcsec, -90* u.arcsec, frame=hmi.coordinate_frame)

sub_aia = aia.submap(bottom_left_1,top_right=top_right_1)
sub_hmi = scipy_map.submap(bottom_left_2,top_right=top_right_2)

fig = plt.figure(figsize=(11, 5))
ax1 = fig.add_subplot(121, projection=sub_aia)
sub_aia.plot()

ax2 = fig.add_subplot(122, projection=sub_hmi)
sub_hmi.plot(axes=ax2)

# ax = fig.add_subplot(projection=sub_aia)

# levels = [50, 100, 150, 300, 500, 1000] * u.Gauss
# levels = np.concatenate((-1 * levels[::-1], levels))
# bounds = ax.axis()
# cset = sub_hmi.draw_contours(levels, axes=ax, cmap='seismic', alpha=0.5)
# ax.axis(bounds)

plt.show()