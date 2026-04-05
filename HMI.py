# -*- coding: utf-8 -*-
"""
Created on Sun Mar 16 20:15:09 2025

@author: 李
"""

import os
import glob
import sunpy.map
import numpy as np
import matplotlib.pyplot as plt
import astropy.units as u
from astropy.coordinates import SkyCoord
from matplotlib.colors import Normalize
from sunpy.coordinates import frames

input_dir = 'D:/spike_topping_type_III/20250124/All/hmi/2'
output_dir = 'D:/spike_topping_type_III/20250124/All/hmi/2/plot'
os.makedirs(output_dir, exist_ok=True)

# Get all FITS files and sort them
fits_files = sorted(glob.glob(os.path.join(input_dir, "*.fits")))

# Display file information
print(f"Found {len(fits_files)} FITS files")
print("File list:")
for i, file_path in enumerate(fits_files):
    print(f"{i:3d}: {os.path.basename(file_path)}")

# User selects file range
try:
    start_idx = int(input("\nEnter start file index (default 0): ") or 0)
    end_idx = int(input(f"Enter end file index (default {len(fits_files)-1}): ") or len(fits_files)-1)
    
    # Validate index range
    start_idx = max(0, min(start_idx, len(fits_files)-1))
    end_idx = max(start_idx, min(end_idx, len(fits_files)-1))
    
    selected_files = fits_files[start_idx:end_idx+1]
    print(f"\nSelected {len(selected_files)} files for processing (index {start_idx} to {end_idx})")
    
except ValueError:
    print("Invalid input, will process all files")
    selected_files = fits_files

# Set clean plotting style
plt.style.use('default')

for file_path in selected_files:
    HMI_IMAGE = file_path
    my_map_0 = sunpy.map.Map(HMI_IMAGE)
    my_map = my_map_0.rotate(method='scipy')
    
    # Check and correct coordinate system
    print(f"Processing file: {os.path.basename(file_path)}")
    print(f"Coordinate frame: {my_map.coordinate_frame}")
    print(f"Data shape: {my_map.data.shape}")
    
    # Define region of interest
    # If there are orientation issues, try swapping coordinates or using different coordinate values
    roi_top_right = SkyCoord(700*u.arcsec, -200*u.arcsec, frame=my_map.coordinate_frame)
    roi_bottom_left = SkyCoord(900*u.arcsec, 0*u.arcsec, frame=my_map.coordinate_frame)
    
    # Extract submap - no longer using transform_to
    my_submap = my_map.submap(roi_bottom_left, top_right=roi_top_right)
    
    # Create figure
    fig = plt.figure(figsize=(8, 6))
    
    # Use correct projection
    ax = plt.subplot(projection=my_submap)
    
    # Correctly set normalization parameters - via plot_settings
    # First check if normalization is already set
    if 'norm' in my_submap.plot_settings:
        # If yes, update its vmin and vmax
        my_submap.plot_settings['norm'].vmin = -1500
        my_submap.plot_settings['norm'].vmax = 1500
    else:
        # If not, create a new normalization object
        my_submap.plot_settings['norm'] = Normalize(vmin=-1500, vmax=1500)
    
    # Plot magnetic field map - using colormap suitable for HMI
    im = my_submap.plot(
        axes=ax, 
        title=False, 
        cmap='hmimag'  # Color map specifically designed for HMI magnetograms
    )
    
    # Add color bar
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Magnetic Field [G]', rotation=270, labelpad=15)
    
    # Set axis labels
    ax.set_xlabel('Helioprojective Longitude (Solar-X) [arcsec]')
    ax.set_ylabel('Helioprojective Latitude (Solar-Y) [arcsec]')
    
    # Remove grid
    ax.grid(False)
    
    # Add title
    obs_time = my_submap.date.strftime('%Y-%m-%d %H:%M:%S')
    ax.set_title(f'HMI Magnetogram - {obs_time}', fontsize=11, pad=10)
    
    # Draw solar limb
    my_submap.draw_limb(axes=ax, color='black', linewidth=1.0)
    
    # If needed, can add orientation markers (north arrow and east arrow)
    # This helps confirm if the image orientation is correct
    ax.set_autoscale_on(False)
    
    # Adjust layout
    plt.tight_layout()
    
    # Save image
    output_filename = os.path.splitext(os.path.basename(file_path))[0] + '.png'
    output_path = os.path.join(output_dir, output_filename)
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.show()
    plt.close()  # Close figure to free memory
    
    print(f"Generated: {output_filename}")

print(f"\nProcessing complete! Generated {len(selected_files)} images in total.")
print(f"Output directory: {output_dir}")
