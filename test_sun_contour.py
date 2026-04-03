# -*- coding: utf-8 -*-
"""
Created on Sun Jan 18 15:21:18 2026

@author: Severus
"""

import sunpy.map
import sunpy.data.sample
import matplotlib.pyplot as plt

# 1. 载入太阳图像数据（此处使用SunPy内置的AIA 171Å样本图像）
# 如需使用自己的数据，可将文件路径替换为：sunpy.map.Map('your_file.fits')
aia_map = sunpy.map.Map(sunpy.data.sample.AIA_171_IMAGE)

# 2. 创建图像并绘制太阳轮廓
fig = plt.figure()
ax = fig.add_subplot(projection=aia_map) # 关键：使用地图自带的投影
aia_map.plot(axes=ax)                    # 绘制底图
aia_map.draw_limb(axes=ax, color='red')  # 绘制太阳轮廓，可自定义颜色
plt.colorbar()                            # 添加颜色条
plt.show()