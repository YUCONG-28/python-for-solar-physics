# Gaussian fitting 方法综述

## 当前纳入的核心文献

- Imaging spectroscopy reveals spike-like repeating radio burst pairs in the solar corona
- Magnetic Field Geometry and Anisotropic Scattering Effects on Solar Radio Burst Observations
- Sizes and Shapes of Solar Type III Radio Burst Sources in LOFAR Tied-Array Imaging and the Role of Scattering
- Sub-second Time Evolution of Type III Solar Radio Burst Sources at Fundamental and Harmonic Frequencies
- Frequency-Distance Structure of Solar Radio Sources Observed by LOFAR
- On the Source Position and Duration of a Solar Type III Radio Burst Observed by LOFAR
- The apparent positions of solar radio sources observed by the Low Frequency Array
- A decade of solar Type III radio bursts observed by the Nancay Radioheliograph 1998-2008
- Electron Beam Propagation and Radio-Wave Scattering in the Inner Heliosphere using Five Spacecraft
- A Review of Recent Solar Type III Imaging Spectroscopy
- Type III Solar Radio Burst Source Region Splitting Due to a Quasi-Separatrix Layer

## 5.1 图像输入与坐标

- 射电图像输入应保留 FITS 原始头信息，优先记录 RA / Dec 与 helioprojective coordinates 之间的转换链条。
- 多频率射电图像不应直接比较，必须先检查 pixel-to-world transformation、观测时刻和太阳半径定义。
- 叠加到 AIA 背景图时，需要明确射电太阳半径与 EUV 太阳半径可能不一致，并记录任何经验缩放。

## 5.2 背景扣除

- 优先支持 pre-burst background subtraction、quiet-Sun background、running median / temporal median 三类背景估计。
- 当前项目建议把背景作为可切换项，至少保留 Gaussian + constant background 和 Gaussian + tilted plane background。
- 背景扣除会直接影响 centroid，弱源、扩展源和偏心源尤其敏感。

## 5.3 拟合模型

默认模型：

    I(x, y) = A exp[-0.5 * Q(x, y)] + B
    Q = (x' / sigma_x)^2 + (y' / sigma_y)^2

带倾斜背景模型：

    I(x, y) = Gaussian(x, y) + B0 + Bx x + By y

- 当前项目默认优先使用单源 elliptical Gaussian。
- 只有在 ROI 明显多峰且文献支持时，才考虑多源模型。

## 5.4 初始参数选择

- amplitude 初值可取 ROI 最大值减边缘背景。
- x0, y0 初值可取最大亮度像素或 intensity-weighted centroid。
- sigma 初值可由半高宽区域估计。
- theta 初值可设为 0，或由二阶矩估计。
- background 初值建议取 ROI 边缘中位数。

## 5.5 拟合约束

    A > 0
    sigma_x > 0
    sigma_y > 0
    centroid 位于 ROI 内
    background 不主导总强度

- 需要重点复核 max_fwhm_arcsec = 1800.0 是否过宽。

## 5.6 拟合质量控制

- 建议输出 fit_success, fit_reason, snr, noise_sigma, reduced_chi_square, residual_rms。
- 噪声优先用 sigma_noise ≈ 1.4826 × MAD。
- 需要同步输出 is_edge_source, is_multi_peak, is_overlarge_fwhm, is_low_snr, is_bad_fit。

## 5.7 centroid 可靠性验证

- 必须并行记录 Gaussian fitted center 与 contour center。
- 推荐输出 gaussian_x_arcsec, gaussian_y_arcsec, contour_x_arcsec, contour_y_arcsec, delta_r_arcsec。
- 如果 Gaussian fitted center 与 contour center 偏差过大，应优先检查背景项、ROI、阈值与多峰结构。

## 5.8 beam / PSF / 分辨率修正

    FWHM_intrinsic^2 ≈ FWHM_observed^2 - FWHM_beam^2

- 如果缺少可靠 beam 信息，当前 source size 应写成 observed apparent size，而不是 intrinsic source size。
- 对 major / minor axis 不同的 beam，应分别去卷积。

## 5.9 与 Newkirk 高度和频率漂移率结合

- 每个频率对应一个 Gaussian center，并通过 Newkirk density model 转换成理论高度。
- 对比 spatial trajectory、height-frequency、height-time 和 dynamic-spectrum drift rate。
- 不同速度量含义不同，不能把 Gaussian center motion speed、Newkirk height-derived speed、dynamic-spectrum drift-rate-derived speed 简单等同。