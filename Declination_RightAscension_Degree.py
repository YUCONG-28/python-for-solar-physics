# -*- coding: utf-8 -*-
"""
Created on Sun Nov 23 00:19:30 2025

@author: Severus
"""

import numpy as np
import matplotlib.pyplot as plt
from astropy.io import fits
from pathlib import Path

def read_fits_data(file_path):
    """
    读取FITS文件的图像数据和头部信息
    :param file_path: FITS文件路径（字符串或Path对象）
    :return: 二维numpy数组（图像数据）和头部信息字典
    """
    try:
        with fits.open(file_path) as hdu_list:
            print(f"\n=== {file_path} 的Header信息 ===")
            print(hdu_list[0].header)
            data = hdu_list[0].data
            header = hdu_list[0].header  # 获取头部信息
            if data.shape != (256, 256):
                print(f"警告：{file_path} 的数据形状为 {data.shape}，预期为 (256, 256)")
            return data, header
    except FileNotFoundError:
        print(f"错误：文件 {file_path} 不存在，请检查路径！")
        return None, None
    except Exception as e:
        print(f"错误：读取 {file_path} 时发生异常：{str(e)}")
        return None, None

def get_coordinate_labels(file_name):
    """根据文件名判断坐标类型"""
    if "Declination" in file_name:
        return "赤经", "赤纬"  # Y轴为赤纬，X轴为配套赤经
    elif "RightAscension" in file_name:
        return "赤经", "赤纬"  # X轴为赤经，Y轴为配套赤纬
    else:
        return "X (像素)", "Y (像素)"

def calculate_coordinate_range(header):
    """
    从FITS头部计算坐标范围
    :param header: FITS文件头部信息
    :return: 赤经范围和赤纬范围 (ra_min, ra_max, dec_min, dec_max)
    """
    try:
        # 从header获取坐标参考值、像素间隔和参考像素位置
        ra_ref = header['CRVAL1']  # 赤经参考点坐标
        dec_ref = header['CRVAL2']  # 赤纬参考点坐标
        ra_step = header['CDELT1']  # 赤经方向像素间隔
        dec_step = header['CDELT2']  # 赤纬方向像素间隔
        ra_pix_ref = header['CRPIX1']  # 赤经参考像素位置
        dec_pix_ref = header['CRPIX2']  # 赤纬参考像素位置
        ra_size = header['NAXIS1']  # 赤经方向像素数
        dec_size = header['NAXIS2']  # 赤纬方向像素数

        # 计算赤经范围
        ra_min = ra_ref - (ra_pix_ref - 1) * ra_step
        ra_max = ra_ref + (ra_size - ra_pix_ref) * ra_step
        # 计算赤纬范围
        dec_min = dec_ref - (dec_pix_ref - 1) * dec_step
        dec_max = dec_ref + (dec_size - dec_pix_ref) * dec_step

        return round(ra_min, 2), round(ra_max, 2), round(dec_min, 2), round(dec_max, 2)
    except KeyError as e:
        print(f"警告：Header中缺少坐标信息 {e}，无法计算坐标范围")
        return None, None, None, None
    except Exception as e:
        print(f"计算坐标范围时发生错误：{str(e)}")
        return None, None, None, None

def plot_fits_images(data1, data2, header1, header2, file1_name, file2_name):
    """
    绘制两个FITS文件的图像对比，显示坐标轴标签和实际坐标范围
    """
    # 计算两个文件的坐标范围
    ra1_min, ra1_max, dec1_min, dec1_max = calculate_coordinate_range(header1)
    ra2_min, ra2_max, dec2_min, dec2_max = calculate_coordinate_range(header2)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('149MHz频率的天体辐射强度分布对比', fontsize=14, fontweight='bold')

    # 第一个图像设置（赤纬文件）
    xlabel1, ylabel1 = get_coordinate_labels(file1_name)
    # 设置坐标轴范围（extent参数：[左, 右, 下, 上]）
    extent1 = [ra1_min, ra1_max, dec1_min, dec1_max] if ra1_min is not None else None
    im1 = ax1.imshow(data1, cmap='inferno', origin='lower', extent=extent1)
    ax1.set_title(file1_name, fontsize=12)
    ax1.set_xlabel(xlabel1, fontsize=10)
    ax1.set_ylabel(ylabel1, fontsize=10)
    plt.colorbar(im1, ax=ax1, shrink=0.8, label='辐射强度 (任意单位)')

    # 第二个图像设置（赤经文件）
    xlabel2, ylabel2 = get_coordinate_labels(file2_name)
    extent2 = [ra2_min, ra2_max, dec2_min, dec2_max] if ra2_min is not None else None
    im2 = ax2.imshow(data2, cmap='inferno', origin='lower', extent=extent2)
    ax2.set_title(file2_name, fontsize=12)
    ax2.set_xlabel(xlabel2, fontsize=10)
    ax2.set_ylabel(ylabel2, fontsize=10)
    plt.colorbar(im2, ax=ax2, shrink=0.8, label='辐射强度 (任意单位)')

    plt.tight_layout()
    plt.show()

    return (ra1_min, ra1_max, dec1_min, dec1_max), (ra2_min, ra2_max, dec2_min, dec2_max)

if __name__ == "__main__":
    # 输入文件路径
    fits_file1 = r'D:\spike_topping_type_III\20250124\share\Data\UnPack\20250124UT0447-0450\ImageData_RRLL\149MHz\149MHz_DeclinationDegree.fits'
    fits_file2 = r'D:\spike_topping_type_III\20250124\share\Data\UnPack\20250124UT0447-0450\ImageData_RRLL\149MHz\149MHz_RightAscensionDegree.fits'

    # 读取数据和头部信息
    data1, header1 = read_fits_data(fits_file1)
    data2, header2 = read_fits_data(fits_file2)

    if data1 is not None and data2 is not None:
        # 获取文件名
        file1_name = Path(fits_file1).name
        file2_name = Path(fits_file2).name
        
        # 绘图并获取坐标范围
        range1, range2 = plot_fits_images(
            data1, data2, header1, header2,
            file1_name=file1_name,
            file2_name=file2_name
        )
        ra1_min, ra1_max, dec1_min, dec1_max = range1
        ra2_min, ra2_max, dec2_min, dec2_max = range2
        
        # 图像含义解释
        print("\n=== 观测坐标范围说明 ===")
        print(f"1. 左图（{file1_name}）观测范围：")
        print(f"   - 赤经范围：{ra1_min}° 至 {ra1_max}°")
        print(f"   - 赤纬范围：{dec1_min}° 至 {dec1_max}°")
        print(f"2. 右图（{file2_name}）观测范围：")
        print(f"   - 赤经范围：{ra2_min}° 至 {ra2_max}°")
        print(f"   - 赤纬范围：{dec2_min}° 至 {dec2_max}°")

        print("\n=== 图像来源与异同分析 ===")
        print("1. 共同来源：")
        print("   - 两图均来自同一观测时段（20250124UT0447-0450）")
        print("   - 采用相同观测频率（149MHz）和仪器参数")
        print("   - 数据均反映太阳及近邻天区的射电辐射强度分布")

        print("\n2. 图像差异：")
        print("   - 左图（赤纬文件）：以赤纬为主要维度，展示不同赤经位置上的赤纬方向辐射分布特征，"
              "适合分析辐射在南北方向（赤纬）上的变化规律")
        print("   - 右图（赤经文件）：以赤经为主要维度，展示不同赤纬位置上的赤经方向辐射分布特征，"
              "适合分析辐射在东西方向（赤经）上的变化规律")
        print("   - 坐标轴映射不同：左图X轴为赤经、Y轴为赤纬；右图保持相同坐标轴定义，但数据切片方式不同")

        print("\n3. 核心异同：")
        print("   - 相同点：辐射强度的颜色映射标准一致，均使用'inferno'色标（亮色表示辐射更强）")
        print("   - 不同点：数据采集时的空间扫描方向不同，左图侧重赤纬方向扫描，右图侧重赤经方向扫描")
        print("   - 互补性：两图结合可完整呈现太阳活动在天球坐标系中的二维分布特征，便于分析空间关联性")
    else:
        print("数据读取失败，无法绘图！")