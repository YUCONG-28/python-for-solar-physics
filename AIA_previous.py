# -*- coding: utf-8 -*-
"""
AIA Data Processing Script
==========================
This script processes AIA 1600Å solar observation FITS files.
It performs the following operations:
1. Loads FITS files from a specified directory
2. Normalizes data by exposure time
3. Reprojects images to a common coordinate system
4. Creates and saves visualization plots
5. Manages memory usage during batch processing

Author: 李
Created on: Wed Mar  5 21:51:43 2025
"""

import os
import gc
import time
import matplotlib.pyplot as plt
import matplotlib.colors as colors
import astropy.units as u
from tqdm import tqdm

# Import common utilities
from common_utils import (
    create_roi_coordinates,
    normalize_exposure_time,
    reproject_to_target
)

# Configuration parameters
vmin = 9   # Minimum value for logarithmic scale
vmax = 999  # Maximum value for logarithmic scale
norm = colors.LogNorm(vmin=vmin, vmax=vmax)
data_dir = '<DATA_ROOT>/JSOCdata/All/AIA_1600/'
output_dir = '<DATA_ROOT>/JSOCdata/All/AIA_1600/plot_s_2/'
os.makedirs(output_dir, exist_ok=True)

# File range settings
start_idx = 0    # Start index (inclusive)
end_idx = 300    # End index (exclusive)

def main():
    """Main processing function"""
    # Get all FITS file paths and sort them
    file_paths = [os.path.join(data_dir, f) for f in os.listdir(data_dir) 
                  if f.endswith('.fits')]
    file_paths.sort()

    # Validate file range
    if len(file_paths) == 0:
        raise ValueError("No FITS files found in data directory!")
    if start_idx < 0:
        raise ValueError("Start index cannot be less than 0!")
    if end_idx > len(file_paths):
        raise ValueError(f"End index cannot exceed total number of files ({len(file_paths)})!")
    if start_idx >= end_idx:
        raise ValueError("Start index must be less than end index!")

    selected_files = file_paths[start_idx:end_idx]
    total_files = len(selected_files)
    print(f"Selected {total_files} files for processing (from index {start_idx} to {end_idx-1})")

    # Load reference file to determine cropping region and coordinate transformation
    target_wcs = None
    if len(file_paths) >= 2:
        import sunpy.map
        from astropy.coordinates import SkyCoord
        
        temp_map = sunpy.map.Map(file_paths[1])
        
        # Define cropping region
        roi_bottom_left = SkyCoord(Tx=250 * u.arcsec, Ty=-270 * u.arcsec, 
                                   frame=temp_map.coordinate_frame)
        roi_top_right = SkyCoord(Tx=430 * u.arcsec, Ty=-140 * u.arcsec, 
                                 frame=temp_map.coordinate_frame)
        cutout_map = temp_map.submap(roi_bottom_left, top_right=roi_top_right)
        target_wcs = cutout_map.wcs
        
        # Clean up temporary variables
        del temp_map, cutout_map

    # Process files with progress display
    start_time = time.time()
    for file_path in tqdm(selected_files, desc="Processing", unit="File"):
        try:
            # Load current map
            import sunpy.map
            current_map = sunpy.map.Map(file_path)
            
            # Normalize by exposure time
            normalized_map = normalize_exposure_time(current_map)
            
            # Reproject to target coordinate system
            aligned_map = reproject_to_target(normalized_map, target_wcs)
            
            # Create visualization
            fig = plt.figure()
            ax = fig.add_subplot(projection=aligned_map)
            aligned_map.plot(axes=ax, cmap='sdoaia1600', norm=norm)
            
            # Save or display
            base_name = os.path.basename(file_path)
            output_path = os.path.join(output_dir, f"{base_name}.png")
            time_str = base_name.split('.')[2]
            plt.title(time_str)
            
            # Save the plot
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.show()
            plt.close(fig)
            
            # Clean up memory
            del current_map, normalized_map, aligned_map, ax, fig
            gc.collect()
            
        except Exception as e:
            print(f"\nError processing file: {file_path} : {str(e)}")
            plt.close('all')
            gc.collect()
            continue

    total_time = time.time() - start_time
    print(f"\nProcessing complete! Processed {total_files} files in {total_time:.2f} seconds")

if __name__ == "__main__":
    main()
