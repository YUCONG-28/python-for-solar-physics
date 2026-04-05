# -*- coding: utf-8 -*-
"""
Created on Tue Mar  4 09:21:34 2025

@author: 李
"""

import xarray as xr
import matplotlib.pyplot as plt
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示异常

file_path = '<DATA_ROOT>/dn_xrsf-l2-flx1s_g16_d20240808_v2-2-0.nc'
ds = xr.open_dataset(file_path)
print(ds)
ds = xr.decode_cf(ds)
condition = (ds.time)
start_time = "2024-08-08T18:00:00"
end_time = "2024-08-08T22:00:00"
ds_subset = ds.sel(time=slice(start_time, end_time))
time_subset = ds_subset["time"]
xrsa_flux_subset = ds_subset["xrsa_flux"]
xrsb_flux_subset = ds_subset["xrsb_flux"]
plt.figure(figsize=(10, 6))
plt.semilogy(time_subset,xrsa_flux_subset) 
plt.semilogy(time_subset,xrsb_flux_subset) 
plt.xlabel("Time (UTC)", fontsize=12, labelpad=10)
plt.ylabel("Flux (W/m²)", fontsize=12, labelpad=10)
plt.title("GOES-16 Solar Soft X-ray Flux (0.5-4 Å)", fontsize=14, fontweight="bold")
plt.show()