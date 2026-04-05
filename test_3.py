# -*- coding: utf-8 -*-
"""
Created on Mon Mar  3 08:58:43 2025

@author: 李
"""

import numpy as np
import matplotlib.pyplot as plt
x = np.arange(0,2*np.pi,0.1)
y1 = np.sin(x)
y2 = np.cos(x)
plt.figure(figsize=(16,16))
plt.plot(x,y1,label='sin(x)',color='red',linestyle='-')
plt.plot(x,y2,label='cos(x)',color='blue',linestyle='--')
plt.title("正弦与余弦曲线")
plt.xlabel("x")
plt.ylabel("y1=sin(x) y2=cos(x)")
plt.grid(True)#显示网格
plt.legend()#显示图例
plt.show()