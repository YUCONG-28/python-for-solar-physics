"""
Common utilities for solar data processing.
This module provides shared functions for handling FITS files, coordinate transformations,
and data processing used across multiple scripts.
"""

import os
import re
import numpy as np
import sunpy.map
import astropy.units as u
from astropy.coordinates import SkyCoord
from sunpy.coordinates import propagate_with_solar_surface
from datetime import datetime

def extract_time_from_filename(filename):
    """
    Extract time information from various filename formats.
    
    Args:
        filename (str): The filename to parse
        
    Returns:
        datetime: Extracted datetime object
        
    Raises:
        ValueError: If time cannot be extracted from filename
    """
    # Match HMI filename format
    hmi_match = re.search(r'(\d{8}_\d{6})_TAI', filename)
    if hmi_match:
        time_str = hmi_match.group(1)
        return datetime.strptime(time_str, '%Y%m%d_%H%M%S')
    
    # Match AIA filename format (with colons)
    aia_match1 = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)', filename)
    if aia_match1:
        time_str = aia_match1.group(1)
        return datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%SZ')
    
    # Match AIA filename format (without colons)
    aia_match2 = re.search(r'(\d{4}-\d{2}-\d{2}T\d{6}Z)', filename)
    if aia_match2:
        time_str = aia_match2.group(1)
        return datetime.strptime(time_str, '%Y-%m-%dT%H%M%SZ')
    
    # Alternative AIA filename format
    aia_alt_match = re.search(r'(\d{8})T(\d{6})', filename)
    if aia_alt_match:
        time_str = f"{aia_alt_match.group(1)}_{aia_alt_match.group(2)}"
        return datetime.strptime(time_str, '%Y%m%d_%H%M%S')
    
    raise ValueError(f"Cannot extract time from filename: {filename}")

def get_sorted_files_with_time(input_dir):
    """
    Get all FITS files in a directory sorted by time.
    
    Args:
        input_dir (str): Directory path containing FITS files
        
    Returns:
        list: List of tuples (file_path, file_time, filename) sorted by time
    """
    files = []
    for f in os.listdir(input_dir):
        if f.lower().endswith('.fits'):
            try:
                file_path = os.path.join(input_dir, f)
                if os.path.getsize(file_path) < 1024:  # Skip empty files
                    print(f"Skipping empty file: {f}")
                    continue
                file_time = extract_time_from_filename(f)
                files.append((file_path, file_time, f))
            except ValueError as e:
                print(f"Skipping file (time extraction failed): {e}")
            except Exception as e:
                print(f"Error processing file: {f}, error: {e}")
    return sorted(files, key=lambda x: x[1])

def create_roi_coordinates(temp_map, tx_min=180, tx_max=520, ty_min=-340, ty_max=20):
    """
    Create region of interest coordinates for solar data.
    
    Args:
        temp_map: SunPy map object for coordinate frame reference
        tx_min (float): Minimum Tx coordinate in arcseconds
        tx_max (float): Maximum Tx coordinate in arcseconds
        ty_min (float): Minimum Ty coordinate in arcseconds
        ty_max (float): Maximum Ty coordinate in arcseconds
        
    Returns:
        tuple: (roi_bottom_left, roi_top_right) SkyCoord objects
    """
    roi_bottom_left = SkyCoord(
        Tx=tx_min * u.arcsec, 
        Ty=ty_min * u.arcsec, 
        frame=temp_map.coordinate_frame
    )
    roi_top_right = SkyCoord(
        Tx=tx_max * u.arcsec, 
        Ty=ty_max * u.arcsec, 
        frame=temp_map.coordinate_frame
    )
    return roi_bottom_left, roi_top_right

def normalize_exposure_time(sunpy_map):
    """
    Normalize map data by exposure time.
    
    Args:
        sunpy_map: SunPy map object
        
    Returns:
        SunPy map: Normalized map object
    """
    if sunpy_map.exposure_time <= 0:
        raise ValueError("Exposure time must be positive")
    
    normalized_data = sunpy_map.data / sunpy_map.exposure_time
    return sunpy.map.Map(normalized_data, sunpy_map.meta)

def reproject_to_target(sunpy_map, target_wcs):
    """
    Reproject map to target coordinate system.
    
    Args:
        sunpy_map: SunPy map object to reproject
        target_wcs: Target world coordinate system
        
    Returns:
        SunPy map: Reprojected map object
    """
    with propagate_with_solar_surface():
        return sunpy_map.reproject_to(target_wcs)

def process_fits_file(file_path, target_wcs, roi_bottom_left=None, roi_top_right=None):
    """
    Process a single FITS file: load, normalize, and reproject.
    
    Args:
        file_path (str): Path to FITS file
        target_wcs: Target coordinate system for reprojection
        roi_bottom_left: Bottom-left coordinate for submap (optional)
        roi_top_right: Top-right coordinate for submap (optional)
        
    Returns:
        tuple: (processed_map, exposure_time, original_map)
    """
    # Load the map
    current_map = sunpy.map.Map(file_path)
    
    # Check exposure time
    if current_map.exposure_time <= 0:
        raise ValueError(f"Invalid exposure time in file: {os.path.basename(file_path)}")
    
    # Create submap if ROI coordinates are provided
    if roi_bottom_left and roi_top_right:
        current_map = current_map.submap(roi_bottom_left, top_right=roi_top_right)
    
    # Normalize by exposure time
    normalized_map = normalize_exposure_time(current_map)
    
    # Reproject to target coordinate system
    aligned_map = reproject_to_target(normalized_map, target_wcs)
    
    return aligned_map, current_map.exposure_time, current_map
