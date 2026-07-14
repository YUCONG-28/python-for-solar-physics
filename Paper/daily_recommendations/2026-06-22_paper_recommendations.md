# 2026-06-22 文献检索日报

## 1. 今日检索关键词

今日沿用 `config/paper_search_config.json` 中的四组主关键词，并对 2026-06-18 以后更新的论文元数据做增量核验。

- spikes topping type III / spike-like toppings / solar radio spikes type III bursts
- type III radio burst source centroid / imaging spectroscopy / source trajectory
- solar radio source Gaussian fitting / 2D elliptical Gaussian / CLEAN beam / centroid uncertainty
- AIA EUV radio type III burst / Newkirk density model / frequency drift rate / source motion

检索与核验来源：

- arXiv API，核验日期：2026-06-22；核验条目：arXiv:2605.20937、arXiv:2605.31450，并检查 `solar radio type III`、`Gaussian solar radio`、`spike-like type III`、`Newkirk type III` 的最新条目。
- Crossref DOI metadata，核验日期：2026-06-22；核验 DOI：10.1051/0004-6361/202660446、10.3847/1538-4357/ae7429、10.1038/s41467-026-74137-2。
- A&A / IOP / Nature DOI 页面作为正式出版入口；A&A 网页抓取受限，因此采用 Crossref + DOI 跳转元数据，不把不可访问全文细节写成新增事实。

结论：今日没有发现比已有文献更相关的全新 A/B 级论文；今日有效增量是 2 篇已纳入核心文献的正式出版元数据更新。

## 2. 今日新增重点论文总览

| 序号 | 论文 | 年份 | 方向 | 相关性 | 推荐等级 | DOI/arXiv/ADS | 本地记录 |
|---|---|---|---|---|---|---|---|
| 1 | Frequency-time-resolved Imaging Spectroscopy of Fine Structures in a Solar Radio Noise Storm | 2026 | Gaussian fitting / radio source centroid | A | high | DOI: 10.3847/1538-4357/ae7429；arXiv:2605.31450 | `paper_master_index.csv`；`gaussian_fitting_paper_index.csv` |
| 2 | Type-III solar radio bursts with spike-like toppings | 2026 | spikes topping type III / type III burst | A | high | DOI: 10.1051/0004-6361/202660446；arXiv:2605.20937 | `paper_master_index.csv` |

说明：两条均为“已收录核心论文的正式出版状态更新”，不是今日全新主题论文。今日不新增低相关 C/D 级论文到重点推荐。

## 3. 与 spikes topping type III / type III burst 相关论文

### Type-III solar radio bursts with spike-like toppings

- 年份：2026
- 期刊/来源：Astronomy & Astrophysics；Crossref 核验日期：2026-06-22；published-online：2026-06-19；volume 710，article A272。
- DOI / arXiv：10.1051/0004-6361/202660446；arXiv:2605.20937。
- 今日状态：由 arXiv 预印本状态更新为 A&A 正式论文。
- 相关性：A。
- 简述：统计 spike-like toppings 与 III 型暴主体的时间差、频率差、形态分类和偏振特征，是当前项目最直接的主题论文。
- 对当前项目的价值：可作为 spike topping 事件定义、统计边界和讨论部分的核心对照文献。

## 4. 与 solar radio spikes / fine structures 相关论文

### Frequency-time-resolved Imaging Spectroscopy of Fine Structures in a Solar Radio Noise Storm

- 年份：2026
- 期刊/来源：The Astrophysical Journal；Crossref 核验日期：2026-06-22；published-online：2026-06-19；volume 1005，issue 1。
- DOI / arXiv：10.3847/1538-4357/ae7429；arXiv:2605.31450。
- 今日状态：由 arXiv accepted 状态更新为 ApJ 正式论文。
- 相关性：A。
- 简述：LOFAR 30-40 MHz 噪声暴精细结构研究，使用 CLEAN 后图像的 2D elliptical Gaussian 拟合，输出 centroid、FWHM major/minor、面积和不确定度。
- 对当前项目的价值：直接补强 DART / DRAT 图像的 Gaussian center、FWHM、beam/PSF、centroid uncertainty 和 multi-peak 诊断方案。

## 5. 与 AIA / EUV / HMI / radio 联合分析相关论文

今日没有发现比已有文献更相关的全新 A/B 级 AIA / EUV / HMI / radio 联合分析论文。

仍建议继续把以下既有核心文献作为联合分析框架：

- `Multiwavelength Multipoint Observations of the October 28, 2021 Type III Radio Burst`：AIA/HMI/X-ray/radio 与多航天器证据链模板。
- `Low Altitude Solar Magnetic Reconnection, Type III Solar Radio Bursts, and X-ray Emissions`：低高度磁重联、X-ray 与 type III 射电暴联合分析模板。

## 6. 与 Gaussian fitting / radio source centroid 相关论文

必须重点回答：

- 该论文如何定义 radio source center？
- 是否使用 2D Gaussian / elliptical Gaussian？
- 是否讨论 FWHM / source size？
- 是否处理 beam deconvolution？
- 是否讨论 centroid uncertainty？
- 是否适合当前 DART / DRAT 射电源图像？

### Frequency-time-resolved Imaging Spectroscopy of Fine Structures in a Solar Radio Noise Storm

- 该论文如何定义 radio source center：以 clean LOFAR maps 的 2D elliptical Gaussian 拟合中心 `x0/y0` 作为 centroid，并随时间/频率追踪。
- 是否使用 2D Gaussian / elliptical Gaussian：是；图像源区采用 2D elliptical Gaussian；频谱 drift profile 还使用 Gaussian + background + linear continuum。
- 是否讨论 FWHM / source size：是；由 Gaussian widths 得到 FWHM major/minor 和面积，并区分 continuum 与 embedded fine structures。
- 是否处理 beam deconvolution：是；使用 CLEAN 图像，并用 Tau A 估计有效 PSF，还考虑电离层折射修正。
- 是否讨论 centroid uncertainty：是；采用 Condon-style uncertainty，并用 faint beams 估计 flux/noise。
- 是否适合当前 DART / DRAT 射电源图像：高度适合。建议直接借鉴 `centroid_uncertainty`、`fwhm_major/minor`、`beam_status`、`continuum_reference_center`、`is_centroid_jump`、`is_multi_source_candidate` 等字段。

今日没有发现新的 Gaussian fitting 方法论文；这篇 ApJ 正式出版元数据更新后，仍是当前方法库最值得精读的 Gaussian/source-size 参考之一。

## 7. 与 Newkirk density model / frequency drift rate / source motion 相关论文

今日没有新增 A/B 级 Newkirk / drift-rate 论文。

本轮核验仍支持既有判断：

- 不应把 Gaussian center motion speed、Newkirk height-derived speed 和 dynamic-spectrum drift-rate-derived speed 简单等同。
- `Type-III solar radio bursts with spike-like toppings` 给出 spike-like clusters 的时间/频率偏移和漂移形态边界，可用于定义 topping 与 type III 主体的相对位置。
- `Frequency-time-resolved Imaging Spectroscopy...` 强化了 apparent source size、centroid uncertainty 与传播/散射因素的讨论，适合约束 Gaussian center 与 Newkirk 高度比较的物理解释。

## 8. 今日最值得精读的 3-5 篇论文

1. `Frequency-time-resolved Imaging Spectroscopy of Fine Structures in a Solar Radio Noise Storm`：优先精读方法部分，尤其是 CLEAN map、2D elliptical Gaussian、FWHM、PSF 与 centroid uncertainty。
2. `Type-III solar radio bursts with spike-like toppings`：优先精读事件定义、时间/频率偏移统计、形态分类和偏振结果。
3. `Frequency-Distance Structure of Solar Radio Sources Observed by LOFAR`：继续作为 Gaussian center、峰值中心、阈值质心三者对比的关键方法文献。
4. `A decade of solar Type III radio bursts observed by the Nancay Radioheliograph 1998-2008`：继续作为 2D elliptical Gaussian、FWHM 与 beam deconvolution 的统计参考。

## 9. 对当前项目的具体建议

- Gaussian fitting 参数：仍建议复核 `max_fwhm_arcsec = 1800.0` 是否过宽；过宽会增加无物理意义大椭圆风险。
- ROI / mask / threshold：建议缩紧 ROI 或使用阈值 mask，避免背景主导拟合。
- 背景扣除开关：建议加入 `none`、`constant`、`tilted_plane` 三种模式，至少先输出诊断，不急于修改核心模型。
- Gaussian center 与 contour center：必须逐频逐时保存差值；`delta_r_arcsec` 过大时不应用该帧做速度估计。
- drift 选取频谱图：建议保存 selected spectrogram、selected lines、selected_points.csv 和 drift-fit residuals。
- Newkirk 高度比较：建议从“空间外推”改为 `height-frequency` 与 `height-time` 两条证据链，并明确其只是 density-model height。
- README / 方法综述：已通过今天索引刷新补充正式 DOI；后续建议把 ApJ/A&A 正式引用替换进论文草稿参考文献。

## 10. 今日更新文件列表

- `daily_recommendations/2026-06-22_paper_recommendations.md`
- `paper_master_index.csv`
- `02_methods_gaussian_fitting/gaussian_fitting_literature_daily/2026-06-22_gaussian_fitting_papers.md`
- `08_project_method_notes/gaussian_fitting_code_improvement_suggestions_2026-06-22.md`
- `organization_log_2026-06-22.md`
- `.paper_recommendation_state.json`
- `data/seed_papers.json`

