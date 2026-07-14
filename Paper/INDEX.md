# Paper 推荐索引

## 主入口

- `README.md`：本地生成、安全发布和维护说明。
- `paper_master_index.csv` / `paper_master_index.md`：全局文献索引。
- `daily_recommendations/`：每日文献检索日报。
- `02_methods_gaussian_fitting/`：Gaussian fitting、radio source centroid、source size、beam / uncertainty 方法库。
- `08_project_method_notes/`：面向当前 DART / DRAT 分析的代码与方法建议。
- `00_local_documents/`：本地 PDF、Word 手稿和博士论文归档；该目录不进入公开 Git 仓库。

## 主题目录

- `type_III_radio_bursts/`：Type III 主线、传播、频漂与源区定位相关文献。
- `solar_radio_spikes/`：solar radio spikes、spike-like toppings、IIIb/striae 细结构。
- `AIA_observations/`：AIA 多波段、活动区上下文与联合观测。
- `DART_methods/`：DART/DRAT、自动检测、实时识别与方法学补充。
- `review_background/`：综述、成像频谱学与背景材料。
- `references/`：旧版每日推荐记录。

## 每日推荐记录

- 2026-06-08: [daily_recommendations/2026-06-08_paper_recommendations.md](daily_recommendations/2026-06-08_paper_recommendations.md)
- 2026-06-01: [daily_recommendations/2026-06-01_paper_recommendations.md](daily_recommendations/2026-06-01_paper_recommendations.md)
- 2026-05-31: [references/paper_recommendation_2026-05-31.md](references/paper_recommendation_2026-05-31.md)
- 2026-05-24: [references/paper_recommendation_2026-05-24.md](references/paper_recommendation_2026-05-24.md)

## 当前关注关键词

- `spikes topping type III`
- `spike-like repeating burst pairs`
- `type III radio burst`
- `solar radio spikes`
- `radio source centroid`
- `Gaussian fitting`
- `source size / FWHM`
- `frequency drift rate`
- `Newkirk density model`
- `AIA multiwavelength context`
- `DART / DRAT`

## 最新更新摘要

- `2026-07-14`：日报脚本改为默认仅本地生成；只有显式 `-CommitAndPush` 才按 Paper 白名单暂存、提交和推送，并在无白名单变化时跳过 push。
- `2026-06-08`：日报脚本曾增加自动推送；该行为已由 2026-07-14 的显式安全发布流程取代。
- `2026-06-08`：新增 5 篇高价值漏收文献，其中 4 篇进入 Gaussian / centroid / source-size / propagation 方法链条；校正 1 篇 2026 Solar Physics 文献元数据。
- `2026-06-01`：建立可本地运行的 PowerShell 日报生成流程、总索引和 Gaussian fitting 方法库。
- `2026-05-31`：补录 `Imaging spectroscopy reveals spike-like repeating radio burst pairs in the solar corona`。
