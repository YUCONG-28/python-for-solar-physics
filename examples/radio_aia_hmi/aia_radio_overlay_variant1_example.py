# 模块用途: 测试 AIA 与射电源叠加流程的另一组参数变体。
# 主要输入: AIA 和射电源测试数据。
# 主要输出/运行说明: 输出叠加调试结果，用于比较不同配置。
"""
Created on Tue Jan 20 22:39:17 2026

@author: Severus
"""

import gc
import os
import time
import warnings

import matplotlib.colors as colors
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
import sunpy.map
from astropy.io import fits

warnings.filterwarnings("ignore")

# ============================== 配置参数 ==============================
# AIA图像参数
aia_file = "D:/spike_topping_type_III/2025/20250124/AIA/171/1/aia.lev1_euv_12s.2025-01-24T044810Z.171.image_lev1.fits"
aia_vmin = 16  # 最小值（对数尺度）
aia_vmax = 6666  # 最大值（对数尺度）
aia_cmap = "sdoaia171"  # 如果这个颜色映射不存在，使用'hot'
aia_norm = colors.LogNorm(vmin=aia_vmin, vmax=aia_vmax)

# 射电图像参数
radio_file = r"D:\spike_topping_type_III\2025\20250124\RS_0447-0450\149MHz\RR\149MHz_2025124_044910_449.fits"
radio_cmap = "jet"

# 显示范围参数 - 可以在这里修改最终显示的坐标范围
# 格式: [x_min, x_max, y_min, y_max] (单位: 角秒)
# 示例: 如果要显示X:100~-1000, Y:700~100
display_extent = [-2200, 2200, -2200, 2200]  # 注意: x_min > x_max, y_min > y_max

# 等高线参数
contour_levels = [0.9]  # 等高线强度级别（百分比）
contour_colors = ["cyan", "yellow", "red"]  # 等高线颜色
contour_linewidths = [2, 2.5, 3]  # 等高线线宽
contour_alpha = 0.8  # 等高线透明度

# 输出参数
output_dir = None  # 输出目录
save_figure = None  # 是否保存图像
dpi = 300  # 图像DPI


# ============================== 辅助函数 ==============================
def get_sun_center_and_radius(header):
    """从FITS头文件中获取太阳中心坐标和半径"""
    try:
        # 获取太阳中心像素位置
        crpix1 = header.get("CRPIX1", 0)
        crpix2 = header.get("CRPIX2", 0)

        # 获取太阳中心坐标（角秒）
        crval1 = header.get("CRVAL1", 0)
        crval2 = header.get("CRVAL2", 0)

        # 获取像素比例
        cdelt1 = header.get("CDELT1", 1)
        cdelt2 = header.get("CDELT2", 1)

        # 获取太阳半径
        if "RSUN_OBS" in header:
            rsun_obs = header["RSUN_OBS"]  # 角秒
        elif "R_SUN" in header and "CDELT1" in header:
            # 如果半径是像素单位，转换为角秒
            rsun_obs = abs(header["R_SUN"] * header["CDELT1"])
        else:
            rsun_obs = 960.0  # 默认值

        return crpix1, crpix2, crval1, crval2, cdelt1, cdelt2, rsun_obs
    except Exception as e:
        print(f"获取太阳信息时出错: {e}")
        return 0, 0, 0, 0, 1, 1, 960.0


def calculate_image_extent(data_shape, crpix1, crpix2, crval1, crval2, cdelt1, cdelt2):
    """计算图像的完整范围（角秒）"""
    nx, ny = data_shape[1], data_shape[0]

    # 计算每个像素的角秒坐标
    # 像素索引从1开始，所以第一个像素的位置是 (1 - crpix1) * cdelt1 + crval1
    x_min = crval1 + (1 - crpix1) * cdelt1
    x_max = crval1 + (nx - crpix1) * cdelt1
    y_min = crval2 + (1 - crpix2) * cdelt2
    y_max = crval2 + (ny - crpix2) * cdelt2

    # 确保正确的顺序（x从左到右，y从下到上）
    if cdelt1 > 0:
        x_extent = [x_min, x_max]
    else:
        x_extent = [x_max, x_min]

    if cdelt2 > 0:
        y_extent = [y_min, y_max]
    else:
        y_extent = [y_max, y_min]

    return x_extent, y_extent


def get_pixel_coordinates(arcsec_x, arcsec_y, crpix, crval, cdelt):
    """将角秒坐标转换为像素坐标"""
    pix_x = crpix[0] + (arcsec_x - crval[0]) / cdelt[0]
    pix_y = crpix[1] + (arcsec_y - crval[1]) / cdelt[1]
    return int(pix_x), int(pix_y)


def smooth_radio_data(data, sigma=1.0):
    """平滑射电数据，用于更好的等高线显示"""
    # 移除NaN和Inf
    clean_data = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)

    # 应用高斯平滑
    if sigma > 0:
        try:
            from scipy.ndimage import gaussian_filter

            smoothed = gaussian_filter(clean_data, sigma=sigma)
        except ImportError:
            print("  scipy不可用，跳过平滑处理")
            smoothed = clean_data
    else:
        smoothed = clean_data

    return smoothed


def plot_aia_image_simple(ax, aia_data, extent, title="AIA 94Å Image"):
    """简化版的AIA图像绘制"""
    # 检查颜色映射是否存在
    try:
        plt.cm.get_cmap(aia_cmap)
        cmap_to_use = aia_cmap
    except Exception:
        cmap_to_use = "hot"
        print(f"  警告: 颜色映射 '{aia_cmap}' 不存在，使用 'hot' 替代")

    im = ax.imshow(
        aia_data,
        extent=extent,
        origin="lower",
        cmap=cmap_to_use,
        norm=aia_norm,
        aspect="equal",
    )
    ax.set_title(title, fontsize=14)
    ax.set_xlabel("Solar-X (arcsec)", fontsize=12)
    ax.set_ylabel("Solar-Y (arcsec)", fontsize=12)

    # 添加网格
    ax.grid(True, alpha=0.3, linestyle=":", color="gray")

    return im


def get_display_extent(display_extent_param):
    """处理显示范围参数，确保正确的坐标顺序"""
    x_min, x_max, y_min, y_max = display_extent_param

    # 确保x_min < x_max, y_min < y_max
    if x_min > x_max:
        x_min, x_max = x_max, x_min
    if y_min > y_max:
        y_min, y_max = y_max, y_min

    return [x_min, x_max, y_min, y_max]


# ============================== 主程序 ==============================
def main():
    print("开始处理图像投影...")
    start_time = time.time()

    # 创建输出目录
    if save_figure and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 处理显示范围
    final_display_extent = get_display_extent(display_extent)
    print(
        f"显示范围: X=[{final_display_extent[0]:.0f}, {final_display_extent[1]:.0f}], "
        f"Y=[{final_display_extent[2]:.0f}, {final_display_extent[3]:.0f}] arcsec"
    )

    # ==================== 1. 处理AIA图像 ====================
    print("\n1. 处理AIA图像...")
    try:
        # 读取AIA图像
        aia_map = sunpy.map.Map(aia_file)

        # 归一化处理：除以曝光时间
        if hasattr(aia_map, "exposure_time") and aia_map.exposure_time is not None:
            normalized_data = aia_map.data / aia_map.exposure_time
            aia_map = sunpy.map.Map(normalized_data, aia_map.meta)
            print(f"  AIA图像已归一化，曝光时间: {aia_map.exposure_time}")

        # 获取AIA图像的太阳信息
        aia_header = aia_map.meta
        (
            aia_crpix1,
            aia_crpix2,
            aia_crval1,
            aia_crval2,
            aia_cdelt1,
            aia_cdelt2,
            aia_rsun,
        ) = get_sun_center_and_radius(aia_header)
        print(f"  AIA太阳半径: {aia_rsun:.1f} arcsec")
        print(f"  AIA像素比例: {aia_cdelt1:.3f} arcsec/pixel")
        print(f"  AIA图像尺寸: {aia_map.data.shape}")

        # 计算AIA图像的完整范围
        aia_x_extent, aia_y_extent = calculate_image_extent(
            aia_map.data.shape,
            aia_crpix1,
            aia_crpix2,
            aia_crval1,
            aia_crval2,
            aia_cdelt1,
            aia_cdelt2,
        )
        print(
            f"  AIA图像范围: X={aia_x_extent[0]:.0f}~{aia_x_extent[1]:.0f}, Y={aia_y_extent[0]:.0f}~{aia_y_extent[1]:.0f}"
        )

        # 完整的AIA图像范围
        aia_full_extent = [
            aia_x_extent[0],
            aia_x_extent[1],
            aia_y_extent[0],
            aia_y_extent[1],
        ]

    except Exception as e:
        print(f"处理AIA图像时出错: {e}")
        import traceback

        traceback.print_exc()
        return

    # ==================== 2. 处理射电图像 ====================
    print("\n2. 处理射电图像...")
    try:
        # 读取射电图像
        with fits.open(radio_file) as hdul:
            if len(hdul) > 1 and isinstance(hdul[1], fits.ImageHDU):
                radio_data = hdul[1].data
                radio_header = hdul[1].header
            else:
                radio_data = hdul[0].data
                radio_header = hdul[0].header

        # 数据维度处理
        if radio_data.ndim > 2:
            radio_data = radio_data.squeeze()
        if radio_data.ndim != 2:
            raise ValueError(f"射电图像数据不是2D数组，维度为: {radio_data.ndim}")

        # 获取射电图像的太阳信息
        (
            radio_crpix1,
            radio_crpix2,
            radio_crval1,
            radio_crval2,
            radio_cdelt1,
            radio_cdelt2,
            radio_rsun,
        ) = get_sun_center_and_radius(radio_header)
        print(f"  射电太阳半径: {radio_rsun:.1f} arcsec")
        print(f"  射电像素比例: {radio_cdelt1:.3f} arcsec/pixel")
        print(f"  射电图像尺寸: {radio_data.shape}")

        # 获取观测信息
        freq = radio_header.get("FREQ", 149.0)
        polar = radio_header.get("POLAR", "StokesI").strip()
        date_obs = radio_header.get("DATE-OBS", "Unknown")
        print(f"  观测频率: {freq} MHz")
        print(f"  偏振: {polar}")
        print(f"  观测时间: {date_obs}")

        # 计算射电图像的完整范围
        radio_x_extent, radio_y_extent = calculate_image_extent(
            radio_data.shape,
            radio_crpix1,
            radio_crpix2,
            radio_crval1,
            radio_crval2,
            radio_cdelt1,
            radio_cdelt2,
        )
        print(
            f"  射电图像范围: X={radio_x_extent[0]:.0f}~{radio_x_extent[1]:.0f}, Y={radio_y_extent[0]:.0f}~{radio_y_extent[1]:.0f}"
        )

        # 完整的射电图像范围
        _unused_radio_full_extent = [
            radio_x_extent[0],
            radio_x_extent[1],
            radio_y_extent[0],
            radio_y_extent[1],
        ]

        # 计算缩放因子，使射电太阳半径与AIA太阳半径匹配
        scale_factor = aia_rsun / radio_rsun
        print(f"  缩放因子: {scale_factor:.4f} (AIA半径/{radio_rsun:.1f})")

        # 平滑射电数据
        radio_data_smoothed = smooth_radio_data(radio_data, sigma=1.0)

        # 计算等高线值（基于强度百分比）
        contour_values = []  # 初始化为空列表
        if np.any(radio_data_smoothed > 0):
            # 找到正值的最小值
            positive_mask = radio_data_smoothed > 0
            if np.any(positive_mask):
                radio_min = np.nanmin(radio_data_smoothed[positive_mask])
                radio_max = np.nanmax(radio_data_smoothed)
                radio_range_val = radio_max - radio_min

                if radio_range_val > 0:
                    contour_values = [
                        radio_min + level * radio_range_val for level in contour_levels
                    ]
                    print(f"  射电强度范围: {radio_min:.2e} - {radio_max:.2e}")
                    print(f"  等高线值: {[f'{v:.2e}' for v in contour_values]}")
                else:
                    print(f"  警告: 射电强度范围为零，使用最大值: {radio_max:.2e}")
                    contour_values = [radio_max] * len(contour_levels)
            else:
                print("  警告: 射电数据没有正值")
                contour_values = [0, 0, 0]
        else:
            print("  警告: 射电数据全为零或负值")
            contour_values = [0, 0, 0]

    except Exception as e:
        print(f"处理射电图像时出错: {e}")
        import traceback

        traceback.print_exc()
        return

    # ==================== 3. 创建重叠图像 ====================
    print("\n3. 创建重叠图像...")
    try:
        # 创建图形（只创建一个子图）
        fig, ax = plt.subplots(1, 1, figsize=(12, 10))

        # 设置标题
        base_name = os.path.basename(aia_file)
        time_str = (
            base_name.split(".")[2] if len(base_name.split(".")) > 2 else base_name
        )
        fig.suptitle(
            f"AIA + Radio Overlay\nAIA: {time_str} | Radio: {date_obs} {freq}MHz {polar}",
            fontsize=16,
            fontweight="bold",
        )

        # 显示完整的AIA图像作为背景
        _unused_im = plot_aia_image_simple(
            ax, aia_map.data, aia_full_extent, "AIA + Radio Contours"
        )

        # 计算射电图像缩放后的范围
        # 缩放射电图像范围，使其太阳半径与AIA匹配
        radio_center_x = radio_crval1
        radio_center_y = radio_crval2

        # 计算缩放后的射电图像范围
        scaled_radio_x_min = (
            radio_center_x + (radio_x_extent[0] - radio_center_x) * scale_factor
        )
        scaled_radio_x_max = (
            radio_center_x + (radio_x_extent[1] - radio_center_x) * scale_factor
        )
        scaled_radio_y_min = (
            radio_center_y + (radio_y_extent[0] - radio_center_y) * scale_factor
        )
        scaled_radio_y_max = (
            radio_center_y + (radio_y_extent[1] - radio_center_y) * scale_factor
        )

        scaled_radio_extent = [
            min(scaled_radio_x_min, scaled_radio_x_max),
            max(scaled_radio_x_min, scaled_radio_x_max),
            min(scaled_radio_y_min, scaled_radio_y_max),
            max(scaled_radio_y_min, scaled_radio_y_max),
        ]

        print(
            f"  缩放后射电图像范围: X={scaled_radio_extent[0]:.0f}~{scaled_radio_extent[1]:.0f}, "
            f"Y={scaled_radio_extent[2]:.0f}~{scaled_radio_extent[3]:.0f}"
        )

        # 检查是否有等高线可绘制
        has_valid_contours = False
        if len(contour_values) > 0:
            # 检查contour_values中是否有大于0的值
            contour_values_array = np.array(contour_values)
            valid_contour_indices = np.asarray(
                np.nonzero(np.asarray(contour_values_array > 0, dtype=np.bool_))[0],
                dtype=np.intp,
            )

            if len(valid_contour_indices) > 0:
                has_valid_contours = True

                # 绘制等高线
                for i in valid_contour_indices.tolist():
                    level = contour_values[i]
                    color = contour_colors[i]
                    lw = contour_linewidths[i]

                    if level > 0:  # 再次检查确保level是正值
                        try:
                            # 创建等高线
                            contour = ax.contour(
                                radio_data_smoothed,
                                levels=[level],
                                colors=color,
                                linewidths=lw,
                                alpha=contour_alpha,
                                extent=scaled_radio_extent,
                                origin="lower",
                            )

                            # 为等高线添加标签（使用lambda函数避免格式字符串问题）
                            if i == 1:  # 只在50%等高线上添加标签
                                # 创建标签格式函数
                                def make_label(x, level=contour_levels[i]):
                                    return f"{level*100:.0f}%"

                                ax.clabel(
                                    contour, inline=True, fontsize=9, fmt=make_label
                                )
                        except Exception as e:
                            print(
                                f"  绘制等高线 {contour_levels[i]*100:.0f}% 时出错: {e}"
                            )

        if not has_valid_contours:
            print("  警告: 没有有效的等高线可绘制")

        # 添加太阳轮廓（使用AIA太阳半径）
        solar_limb = patches.Circle(
            (0, 0),
            radius=aia_rsun,
            edgecolor="cyan",
            facecolor="none",
            linewidth=2,
            linestyle="-",
            alpha=0.8,
        )
        ax.add_patch(solar_limb)

        # 设置坐标轴范围 - 使用指定的显示范围
        ax.set_xlim(final_display_extent[0], final_display_extent[1])
        ax.set_ylim(final_display_extent[2], final_display_extent[3])

        print(
            f"  最终显示范围: X=[{final_display_extent[0]:.0f}, {final_display_extent[1]:.0f}], "
            f"Y=[{final_display_extent[2]:.0f}, {final_display_extent[3]:.0f}] arcsec"
        )

        # 添加方向标记
        # 计算标记位置（基于显示范围）
        x_center = (final_display_extent[0] + final_display_extent[1]) / 2
        y_center = (final_display_extent[2] + final_display_extent[3]) / 2
        x_range = abs(final_display_extent[1] - final_display_extent[0])
        y_range = abs(final_display_extent[3] - final_display_extent[2])

        # 北方向标记
        north_x = x_center
        north_y = final_display_extent[3] - y_range * 0.05
        ax.annotate(
            "N",
            xy=(north_x, north_y),
            xytext=(north_x, north_y + y_range * 0.1),
            ha="center",
            va="bottom",
            fontsize=12,
            color="yellow",
            arrowprops=dict(arrowstyle="->", color="yellow", lw=1.5),
        )

        # 东方向标记
        east_x = final_display_extent[1] - x_range * 0.05
        east_y = y_center
        ax.annotate(
            "E",
            xy=(east_x, east_y),
            xytext=(east_x + x_range * 0.1, east_y),
            ha="left",
            va="center",
            fontsize=12,
            color="yellow",
            arrowprops=dict(arrowstyle="->", color="yellow", lw=1.5),
        )

        # 添加图例
        from matplotlib.lines import Line2D

        legend_elements = [
            Line2D(
                [0],
                [0],
                color="cyan",
                lw=2,
                linestyle="-",
                label=f'AIA Solar Limb (R={aia_rsun:.0f}")',
            ),
        ]

        # 只添加有效的等高线到图例
        if has_valid_contours:
            for i in valid_contour_indices:
                legend_elements.append(
                    Line2D(
                        [0],
                        [0],
                        color=contour_colors[i],
                        lw=contour_linewidths[i],
                        label=f"Radio {contour_levels[i]*100:.0f}% contour",
                    )
                )

        ax.legend(handles=legend_elements, loc="upper right", fontsize=9)

        # 在图像上添加显示范围信息
        range_text = f"Display: X=[{final_display_extent[0]:.0f}, {final_display_extent[1]:.0f}]\nY=[{final_display_extent[2]:.0f}, {final_display_extent[3]:.0f}] arcsec"
        ax.text(
            0.02,
            0.02,
            range_text,
            transform=ax.transAxes,
            fontsize=9,
            color="white",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.7),
        )

        # 添加太阳中心标记
        ax.scatter(
            0, 0, color="white", s=50, marker="+", linewidth=1.5, label="Solar Center"
        )

        # 调整布局
        plt.tight_layout()

        # 保存图像
        # if save_figure:
        #     output_filename = f"AIA_Radio_overlay_{time_str.replace(':', '').replace('-', '').replace('T', '_')}_range_{final_display_extent[0]:.0f}_{final_display_extent[1]:.0f}_{final_display_extent[2]:.0f}_{final_display_extent[3]:.0f}.png"
        #     output_path = os.path.join(output_dir, output_filename)
        #     plt.savefig(output_path, dpi=dpi, bbox_inches='tight')
        #     print(f"  图像已保存: {output_path}")

        # 显示图像
        plt.show()

        # 清理资源
        plt.close(fig)
        del aia_map, radio_data, radio_data_smoothed
        gc.collect()

    except Exception as e:
        print(f"创建重叠图像时出错: {e}")
        import traceback

        traceback.print_exc()

    # ==================== 完成 ====================
    total_time = time.time() - start_time
    print(f"\n处理完成！总耗时: {total_time:.2f} 秒")


# ============================== 执行主程序 ==============================
if __name__ == "__main__":
    main()
