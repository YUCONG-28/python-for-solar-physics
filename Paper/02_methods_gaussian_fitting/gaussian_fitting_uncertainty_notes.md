# Gaussian fitting uncertainty notes

- centroid_uncertainty_x 与 centroid_uncertainty_y 应区分拟合参数误差和成像系统误差。
- 若 beam 未知或散射显著，应把位置误差与 source-size 误差写成保守上界。
- 低 SNR、偏心源、背景梯度和多峰结构都会放大 centroid 偏差。
- 对论文级结果，建议同时报告 Gaussian fitted center、contour center 与两者差值。