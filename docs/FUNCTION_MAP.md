# Function Map / 功能地图

This map records the intended public boundaries after the Astropy/SunPy-style
cleanup. It separates stable library imports from runnable research scripts and
from compatibility paths that are kept for local reproducibility.

本文件记录参照 Astropy/SunPy 风格整理后的公共边界：稳定库层、可运行科研脚本
以及为本地复现保留的兼容路径。

## Public Library Layer / 公共库层

| Package | Responsibility | 中文说明 |
| --- | --- | --- |
| `solar_toolkit.aia` | SDO/AIA configuration, FITS selection, difference-image helpers, mosaics, and lazy EUV processing. | AIA 配置、FITS 选择、差分图、多波段拼图与延迟加载的 EUV 处理入口。 |
| `solar_toolkit.hmi` | HMI-facing helpers and facades for magnetogram, FITS renaming, and AIA/HMI overlay workflows. | HMI 磁图、FITS 规范命名和 AIA/HMI 叠加流程的公共边界。 |
| `solar_toolkit.radio` | Radio coordinates, threshold/contour center extraction, Gaussian fitting, trajectory table normalization, Newkirk models, spectrogram overlays, drift products, raw quality checks, and quicklook helpers. | 射电坐标、阈值/等值线中心提取、Gaussian 拟合、轨迹表规范化、Newkirk 模型、频谱叠加、漂移率产品、原始数据质量检查和 quicklook。 |
| `solar_toolkit.xray_dem` | Public namespace for GOES/HXR/HXI/DEM helpers that are still mostly script-backed. | GOES、HXR/HXI、DEM 相关辅助逻辑的公共命名空间，当前主要由脚本承载。 |
| `solar_toolkit.cme` | Public namespace for LASCO/CME helpers. | LASCO/CME 相关辅助逻辑的公共命名空间。 |
| `solar_toolkit.net` | Archive query and download helper namespace. | 数据归档查询与下载辅助逻辑命名空间。 |
| `solar_toolkit.modeling` | Shared science-model boundary for Gaussian and density-model helpers. | 高斯模型、密度模型等共享科学模型边界。 |
| `solar_toolkit.visualization` | Shared plotting, media-generation, local image-sequence viewer, video export, and interactive HTML visualization namespace. | 可复用绘图、视频/媒体生成、本地图片序列查看器、视频导出和交互式 HTML 可视化命名空间。 |

## Runnable Entrypoints / 可运行入口

| Entrypoint | Calls Into | Purpose |
| --- | --- | --- |
| `scripts/aia_hmi/run_aia_euv_processor.py` | `solar_toolkit.aia.cli` | Recommended AIA EUV processor entrypoint. |
| `scripts/radio/run_radio_burst_pipeline.py` | `solar_toolkit.radio` plus compatibility workflows | Full radio burst analysis pipeline. |
| `scripts/radio/run_radio_source_map.py` | `scripts.radio.legacy.radio_source_map_plot_gaussian_overlay` | Compatibility source-map runner. |
| `scripts/radio/extract_radio_centers.py` | `solar_toolkit.radio.centers` | Threshold/contour radio-source center extraction to CSV/XLSX. |
| `scripts/radio/run_radio_source_app.py` | `solar_toolkit.radio.trajectory`, `solar_toolkit.aia.background`, `solar_toolkit.visualization.radio_source_trajectory` | Streamlit playback frontend for radio-source trajectories with optional AIA background. |
| `scripts/radio/export_radio_source_trajectory.py` | `solar_toolkit.radio.trajectory`, `solar_toolkit.aia.background`, `solar_toolkit.visualization.radio_source_trajectory` | Static Plotly HTML export for selected trajectory frames. |
| `scripts/radio/run_aia_radio_hmi_overlay.py` | `scripts.radio.legacy.sdo_aia_radio_hmi_overlay` | Compatibility AIA/radio/HMI overlay runner. |
| `scripts/radio/run_radio_raw_quality.py` | `solar_toolkit.radio.raw_quality` | Raw radio FITS quality diagnostics. |
| `scripts/tools/run_image_web_viewer.py` | `solar_toolkit.visualization.image_web_viewer` | Local multi-folder image-sequence browser with synchronized playback, ROI review, and composite/separate MP4 export. |

## Compatibility Policy / 兼容策略

- Historical `scripts.radio.core.*` imports remain aliases of the matching
  `solar_toolkit.radio.*` modules when the reusable implementation has moved.
- Historical `scripts.aia_hmi.core.*` imports remain aliases of the matching
  `solar_toolkit.aia.*` modules.
- Large legacy workflows are not deleted in this cleanup. They stay runnable
  until output-equivalence checks with real observation data justify a separate
  removal or deprecation step.
- New reusable code should import from `solar_toolkit.*`. Thin scripts may keep
  user-facing command-line behavior and local path configuration.

兼容要求：

- 已迁移的 `scripts.radio.core.*` 旧导入继续别名到对应的 `solar_toolkit.radio.*`。
- 已迁移的 `scripts.aia_hmi.core.*` 旧导入继续别名到对应的 `solar_toolkit.aia.*`。
- 本轮不删除大型 legacy 工作流；只有在真实观测数据输出等价确认后，才单独处理删除或弃用。
- 新的可复用代码优先从 `solar_toolkit.*` 导入；脚本层只保留命令行、配置加载和本地路径处理。
