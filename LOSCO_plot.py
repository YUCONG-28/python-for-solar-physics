# -*- coding: utf-8 -*-
"""
Created on Mon Mar 31 11:06:15 2025

@author: 李
"""
import os
import glob

from sunpy.map import Map

import matplotlib.pyplot as plt

input_dir = '<DATA_ROOT>/data/'
output_dir = '<DATA_ROOT>/plot/'
os.makedirs(output_dir,exist_ok=True)
files = glob.glob(os.path.join(input_dir, "*.jp2"))
 
for file_path in files:
    lasco_map = Map(file_path)
    fig = plt.figure()
    ax = fig.add_subplot(projection=lasco_map)
    lasco_map.plot(axes=ax)
    
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_path = os.path.join(output_dir, base_name + '.png')
    plt.savefig(output_path, dpi=200, bbox_inches='tight')
    
    plt.show()