# 2026-07-05 Gaussian fitting 文献更新

## 今日结论

- 新增 Gaussian / source-centroid 方法参考：1 篇。
- 新增等级：B；方法可借鉴，但科学对象不是当前项目的 type III spike topping。
- 今日没有发现新的、比现有 LOFAR / NRH 核心文献更直接的 A 级 DART / DRAT Gaussian center 论文。
- `Radio Diagnostics of Particle Acceleration in Solar Flares with SKAO Observations` 只进入总索引，不进入 Gaussian 方法库；它是观测能力综述，不提供当前源区拟合公式。

## 1. 今日新增方法论文

### Comprehensive study of solar type II radio bursts and the properties of the associated shock waves

- 年份：2026。
- 来源：arXiv preprint；v4 更新日期 2026-06-29。
- DOI / arXiv：无可信 Crossref DOI；arXiv `2512.21846`。
- 推荐等级：B / medium。
- 仪器：Nancay Radioheliograph；AIA/SUVI/STEREO；ORFEES/e-CALLISTO/NDA。
- 目标：type II bursts and herringbones。

方法价值：

- 在 NRH Stokes I 图像中用 2D Gaussian 求 radio source centroid 和 peak intensity。
- 将 radio contours 叠加到 AIA running-difference 图像上。
- 使用电子密度等值面将平面源中心去投影到三维位置。
- 将 herringbone dynamic-spectrum drift rates 转换为 electron-beam speed / energy 估计。

对 DART / DRAT 的直接建议：

- 可借鉴其证据链组织方式：radio centroid、AIA overlay、density-model configuration、dynamic-spectrum selected points 和速度估计应一起保存。
- 该文不是 type III spike topping 论文，不能迁移 shock-streamer 物理结论。
- 该文不提供当前项目可直接采用的 beam 去卷积或 intrinsic source size 方案。
- 当前项目仍应把没有可靠 beam 信息的 DART / DRAT 尺寸称为 observed apparent size。

## 2. 今日未纳入 Gaussian 方法库的新增背景论文

### Radio Diagnostics of Particle Acceleration in Solar Flares with SKAO Observations

- 年份：2026。
- 来源：AASKAII 2026 章节；arXiv `2606.28782`。
- 纳入位置：总索引和日报背景部分。
- 未纳入 Gaussian 方法库的原因：该文讨论 SKAO 未来高时空分辨成像、偏振和 EUV/X-ray 协同诊断，不给出当前 DART / DRAT 可执行的源区拟合模型、中心定义、FWHM 或 beam 修正流程。

## 3. 对当前代码建议的增量

- 暂不修改核心拟合模型。
- 优先补齐诊断输出：`fit_quality_flag`、`density_model_name`、`density_model_parameters`、`drift_selected_points_path`、`aia_overlay_path`、`centroid_deprojection_status`。
- 继续把 Gaussian center、contour center、Newkirk/MAS 等 density-model height 和 dynamic-spectrum drift-rate speed 分开记录。
- 对 149 MHz 前几个低信噪时间帧，应先看 burst 是否真实存在，再决定是否纳入速度估计。

## 4. 今日保留的核心方法链

- `Frequency-time-resolved Imaging Spectroscopy of Fine Structures in a Solar Radio Noise Storm`：CLEAN map + 2D elliptical Gaussian + centroid uncertainty + drift-rate。
- `Frequency-Distance Structure of Solar Radio Sources Observed by LOFAR`：比较 intensity maximum、threshold center-of-mass 和 2D elliptical Gaussian center。
- `A decade of solar Type III radio bursts observed by the Nancay Radioheliograph 1998-2008`：NRH 2D elliptical Gaussian、FWHM major/minor 和 beam deconvolution。
- `LOFAR observations of radio burst source sizes and scattering in the solar corona`：visibility-domain elliptical Gaussian 和 observed apparent size / scattering 解释。

