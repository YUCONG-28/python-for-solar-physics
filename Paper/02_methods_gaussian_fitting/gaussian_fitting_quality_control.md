# Gaussian fitting quality control

- 噪声估计：优先使用 1.4826 × MAD，记录估计区域。
- SNR 过低、FWHM 过大、ROI 触边、多峰源和残差结构异常时都应触发 flag。
- 低频图像分辨率更差，若 Gaussian center 与 contour center 偏差显著，不应用于速度拟合。
- 建议每次运行保存一份 fit_reason 汇总，便于筛掉不稳定时间帧。