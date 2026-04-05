# -*- coding: utf-8 -*-
"""
Created on Mon Mar 31 11:06:15 2025

@author: 李
"""

from datetime import datetime, timedelta
import hvpy
import matplotlib.pyplot as plt
from hvpy.datasource import DataSource
import astropy.units as u
from astropy.coordinates import SkyCoord
import sunpy.data.sample
from sunpy.coordinates import SphericalScreen
from sunpy.map import Map
from sunpy.util.config import get_and_create_download_dir

# 起始时间和结束时间
# start_time = datetime(2024, 8, 8, 19, 20)
# end_time = datetime(2024, 8, 8, 19, 24)

# time_interval = timedelta(seconds=60)

# current_time = start_time
# while current_time <= end_time:
#     try:
#         lasco_jp2_file = hvpy.save_file(hvpy.getJP2Image(current_time,
#                                                          DataSource.LASCO_C2.value),
#                                         filename=get_and_create_download_dir() + f"/LASCO_C2_{current_time.strftime('%Y%m%d_%H%M%S')}.jp2", overwrite=True)
#         file_path = 'D:/LASCO/LASCO_C2.jp2'
#         lasco_map = Map(file_path)
#         aia_map = Map(sunpy.data.sample.AIA_171_IMAGE)
#         # 你可以在这里添加对 lasco_map 和 aia_map 的处理代码
#     except Exception as e:
#         print(f"处理 {current_time} 时出现错误: {e}")
#     # 更新当前时间
#     current_time += time_interval
file_path= 'D:/Flare/JSOCdata/AIA_171/aia.lev1_euv_12s.2024-08-08T192222Z.171.image_lev1.fits'
lasco_map = Map('D:/LASCO/LASCO_C2.jp2')
aia_map = Map(file_path)
projected_coord = SkyCoord(0*u.arcsec, 0*u.arcsec,
                           obstime=lasco_map.observer_coordinate.obstime,
                           frame='helioprojective',
                           observer=lasco_map.observer_coordinate,
                           rsun=aia_map.coordinate_frame.rsun)
projected_header = sunpy.map.make_fitswcs_header(aia_map.data.shape,
                                                 projected_coord,
                                                 scale=u.Quantity(aia_map.scale),
                                                 instrument=aia_map.instrument,
                                                 wavelength=aia_map.wavelength)
# We use `~sunpy.coordinates.SphericalScreen` to ensure that the off limb AIA pixels
# are reprojected. Otherwise it will only be the on disk pixels that are reprojected.
with SphericalScreen(aia_map.observer_coordinate):
    aia_reprojected = aia_map.reproject_to(projected_header)
    
fig = plt.figure()
ax = fig.add_subplot(projection=lasco_map)
lasco_map.plot(axes=ax)
aia_reprojected.plot(axes=ax, clip_interval=(1, 99.9)*u.percent, autoalign=True)
ax.set_title("AIA and LASCO C2 Overlay")

plt.show()