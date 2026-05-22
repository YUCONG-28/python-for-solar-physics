# Project Optimization Plan

生成日期：2026-05-22

本计划基于 `PROJECT_OVERVIEW.md`，用于第一阶段项目整理。目标是让仓库更适合 GitHub 展示、README 维护和后续代码重构，同时不改变任何科研算法。

## 1. 本轮优化目标

- 明确 README 和文档中的推荐主入口脚本。
- 把核心工作流、工具脚本、legacy/experimental 脚本和示例脚本区分清楚。
- 新增模块化配置模板，为后续集中配置做准备。
- 明确 `docs/assets/` 的 README 展示资产策略。
- 建立 legacy 与人工确认文件清单，避免误删重要历史参数、实验脚本或科研结果。
- 继续保留所有已有文件，不移动、不重命名、不删除核心代码和高风险文件。

## 2. 不修改的文件清单

以下文件本轮不移动、不重命名、不删除；除非未来人工确认，否则不要自动处理：

- `scripts/radio/sdo_aia_radio_hmi_overlay_bgcorrected.py`
- `scripts/radio/spectrogram_drift_rate_manual_selection.json`
- `HXR.png`
- `SXR.png`
- `SXR to HXR.png`
- `SXR to HXR enhance.png`
- `AIA.xlsx`
- `CSO.xlsx`
- `examples/radio_aia_hmi/*`

本轮也不修改以下科研算法相关逻辑：

- AIA/HMI/radio 坐标变换逻辑
- WCS、extent、origin 处理逻辑
- 高斯拟合数学模型
- 频漂率计算公式
- AIA 差分图计算公式
- HMI/radio 时间匹配逻辑

## 3. 核心入口脚本清单

| Workflow | 推荐入口 |
| --- | --- |
| AIA 图像与差分 | `scripts/aia_hmi/sdo_aia_euv_processor.py` |
| 射电源图、高斯拟合、频漂率 | `scripts/radio/radio_source_map_plot_gaussian_overlay.py` |
| AIA + radio + HMI 叠加 | `scripts/radio/sdo_aia_radio_hmi_overlay.py` |
| CSO 动态频谱 | `scripts/radio/cso_radio_spectrogram_plot.py` |
| 高斯拟合工具 | `scripts/tools/gaussian_source_fitting.py` |

核心包：

- `solar_toolkit/path_config.py`
- `solar_toolkit/solar_analysis_utils.py`
- `solar_toolkit/__init__.py`

## 4. 可整理但暂不删除的 Legacy 文件清单

| 文件 | 当前判断 |
| --- | --- |
| `scripts/aia_hmi/sdo_aia_base_difference.py` | 与 AIA 主处理器的差分功能重复，暂保留 |
| `scripts/aia_hmi/sdo_aia_running_difference.py` | 与 AIA 主处理器的差分功能重复，暂保留 |
| `scripts/aia_hmi/sdo_aia_multichannel_panel.py` | 与 AIA mosaic 功能部分重复，暂保留 |
| `scripts/radio/radio_source_map_plot.py` | 射电源基础绘图入口，可能被高级高斯版覆盖，暂保留 |
| `scripts/radio/cso_spectrogram_class.py` | CSO 读取/绘图工具类，与正式频谱脚本和 GUI 重复，暂保留 |
| `scripts/radio/cso_radio_spectra_gui.py` | 可选 GUI/历史交互工具，依赖额外 GUI 包，暂保留 |
| `examples/radio_aia_hmi/aia_radio_overlay_variant0_example.py` | 历史叠加示例，可能含复现参数，暂保留 |
| `examples/radio_aia_hmi/aia_radio_overlay_variant1_example.py` | 历史叠加示例，可能含复现参数，暂保留 |

详细人工确认表见 `docs/LEGACY_AND_REVIEW_FILES.md`。

## 5. 配置集中化建议

第一阶段只新增模板，不强制现有脚本读取这些文件。

- `configs/aia.example.yaml`：AIA 波段、模式、差分、色标、输出路径。
- `configs/radio.example.yaml`：射电频率、偏振、阈值、高斯拟合、输出路径。
- `configs/cso.example.yaml`：CSO FITS、时间/频率范围、强度裁剪、下采样、频漂率开关。
- `configs/overlay.example.yaml`：AIA/HMI/radio 路径、叠加波段、等值线、时间容差、WCS 保持策略。

后续建议：

1. 保留脚本内默认值作为 fallback。
2. 先统一路径和输出目录，再统一科学参数。
3. 对会影响科学结果的参数，例如 WCS/origin、时间匹配阈值和高斯质量阈值，增加测试和文档后再迁移。

## 6. README 展示结构建议

README 推荐顺序：

1. 项目定位和功能摘要。
2. 推荐主入口脚本。
3. 输入数据与输出产品说明。
4. 本地路径配置。
5. 推荐运行顺序。
6. Quick Start。
7. Radio Gaussian and Drift-Rate Workflow。
8. Verification。
9. Data Policy。
10. Citation and License。

建议展示图：

- AIA 单波段或 mosaic。
- AIA running/base difference。
- AIA/radio/HMI overlay。
- CSO dynamic spectrogram。
- Radio Gaussian fitting example。

展示图应放入 `docs/assets/images/`；短视频放入 `docs/assets/videos/`。

## 7. GitHub 上传前检查清单

- 不上传真实 FITS、JP2、NetCDF、NPY/NPZ、HDF5 数据。
- 不上传批量 PNG/JPG 输出目录。
- 不上传 MP4/AVI/MOV/GIF/MKV 批量视频。
- 不上传 `configs/paths.local.yaml` 或个人路径。
- 确认根目录 PNG 是否要保留、压缩或迁入 `docs/assets/images/`。
- 确认 `AIA.xlsx`、`CSO.xlsx` 是否为可公开数据。
- 确认 `spectrogram_drift_rate_manual_selection.json` 是示例还是本地结果。
- 运行轻量测试：`python -m pytest tests`。
- 运行编译检查：`python -m compileall solar_toolkit scripts tests`。
- 检查 `git status --short`，不要混入临时输出。

## 8. 第二阶段可执行的重构计划

高优先级：

1. 为 radio FITS `extent/origin/WCS` 坐标转换建立公共函数和单元测试。
2. 为 AIA/HMI/radio 时间匹配建立统一诊断输出。
3. 统一高斯拟合实现和质量判据，避免多脚本结果不一致。

中优先级：

1. 将路径、输出目录和非敏感显示参数迁移到统一配置加载。
2. 把重复的 CSO FITS 读取逻辑合并到公共模块。
3. 给 legacy 脚本增加文档标识或迁入明确的 legacy/example 区域。

低优先级：

1. 清理乱码注释和过长脚本头部说明。
2. 增加 README 示例图和缩略图。
3. 为 `docs/assets/` 增加来源说明和压缩规范。
