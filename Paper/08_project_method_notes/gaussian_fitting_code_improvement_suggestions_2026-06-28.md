# Gaussian fitting 代码改进建议

## 0. 2026-06-28 增量依据

- 新增核心方法论文：`Sizes and Shapes of Sources in Solar Metric Radio Bursts`，强调 2D Gaussian profiles、elliptical half-maximum contours、deconvolved source sizes、仪器/电离层修正和各向异性散射。
- 修正核心方法论文：`LOFAR observations of radio burst source sizes and scattering in the solar corona`，强调 visibility-domain elliptical Gaussian 可避免图像域 PSF 去卷积伪影。
- 对当前项目的直接含义：DART / DRAT 若缺少可靠 beam / PSF / visibility 信息，应把 FWHM 写成 `observed apparent size`，暂不写成 intrinsic source size。

## 1. 当前项目可能已有功能

- 基于射电图像选择 ROI。
- 估计 source center、source size、频率漂移率和 Newkirk 高度。
- 生成 AIA / 射电联合图和动态频谱选点结果。

## 2. 当前可能存在的问题

- Gaussian center 是否偏离真实源区。
- ROI 是否过大，导致背景主导拟合。
- FWHM 是否异常放大。
- 是否存在多峰源、低 SNR 拟合和低频分辨率退化。
- 149 MHz 前几个时间帧是否没有真实 burst。
- Gaussian center 与 contour center 是否一致。

## 3. 建议新增输出字段

- fit_success, fit_reason, snr, noise_sigma
- gaussian_x_arcsec, gaussian_y_arcsec
- contour_x_arcsec, contour_y_arcsec
- delta_r_arcsec, fwhm_major_arcsec, fwhm_minor_arcsec
- ellipticity, deconvolution_status, beam_or_psf_reference
- morphology_frequency_trend, propagation_warning
- is_multi_peak, is_overlarge_fwhm, is_low_snr, fit_quality_flag

## 4. 建议新增诊断图

- 原始射电图 + contour + Gaussian ellipse
- Gaussian center 与 contour center 对比
- residual map
- FWHM 随时间/频率变化
- SNR 随时间/频率变化
- centroid offset 随时间/频率变化
- Gaussian center trajectory
- Newkirk height vs frequency
- Gaussian center height comparison
- drift-rate selected spectrogram with saved selected lines

## 5. 建议新增质量控制 flag

- is_edge_source
- is_multi_peak
- is_overlarge_fwhm
- is_low_snr
- is_bad_fit

## 6. 是否建议当前阶段修改算法

- 当前建议：只整理文献、增加诊断输出、增加背景扣除开关、增加 contour center 对比。
- 暂不建议立即修改核心拟合模型。
- 当诊断输出确认系统性偏差后，再进入算法改进阶段。
