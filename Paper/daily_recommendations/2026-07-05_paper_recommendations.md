# 2026-07-05 文献检索日报

## 1. 今日检索关键词

数据日期：2026-07-05；检索来源：arXiv、Crossref、项目本地 `data/seed_papers.json`。

重点检索组合：

- `spike-like AND solar AND radio`
- `solar AND radio AND fine AND structures`
- `solar AND radio AND Gaussian`
- `radio AND source AND centroid AND solar`
- `type III AND radio burst AND AIA`
- `Newkirk AND type III`
- `SKAO AND solar AND radio`
- `2D Gaussian AND solar AND radio`

Crossref 对以下新增候选做了题名检索，但未返回可信匹配 DOI：

- `Radio Diagnostics of Particle Acceleration in Solar Flares with SKAO Observations`
- `Comprehensive study of solar type II radio bursts and the properties of the associated shock waves`

## 2. 今日新增重点论文总览

今日没有发现比已有核心文献更直接的新 A 级论文。新增 B 级论文 2 篇；其中 1 篇进入 Gaussian/source-centroid 方法库。

| 序号 | 论文 | 年份 | 方向 | 相关性 | 推荐等级 | DOI/arXiv/ADS | 本地记录 |
|---|---|---|---|---|---|---|---|
| 1 | Radio Diagnostics of Particle Acceleration in Solar Flares with SKAO Observations | 2026 | AIA / EUV / HMI / radio joint analysis | B | medium | arXiv: 2606.28782 | paper_master_index.csv |
| 2 | Comprehensive study of solar type II radio bursts and the properties of the associated shock waves | 2026 | Gaussian fitting / radio source centroid | B | medium | arXiv: 2512.21846 | paper_master_index.csv; gaussian_fitting_paper_index.csv |

今日元数据修正：

- `Solar Radio Burst Fine Structures`：从普通 `arXiv preprint` 修正为 `Advancing Astrophysics with the SKA II (AASKAII)` 章节记录；截至 2026-07-05 未在 Crossref 检索到可信出版社 DOI，保留 arXiv 记录 `2606.25469`。

## 3. 与 spikes topping type III / type III burst 相关论文

今日没有发现比 `Type-III solar radio bursts with spike-like toppings`、`Imaging spectroscopy reveals spike-like repeating radio burst pairs in the solar corona`、`Frequency-time-resolved Imaging Spectroscopy of Fine Structures in a Solar Radio Noise Storm` 更直接的新增 A 级主题论文。

`Solar Radio Burst Fine Structures` 的 AASKAII 状态已更新，适合作为 spikes、drift pairs、type III striae、herringbones 和未来 SKA full-Stokes 成像能力的综述背景，但仍不是 DART / DRAT 源区拟合公式来源。

## 4. 与 solar radio spikes / fine structures 相关论文

### Radio Diagnostics of Particle Acceleration in Solar Flares with SKAO Observations

- 来源状态：AASKAII 2026 章节；arXiv 2026-06-27 提交；Crossref 未核验到可信正式 DOI。
- 相关性：B。
- 项目价值：可用于引言或展望中说明高时空分辨成像、偏振和 EUV/X-ray 联合诊断对电子束与磁拓扑约束的重要性。
- 限制：综述/前瞻性质，不提供当前 DART / DRAT 可直接采用的 Gaussian 拟合、source center 或 FWHM 方案。

## 5. 与 AIA / EUV / HMI / radio 联合分析相关论文

`Radio Diagnostics of Particle Acceleration in Solar Flares with SKAO Observations` 值得纳入总索引，但只作为 B 级背景文献。它强调 SKAO 高保真射电数据与 EUV、X-ray 的协同诊断，对当前项目的写作价值主要在讨论未来观测能力，而不是改变当前方法链。

当前项目仍应优先沿用已有 A 级联合分析文献来支撑 AIA/HMI 背景、耀斑源区定位和射电证据链。

## 6. 与 Gaussian fitting / radio source centroid 相关论文

### Comprehensive study of solar type II radio bursts and the properties of the associated shock waves

- 该论文如何定义 radio source center：使用 NRH Stokes I 图像中的 2D Gaussian centroid，并结合电子密度等值面做去投影。
- 是否使用 2D Gaussian / elliptical Gaussian：使用 2D Gaussian 求源中心和峰值强度；不是专门讨论椭圆形态或源区尺度的论文。
- 是否讨论 FWHM / source size：否，今天只把它作为源中心定位和诊断链条参考。
- 是否处理 beam deconvolution：未核验到可直接迁移的 beam 去卷积流程；不能据此讨论 intrinsic source size。
- 是否讨论 centroid uncertainty：主要不确定性来自密度模型、去投影和 shock 几何匹配；没有可直接迁移到当前项目的 centroid covariance 公式。
- 是否适合当前 DART / DRAT 射电源图像：中等。可借鉴“射电中心 + AIA overlay + density-model deprojection + dynamic-spectrum drift-rate”的证据组织方式，但 type II / herringbone 的 shock 物理结论不能直接套到 type III spike topping。

## 7. 与 Newkirk density model / frequency drift rate / source motion 相关论文

今日没有发现新的 A/B 级 Newkirk 专门论文。

`Comprehensive study...` 使用的是 MAS/MHD density model，而不是 Newkirk model；它对当前项目的价值在于提醒：把 2D 图像中心、密度模型高度和 dynamic spectrum drift-rate 放进同一证据链时，必须明确各自物理含义，不要把 Gaussian apparent motion、density-model height motion 和 electron-beam speed 简单等同。

## 8. 今日最值得精读的 3-5 篇论文

1. `Comprehensive study of solar type II radio bursts and the properties of the associated shock waves`：今日新增 B 级方法参考；重点看 2D Gaussian centroid、AIA overlay、密度模型去投影和动态频谱 drift 证据链。
2. `Radio Diagnostics of Particle Acceleration in Solar Flares with SKAO Observations`：今日新增 B 级背景；适合写未来高保真成像与多波段诊断展望。
3. `Solar Radio Burst Fine Structures`：今日完成状态修正；适合作为 fine structures / SKA 观测能力综述入口。

## 9. 对当前项目的具体建议

- 不建议今天修改核心 Gaussian fitting 算法。
- 建议继续优先增加诊断输出，而不是调大 `max_fwhm_arcsec = 1800.0`。
- 建议保留并强化 Gaussian center 与 contour center 的逐频逐时对比。
- 建议将 `Comprehensive study...` 的证据链借鉴为当前论文图版组织方式：AIA overlay、radio centroid、density-model configuration、dynamic-spectrum selected points 和速度估计结果一起保存。
- 建议把 Newkirk 比较继续写成 height-frequency / height-time 关系，不把二维图像外推位置直接称为真实三维高度。
- 建议在 README / 方法综述中保留 `Solar Radio Burst Fine Structures` 与 SKAO 章节作为未来观测能力背景，但不要把它们写成当前 DART / DRAT 源区拟合依据。

## 10. 今日更新文件列表

- `data/seed_papers.json`
- `paper_master_index.csv`
- `paper_master_index.md`
- `daily_recommendations/2026-07-05_paper_recommendations.md`
- `02_methods_gaussian_fitting/gaussian_fitting_paper_index.csv`
- `02_methods_gaussian_fitting/gaussian_fitting_paper_index.md`
- `02_methods_gaussian_fitting/gaussian_fitting_method_review.md`
- `02_methods_gaussian_fitting/gaussian_fitting_implementation_notes.md`
- `02_methods_gaussian_fitting/gaussian_fitting_quality_control.md`
- `02_methods_gaussian_fitting/gaussian_fitting_uncertainty_notes.md`
- `02_methods_gaussian_fitting/gaussian_fitting_literature_daily/2026-07-05_gaussian_fitting_papers.md`
- `08_project_method_notes/gaussian_fitting_code_improvement_suggestions_2026-07-05.md`
- `organization_log_2026-07-05.md`
- `.paper_recommendation_state.json`

