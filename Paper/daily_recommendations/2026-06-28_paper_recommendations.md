# 2026-06-28 文献检索日报

## 1. 今日检索关键词

本次沿用 `config/paper_search_config.json` 中的完整关键词组，并实际核查了以下增量入口：

- arXiv: `all:"solar radio burst" AND all:"type III"`
- arXiv: `all:"solar radio" AND all:"Gaussian"`
- arXiv: `all:"radio source centroid" AND all:"solar"`
- arXiv: `all:"type III burst" AND all:"AIA"`
- arXiv: `all:"Newkirk" AND all:"type III"`
- arXiv: `all:"spike-like" AND all:"solar radio"`
- Crossref DOI metadata: `10.1051/0004-6361/202660446`, `10.3847/1538-4357/ae7429`, `10.1038/s41467-026-74137-2`, `10.3847/1538-4357/acbd3f`, `10.1051/0004-6361/202038518`, `10.3847/1538-4357/ac3bb7`
- Semantic Scholar: 对 fine-structure / Gaussian-source 关键词做补充检查；部分查询触发 429，因此不把未返回结果当作否定证据。

## 2. 今日新增重点论文总览

| 序号 | 论文 | 年份 | 方向 | 相关性 | 推荐等级 | DOI/arXiv/ADS | 本地记录 |
|---|---|---|---|---|---|---|---|
| 1 | Sizes and Shapes of Sources in Solar Metric Radio Bursts | 2022 | Gaussian fitting / radio source centroid | A | high | DOI: 10.3847/1538-4357/ac3bb7; arXiv: 2111.07777 | paper_master_index.csv; gaussian_fitting_paper_index.csv |
| 2 | Solar Radio Burst Fine Structures | 2026 | solar radio spikes / fine structures | B | medium | arXiv: 2606.25469 | paper_master_index.csv |

今日还完成 2 条重要元数据修正：

- `Solar Radio Spikes and Type IIIb Striae...` 从 arXiv preprint 修正为 The Astrophysical Journal，DOI `10.3847/1538-4357/acbd3f`。
- `arXiv:2011.13735` 修正为 `LOFAR observations of radio burst source sizes and scattering in the solar corona`，A&A DOI `10.1051/0004-6361/202038518`。

## 3. 与 spikes topping type III / type III burst 相关论文

今日未发现比已有核心论文 `Type-III solar radio bursts with spike-like toppings` 更直接的新 A 级主题论文。

新增 B 级背景论文 `Solar Radio Burst Fine Structures` 覆盖 spikes、drift pairs、Type III striae 和高时频成像，是引言/讨论部分可用的近期综述入口，但不直接提供 DART / DRAT 源区拟合公式。

## 4. 与 solar radio spikes / fine structures 相关论文

`Solar Radio Burst Fine Structures` 是今天最重要的新增 fine-structure 背景文献。其价值在于把 spikes、striae、herringbone 等精细结构放在 sub-second imaging spectroscopy 和 SKA full-Stokes 成像能力需求下讨论，适合支撑“当前数据分辨率与理论解释仍有边界”的论文表述。

`Solar Radio Spikes and Type IIIb Striae...` 的 ApJ DOI 已补齐；它仍是把 spikes 与 Type IIIb striae 放入共同亚秒电子加速框架的核心文献。

## 5. 与 AIA / EUV / HMI / radio 联合分析相关论文

今日没有发现新的高质量 AIA/EUV/HMI/radio 联合分析 A/B 级论文。当前仍建议沿用已有的 `Low Altitude Solar Magnetic Reconnection...` 和 `Multiwavelength Multipoint Observations...` 作为联合分析框架参考。

## 6. 与 Gaussian fitting / radio source centroid 相关论文

### Sizes and Shapes of Sources in Solar Metric Radio Bursts

- 如何定义 radio source center：源位置需要与 2D Gaussian morphology 和 elliptical half-maximum contour 一起解释，并考虑仪器/电离层修正。
- 是否使用 2D Gaussian / elliptical Gaussian：是；用 2D Gaussian profiles 近似强度分布，并使用 elliptical half-maximum contours。
- 是否讨论 FWHM / source size：是；给出 source sizes、ellipticities 和 deconvolved sizes。
- 是否处理 beam deconvolution：是；通过已知源观测估计仪器/电离层效应，再解释去卷积后的源尺寸。
- 是否讨论 centroid uncertainty：以仪器、电离层和各向异性散射作为主要系统误差来源。
- 是否适合当前 DART / DRAT 射电源图像：高度适合，建议用于新增 `ellipticity`、`deconvolution_status`、`beam_or_psf_reference` 和 `morphology_frequency_trend` 等输出字段。

### LOFAR observations of radio burst source sizes and scattering in the solar corona

- 本次不是新增论文，而是纠正旧索引条目的题名、作者、期刊和 DOI。
- 该文直接在 LOFAR visibilities 上拟合 elliptical Gaussian 来估计 Type IIIb 源区尺寸和位置。
- 对当前项目的核心价值是提醒：如果 DART / DRAT 没有可靠 beam 或 visibility 信息，论文中应称 `observed apparent size`，不要写成 `intrinsic source size`。

## 7. 与 Newkirk density model / frequency drift rate / source motion 相关论文

今日未发现新的 A/B 级 Newkirk 或 drift-rate 论文。现有建议保持不变：

- Newkirk height-derived speed、dynamic-spectrum drift-rate speed、Gaussian apparent motion speed 不能简单等同。
- 若低频源区 FWHM 过大或 Gaussian center 与 contour center 偏差明显，应先打质量标记，不直接进入速度拟合。

## 8. 今日最值得精读的 3-5 篇论文

1. `Sizes and Shapes of Sources in Solar Metric Radio Bursts`：今天新增的核心 Gaussian/source-size 方法论文。
2. `Solar Radio Burst Fine Structures`：今天新增的 fine-structure 综述/前瞻，适合引言和讨论。
3. `LOFAR observations of radio burst source sizes and scattering in the solar corona`：旧条目修正后应作为 observed apparent size 与 scattering 解释的核心参考。
4. `Solar Radio Spikes and Type IIIb Striae...`：ApJ DOI 已补齐，适合支撑 spikes/Type IIIb 共同加速框架。

## 9. 对当前项目的具体建议

- 不建议今天直接修改核心 Gaussian fitting 算法。
- 建议先增加诊断输出：`ellipticity`、`fwhm_deconvolution_status`、`beam_or_psf_reference`、`morphology_frequency_trend`。
- 建议继续比较 Gaussian center 与 contour center；偏差大时检查 ROI、背景、多峰结构和 FWHM 是否过宽。
- `max_fwhm_arcsec = 1800.0` 仍应作为重点风险参数复核，避免无物理意义的大椭圆进入速度估计。
- 建议把 Newkirk 比较放在 height-frequency / height-time 视角下，不把二维图像外推位置直接当作三维高度。
- 建议保存 drift 选取频谱图和选点线条，保证 drift-rate 速度讨论可复核。

## 10. 今日更新文件列表

- `data/seed_papers.json`
- `paper_master_index.csv`
- `paper_master_index.md`
- `daily_recommendations/2026-06-28_paper_recommendations.md`
- `02_methods_gaussian_fitting/gaussian_fitting_paper_index.csv`
- `02_methods_gaussian_fitting/gaussian_fitting_paper_index.md`
- `02_methods_gaussian_fitting/gaussian_fitting_method_review.md`
- `02_methods_gaussian_fitting/gaussian_fitting_implementation_notes.md`
- `02_methods_gaussian_fitting/gaussian_fitting_quality_control.md`
- `02_methods_gaussian_fitting/gaussian_fitting_uncertainty_notes.md`
- `02_methods_gaussian_fitting/gaussian_fitting_literature_daily/2026-06-28_gaussian_fitting_papers.md`
- `08_project_method_notes/gaussian_fitting_code_improvement_suggestions_2026-06-28.md`
- `organization_log_2026-06-28.md`
- `.paper_recommendation_state.json`
