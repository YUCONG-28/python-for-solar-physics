# -*- coding: utf-8 -*-
"""
Created on Sat Mar  1 21:18:46 2025

@author: 李
"""

import numpy as np
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei']  # Windows
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示异常
x=np.arange(0,9,0.1)
y=np.sin(x)
plt.plot(x,y)
#plt.scatter(x,y)
plt.show()