# -*- coding: utf-8 -*-
"""
Created on Sun Mar  9 20:39:21 2025

@author: 21129
"""

from astropy.io import fits
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os  # 用于文件路径处理

# 修改字体设置部分
plt.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示问题

def process_hxi_fits(input_dir, output_dir):
    # 检查输入文件夹是否存在
    if not os.path.exists(input_dir):
        print(f"错误：输入文件夹 '{input_dir}' 不存在！")
        return
    
    # 创建输出文件夹（如果不存在）
    os.makedirs(output_dir, exist_ok=True)
    
    # 获取文件夹中所有FITS文件
    fits_files = [f for f in os.listdir(input_dir) if f.endswith('.fits')]
    
    if not fits_files:
        print(f"警告：在 '{input_dir}' 中未找到任何FITS文件！")
        return
    
    # 遍历处理每个FITS文件
    for fits_file in fits_files:
        try:
            # 构建完整文件路径
            file_path = os.path.join(input_dir, fits_file)
            print(f"正在处理: {file_path}")
            
            # 打开FITS文件
            with fits.open(file_path) as hdul:
                # 提取数据
                h1 = hdul[1].data
                h3 = hdul[3].data
                CTS = h3['CTS_THINTHICK']
                C0 = CTS[:, 0]
                C1 = CTS[:, 1]
                C2 = CTS[:, 2]
                C3 = CTS[:, 3]
                
                # 计算时间序列
                base_time = datetime(2018, 12, 31, 16, 00, 00)
                utc_times = [base_time + timedelta(seconds=t) for t in h1.TIME]
                
                # 创建图像
                plt.figure(figsize=(25, 16))
                ax1 = plt.gca()
                
                # 绘制光变曲线
                plt.semilogy(utc_times, C0, label='HXI 10-20 keV')
                plt.semilogy(utc_times, C1, label='HXI 20-50 keV')
                plt.semilogy(utc_times, C2, label='HXI 50-100 keV')
                plt.semilogy(utc_times, C3, label='HXI 100-300 keV')
                
                # 设置坐标轴和标题
                plt.ylabel("Counts s⁻¹ detector⁻¹", fontsize=22, labelpad=12)
                plt.legend(loc='upper left', ncol=1, fontsize=18)
                
                # 添加分钟级网格线
                ax1.xaxis.set_minor_locator(mdates.MinuteLocator())
                ax1.xaxis.grid(True, which='minor', linestyle='--', color='gray', alpha=0.5)
                
                # 设置时间格式
                plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
                plt.gcf().autofmt_xdate()  # 自动旋转日期标签
                plt.xlabel("时间 (UTC)", fontsize=22, labelpad=12)
                
                # 使用文件名作为部分标题
                file_name = os.path.splitext(fits_file)[0]
                plt.title(f"{file_name}", fontsize=22, fontweight="bold")
                
                # 保存图像（使用FITS文件名作为图像名）
                img_name = f"{file_name}.png"
                img_path = os.path.join(output_dir, img_name)
                plt.savefig(img_path, dpi=300, bbox_inches='tight')
                plt.show()
                print(f"图像已保存至: {img_path}")
                
                plt.close()  # 关闭图像以释放内存
                
        except Exception as e:
            print(f"处理文件 {fits_file} 时出错: {str(e)}")

if __name__ == "__main__":
    # 配置输入输出文件夹路径（可根据需要修改）
    INPUT_DIRECTORY = 'D:/spike_topping_type_III/HXR/2025_05_03'  # FITS文件所在文件夹
    OUTPUT_DIRECTORY = 'D:/spike_topping_type_III/HXR/2025_05_03'  # 图像保存文件夹
    
    # 执行处理函数
    process_hxi_fits(INPUT_DIRECTORY, OUTPUT_DIRECTORY)
    print("处理完成！")