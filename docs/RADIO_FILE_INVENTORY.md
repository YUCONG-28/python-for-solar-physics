# Radio 文件清单与后续优化判断表

日期：2026-05-27

## 范围

本清单整理仓库中与 `radio` 直接相关的源码、配置、文档、测试和示例文件，供后续判断“保留、合并、迁移、删除、补测试”时使用。

未纳入：

- `__pycache__/` 下的缓存文件。
- 非 radio 专属但被 radio 调用的通用模块，除非测试或文档明确涉及。

## 当前结构概览

| 区域 | 作用 | 当前判断 |
| --- | --- | --- |
| `scripts/radio/run_*.py` | 用户入口层 | 保留，作为推荐运行入口。 |
| `scripts/radio/core/` | 已抽出的可复用分析逻辑 | 继续迁移、补测试，逐步降低对 legacy 的依赖。 |
| `scripts/radio/legacy/` | 兼容旧流程的大脚本 | 暂不删除；先拆分、记录差异、做输出对比。 |
| `scripts/radio/configs/` | 事件配置和配置加载器 | 保留；后续把硬编码参数继续迁入配置。 |
| `scripts/radio/docs/` | radio 重构、入口和配置说明 | 保留；本清单可作为后续维护索引。 |
| `scripts/radio/outputs/` | 本地选择结果或运行产物 | 不作为代码优化对象；需确认是否应保留在仓库。 |
| `tests/test_radio_*.py` | radio 相关测试 | 需要更新 import 路径并扩展覆盖。 |
| `examples/radio*` | 示例或历史分析脚本 | 暂不删；先确认是否含论文图参数或一次性调参。 |
| `configs/radio.example.yaml` | 顶层 YAML 示例 | 保留，可与 Python config 对齐。 |

## 推荐入口

| 文件 | 行数 | 主要用途 | 调用关系 | 后续判断 |
| --- | ---: | --- | --- | --- |
| `scripts/radio/run_radio_burst_pipeline.py` | 941 | 完整射电爆发分析：源图 Gaussian、频谱、频漂率、Newkirk 外推、汇总图表。 | 读取 `configs`，调用 `legacy.radio_source_map_plot_gaussian_overlay`，再调用 `core`/本文件内的 Newkirk 绘图逻辑。 | 作为完整流程入口保留；后续把本文件内较长的绘图/表格逻辑继续拆到 `core`。 |
| `scripts/radio/run_radio_source_map.py` | 36 | 射电源图和 Gaussian overlay 的快速入口。 | 薄包装 `legacy.radio_source_map_plot_gaussian_overlay.main()`。 | 保留为低门槛入口；等 legacy orchestration 拆小后改为调用新函数。 |
| `scripts/radio/run_aia_radio_hmi_overlay.py` | 40 | AIA/HMI/radio 叠加入口。 | 加载 AIA/radio/HMI config，调用 `legacy.sdo_aia_radio_hmi_overlay.main(user_config=...)`。 | 保留；后续替换 legacy 内重复 Gaussian 逻辑。 |

## Core 模块

| 文件 | 行数 | 主要内容 | 当前依赖/风险 | 后续动作 |
| --- | ---: | --- | --- | --- |
| `scripts/radio/core/radio_gaussian_fit.py` | 1382 | Gaussian 模型、背景估计、source mask、拟合诊断、overlay、CSV 输出。 | 仍从 `legacy.radio_source_map_plot_gaussian_overlay` 导入数组别名、诊断字段、坐标转换和输出目录逻辑。 | 高优先级：把中性 IO/诊断常量迁到 `core/radio_io.py` 或通用模块，减少反向依赖。 |
| `scripts/radio/core/radio_spectrogram.py` | 613 | 动态频谱缓存、时间窗解析、rebinned plane、频谱面板 overlay。 | 仍依赖 legacy 的时间/index 解析 helper。 | 中高优先级：提取时间解析与路径归一化 helper。 |
| `scripts/radio/core/radio_drift_rate.py` | 857 | 手动频漂率选点、JSON 保存/读取、预览图、交互 server、频漂率 overlay 和诊断。 | 仍依赖 legacy 的时间解析、输出路径和诊断字段。 | 中高优先级：和 `radio_spectrogram` 一起抽公共 IO/time helper。 |
| `scripts/radio/core/radio_newkirk_extrapolation.py` | 185 | Newkirk 密度模型、频率-高度转换、频漂速度外推、Gaussian 行过滤。 | 依赖 `numpy/pandas`，相对独立。 | 保留并扩展测试；当前适合成为稳定 core。 |
| `scripts/radio/core/__init__.py` | 1 | 包标记。 | 无。 | 保留。 |

## Legacy 兼容脚本

| 文件 | 行数 | 主要内容 | 独特价值 | 风险等级 | 后续动作 |
| --- | ---: | --- | --- | --- | --- |
| `scripts/radio/legacy/radio_source_map_plot_gaussian_overlay.py` | 8224 | 射电源图主旧流程：配置迁移、FITS 读取、Gaussian、频谱面板、频漂率、输出。 | 当前仍是完整 source-map orchestration 的事实主实现。 | 高 | 不直接删。先抽 `radio_io`、拆 main orchestration、做输出对比。 |
| `scripts/radio/legacy/sdo_aia_radio_hmi_overlay.py` | 3206 | AIA/HMI/radio 对齐叠加、WCS/reproject、HMI contour、radio contour、Gaussian 重投影。 | 保留了叠加流程和 AIA/HMI/radio 专用参数。 | 高 | 先把重复 Gaussian 逻辑替换为 `core.radio_gaussian_fit`，但背景/阈值行为需对比。 |
| `scripts/radio/legacy/cso_radio_spectrogram_plot.py` | 2930 | CSO 动态频谱绘制、内存友好降采样、多偏振、type-II/频漂辅助、配置管理。 | 包含完整 CSO 频谱绘图与交互选择行为。 | 中高 | 先归档接口说明；可逐步拆出 reader/cache/plotter，不影响 GUI/交互行为。 |
| `scripts/radio/legacy/__init__.py` | 1 | 包标记。 | 保证兼容 import。 | 低 | 保留。 |

## 配置文件

| 文件 | 行数 | 作用 | 后续动作 |
| --- | ---: | --- | --- |
| `scripts/radio/configs/__init__.py` | 62 | 配置模块名归一化、加载 radio config、加载 AIA/radio/HMI config。 | 保留；可补失败路径测试。 |
| `scripts/radio/configs/radio_20250124_config.py` | 203 | 2025-01-24 radio 主配置，含 `USER_CONFIG`、`NEWKIRK_CONFIG`，并复用 AIA overlay config。 | 作为当前默认事件配置保留。 |
| `scripts/radio/configs/radio_20250503_config.py` | 33 | 未来 2025-05-03 事件模板，基于 2025-01-24 深拷贝调整。 | 保留为模板；实际使用前检查路径和事件参数。 |
| `scripts/radio/configs/example_radio_pipeline_config.py` | 5 | 兼容 alias，导出 2025-01-24 配置。 | 可保留到旧文档/脚本不再引用。 |
| `scripts/radio/configs/README.md` | 37 | 配置编辑说明。 | 保留并与本清单交叉引用。 |
| `configs/radio.example.yaml` | 35 | 顶层 YAML 示例，面向 source-map。 | 后续决定是否统一到 YAML 或继续 Python config 双轨。 |

## 文档

| 文件 | 行数 | 作用 | 后续动作 |
| --- | ---: | --- | --- |
| `scripts/radio/docs/RADIO_ENTRYPOINTS.md` | 56 | 三个 root-level radio 入口说明。 | 保留；入口变化时同步更新。 |
| `scripts/radio/docs/RADIO_MIGRATION_NOTES.md` | 42 | 当前兼容层、剩余 legacy 依赖和安全下一步。 | 保留；本清单的优化判断主要继承这里的迁移顺序。 |
| `scripts/radio/docs/RADIO_REFACTOR_REPORT.md` | 91 | radio 文件移动和重构报告。 | 保留作历史记录。 |
| `scripts/radio/docs/RADIO_CONFIG_EXTRACTION_REPORT.md` | 118 | radio 配置抽取记录和验证说明。 | 保留；后续配置迁移继续追加或另建阶段报告。 |
| `scripts/radio/docs/AIA_CONFIG_EXTRACTION_REPORT.md` | 102 | AIA/HMI/radio 配置抽取记录。 | 保留。 |
| `docs/RADIO_SOURCE_MAP_REFACTOR_REPORT.md` | 127 | source-map 重构历史报告。 | 保留；若内容与当前结构冲突，标注历史状态。 |
| `docs/RADIO_COORDINATE_AUDIT.md` | 62 | radio 坐标/extent/origin 审计。 | 保留；坐标相关改动必须先看。 |

## 示例、外部流程与运行产物

| 文件 | 行数 | 类型 | 用途 | 后续判断 |
| --- | ---: | --- | --- | --- |
| `examples/radio_aia_hmi/aia_radio_hmi_overlay_demo.py` | 1797 | 示例/历史脚本 | AIA、radio、HMI 叠加 demo，含重复时间解析、RR/LL 匹配、Gaussian、reproject 等逻辑。 | 不直接删；先确认是否包含论文图参数。可后续缩成薄 wrapper。 |
| `examples/radio/fits_header_metadata_example.py` | 36 | 示例 | FITS header/map metadata 查看示例。 | 保留为小示例；可确认是否仍能跑。 |
| `scripts/xray_dem/dem_radio_source_overlay.py` | 738 | 跨模块脚本 | DEM/TB 与 radio source overlay。 | 不属于 `scripts/radio`，但 radio 改坐标/读取逻辑时需纳入回归检查。 |
| `scripts/radio/outputs/selections/spectrogram_drift_rate_manual_selection.json` | 128 | 运行产物/手动选点 | 频漂率手动选择结果。 | 需人工确认是否为示例数据、论文复现实验，还是本地临时产物；不建议自动删除。 |

## 测试与当前疑点

| 文件 | 行数 | 当前覆盖 | 疑点/风险 | 建议 |
| --- | ---: | --- | --- | --- |
| `tests/test_radio_coordinates.py` | 122 | 纯坐标 display helper：extent、origin、异常信息。 | 覆盖的是 `solar_toolkit.coordinates`，对 radio 绘图流程只有间接保护。 | 坐标相关改动必须保留并扩展。 |
| `tests/test_radio_newkirk_extrapolation.py` | 99 | Newkirk round-trip、harmonic、drift speed、Gaussian 行过滤。 | 当前 import 写成 `scripts.radio.radio_newkirk_extrapolation`，而源码在 `scripts.radio.core.radio_newkirk_extrapolation`。 | 需要更新 import，或在 `scripts/radio/__init__.py` 提供兼容导出。 |
| `tests/test_radio_pipeline_modules.py` | 12 | 检查 refactored radio modules public API。 | 当前 import 写成 `from scripts.radio import radio_drift_rate, radio_gaussian_fit, radio_spectrogram`，但模块实际位于 `scripts.radio.core`。 | 需要更新测试或补兼容导出。 |

## 优化优先级建议

| 优先级 | 目标 | 涉及文件 | 判断标准 |
| --- | --- | --- | --- |
| P0 | 修正测试 import 路径或补兼容导出 | `tests/test_radio_newkirk_extrapolation.py`, `tests/test_radio_pipeline_modules.py`, `scripts/radio/__init__.py` | `pytest tests/test_radio_*.py` 至少能进入真实测试逻辑。 |
| P1 | 抽出低风险公共 helper | `legacy/radio_source_map_plot_gaussian_overlay.py`, `core/radio_gaussian_fit.py`, `core/radio_spectrogram.py`, `core/radio_drift_rate.py` | `core` 不再依赖 legacy 的时间解析、输出路径、诊断字段常量。 |
| P1 | 拆小 source-map orchestration | `legacy/radio_source_map_plot_gaussian_overlay.py`, `run_radio_source_map.py` | `run_radio_source_map.py` 调用明确的 callable，而不是整段 legacy `main()`。 |
| P2 | 收敛 AIA/HMI/radio Gaussian 重复实现 | `legacy/sdo_aia_radio_hmi_overlay.py`, `core/radio_gaussian_fit.py`, `examples/radio_aia_hmi/aia_radio_hmi_overlay_demo.py` | 同一输入下中心、FWHM、诊断标记与旧输出一致或差异有记录。 |
| P2 | 清理示例脚本 | `examples/radio_aia_hmi/*`, `examples/radio/*` | 唯一参数已记录，保留一个最小 demo，其他标为历史或迁出。 |
| P3 | 运行产物归位 | `scripts/radio/outputs/selections/*.json` | 明确是否纳入示例数据；否则迁到忽略路径或输出目录。 |

## 修改前检查清单

- 是否会改变坐标方向、extent、origin 或 WCS/reproject 行为？
- 是否会改变 Gaussian source mask、背景模型、阈值或质量标记？
- 是否会改变频谱时间窗、频率轴方向、降采样或手动选点坐标映射？
- 是否会改变输出文件名、输出目录或 CSV 字段？
- 是否有旧示例/论文图依赖当前默认参数？
- 修改后是否能运行对应测试，或至少完成 `compileall scripts/radio`？
