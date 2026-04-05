# -*- coding: utf-8 -*-
"""
Created on Sun Jan 18 15:21:18 2026

@author: Severus
"""

import sunpy.map
import sunpy.data.sample
import matplotlib.pyplot as plt

# 1. Load solar image data (using SunPy's built-in AIA 171Å sample image here)
# To use your own data, replace with: sunpy.map.Map('your_file.fits')
aia_map = sunpy.map.Map(sunpy.data.sample.AIA_171_IMAGE)

# 2. Create image and draw solar limb
fig = plt.figure()
ax = fig.add_subplot(projection=aia_map) # Key: use the map's own projection
aia_map.plot(axes=ax)                    # Draw base map
aia_map.draw_limb(axes=ax, color='red')  # Draw solar limb, color can be customized
plt.colorbar()                            # Add color bar
plt.show()
