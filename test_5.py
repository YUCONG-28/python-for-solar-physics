# -*- coding: utf-8 -*-
"""
Created on Mon Mar  3 09:28:24 2025

@author: 李
"""

#import numpy as np
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei']  # Windows
categories = ['A','B','C','D']
values = [22,34,42,66]
plt.bar(categories, values, color='skyblue')
plt.title("柱状图")
plt.xlabel("种类")
plt.ylabel("y")
plt.show()