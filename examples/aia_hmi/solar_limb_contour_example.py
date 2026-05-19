# 模块用途: 测试从 SunPy map 数据中提取日面轮廓/边界。
# 主要输入: 太阳图像 map 或 FITS 测试数据。
# 主要输出/运行说明: 输出轮廓检测结果或调试图像。
"""
Created on Sun Jan 18 15:21:18 2026

@author: Severus
"""

import matplotlib.pyplot as plt
import sunpy.data.sample
import sunpy.map

# 1. Load solar image data (using SunPy's built-in AIA 171Å sample image here)
# To use your own data, replace with: sunpy.map.Map('your_file.fits')
aia_map = sunpy.map.Map(sunpy.data.sample.AIA_171_IMAGE)

# 2. Create image and draw solar limb
fig = plt.figure()
ax = fig.add_subplot(projection=aia_map)  # Key: use the map's own projection
aia_map.plot(axes=ax)  # Draw base map
aia_map.draw_limb(axes=ax, color="red")  # Draw solar limb, color can be customized
plt.colorbar()  # Add color bar
plt.show()
