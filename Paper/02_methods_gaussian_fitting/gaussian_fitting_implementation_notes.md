# Gaussian fitting implementation notes

- 默认优先实现单源 elliptical Gaussian，并保留常数背景项。
- 当 ROI 存在明显梯度时，切换到 Gaussian + tilted plane background。
- 先输出 observed centroid 与 observed apparent size，再在 beam 信息可靠时做去卷积。
- 每个拟合结果应保留原始 ROI、拟合图、残差图和参数协方差矩阵。