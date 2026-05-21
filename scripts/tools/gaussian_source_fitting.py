#!/usr/bin/env python3
# 模块用途: 拟合一维/二维高斯模型，估计源区位置、尺寸和强度。
# 主要输入: 曲线、图像或射电源强度矩阵。
# 主要输出/运行说明: 输出高斯拟合参数，可供射电源形态分析复用。

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import curve_fit

IntArray = NDArray[np.intp]


# ------------------------------------------------------------
# 二维椭圆高斯模型（支持旋转）
# ------------------------------------------------------------
def elliptical_gaussian_2d(xy, A, x0, y0, sigma_x, sigma_y, theta):
    """
    二维椭圆高斯函数
    参数：
        A      : 峰值振幅
        x0, y0 : 中心位置（质心）
        sigma_x, sigma_y : 沿长轴和短轴的 rms 宽度
        theta  : 长轴相对于 x 轴的角度（弧度）
    返回：对应坐标的高斯值
    """
    x, y = xy
    cos_t = np.cos(theta)
    sin_t = np.sin(theta)
    x_rot = (x - x0) * cos_t + (y - y0) * sin_t
    y_rot = -(x - x0) * sin_t + (y - y0) * cos_t
    exponent = (x_rot**2) / (2 * sigma_x**2) + (y_rot**2) / (2 * sigma_y**2)
    return A * np.exp(-exponent)


def _unravel_2d_index(
    flat_index: int | np.integer, shape: tuple[int, ...]
) -> tuple[int, int]:
    coords = np.asarray(np.unravel_index(int(flat_index), shape), dtype=np.intp)
    return int(coords[0]), int(coords[1])


def _true_indices(mask: np.ndarray) -> IntArray:
    mask_bool = np.asarray(mask, dtype=np.bool_)
    return np.asarray(np.nonzero(mask_bool)[0], dtype=np.intp)


# ------------------------------------------------------------
# 对二维图像进行椭圆高斯拟合，返回中心坐标等参数
# ------------------------------------------------------------
def fit_elliptical_gaussian(data, x, y, initial_guess=None):
    """
    拟合二维椭圆高斯到图像数据

    输入：
        data : 2D numpy数组，图像强度
        x    : 1D numpy数组，x坐标（长度 = data.shape[1]）
        y    : 1D numpy数组，y坐标（长度 = data.shape[0]）
        initial_guess : 可选，初始参数 (A, x0, y0, sigma_x, sigma_y, theta)

    输出：
        popt : 拟合参数 [A, x0, y0, sigma_x, sigma_y, theta]
        pcov : 协方差矩阵
    """
    X, Y = np.meshgrid(x, y)
    x_flat = X.ravel()
    y_flat = Y.ravel()
    data_flat = data.ravel()

    # 如果没有提供初始猜测，自动估计
    if initial_guess is None:
        max_y, max_x = _unravel_2d_index(int(np.argmax(data)), data.shape)
        init_x0 = x[max_x]
        init_y0 = y[max_y]
        init_A = np.max(data)

        # 粗略估计 sigma（通过半高宽）
        half_max = init_A / 2.0
        # x方向
        row_max = data[max_y, :]
        indices = _true_indices(row_max >= half_max)
        if len(indices) > 1:
            init_sigma_x = (x[indices[-1]] - x[indices[0]]) / (2.355)  # FWHM -> sigma
        else:
            init_sigma_x = (x[-1] - x[0]) / 10.0
        # y方向
        col_max = data[:, max_x]
        indices_y = _true_indices(col_max >= half_max)
        if len(indices_y) > 1:
            init_sigma_y = (y[indices_y[-1]] - y[indices_y[0]]) / (2.355)
        else:
            init_sigma_y = (y[-1] - y[0]) / 10.0
        init_theta = 0.0
        initial_guess = (
            init_A,
            init_x0,
            init_y0,
            init_sigma_x,
            init_sigma_y,
            init_theta,
        )

    # 参数边界
    bounds = (
        [0, -np.inf, -np.inf, 1e-3, 1e-3, -np.pi / 2],
        [np.inf, np.inf, np.inf, np.inf, np.inf, np.pi / 2],
    )

    popt, pcov = curve_fit(
        elliptical_gaussian_2d,
        (x_flat, y_flat),
        data_flat,
        p0=initial_guess,
        bounds=bounds,
        maxfev=5000,
    )
    return popt, pcov
