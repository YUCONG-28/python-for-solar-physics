# -*- coding: utf-8 -*-
"""
Created on Mon Oct 13 16:21:56 2025

@author: Severus
"""

import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from scipy.ndimage import uniform_filter1d, label
from scipy.stats import kurtosis, skew

# ==============================
# 配置参数与常量定义
# ==============================
# 绘图参数设置
plt.rcParams["font.family"] = [
    "Microsoft YaHei",    # 微软雅黑（Windows 7+ 默认中文字体，兼容性最佳）
    "SimHei",            # 黑体（Windows 所有版本默认，无衬线清晰）
    "SimSun",            # 宋体（Windows 所有版本默认，兼容性最强）
    "Microsoft JhengHei",# 微软正黑体（Windows 7+ 默认，支持繁体）
    "Arial",             # Windows 默认英文字体（支持Unicode符号，含负号）
    "sans-serif"         # 系统最终兜底字体
]
plt.rcParams['axes.unicode_minus'] = False  # 正确显示负号
plt.rcParams['figure.dpi'] = 300  # 图像分辨率

# 分析参数
WINDOW_SIZE = 30  # 滑动窗口大小(数据点)
FLUCT_THRESHOLD = 3  # 波动检测阈值(标准差倍数)
DERIV_ABNORMAL_THRESHOLD = 5  # 导数异常检测阈值(标准差倍数)
JUMP_THRESHOLD = 5  # 流量突变检测阈值(标准差倍数)
SPECIFIC_ANALYSIS_PERIOD = ("2024-08-08T19:06:00", "2024-08-08T19:11:00")  # 特定分析时段


# ==============================
# 核心功能函数
# ==============================
def detect_fluctuations(data, threshold_factor=FLUCT_THRESHOLD):
    """检测数据中超过阈值的波动区域"""
    mean_val = np.mean(data)
    std_val = np.std(data)
    threshold = mean_val + threshold_factor * std_val
    return data > threshold


def detect_flux_jumps(flux, threshold_factor=JUMP_THRESHOLD):
    """
    检测原始流量数据中的突变点
    
    参数:
        flux: 流量数据数组
        threshold_factor: 阈值因子(默认5倍标准差)
        
    返回:
        布尔数组，True表示该位置为突变点
    """
    # 计算相邻数据点的绝对差值
    flux_diff = np.abs(np.diff(flux))
    # 为了与原始数据长度匹配，在末尾补0
    flux_diff = np.append(flux_diff, 0)
    
    # 计算阈值
    mean_diff = np.mean(flux_diff)
    std_diff = np.std(flux_diff)
    jump_threshold = mean_diff + threshold_factor * std_diff
    
    # 检测突变点
    jump_mask = flux_diff > jump_threshold
    
    return jump_mask, flux_diff, jump_threshold


def classify_fluctuations(flux, deriv, fluct_mask, time_seconds):
    """基于多特征对波动区域进行分类"""
    # 标记连续波动区域(8邻域连接)
    labeled_regions, num_regions = label(fluct_mask)
    classification = np.zeros_like(fluct_mask, dtype=int)
    
    # 计算全局统计量(用于相对特征计算)
    global_mean_flux = np.mean(flux)
    global_abs_deriv_mean = np.mean(np.abs(deriv)) if np.any(np.abs(deriv)) else 1e-10  # 避免除零
    
    # 逐区域分析分类
    for region in range(1, num_regions + 1):
        region_mask = labeled_regions == region
        region_indices = np.where(region_mask)[0]
        if not region_indices.size:  # 空区域跳过
            continue
            
        # 提取区域内数据
        region_flux = flux[region_indices]
        region_deriv = deriv[region_indices]
        region_time = time_seconds[region_indices]
        
        # 计算区域特征
        duration = region_time[-1] - region_time[0]  # 持续时间(秒)
        flux_max = np.max(region_flux)
        flux_range = flux_max - np.min(region_flux)
        deriv_max = np.max(np.abs(region_deriv))
        
        # 相对特征(避免除零)
        flux_ratio = flux_max / global_mean_flux if global_mean_flux > 0 else 0
        deriv_ratio = deriv_max / global_abs_deriv_mean
        
        # 形态特征
        flux_kurtosis = kurtosis(region_flux)  # 峰度(描述分布陡峭程度)
        flux_skew = skew(region_flux)          # 偏度(描述分布对称性)
        
        # 分类逻辑
        if 10 < duration < 100 and flux_ratio > 5 and flux_kurtosis > 3:
            classification[region_mask] = 1  # 耀斑
        elif duration < 5 and flux_ratio < 2 and np.abs(flux_skew) < 1:
            classification[region_mask] = 2  # 噪声
        elif duration > 100 and deriv_ratio < 3 and flux_skew > 1:
            classification[region_mask] = 3  # 瞬变现象
        else:
            classification[region_mask] = 4  # 数据异常
    
    return classification, labeled_regions, num_regions


def analyze_deriv_abnormalities(time, flux, deriv, jump_mask, band_name):
    """分析导数波动异常大的原因并可视化，新增突变点标记"""
    # 检测导数异常点(使用更高阈值)
    deriv_abs = np.abs(deriv)
    abnormal_mask = detect_fluctuations(deriv_abs, DERIV_ABNORMAL_THRESHOLD)
    abnormal_indices = np.where(abnormal_mask)[0]
    
    if not np.any(abnormal_mask) and not np.any(jump_mask):
        print(f"\n{band_name}波段未检测到导数异常波动点和流量突变点")
        return None
    
    # 创建分析图表
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={'hspace': 0.3})
    fig.suptitle(f"{band_name}波段异常分析(含突变检测)", fontsize=14)
    
    # 1. 原始流量图(标记异常点和突变点对应位置)
    ax1.plot(time, flux, 'b-', alpha=0.7, label='流量数据')
    ax1.scatter(time[abnormal_mask], flux[abnormal_mask], 
                color='red', s=30, label='导数异常对应点', zorder=3)
    ax1.scatter(time[jump_mask], flux[jump_mask], 
                color='orange', s=40, marker='*', label='流量突变点', zorder=4)
    ax1.set_ylabel('流量 (W/m²)')
    ax1.set_title('原始流量数据与异常点标记')
    ax1.legend()
    ax1.grid(True, linestyle="--", alpha=0.5)
    
    # 2. 导数图(标记异常点)
    ax2.plot(time, deriv, 'g-', alpha=0.7, label='导数数据')
    ax2.scatter(time[abnormal_mask], deriv[abnormal_mask], 
                color='red', s=30, label='导数异常点', zorder=3)
    ax2.axhline(y=np.mean(deriv_abs) + DERIV_ABNORMAL_THRESHOLD*np.std(deriv_abs), 
                color='black', linestyle='--', label='异常阈值')
    ax2.set_ylabel('导数 (W/m²/s)')
    ax2.set_title('导数数据与异常阈值')
    ax2.legend()
    ax2.grid(True, linestyle="--", alpha=0.5)
    
    # 设置时间轴
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    plt.xticks(rotation=45, ha="right")
    
    # 分析异常原因
    print(f"\n{band_name}波段检测到{len(abnormal_indices)}个导数异常点和{np.sum(jump_mask)}个流量突变点:")
    for idx in abnormal_indices[:3]:  # 打印前3个异常点分析
        if idx > 0 and idx < len(flux)-1:
            prev_change = flux[idx] - flux[idx-1]
            next_change = flux[idx+1] - flux[idx]
            print(f"时间 {time[idx]}: 流量变化 {prev_change:.2e} → {next_change:.2e}, 导数 {deriv[idx]:.2e}")
    
    return fig


def plot_jump_analysis(time, flux, jump_mask, flux_diff, jump_threshold, band_name):
    """专门展示流量突变分析的图表"""
    if not np.any(jump_mask):
        print(f"\n{band_name}波段无明显流量突变点，不生成突变分析图")
        return None
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={'hspace': 0.3})
    fig.suptitle(f"{band_name}波段流量突变详细分析", fontsize=14)
    
    # 1. 原始流量与突变点
    ax1.plot(time, flux, 'b-', alpha=0.7, label='流量数据')
    ax1.scatter(time[jump_mask], flux[jump_mask], 
                color='orange', s=50, marker='*', label='流量突变点', zorder=3)
    ax1.set_ylabel('流量 (W/m²)')
    ax1.set_title('原始流量数据与突变点标记')
    ax1.legend()
    ax1.grid(True, linestyle="--", alpha=0.5)
    
    # 2. 流量变化率与突变阈值
    ax2.plot(time, flux_diff, 'purple', alpha=0.7, label='相邻流量差')
    ax2.scatter(time[jump_mask], flux_diff[jump_mask], 
                color='orange', s=50, marker='*', label='流量突变点', zorder=3)
    ax2.axhline(y=jump_threshold, color='black', linestyle='--', label='突变检测阈值')
    ax2.set_ylabel('相邻流量差 (W/m²)')
    ax2.set_title('流量变化幅度与突变阈值')
    ax2.legend()
    ax2.grid(True, linestyle="--", alpha=0.5)
    
    # 设置时间轴
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    plt.xticks(rotation=45, ha="right")
    
    return fig


def plot_combined_analysis(time, flux_data, deriv_data, class_data, jump_masks, band_names, fig_title):
    """绘制整合式分析图表(流量+导数+分类+突变点)"""
    fig, axes = plt.subplots(4, 1, figsize=(16, 16), sharex=True, gridspec_kw={'hspace': 0.2})
    fig.suptitle(fig_title, fontsize=16)
    
    # 分类样式配置
    colors = {1: 'red', 2: 'blue', 3: 'green', 4: 'purple'}
    labels = {1: '可能是耀斑', 2: '可能是噪声', 3: '可能是瞬变现象', 4: '可能是数据异常'}
    
    # 逐波段绘制
    for i, (band_name, flux, deriv, classification, jump_mask) in enumerate(
            zip(band_names, flux_data, deriv_data, class_data, jump_masks)):
        # 流量图
        ax_flux = axes[2*i]
        ax_flux.semilogy(time, flux, label=f'{band_name} 流量', alpha=0.7)
        for cat in [1, 2, 3, 4]:
            mask = classification == cat
            if np.any(mask):
                ax_flux.scatter(time[mask], flux[mask], color=colors[cat], 
                               s=15, label=labels[cat], alpha=0.8)
        # 添加突变点标记
        if np.any(jump_mask):
            ax_flux.scatter(time[jump_mask], flux[jump_mask], 
                           color='orange', s=40, marker='*', label='流量突变点', zorder=4)
        ax_flux.set_ylabel('流量 (W/m²)')
        ax_flux.set_title(f'{band_name} 流量及波动分类')
        ax_flux.legend(loc='upper right')
        ax_flux.grid(True, linestyle="--", alpha=0.5)
        
        # 导数图
        ax_deriv = axes[2*i + 1]
        ax_deriv.plot(time, deriv, label=f'{band_name} 导数', alpha=0.7)
        for cat in [1, 2, 3, 4]:
            mask = classification == cat
            if np.any(mask):
                ax_deriv.scatter(time[mask], deriv[mask], color=colors[cat], 
                                s=15, label=labels[cat], alpha=0.8)
        # 添加突变点标记
        if np.any(jump_mask):
            ax_deriv.scatter(time[jump_mask], deriv[jump_mask], 
                           color='orange', s=40, marker='*', label='流量突变点', zorder=4)
        ax_deriv.axhline(y=np.mean(np.abs(deriv)) + FLUCT_THRESHOLD*np.std(np.abs(deriv)), 
                         color='black', linestyle='--', label='波动阈值')
        ax_deriv.set_ylabel('导数 (W/m²/s)')
        ax_deriv.set_title(f'{band_name} 导数及波动分类')
        ax_deriv.legend(loc='upper right')
        ax_deriv.grid(True, linestyle="--", alpha=0.5)
    
    # 配置时间轴
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    axes[-1].xaxis.set_major_locator(mdates.MinuteLocator(interval=5))
    plt.xticks(rotation=45, ha="right")
    
    return fig


def analyze_specific_period(time, flux, deriv, jump_mask, start_time, end_time, band_name):
    """分析特定时间段的流量与导数特征，包含突变点"""
    # 时间筛选
    start_dt, end_dt = np.datetime64(start_time), np.datetime64(end_time)
    mask = (time >= start_dt) & (time <= end_dt)
    period_time, period_flux, period_deriv = time[mask], flux[mask], deriv[mask]
    period_jump = jump_mask[mask]
    
    if not period_time.size:
        print(f"\n{band_name}波段在{start_time}至{end_time}期间无数据")
        return None
    
    # 计算统计特征
    flux_change = period_flux[-1] - period_flux[0]
    avg_deriv = np.mean(np.abs(period_deriv))
    time_delta = (period_time[-1] - period_time[0]).astype('timedelta64[s]').astype(int)
    jump_count = np.sum(period_jump)
    
    print(f"\n{band_name}波段{start_time}至{end_time}分析:")
    print(f"- 流量变化: {flux_change:.2e} W/m²")
    print(f"- 平均变化率: {avg_deriv:.2e} W/m²/s")
    print(f"- 持续时间: {time_delta}秒")
    print(f"- 该时段内检测到{jump_count}个流量突变点")
    
    # 绘图
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={'hspace': 0.3})
    fig.suptitle(f"{band_name}波段 {start_time}至{end_time} 详细分析", fontsize=14)
    
    ax1.plot(period_time, period_flux, 'b-', alpha=0.8)
    if np.any(period_jump):
        ax1.scatter(period_time[period_jump], period_flux[period_jump], 
                   color='orange', s=50, marker='*', label='流量突变点', zorder=3)
        ax1.legend()
    ax1.set_ylabel('流量 (W/m²)')
    ax1.set_title('流量变化曲线')
    ax1.grid(True, linestyle="--", alpha=0.5)
    
    ax2.plot(period_time, period_deriv, 'r-', alpha=0.8)
    ax2.axhline(y=0, color='k', linestyle='-', alpha=0.3)
    if np.any(period_jump):
        ax2.scatter(period_time[period_jump], period_deriv[period_jump], 
                   color='orange', s=50, marker='*', label='流量突变点', zorder=3)
        ax2.legend()
    ax2.set_ylabel('导数 (W/m²/s)')
    ax2.set_title('变化率曲线')
    ax2.grid(True, linestyle="--", alpha=0.5)
    
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    plt.xticks(rotation=45, ha="right")
    
    return fig


def analyze_fluctuation_stats(classification, labeled_regions, num_regions, jump_mask, band_name):
    """统计各类型波动的数量与持续时间，增加突变点统计"""
    stats = {1: 0, 2: 0, 3: 0, 4: 0}
    duration_stats = {1: [], 2: [], 3: [], 4: []}
    
    for region in range(1, num_regions + 1):
        mask = labeled_regions == region
        if np.any(mask):
            cat = classification[mask][0]
            stats[cat] += 1
            duration_stats[cat].append(np.sum(mask))  # 持续数据点数量
    
    # 打印统计结果
    print(f"\n{band_name}波段波动统计:")
    labels = {1: '可能是耀斑', 2: '可能是噪声', 3: '可能是瞬变现象', 4: '可能是数据异常'}
    for cat in [1, 2, 3, 4]:
        if stats[cat] > 0:
            avg_dur = np.mean(duration_stats[cat]) if duration_stats[cat] else 0
            print(f"- {labels[cat]}: {stats[cat]}个区域, 平均持续{avg_dur:.1f}个数据点")
    
    # 突变点统计
    jump_count = np.sum(jump_mask)
    print(f"- 流量突变点: {jump_count}个")
    
    return stats, jump_count


def process_band(time, flux, time_seconds):
    """处理单个波段数据的流水线函数，增加突变检测"""
    # 计算时间导数(变化率)
    deriv = np.gradient(flux, time_seconds)
    # 检测显著波动
    fluct_mask = detect_fluctuations(np.abs(deriv))
    # 分类波动
    classification, labeled_regions, num_regions = classify_fluctuations(
        flux, deriv, fluct_mask, time_seconds)
    # 检测流量突变
    jump_mask, flux_diff, jump_threshold = detect_flux_jumps(flux)
    
    return deriv, fluct_mask, classification, labeled_regions, num_regions, jump_mask, flux_diff, jump_threshold


# ==============================
# 主程序
# ==============================
if __name__ == "__main__":
    # 1. 数据读取与预处理
    file_path = '<DATA_ROOT>/dn_xrsf-l2-flx1s_g16_d20240808_v2-2-0.nc'
    try:
        ds = xr.open_dataset(file_path)
        ds = xr.decode_cf(ds)  # 解码CF格式数据
    except FileNotFoundError:
        raise SystemExit(f"错误: 未找到数据文件 {file_path}")
    
    # 时间范围筛选
    start_time, end_time = "2024-08-08T19:00:00", "2024-08-08T20:00:00"
    ds_subset = ds.sel(time=slice(start_time, end_time))
    time_subset = ds_subset["time"].data
    time_seconds = time_subset.astype('datetime64[s]').astype(float)  # 转换为秒
    
    # 2. 多波段数据处理
    bands = {
        "0.5-4.0 A": ds_subset["xrsa_flux"].data,
        "1.0-8.0 A": ds_subset["xrsb_flux"].data
    }
    
    # 批量处理各波段
    results = {}
    for band_name, flux in bands.items():
        results[band_name] = process_band(time_subset, flux, time_seconds)
    
    # 3. 生成整合分析图表(包含突变点)
    flux_data = [bands[name] for name in bands]
    deriv_data = [results[name][0] for name in bands]
    class_data = [results[name][2] for name in bands]
    jump_masks = [results[name][5] for name in bands]
    
    combined_fig = plot_combined_analysis(
        time_subset, flux_data, deriv_data, class_data, jump_masks,
        list(bands.keys()), "SXR流量与导数波动整合分析(含突变检测)"
    )
    
    # 4. 导数异常与突变综合分析
    deriv_anomaly_figs = []
    for band_name in bands:
        fig = analyze_deriv_abnormalities(
            time_subset, bands[band_name], 
            results[band_name][0], results[band_name][5], band_name
        )
        if fig:
            deriv_anomaly_figs.append(fig)
    
    # 5. 流量突变专门分析
    jump_figs = []
    for band_name in bands:
        fig = plot_jump_analysis(
            time_subset, bands[band_name],
            results[band_name][5], results[band_name][6],
            results[band_name][7], band_name
        )
        if fig:
            jump_figs.append(fig)
    
    # 6. 特定时段分析(包含突变点)
    specific_figs = []
    for band_name in bands:
        fig = analyze_specific_period(
            time_subset, bands[band_name], 
            results[band_name][0], results[band_name][5],
            *SPECIFIC_ANALYSIS_PERIOD, band_name
        )
        if fig:
            specific_figs.append(fig)
    
    # 7. 波段对比总览图(标记突变点)
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(time_subset, bands["0.5-4.0 A"], 'r-', alpha=0.7, label='0.5-4.0 A')
    ax.plot(time_subset, bands["1.0-8.0 A"], 'g-', alpha=0.7, label='1.0-8.0 A')
    
    # 标记突变点
    jump_mask_a = results["0.5-4.0 A"][5]
    jump_mask_b = results["1.0-8.0 A"][5]
    if np.any(jump_mask_a):
        ax.scatter(time_subset[jump_mask_a], bands["0.5-4.0 A"][jump_mask_a],
                  color='orange', s=40, marker='*', label='0.5-4.0 A突变点')
    if np.any(jump_mask_b):
        ax.scatter(time_subset[jump_mask_b], bands["1.0-8.0 A"][jump_mask_b],
                  color='purple', s=40, marker='*', label='1.0-8.0 A突变点')
    
    ax.axvspan(*SPECIFIC_ANALYSIS_PERIOD, color='yellow', alpha=0.3, label='分析时段')
    ax.set_title(f"SXR两波段流量对比 ({start_time}至{end_time})")
    ax.set_ylabel('流量 (W/m²)')
    ax.set_yscale('log')
    ax.legend()
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    
    # 8. 统计分析与综合报告
    total_stats = {1: 0, 2: 0, 3: 0, 4: 0}
    total_jumps = 0
    for band_name in bands:
        stats, jump_count = analyze_fluctuation_stats(
            results[band_name][2], results[band_name][3], 
            results[band_name][4], results[band_name][5], band_name
        )
        total_jumps += jump_count
        for key in total_stats:
            total_stats[key] += stats[key]
    
    # 综合分析报告
    print("\n===== 综合分析报告 =====")
    labels = {1: '可能的耀斑', 2: '可能的噪声', 3: '可能的瞬变现象', 4: '可能的数据异常'}
    for cat, count in total_stats.items():
        if count > 0:
            print(f"- 共检测到{count}个{labels[cat]}区域")
    print(f"- 共检测到{total_jumps}个流量突变点")
    
    # 异常原因总结
    print("\n===== 异常原因综合分析 =====")
    print("1. 流量突变分析:")
    print("   - 可能由仪器采集错误导致的突然跳变")
    print("   - 也可能是快速物理过程的真实反映")
    print("   - 可通过多波段一致性验证: 多波段同时出现的突变更可能是真实现象")
    
    print("\n2. 导数异常分析:")
    print("   - 反映数据变化率，大的导数通常对应快速变化")
    print("   - 与流量突变点相关的导数异常多为真实变化")
    print("   - 孤立的导数异常多为高频噪声")
    
    print("\n3. 建议处理方案:")
    print("   - 对确认的噪声区域可采用滑动平均滤波")
    print("   - 对数据异常点需结合原始数据质量报告验证")
    print("   - 对可能的耀斑和瞬变现象建议进行更精细的时域分析")
    
    # 显示所有图表
    plt.show()