# -*- coding: utf-8 -*-
"""
Created on Sun Mar  9 20:39:21 2025

@author: Solar Physics Toolkit contributors
"""

from astropy.io import fits
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os  # For file path processing

# Modify font settings
plt.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False  # Fix minus sign display issue

def process_hxi_fits(input_dir, output_dir):
    # Check if input directory exists
    if not os.path.exists(input_dir):
        print(f"Error: Input directory '{input_dir}' does not exist!")
        return
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Get all FITS files in the directory
    fits_files = [f for f in os.listdir(input_dir) if f.endswith('.fits')]
    
    if not fits_files:
        print(f"Warning: No FITS files found in '{input_dir}'!")
        return
    
    # Process each FITS file
    for fits_file in fits_files:
        try:
            # Build full file path
            file_path = os.path.join(input_dir, fits_file)
            print(f"Processing: {file_path}")
            
            # Open FITS file
            with fits.open(file_path) as hdul:
                # Extract data
                h1 = hdul[1].data
                h3 = hdul[3].data
                CTS = h3['CTS_THINTHICK']
                C0 = CTS[:, 0]
                C1 = CTS[:, 1]
                C2 = CTS[:, 2]
                C3 = CTS[:, 3]
                
                # Calculate time series
                base_time = datetime(2018, 12, 31, 16, 00, 00)
                utc_times = [base_time + timedelta(seconds=t) for t in h1.TIME]
                
                # Create figure
                plt.figure(figsize=(25, 16))
                ax1 = plt.gca()
                
                # Plot light curves
                plt.semilogy(utc_times, C0, label='HXI 10-20 keV')
                plt.semilogy(utc_times, C1, label='HXI 20-50 keV')
                plt.semilogy(utc_times, C2, label='HXI 50-100 keV')
                plt.semilogy(utc_times, C3, label='HXI 100-300 keV')
                
                # Set axis labels and title
                plt.ylabel("Counts s⁻¹ detector⁻¹", fontsize=22, labelpad=12)
                plt.legend(loc='upper left', ncol=1, fontsize=18)
                
                # Add minute-level grid lines
                ax1.xaxis.set_minor_locator(mdates.MinuteLocator())
                ax1.xaxis.grid(True, which='minor', linestyle='--', color='gray', alpha=0.5)
                
                # Set time format
                plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
                plt.gcf().autofmt_xdate()  # Auto-rotate date labels
                plt.xlabel("Time (UTC)", fontsize=22, labelpad=12)
                
                # Use filename as part of title
                file_name = os.path.splitext(fits_file)[0]
                plt.title(f"{file_name}", fontsize=22, fontweight="bold")
                
                # Save image (use FITS filename as image name)
                img_name = f"{file_name}.png"
                img_path = os.path.join(output_dir, img_name)
                plt.savefig(img_path, dpi=300, bbox_inches='tight')
                plt.show()
                print(f"Image saved to: {img_path}")
                
                plt.close()  # Close figure to free memory
                
        except Exception as e:
            print(f"Error processing file {fits_file}: {str(e)}")

if __name__ == "__main__":
    # Configure input and output directory paths (modify as needed)
    INPUT_DIRECTORY = '<PROJECT_ROOT>/HXR/2025_05_03'  # FITS file directory
    OUTPUT_DIRECTORY = '<PROJECT_ROOT>/HXR/2025_05_03'  # Image save directory
    
    # Execute processing function
    process_hxi_fits(INPUT_DIRECTORY, OUTPUT_DIRECTORY)
    print("Processing complete!")
