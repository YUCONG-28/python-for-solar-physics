# 2026-06-22 Gaussian fitting 文献更新

## 今日结论

今日没有发现全新的 A/B 级 Gaussian fitting / radio source centroid 方法论文。

今日有效更新是：`Frequency-time-resolved Imaging Spectroscopy of Fine Structures in a Solar Radio Noise Storm` 已由 arXiv accepted 状态更新为 The Astrophysical Journal 正式论文，DOI 为 `10.3847/1538-4357/ae7429`。Crossref 核验日期：2026-06-22；published-online：2026-06-19。

## 今日重点方法条目

### Frequency-time-resolved Imaging Spectroscopy of Fine Structures in a Solar Radio Noise Storm

- 年份：2026
- 期刊/来源：The Astrophysical Journal
- DOI / arXiv：10.3847/1538-4357/ae7429；arXiv:2605.31450
- 仪器：LOFAR
- 频率范围：30-40 MHz
- 目标事件：noise storm continuum、type I bursts、S-bursts、spikes
- 相关性：A
- 推荐等级：high

## Gaussian fitting 信息

- radio source center：以 clean LOFAR maps 的 2D elliptical Gaussian 拟合中心 `x0/y0` 作为 centroid，并随时间/频率追踪。
- Gaussian 模型：图像源区使用 2D elliptical Gaussian；频谱 drift profile 使用 Gaussian + background + linear continuum。
- source size / FWHM：由 Gaussian widths 得到 FWHM major/minor 和 FWHM area。
- beam / PSF：dirty maps 经 CLEAN；使用 Tau A 估计有效 PSF，并考虑频率相关电离层折射修正。
- centroid uncertainty：采用 Condon-style formulae；用 faint beams 估计 flux/noise。
- 质量控制：CLEAN/PSF 检查、ionospheric correction、continuum-vs-fine-structure 比较、FWHM uncertainty、multi-source centroid-jump flag。

## 对 DART / DRAT 的具体价值

- 适合直接借鉴到当前 DART / DRAT 的 Gaussian center、FWHM、residual、centroid uncertainty 和 multi-peak 诊断输出。
- 建议新增或优先检查：`centroid_uncertainty_x/y`、`fwhm_major/minor`、`beam_status`、`continuum_reference_center`、`is_centroid_jump`、`is_multi_source_candidate`。
- 如果 DART / DRAT 暂无可靠 beam 信息，source size 应写成 `observed apparent size`，不应写成 intrinsic source size。

## 今日未纳入原因记录

- arXiv:2606.12741 `Plasma frequency waves in Earth's electron foreshock` 涉及 plasma-frequency waves 与 Type III source-region 类比，但对象是地球 foreshock，不是太阳射电成像或 Gaussian source-centroid 方法；本轮判为 C/D 背景，不纳入重点推荐。

