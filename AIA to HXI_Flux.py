# -*- coding: utf-8 -*-
"""
AIA to HXI Flux Processing Script
==================================
This script processes AIA 304Å solar observation FITS files to calculate flux
and generate time-series plots. The main functions include:
1. Loading and processing FITS files
2. Normalizing data by exposure time
3. Reprojecting images to a common coordinate system
4. Calculating total flux in a region of interest
5. Generating time-series plots of flux evolution

Author: Severus
Created on: Sun Oct  5 00:04:22 2025
"""

import os
import time
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
from datetime import datetime, timedelta
from tqdm import tqdm

# Import common utilities
from common_utils import (
    extract_time_from_filename,
    create_roi_coordinates,
    process_fits_file
)

# Configuration parameters
data_dir = '<DATA_ROOT>/JSOCdata/All/AIA_304/'
output_dir = '<DATA_ROOT>/JSOCdata/All/Flux/'
os.makedirs(output_dir, exist_ok=True)

# Configure font settings for Chinese display
plt.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False  # Fix minus sign display issue

def main():
    """Main processing function"""
    # Lists to store results
    time_list = []
    sum_data_list = []
    
    # Get and sort FITS files (case-insensitive)
    file_paths = []
    for f in os.listdir(data_dir):
        if f.lower().endswith('.fits'):
            file_paths.append(os.path.join(data_dir, f))
    file_paths.sort()
    total_files = min(595, len(file_paths))
    
    # Determine cropping region
    target_wcs = None
    if len(file_paths) >= 2:
        try:
            import sunpy.map
            from astropy.coordinates import SkyCoord
            from sunpy.coordinates import propagate_with_solar_surface
            
            temp_map = sunpy.map.Map(file_paths[0])
            
            # Define region of interest (ROI)
            roi_bottom_left, roi_top_right = create_roi_coordinates(
                temp_map, tx_min=180, tx_max=520, ty_min=-340, ty_max=20
            )
            
            # Get target coordinate system
            with propagate_with_solar_surface():
                cutout_map = temp_map.submap(roi_bottom_left, top_right=roi_top_right)
                target_wcs = cutout_map.wcs
            
            # Manually release resources
            del temp_map, cutout_map
            
        except Exception as e:
            raise ValueError(f"Failed to initialize cropping region: {str(e)}") from e
    else:
        raise ValueError("Insufficient number of files, at least 2 FITS files are required!")
    
    # Process files
    start_time = time.time()
    
    for i in tqdm(range(total_files), desc="Processing progress", unit="file"):
        try:
            # Process the FITS file
            aligned_map, exposure_time, original_map = process_fits_file(
                file_paths[i], target_wcs, roi_bottom_left, roi_top_right
            )
            
            # Calculate total flux
            data_sum = np.sum(aligned_map.data)
            
            # Extract time from filename
            base_name = os.path.basename(file_paths[i])
            try:
                dt = extract_time_from_filename(base_name)
                time_list.append(dt)
                sum_data_list.append(data_sum)
            except ValueError:
                print(f"\nFile {base_name} time format does not match, skipping")
                continue
            
            # Manually release resources
            del original_map, aligned_map
            
        except Exception as e:
            print(f"\nError processing file {os.path.basename(file_paths[i])}: {str(e)}")
            continue
    
    # Force garbage collection
    import gc
    gc.collect()
    
    # Generate time-series plot
    if time_list and sum_data_list:
        plt.figure(figsize=(16, 8))
        plt.plot(time_list, sum_data_list, 'r-', linewidth=1.5)
        plt.xlabel('Time', fontsize=12)
        plt.ylabel('Flux', fontsize=12)
        plt.title('AIA 304Å Flux Time Series', fontsize=14)
        plt.legend(['Flux'])
        
        ax = plt.gca()
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        
        # Time axis settings
        base_date = time_list[0].date()
        start_19h = datetime.combine(base_date, datetime.min.time().replace(hour=19))
        end_dt = time_list[-1]
        
        # Adjustable time interval
        time_interval_minutes = 5
        tick_times = []
        current_tick = start_19h if start_19h <= end_dt else time_list[0]
        while current_tick <= end_dt:
            tick_times.append(current_tick)
            current_tick += timedelta(minutes=time_interval_minutes)
        
        # Add vertical reference lines
        for tick in tick_times:
            plt.axvline(x=tick, color='gray', linestyle='--', alpha=0.3, linewidth=1)
        
        # Use ticker.FixedLocator instead of mdates.FixedLocator
        ax.xaxis.set_major_locator(ticker.FixedLocator(mdates.date2num(tick_times)))
        plt.xticks(rotation=45, ha='right')
        plt.grid(alpha=0.2)
        plt.tight_layout()
        
        # Save the plot
        output_path = os.path.join(output_dir, 'AIA_304.png')
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"\nTime-series plot saved to: {output_path}")
        plt.show()
    else:
        print("\nNo valid data for plotting!")
    
    # Output processing statistics
    total_time = time.time() - start_time
    print(f"\nProcessing complete! Processed {len(time_list)} files, time taken: {total_time:.2f} seconds")

if __name__ == "__main__":
    main()
