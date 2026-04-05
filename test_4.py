# -*- coding: utf-8 -*-
"""
Created on Mon Mar  3 09:16:16 2025

@author: 李
"""

import numpy as np
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei']  # Windows
x = np.random.rand(50)*10
y = x + 1 + np.random.randn(50)
plt.scatter(x,y,color='red',marker='o',label='散点图')
plt.plot(x,x+1,color='green',label='理论直线')
plt.title("yy")
plt.legend()
plt.show()