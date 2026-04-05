# -*- coding: utf-8 -*-
"""
Created on Wed Mar  5 21:51:43 2025

@author: 李
"""

import matplotlib.pyplot as plt
from astropy.io import fits
from datetime import datetime,timedelta

if __name__ == "__main__":
    file_path = '<DATA_ROOT>/hxi_qld_levq1_20240808_19_hly_v03.fits'
    hdul=fits.open(file_path)

    h1=hdul[1].data
    h3=hdul[3].data

    #选择背景
    A=h3['CTS_THINTHICK']
    B=h3['CTS_BKG_THINTHICK']
    A0=A[:,0]
    A1=A[:,1]
    A2=A[:,2]
    A3=A[:,3]
    B0=B[:,0]
    B1=B[:,1]
    B2=B[:,2]
    B3=B[:,3]
    C0=A0-B0
    C1=A1-B1
    C2=A2-B2
    C3=A3-B3
    
    base_time=datetime(2018,12,13,16,00,00)
    utc_times = [base_time + timedelta(seconds=t) for t in h1.TIME]
    
    plt.figure(figsize=(28, 12))
    plt.semilogy(h1.TIME,C0,label='HXI 10-20 keV') 
    plt.semilogy(h1.TIME,C1,label='HXI 20-50 keV') 
    plt.semilogy(h1.TIME,C2,label='HXI 50-100 keV') 
    plt.semilogy(h1.TIME,C3,label='HXI 100-300 keV') 
    plt.ylim(1,1000)
    plt.legend()


    plt.title("HXl liqhtcurve",fontsize=22, fontweight="bold")
    plt.xlabel("Time (UTC)", fontsize=22, labelpad=12)
    plt.ylabel("Counts s\u207B\u00B9 detector\u207B\u00B9", fontsize=22, labelpad=12)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.xticks(rotation=45, ha="right")
    plt.show()