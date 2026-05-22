# Legacy and Review Files

生成日期：2026-05-22

本清单用于防止后续整理时误删重要历史脚本、实验逻辑、展示图或科研结果。第一阶段只标记，不删除、不移动、不重命名。

## 可考虑合并但暂不删除

| 文件 | 当前作用 | 与哪个核心脚本重复 | 是否建议合并 | 合并风险 | 是否需要人工确认 |
| --- | --- | --- | --- | --- | --- |
| `scripts/aia_hmi/sdo_aia_base_difference.py` | 生成 AIA base difference 图像 | `scripts/aia_hmi/sdo_aia_euv_processor.py` | 是，后续可用主处理器统一入口 | 旧脚本可能保留特定输出路径、色标或论文参数 | 是 |
| `scripts/aia_hmi/sdo_aia_running_difference.py` | 生成 AIA running difference 图像 | `scripts/aia_hmi/sdo_aia_euv_processor.py` | 是，后续可用主处理器统一入口 | 差分参考帧、输出命名或显示范围可能不同 | 是 |
| `scripts/aia_hmi/sdo_aia_multichannel_panel.py` | 生成同步多波段 AIA 面板 | `scripts/aia_hmi/sdo_aia_euv_processor.py` | 可能合并 | 多波段同步逻辑和布局细节可能不同 | 是 |
| `scripts/radio/radio_source_map_plot.py` | 射电源单频/多频基础绘图 | `scripts/radio/radio_source_map_plot_gaussian_overlay.py` | 可能合并或保留为简化入口 | 基础版更简单，删除会降低低门槛使用 | 是 |
| `scripts/radio/cso_spectrogram_class.py` | CSO 频谱读取和绘图 helper 类 | `scripts/radio/cso_radio_spectrogram_plot.py`, `scripts/radio/cso_radio_spectra_gui.py` | 是，读取逻辑可统一 | GUI 或示例可能依赖类接口 | 是 |
| `scripts/radio/cso_radio_spectra_gui.py` | PyQt5/pyqtgraph 交互 GUI 和 type-II 拟合工具 | `scripts/radio/cso_radio_spectrogram_plot.py`, `cso_spectrogram_class.py` | 暂不直接合并，先文档化为 optional GUI | GUI 依赖、交互行为和保存逻辑复杂 | 是 |
| `examples/radio_aia_hmi/aia_radio_overlay_variant0_example.py` | 历史 AIA/radio 单文件叠加示例 | `scripts/radio/sdo_aia_radio_hmi_overlay.py` | 可能合并为一个精简示例 | 可能包含某次论文图的参数 | 是 |
| `examples/radio_aia_hmi/aia_radio_overlay_variant1_example.py` | 历史 AIA/radio 单文件叠加示例 | `scripts/radio/sdo_aia_radio_hmi_overlay.py` | 可能合并为一个精简示例 | 可能包含某次论文图的参数 | 是 |

## 暂时不要动的文件

| 文件 | 当前作用 | 与哪个核心脚本重复 | 是否建议合并 | 合并风险 | 是否需要人工确认 |
| --- | --- | --- | --- | --- | --- |
| `scripts/radio/sdo_aia_radio_hmi_overlay_bgcorrected.py` | 背景扣除实验版 AIA/radio/HMI 叠加 | `scripts/radio/sdo_aia_radio_hmi_overlay.py` | 未来可评估合并 | 背景扣除会改变射电源强度、掩膜和高斯拟合结果，直接合并可能改变科学结论 | 是 |
| `scripts/radio/spectrogram_drift_rate_manual_selection.json` | 手动频漂率选点结果或示例 | `radio_source_map_plot_gaussian_overlay.py` 的运行输出 | 不作为代码合并；需决定是示例还是本地结果 | JSON 内含本地绝对路径，可能不适合公开 | 是 |
| `AIA.xlsx` | 可能是 AIA 科研表格或中间结果 | 无直接核心脚本重复 | 暂不合并 | 可能包含科研数据或未脱敏结果 | 是 |
| `CSO.xlsx` | 可能是 CSO 科研表格或中间结果 | 无直接核心脚本重复 | 暂不合并 | 可能包含科研数据或未脱敏结果 | 是 |
| `HXR.png` | 根目录展示图或历史输出图 | 可能来自 X-ray/DEM plotting scripts | 暂不移动 | 可能是论文/README 资产；迁移前需确认来源和压缩策略 | 是 |
| `SXR.png` | 根目录展示图或历史输出图 | 可能来自 GOES/SXR plotting scripts | 暂不移动 | 可能是论文/README 资产；迁移前需确认来源和压缩策略 | 是 |
| `SXR to HXR.png` | 根目录展示图或历史输出图 | 可能来自 Neupert/SXR-HXR comparison scripts | 暂不移动 | 可能是论文/README 资产；迁移前需确认来源和压缩策略 | 是 |
| `SXR to HXR enhance.png` | 根目录展示图或历史输出图 | 可能来自 Neupert/SXR-HXR comparison scripts | 暂不移动 | 可能是论文/README 资产；迁移前需确认来源和压缩策略 | 是 |

## 后续处理原则

1. 先给 legacy 文件补充文档状态，再考虑代码迁移。
2. 对可能改变科学结果的合并，必须先增加测试和对比图。
3. 对包含本地路径或科研结果的文件，先人工确认是否可公开。
4. 对 README 展示图，优先压缩并迁入 `docs/assets/images/`，不要直接上传批量输出目录。
