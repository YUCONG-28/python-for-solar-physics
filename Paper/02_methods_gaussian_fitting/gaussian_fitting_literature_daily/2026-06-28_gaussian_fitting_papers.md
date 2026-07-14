# 2026-06-28 Gaussian fitting 文献更新

## 今日结论

- 新增 Gaussian / source-size 方法论文：1 篇。
- 重要方法条目元数据修正：1 篇。
- 今日没有发现新的、比现有 LOFAR / NRH 核心文献更直接的 DART / DRAT Gaussian center 论文。

## 1. 今日新增方法论文

### Sizes and Shapes of Sources in Solar Metric Radio Bursts

- 年份：2022
- 来源：The Astrophysical Journal
- DOI / arXiv：`10.3847/1538-4357/ac3bb7`; `2111.07777`
- 推荐等级：A / high
- 仪器：LOFAR
- 目标：solar metric radio burst sources

方法价值：

- 使用 2D Gaussian profiles 近似射电源强度分布。
- 使用 elliptical half-maximum contours 表征源区形状。
- 讨论 source sizes、ellipticities 和 deconvolved sizes。
- 通过已知源观测估计仪器与电离层效应，再解释源区尺寸。
- 将低频源区尺寸和椭圆率变化与各向异性散射联系起来。

对 DART / DRAT 的直接建议：

- 输出 `ellipticity`，不要只输出 `fwhm_major_arcsec` 和 `fwhm_minor_arcsec`。
- 增加 `deconvolution_status` 或 `fwhm_deconvolution_status`，明确尺寸是 observed 还是 deconvolved。
- 增加 `beam_or_psf_reference`，记录是否有可用 beam / PSF 信息。
- 增加 `morphology_frequency_trend`，检查源区尺寸和椭圆率是否随频率系统变化。
- 低频大 FWHM 应优先写成 apparent morphology，不应直接等同 intrinsic source size。

## 2. 今日修正的方法条目

### LOFAR observations of radio burst source sizes and scattering in the solar corona

- arXiv：`2011.13735`
- DOI：`10.1051/0004-6361/202038518`
- 修正内容：旧索引中题名、作者、期刊状态不够准确，今日已修正为 A&A 正式论文记录。

方法价值：

- 直接在 LOFAR visibilities 上使用 elliptical Gaussian 拟合 Type IIIb 源区。
- 估计 apparent source position 和 FWHM major/minor。
- 规避图像域 PSF 去卷积可能引入的 source-size / shape 伪影。
- 强调散射与折射会显著影响观测到的源区尺寸和位置。

对 DART / DRAT 的直接建议：

- 当前若没有 visibility-domain 拟合和可靠 beam 信息，应保守使用 `observed apparent size`。
- Gaussian center 与 contour center 偏差较大时，不应只调大 FWHM 上限；需要检查散射、折射、ROI 和多峰结构。
- 若后续可获得 beam/PSF 约束，再考虑从 observed size 过渡到 deconvolved size。

## 3. 今日未新增但仍应保留的核心方法链

- `Frequency-time-resolved Imaging Spectroscopy of Fine Structures in a Solar Radio Noise Storm`：CLEAN map + 2D elliptical Gaussian + centroid uncertainty + drift-rate。
- `Frequency-Distance Structure of Solar Radio Sources Observed by LOFAR`：比较 intensity maximum、threshold center-of-mass 和 2D elliptical Gaussian center。
- `A decade of solar Type III radio bursts observed by the Nancay Radioheliograph 1998-2008`：NRH 2D elliptical Gaussian、FWHM major/minor 和 beam deconvolution。

## 4. 对当前代码建议的增量

- 今日只建议增加诊断输出和质量控制字段，暂不修改核心拟合模型。
- 最优先字段：`ellipticity`, `deconvolution_status`, `beam_or_psf_reference`, `morphology_frequency_trend`, `propagation_warning`。
- 继续保留 Gaussian center 与 contour center 的逐频逐时对比；该对比是判断中心可靠性的关键证据。
