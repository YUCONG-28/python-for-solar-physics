# 项目只读审计报告

生成日期：2026-05-22

> Current note (2026-05-30): this document is a historical architecture audit.
> The current README-facing AIA entrypoint is
> `scripts/aia_hmi/run_aia_euv_processor.py`, with
> `scripts/aia_hmi/sdo_aia_euv_processor.py` kept as a compatibility wrapper.
> The current tracked file list is authoritative in `docs/script_index.md`.
> Older rows below may mention pre-cleanup examples or scripts that have since
> been archived or removed.
审计范围：只读扫描当前仓库；未修改、删除、移动、重命名任何核心代码。仅新增本报告文件。

## 1. 项目总览

| 项目 | 结论 |
| --- | --- |
| 项目名称 | `solar-physics-toolkit`，README 中项目名为 `python-for-solar-physics` |
| 本地目录 | `<repo-root>` |
| 当前 Git 分支 | `main`，跟踪 `origin/main` |
| 审计前工作区状态 | 干净；`git status --short --branch` 显示 `## main...origin/main` |
| 最近提交 | `e531dbf Prepare project for research release` |
| Python 版本 | 系统 `python` 和 `py` 不在 PATH；可用解释器 `<python-in-solarphysics-env>` 为 Python 3.11.15 |
| 依赖定义 | 存在 `pyproject.toml`、`requirements.txt`；未发现 `environment.yml`；依赖偏向 conda/Miniforge + pip editable install |
| 打包状态 | `pyproject.toml` 只打包 `solar_toolkit*`，`scripts/` 仍是独立研究脚本 |
| 测试 | 存在轻量 pytest：路径配置、导入、AIA/HMI FITS 命名、时间解析 |
| 代码风格 | 配置 Black、Ruff、pre-commit，pre-commit 大文件阈值为 2000 KB |

项目主要用途总结：

1. 该项目是一个面向太阳物理多波段事件分析的 Python 工具包与脚本集合。
2. 核心研究对象包括 SDO/AIA EUV/UV 图像、SDO/HMI 磁场图、太阳射电源 FITS 图像、CSO 动态频谱、GOES SXR、HXR/HXI、DEM/Tb 和 SOHO/LASCO CME 图像。
3. 项目当前以“脚本工作流”为主，公共工具逐步迁移到 `solar_toolkit/` 包中。
4. 最成熟的功能是 AIA 图像处理、AIA 差分图、射电源图像绘制、射电高斯拟合、CSO 频谱绘制和 AIA/radio/HMI 叠加。
5. 项目支持生成论文/报告用 PNG 图、多波段拼图、频谱图、叠加图、诊断 CSV、手动频漂率选择 JSON、以及图片序列 MP4 视频。
6. 大多数科学数据不包含在仓库中，需要通过本地路径、脚本内默认参数或 `configs/paths.local.yaml` 指定。
7. 当前仓库已经有较完整的 README、脚本索引、路径配置说明和清理报告，但部分中文文档存在编码显示异常。
8. 主要风险集中在硬编码 Windows 绝对路径、配置分散、历史/示例脚本重复、坐标/WCS 方向处理敏感，以及根目录仍跟踪较大的输出图片。
9. 上传 GitHub 前建议优先清理输出资产策略、统一配置入口、稳定核心推荐入口。

## 2. 目录结构

### 2.1 完整项目树

```text
.
├── .github/
│   └── workflows/
│       └── ci.yml
├── .pytest_tmp/                      # 本地测试临时目录，不应上传
├── .ruff_cache/                      # Ruff 缓存，不应上传
├── .vscode/                          # 本地 IDE 配置，不建议作为核心发布内容
├── configs/
│   └── paths.example.yaml
├── docs/
│   ├── MAIN_FILES.md
│   ├── PROJECT_CLEANUP_REPORT.md
│   ├── assets/
│   │   ├── images/.gitkeep
│   │   └── videos/.gitkeep
│   ├── path_configuration.md
│   ├── project_structure.md
│   └── script_index.md
├── examples/
│   ├── README.md
│   ├── aia_hmi/
│   │   └── solar_limb_contour_example.py
│   ├── input/.gitkeep
│   ├── output/.gitkeep
│   ├── radio/
│   │   ├── cso_spectrogram_processing_example.py
│   │   └── fits_header_metadata_example.py
│   └── radio_aia_hmi/
│       ├── aia_radio_hmi_overlay_demo.py
│       ├── aia_radio_hmi_overlay_extended_example.py
│       ├── aia_radio_overlay_variant0_example.py
│       └── aia_radio_overlay_variant1_example.py
├── outputs/
│   └── README.md
├── scripts/
│   ├── aia_hmi/
│   │   ├── sdo_aia_base_difference.py
│   │   ├── sdo_aia_euv_processor.py
│   │   ├── sdo_aia_hmi_fits_rename.py
│   │   ├── sdo_aia_hmi_overlay.py
│   │   ├── sdo_aia_lightcurve_extraction.py
│   │   ├── sdo_aia_lightcurve_plot.py
│   │   ├── sdo_aia_multichannel_panel.py
│   │   ├── sdo_aia_running_difference.py
│   │   ├── sdo_aia_time_distance_diagram.py
│   │   ├── sdo_aia_time_file_selector.py
│   │   └── sdo_hmi_magnetogram_plot.py
│   ├── lasco_cme/
│   │   ├── soho_lasco_data_download.py
│   │   ├── soho_lasco_image_plot.py
│   │   └── soho_lasco_running_difference.py
│   ├── radio/
│   │   ├── cso_radio_spectra_gui.py
│   │   ├── cso_radio_spectrogram_plot.py
│   │   ├── cso_spectrogram_class.py
│   │   ├── radio_source_map_plot.py
│   │   ├── radio_source_map_plot_gaussian_overlay.py
│   │   ├── sdo_aia_radio_hmi_overlay.py
│   │   ├── sdo_aia_radio_hmi_overlay_bgcorrected.py
│   │   └── spectrogram_drift_rate_manual_selection.json
│   ├── tools/
│   │   ├── gaussian_source_fitting.py
│   │   └── image_sequence_to_video.py
│   └── xray_dem/
│       ├── asos_hxi_goes_sxr_comparison.py
│       ├── asos_hxi_image_plot.py
│       ├── dem_radio_source_overlay.py
│       ├── flare_aia_sxr_hxr_summary_plot.py
│       ├── goes_sxr_lightcurve_plot.py
│       ├── hessi_hxr_lightcurve_plot.py
│       ├── neupert_sxr_derivative_hxr_comparison.py
│       ├── neupert_timing_error_analysis.py
│       ├── sdo_aia_asos_hxi_overlay.py
│       └── sdo_aia_dem_inversion.py
├── solar_toolkit/
│   ├── __init__.py
│   ├── path_config.py
│   └── solar_analysis_utils.py
├── tests/
│   ├── test_aia_hmi_fits_rename.py
│   ├── test_imports.py
│   ├── test_observation_time_parsing.py
│   └── test_path_config.py
├── .automated-tool-conventions.md
├── .automated-tool.conf.yml
├── .automated-tool.model.settings.yml
├── .aiderignore
├── .gitignore
├── .pre-commit-config.yaml
├── AIA.xlsx
├── CHANGELOG.md
├── CITATION.cff
├── CODE_ORGANIZATION_MANIFEST.md
├── CONTRIBUTING.md
├── CSO.xlsx
├── HXR.png
├── LICENSE
├── PROJECT_OVERVIEW.md
├── README.md
├── SXR to HXR enhance.png
├── SXR to HXR.png
├── SXR.png
├── pyproject.toml
└── requirements.txt
```

### 2.2 主要文件夹作用

| 类型 | 路径 | 作用 | 建议 |
| --- | --- | --- | --- |
| 核心代码目录 | `solar_toolkit/` | 可打包的公共工具包：路径配置、太阳数据工具、元数据 | 后续优先承接可复用逻辑 |
| 脚本目录 | `scripts/` | 按科研工作流分类的可运行脚本 | README 推荐入口应集中到少数成熟脚本 |
| AIA/HMI 脚本 | `scripts/aia_hmi/` | AIA 绘图、差分、光变、HMI、命名整理 | 核心科学工作流之一 |
| 射电脚本 | `scripts/radio/` | CSO 频谱、射电源图、高斯拟合、AIA/radio/HMI 叠加 | 核心科学工作流之一 |
| X-ray/DEM 脚本 | `scripts/xray_dem/` | GOES/HXR/HXI/DEM/Tb 分析 | 多为上下文诊断脚本 |
| LASCO 脚本 | `scripts/lasco_cme/` | LASCO 下载、绘图、running difference | 含下载脚本，后续运行需谨慎 |
| 工具脚本 | `scripts/tools/` | 高斯拟合、图片序列转视频 | 可抽到包内或作为 CLI 工具 |
| 数据目录 | 无正式 `data/`；存在 `examples/input/` 占位 | 仓库不保存原始观测数据 | 继续保持只放 `.gitkeep` 或小型 mock data |
| 输出图片目录 | 根目录 PNG、`outputs/`、`docs/assets/images/` | 根目录已有输出图；`outputs/` 是说明；assets 用于 README | 根目录 PNG 需要人工确认是否迁入 `docs/assets/images/` |
| 临时文件目录 | `.pytest_tmp/`、`.ruff_cache/`、`.vscode/` | 本地缓存/IDE | 不上传或继续忽略 |
| 测试目录 | `tests/` | 轻量数据无关测试 | 保留并扩展 |
| 文档目录 | `docs/`、根目录 Markdown | README、脚本索引、结构、路径配置、清理报告 | 修复中文编码异常 |
| 配置目录 | `configs/`、`pyproject.toml`、`.pre-commit-config.yaml`、`.gitignore` | 路径模板、依赖、格式化、忽略规则 | 建议扩展统一科学参数配置 |

## 3. 主要 Python 文件清单

| 文件路径 | 文件作用 | 主要函数 / 类 | 核心文件 | 旧版本/备份可能 | 依赖外部数据 | 生成图片/视频 | 修改优先级 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `solar_toolkit/path_config.py` | 读取 `configs/paths.local.yaml` 或 `SOLAR_PHYSICS_CONFIG`，覆盖脚本默认参数 | `load_script_config`, `apply_config_to_object` | 是 | 否 | 否 | 否 | 高 |
| `solar_toolkit/solar_analysis_utils.py` | 时间解析、FITS 排序、AIA/HMI/WCS/内存/绘图通用工具 | `extract_time_from_filename`, `create_aia_submap`, `align_maps_to_reference`, `SolarDataConfig`, `SolarLogger` | 是 | 否 | 否 | 可辅助绘图 | 高 |
| `solar_toolkit/__init__.py` | 包元数据 | `__version__` | 是 | 否 | 否 | 否 | 低 |
| `scripts/aia_hmi/sdo_aia_euv_processor.py` | AIA 单波段、多波段拼图、base/running difference 主处理器 | `AIAConfig`, `process_aia_fits`, `build_parser`, `main` | 是 | 否 | 是，AIA FITS | 是 | 高 |
| `scripts/aia_hmi/sdo_aia_hmi_fits_rename.py` | AIA/HMI FITS 文件名规范化，支持 dry-run | `RenameDecision`, `RenameSummary`, `rename_fits_files`, `main` | 是 | 否 | 是，FITS 文件树 | 否 | 中 |
| `scripts/aia_hmi/sdo_aia_hmi_overlay.py` | AIA 图像叠加 HMI 磁场等值线 | 脚本式入口 | 是 | 可能较旧 | 是，AIA/HMI FITS | 是 | 中 |
| `scripts/aia_hmi/sdo_aia_base_difference.py` | AIA base difference 图像生成 | 脚本式入口 | 是 | 与主处理器重复 | 是，AIA FITS | 是 | 中 |
| `scripts/aia_hmi/sdo_aia_running_difference.py` | AIA running difference 图像生成 | 脚本式入口 | 是 | 与主处理器重复 | 是，AIA FITS | 是 | 中 |
| `scripts/aia_hmi/sdo_aia_multichannel_panel.py` | 多波段 AIA 同步面板 | `organize_aia_files`, `process_aia`, `plot_synced_aia` | 是 | 与主处理器部分重复 | 是，AIA FITS | 是 | 中 |
| `scripts/aia_hmi/sdo_aia_lightcurve_extraction.py` | 从 AIA FITS ROI 提取光变数据 | `process_fits_files`, `save_processed_data` | 中 | 否 | 是，AIA FITS | CSV | 中 |
| `scripts/aia_hmi/sdo_aia_lightcurve_plot.py` | 绘制 AIA 光变 CSV | `load_single_file`, `plot_multi_data`, `main` | 中 | 否 | 是，CSV | 是 | 中 |
| `scripts/aia_hmi/sdo_aia_time_distance_diagram.py` | AIA time-distance 示例 | 脚本式示例 | 中 | 示例/教学性质 | 是，SunPy/Fido 示例或 AIA 数据 | 是 | 低 |
| `scripts/aia_hmi/sdo_aia_time_file_selector.py` | 按目标时间筛选/复制 AIA 文件 | `filter_and_copy_aia_files` | 中 | 否 | 是，AIA 文件树 | 复制文件 | 中 |
| `scripts/aia_hmi/sdo_hmi_magnetogram_plot.py` | HMI 磁图绘制 | 脚本式入口 | 中 | 可能较旧 | 是，HMI FITS | 是 | 低 |
| `scripts/radio/radio_source_map_plot_gaussian_overlay.py` | 射电源多频图、高斯拟合、频谱面板、手动频漂率选择主脚本 | `build_config`, `GaussianFitResult`, `SpectrogramCache`, `DriftRateResult`, `main` | 是 | 否 | 是，radio FITS、CSO FITS | PNG、CSV、JSON | 高 |
| `scripts/radio/radio_source_map_plot.py` | 射电源单频/多频图基础版本 | `read_fits`, `calc_extent`, `TimeParser`, `main` | 是 | 可被高斯版本覆盖部分功能 | 是，radio FITS | 是 | 中 |
| `scripts/radio/sdo_aia_radio_hmi_overlay.py` | AIA/radio/HMI 叠加，含高斯重投影 | `Config`, `GaussianReprojectResult`, `process_aia_group` | 是 | 否 | 是，AIA/radio/HMI FITS | 是 | 高 |
| `scripts/radio/sdo_aia_radio_hmi_overlay_bgcorrected.py` | AIA/radio/HMI 背景扣除实验版 | `Config`, `fit_elliptical_gaussian_robust`, `write_fit_diagnostics_csv` | 候选核心 | 实验版 | 是 | PNG、CSV | 高 |
| `scripts/radio/cso_radio_spectrogram_plot.py` | CSO 动态频谱绘制，内存友好下采样 | `PlotConfig`, `LazySpectrogram`, `ConfigManager`, `process_and_plot` | 是 | 否 | 是，CSO FITS | 是 | 高 |
| `scripts/radio/cso_spectrogram_class.py` | 可复用 CSO 频谱类 | `spectrogram`, `readcso_spectrofits` | 中 | 与 GUI/示例重复 | 是，CSO FITS | 是 | 中 |
| `scripts/radio/cso_radio_spectra_gui.py` | PyQt5/pyqtgraph 交互式 CSO 频谱 GUI 和 type-II 拟合 | `dsrtSpecWindow`, `RadioTypeIIfit`, `spectrogram` | 中 | 遗留 GUI 风格 | 是，CSO/DSRT FITS | 可保存图/FITS | 中 |
| `scripts/radio/spectrogram_drift_rate_manual_selection.json` | 频漂率手动选择结果 | JSON 数据 | 否 | 结果文件 | 是，指向本地 FITS | 否 | 低 |
| `scripts/tools/gaussian_source_fitting.py` | 2D 椭圆高斯拟合工具 | `elliptical_gaussian_2d`, `fit_elliptical_gaussian` | 是 | 与 radio 脚本重复 | 否 | 否 | 高 |
| `scripts/tools/image_sequence_to_video.py` | 图片序列转 MP4，支持 ffmpeg/imageio/opencv fallback | `parse_timestamp`, `write_video_ffmpeg_stream`, `main` | 中 | 否 | 是，图片序列 | MP4 | 中 |
| `scripts/xray_dem/sdo_aia_dem_inversion.py` | DEM/Tb 数据在 AIA 坐标中显示 | `SolarMap`, `plot_tb`, `main` | 中 | 否 | 是，AIA FITS、`.npy` | 是 | 中 |
| `scripts/xray_dem/dem_radio_source_overlay.py` | DEM/Tb 与射电源叠加 | `SolarMap`, `find_matching_radio`, `plot_tb` | 中 | 否 | 是，AIA FITS、Tb `.npy`、radio FITS | 是 | 中 |
| `scripts/xray_dem/sdo_aia_asos_hxi_overlay.py` | AIA/HXI 叠加 | `convert_date` | 中 | 旧脚本式 | 是，AIA/HXI FITS | 是 | 低 |
| `scripts/xray_dem/asos_hxi_image_plot.py` | ASO-S/HXI 图像绘制 | `convert_date` | 中 | 旧脚本式 | 是，HXI FITS | 是 | 低 |
| `scripts/xray_dem/asos_hxi_goes_sxr_comparison.py` | HXI 与 GOES SXR 对比 | 脚本式入口 | 中 | 旧脚本式 | 是，HXI/GOES | 是 | 低 |
| `scripts/xray_dem/goes_sxr_lightcurve_plot.py` | GOES SXR 光变绘制 | 脚本式入口 | 中 | 旧脚本式 | 是，NetCDF | 是 | 低 |
| `scripts/xray_dem/hessi_hxr_lightcurve_plot.py` | HESSI/RHESSI/HXI 光变绘制 | `process_hxi_fits` | 中 | 旧脚本式 | 是，FITS | 是 | 低 |
| `scripts/xray_dem/flare_aia_sxr_hxr_summary_plot.py` | AIA/SXR/HXR 总结面板 | `load_sxr_data`, `load_hxi_data`, `plot_combined_data` | 中 | 否 | 是，CSV/NetCDF/FITS | 是 | 中 |
| `scripts/xray_dem/neupert_sxr_derivative_hxr_comparison.py` | Neupert 效应 SXR 导数与 HXR 对比 | `smooth_flux_data`, `calculate_derivative`, `visualize_results` | 中 | 否 | 是，GOES NetCDF | 是 | 中 |
| `scripts/xray_dem/neupert_timing_error_analysis.py` | Neupert 平滑/计时误差探索 | 脚本式入口 | 低 | 诊断脚本 | 是，GOES NetCDF | 可选 | 低 |
| `scripts/lasco_cme/soho_lasco_data_download.py` | Helioviewer 下载 LASCO JP2 | 脚本式入口 | 中 | 否 | 联网下载 | JP2 | 低 |
| `scripts/lasco_cme/soho_lasco_image_plot.py` | LASCO JP2 绘图 | 脚本式入口 | 中 | 否 | 是，JP2 | 是 | 低 |
| `scripts/lasco_cme/soho_lasco_running_difference.py` | LASCO running difference | `get_jp2_files`, `main` | 中 | 否 | 是，JP2 序列 | 是 | 低 |
| `examples/radio_aia_hmi/aia_radio_hmi_overlay_demo.py` | AIA/radio/HMI 叠加示例 | `Config`, 多个解析/重投影函数 | 否 | 示例/历史版 | 是 | 是 | 低 |
| `examples/radio_aia_hmi/aia_radio_hmi_overlay_extended_example.py` | 扩展叠加示例 | `Config`, `fit_elliptical_gaussian_*` | 否 | 示例/历史版 | 是 | 是 | 低 |
| `examples/radio_aia_hmi/aia_radio_overlay_variant0_example.py` | AIA/radio 单文件叠加变体 0 | `main`, `calculate_image_extent` | 否 | 变体/历史版 | 是 | 可选 | 低 |
| `examples/radio_aia_hmi/aia_radio_overlay_variant1_example.py` | AIA/radio 单文件叠加变体 1 | `main`, `calculate_image_extent` | 否 | 变体/历史版 | 是 | 可选 | 低 |
| `examples/radio/cso_spectrogram_processing_example.py` | CSO 频谱处理示例 | `spectrogram`, `process_and_plot_data` | 否 | 与正式脚本重复 | 是 | 是 | 低 |
| `examples/radio/fits_header_metadata_example.py` | FITS header 查看示例 | 脚本式示例 | 否 | 示例 | 是 | 否 | 低 |
| `examples/aia_hmi/solar_limb_contour_example.py` | 太阳边缘轮廓示例 | 脚本式示例 | 否 | 示例 | 是 | 是 | 低 |
| `tests/*.py` | 单元测试 | `test_*` | 是 | 否 | 仅临时/mock | 否 | 中 |

## 4. 核心功能模块分析

| 模块 | 相关文件 | 入口函数 | 输入数据 | 输出结果 | 完整性 | 潜在问题 | 优化方向 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SDO/AIA 图像读取与绘制 | `scripts/aia_hmi/sdo_aia_euv_processor.py`, `solar_toolkit/solar_analysis_utils.py` | `process_aia_fits`, `main` | AIA FITS，按波段目录组织 | 单波段 PNG、多波段 mosaic | 较完整 | 默认路径硬编码；脚本很长；配置项多 | 保留为 AIA 主入口，逐步拆出 plotting、I/O、config |
| AIA base/running difference | `sdo_aia_euv_processor.py`, `sdo_aia_base_difference.py`, `sdo_aia_running_difference.py` | 主处理器中的 difference workflow；旧脚本入口 | AIA FITS 序列 | 差分 PNG/mosaic | 主处理器较完整 | 旧脚本与主脚本重复；derotation/ROI 策略需文档化 | README 推荐主处理器；旧脚本标记为 legacy |
| HMI 磁场叠加 | `sdo_aia_hmi_overlay.py`, `sdo_aia_radio_hmi_overlay.py`, `solar_analysis_utils.py` | 脚本入口、`process_hmi_for_overlay` | HMI FITS、AIA FITS | 磁场等值线叠加图 | 可用 | HMI 时间匹配阈值有小时/秒混用风险；默认阈值较宽 | 统一 HMI 匹配函数和阈值单位 |
| 射电源图像叠加 | `radio_source_map_plot.py`, `radio_source_map_plot_gaussian_overlay.py`, `sdo_aia_radio_hmi_overlay.py` | `main`, `plot_single_band`, `plot_multi_band_slot`, `process_aia_group` | radio FITS、RR/LL 目录、频率目录 | 单频/多频射电源图、叠加图 | 较完整 | FITS WCS orientation 非常敏感；默认路径硬编码 | 把 WCS/extent/origin 转换集中到公共工具并加测试 |
| 高斯拟合 | `radio_source_map_plot_gaussian_overlay.py`, `scripts/tools/gaussian_source_fitting.py`, `sdo_aia_radio_hmi_overlay*.py` | `fit_elliptical_gaussian`, robust fit 函数 | 2D 强度图、坐标轴 | 中心、FWHM、残差、诊断 CSV | 功能强但重复 | 多处实现重复，质量阈值分散 | 统一使用 `scripts/tools/gaussian_source_fitting.py` 或迁入 `solar_toolkit` |
| 射电源中心轨迹 | `radio_source_map_plot_gaussian_overlay.py`, `sdo_aia_radio_hmi_overlay_bgcorrected.py` | 高斯诊断输出相关函数 | 连续 radio FITS | fitted center、raw peak、CSV | 部分完整 | 轨迹级汇总展示尚不明确 | 增加中心轨迹汇总脚本和 README 示例 |
| 频谱图绘制 | `cso_radio_spectrogram_plot.py`, `cso_spectrogram_class.py`, `cso_radio_spectra_gui.py` | `process_and_plot`, class plotting | CSO FITS | LL/RR/sum/ratio 频谱图 | 较完整 | class、GUI、示例重复；依赖 `rebin`/PyQt5 可选 | 以 `cso_radio_spectrogram_plot.py` 为 CLI 主入口 |
| 频漂率测量 | `radio_source_map_plot_gaussian_overlay.py`, `spectrogram_drift_rate_manual_selection.json` | `--select-drift`, `_run_select_drift_workflow` | CSO FITS、手动点击点 | JSON、preview PNG、diagnostic CSV、叠加线 | 较完整 | 会启动本地 HTTP/浏览器；结果 JSON 指向本地绝对路径 | 结果 JSON 放到 ignored output，README 用匿名示例 |
| 视频生成 | `scripts/tools/image_sequence_to_video.py` | `main` | PNG/JPG 序列 | MP4 | 完整 | 会生成大文件；ffmpeg/imageio/opencv fallback 多 | README 标注输出不入 Git |
| 配置参数管理 | `configs/paths.example.yaml`, `solar_toolkit/path_config.py`, 各脚本 dataclass/dict | `load_script_config`, `apply_config_to_object` | YAML、本地默认 | 运行参数覆盖 | 部分完整 | 科学参数仍大量散落在脚本中 | 新建统一 `configs/*.example.yaml` 分模块模板 |
| README/文档展示 | `README.md`, `docs/*`, `docs/assets/*` | 无 | Markdown、示例资产 | GitHub 展示 | 较完整 | 部分中文文档乱码；根目录图片未整理 | 修复编码，挑选小图迁入 assets |

## 5. 程序入口与运行方式

### 5.1 推荐主入口

| 推荐程度 | 文件 | 用途 | 推荐运行方式 |
| --- | --- | --- | --- |
| 首选 | `scripts/aia_hmi/sdo_aia_euv_processor.py` | AIA 单波段、多波段、差分图主流程 | `python scripts\aia_hmi\sdo_aia_euv_processor.py --mode test/single/mosaic ...` |
| 首选 | `scripts/radio/radio_source_map_plot_gaussian_overlay.py` | 射电多频图、高斯拟合、频谱面板、频漂率选择 | `python scripts\radio\radio_source_map_plot_gaussian_overlay.py` |
| 首选 | `scripts/radio/sdo_aia_radio_hmi_overlay.py` | AIA + radio + HMI 综合叠加图 | `python scripts\radio\sdo_aia_radio_hmi_overlay.py` |
| 首选 | `scripts/radio/cso_radio_spectrogram_plot.py` | CSO 动态频谱绘图 | `python scripts\radio\cso_radio_spectrogram_plot.py` |
| 工具 | `scripts/aia_hmi/sdo_aia_hmi_fits_rename.py` | AIA/HMI FITS 命名规范化，默认 dry-run | `python scripts\aia_hmi\sdo_aia_hmi_fits_rename.py <dir> --dry-run` |
| 工具 | `scripts/tools/image_sequence_to_video.py` | 图片序列转 MP4 | `python scripts\tools\image_sequence_to_video.py` |
| 工具 | `scripts/tools/gaussian_source_fitting.py` | 高斯拟合工具库 | 建议作为 import 使用 |

### 5.2 发现的入口类型

| 入口类型 | 发现情况 |
| --- | --- |
| `if __name__ == "__main__"` | 大多数脚本存在，包括 AIA、radio、xray_dem、LASCO、tools、examples |
| `main()` | `sdo_aia_euv_processor.py`, `sdo_aia_hmi_fits_rename.py`, `radio_source_map_plot.py`, `radio_source_map_plot_gaussian_overlay.py`, `image_sequence_to_video.py`, 多个 xray/DEM 脚本 |
| CLI 参数 | `sdo_aia_euv_processor.py` 最完整；`sdo_aia_hmi_fits_rename.py` 有 argparse；`radio_source_map_plot_gaussian_overlay.py` 支持 `--select-drift`, `--self-test` 等 |
| Notebook 入口 | 未发现 `.ipynb` |
| GUI 入口 | `scripts/radio/cso_radio_spectra_gui.py` 为 PyQt5 GUI；`radio_source_map_plot_gaussian_overlay.py` 的频漂率选择会开本地 HTTP 页面 |
| 配置文件入口 | `configs/paths.example.yaml` 可复制为 ignored 的 `configs/paths.local.yaml`；也可用 `SOLAR_PHYSICS_CONFIG` 指向外部 YAML |

推荐后续对外主运行文件：

1. AIA 图像与差分：`scripts/aia_hmi/sdo_aia_euv_processor.py`
2. 射电源图/高斯/频漂率：`scripts/radio/radio_source_map_plot_gaussian_overlay.py`
3. AIA/radio/HMI 叠加：`scripts/radio/sdo_aia_radio_hmi_overlay.py`
4. CSO 频谱：`scripts/radio/cso_radio_spectrogram_plot.py`

## 6. 配置参数整理

| 配置项 | 当前位置 | 作用 | 是否建议集中 |
| --- | --- | --- | --- |
| `selected_bands` | `sdo_aia_radio_hmi_overlay.py`, `sdo_aia_radio_hmi_overlay_bgcorrected.py` | 选择射电频率，如 `149MHz` 到 `238MHz` | 是 |
| AIA 波段 | `sdo_aia_euv_processor.py` 的 `AIA_CONFIG`, `AIAConfig.multi_band_wavelengths` | AIA `94/131/171/193/211/304/335/1600` | 是 |
| radio 频率列表 | `radio_source_map_plot*.py` 的 `multi_band_freqs` | 射电多频图频率 | 是 |
| colormap | `AIA_CONFIG`, `radio_cmap`, `aia_cmap`, `PlotConfig` | AIA/radio/CSO 色图 | 是 |
| `vmin` / `vmax` | AIA config、radio fixed/global/per-band、CSO manual limits | 图像动态范围 | 是 |
| percentile | AIA difference、radio per-band、CSO clipping、DEM/Tb | 自动拉伸范围 | 是 |
| RMS / peak 阈值 | `fit_snr_threshold`, `fit_peak_fraction_threshold`, `contour_levels_peak` | 源区掩膜、高斯质量、等值线 | 是 |
| 差分图参数 | `AIAConfig` 的 `difference_*` | base/running difference、derotation、vlim | 是 |
| 输出路径 | 多数脚本 `output_dir`, `save_path` | PNG/CSV/MP4 输出 | 是 |
| 是否绘制 HMI | `overlay_hmi`, `show_radio_contours`, HMI config | 控制 HMI 等值线 | 是 |
| 是否绘制射电源 | `show_radio_contours`, radio workflow config | 控制 radio contours/markers | 是 |
| 是否启用高斯拟合 | `gaussian_overlay`, `enable_gaussian_overlay` | 椭圆高斯拟合/覆盖 | 是 |
| 是否启用频漂率手动选择 | `drift_rate.enabled`, CLI flags | 本地交互式选点 | 是 |
| `max_workers` / 内存 | AIA、radio、CSO 脚本 | 并行处理与内存保护 | 是 |
| WCS/origin | `preserve_fits_wcs_orientation`, `radio_image_origin_mode`, `extent`, `origin` | 坐标方向和叠加正确性 | 强烈建议集中 |

当前配置分散状态：

- `configs/paths.example.yaml` 已覆盖多数路径和少量脚本参数。
- `solar_toolkit/path_config.py` 已提供统一加载机制。
- 但大量科学参数仍在脚本顶部的 `dataclass` 或 `dict` 中，例如 `AIAConfig`、`USER_CONFIG`、`DEFAULT_CONFIG`、`Config`、`PlotConfig`。
- 建议后续建立分模块配置模板，例如 `configs/aia.example.yaml`、`configs/radio.example.yaml`、`configs/cso.example.yaml`，并保留脚本内默认值作为 fallback。

## 7. 数据流说明

### 7.1 输入数据格式与路径规则

| 数据类型 | 期望格式 | 当前路径规则/例子 |
| --- | --- | --- |
| SDO/AIA | FITS，通常按波段目录分组 | `<root>/<year>/<date>/SDO/AIA/<wave>/*.fits`，文件名类似 `aia.lev1_euv_12s.2025-01-24T044810Z.171.image_lev1.fits` |
| SDO/HMI | FITS magnetogram | `AIA/hmi/1` 或 HMI 独立目录，文件名匹配 `hmi.M_45s` 或 `YYYYMMDD_HHMMSS_TAI` |
| 射电源图像 | FITS，按频率和偏振组织 | `<radio_root>/<freq>MHz/RR/*.fits`、`LL/*.fits`，常见频率 `149/164/190/205/223/238/285/309/324 MHz` |
| CSO 频谱 | FITS | `OROCH_MWRS01_SRSP_L1_05M_YYYYMMDDHHMMSS_V01.01.fits` |
| GOES SXR | NetCDF | `dn_xrsf-l2-flx1s_*.nc` |
| HXR/HXI | FITS | HXI QLD、image cube、HESSI/RHESSI 风格 FITS |
| DEM/Tb | `.npy` + AIA FITS | `Tb_149000000.0.npy` 等 |
| LASCO | JP2 | Helioviewer 下载的 LASCO C2 JP2 |
| 光变数据 | CSV/XLSX | AIA flux extraction 生成 CSV；根目录有 `AIA.xlsx`, `CSO.xlsx` |

### 7.2 输出文件说明

| 输出类型 | 当前规则/路径 | GitHub 建议 |
| --- | --- | --- |
| AIA PNG | 波段目录下 `plot/`，或 `<data_path>/multi_band`，差分图在 `difference` / `multi_band_difference` | 不上传完整输出；挑选压缩示例图放 `docs/assets/images/` |
| AIA/radio/HMI 叠加 PNG | 配置中的 `output_dir`，如 `AIA_RS_HMI/test` | 不上传批量输出 |
| 射电源图 PNG | `output_dir` 或 `multi_band_{polar}` 子目录 | 不上传批量输出 |
| CSO 频谱 PNG | `save_path` | 可保留少量 README 示例 |
| 高斯诊断 CSV | `radio_source_map_plot_gaussian_overlay.py` 输出目录 | 不建议上传完整运行结果 |
| 频漂率 JSON | `spectrogram_drift_rate_manual_selection.json` | 当前在 `scripts/radio/` 中，建议移到 ignored output 或改成匿名示例 |
| 频漂率 preview PNG | `spectrogram_drift_rate_selection_preview.png` | 仅 README 示例可保留压缩版 |
| 视频 MP4 | `image_sequence_to_video.py` 的 `output_dir/video_name` | 不上传大视频；README 可用短小压缩 demo |
| LASCO JP2/PNG | 本地 LASCO 数据/plot 目录 | 不上传原始 JP2 和批量 PNG |

不适合上传 GitHub 的内容：

- `*.fits`, `*.fts`, `*.fit`, `*.fits.gz`, `*.fits.fz`
- `*.npy`, `*.npz`, `*.nc`, `*.cdf`, `*.jp2`, `*.h5`, `*.hdf5`
- 批量 PNG/JPG 输出、MP4/AVI/MOV/GIF/MKV
- `outputs/generated/`, `output/`, `plots/`, `figures/`, `video/`, `videos/`
- 本地路径配置 `configs/paths.local.yaml`
- 本地缓存 `.pytest_tmp/`, `.ruff_cache/`, `__pycache__/`
- 个人 Excel/CSV 数据产物，除非已脱敏且明确用于示例

适合保留用于 README 的示例：

- 小尺寸 AIA 单波段示例图
- AIA running/base difference 对比图
- AIA/radio/HMI 叠加图
- CSO 动态频谱图
- radio Gaussian fitting 诊断图
- 短小压缩的 time-evolution 视频或 GIF，但需低于 pre-commit 大文件阈值并确认版权/数据政策

## 8. 重复/旧版本文件分析

| 文件 A | 文件 B | 相似原因 | 建议保留哪个 | 删除/合并风险 |
| --- | --- | --- | --- | --- |
| `scripts/aia_hmi/sdo_aia_base_difference.py` | `scripts/aia_hmi/sdo_aia_euv_processor.py` | 主处理器已包含 base difference | 保留 `sdo_aia_euv_processor.py` 为主入口 | 旧脚本可能有特定参数习惯，需人工确认 |
| `scripts/aia_hmi/sdo_aia_running_difference.py` | `scripts/aia_hmi/sdo_aia_euv_processor.py` | 主处理器已包含 running difference | 保留 `sdo_aia_euv_processor.py` 为主入口 | 旧脚本可能输出路径不同 |
| `scripts/aia_hmi/sdo_aia_multichannel_panel.py` | `scripts/aia_hmi/sdo_aia_euv_processor.py` | 都生成多波段 AIA 面板 | 主入口用 `sdo_aia_euv_processor.py`，保留 panel 脚本作 legacy | 多波段同步策略可能不同 |
| `scripts/radio/radio_source_map_plot.py` | `scripts/radio/radio_source_map_plot_gaussian_overlay.py` | 后者扩展了射电图、高斯、频谱、频漂率 | 保留高斯版为高级主入口；基础版保留为简化入口 | 基础版较简单，删除会影响低门槛使用 |
| `scripts/radio/sdo_aia_radio_hmi_overlay.py` | `scripts/radio/sdo_aia_radio_hmi_overlay_bgcorrected.py` | 背景扣除实验版基于叠加脚本扩展 | 暂保留正式版；实验版需验证后合并 | 背景扣除会改变科学结果，不能直接替换 |
| `scripts/tools/gaussian_source_fitting.py` | `radio_source_map_plot_gaussian_overlay.py` 内部高斯函数 | 重复的椭圆高斯模型与拟合函数 | 后续保留公共工具或迁入 `solar_toolkit` | 拟合质量控制和诊断字段需统一 |
| `scripts/tools/gaussian_source_fitting.py` | `sdo_aia_radio_hmi_overlay.py` 内部高斯函数 | 重复拟合实现 | 保留公共工具 | 坐标变换与拟合坐标单位需核对 |
| `cso_radio_spectrogram_plot.py` | `cso_spectrogram_class.py` | 都读取/绘制 CSO 频谱 | 保留 plot 脚本为主入口，class 作为可复用库 | class 可能被 GUI/示例依赖 |
| `cso_radio_spectra_gui.py` | `cso_spectrogram_class.py` / examples | 都有 `spectrogram` 类和读取逻辑 | GUI 保留为交互工具，读取逻辑后续复用统一类 | GUI 依赖 PyQt5/pyqtgraph，改动风险高 |
| `examples/radio_aia_hmi/*` | `scripts/radio/sdo_aia_radio_hmi_overlay.py` | 示例是历史/变体版叠加脚本 | 保留正式脚本；示例只保留精简 demo | 示例可能记录论文图参数 |
| `scripts/radio/spectrogram_drift_rate_manual_selection.json` | 运行输出目录中的应有 JSON | JSON 是手动运行结果而非源码 | 建议移到 `examples/` 示例或 ignored output | 可能是当前论文结果，需人工确认 |

文件名带 `test`、`tmp`、`old` 等：

- 正式测试目录 `tests/` 应保留。
- `examples/*variant*` 是变体示例，不建议自动删除。
- `.pytest_tmp/` 是临时目录，不应上传。
- 未发现文件名明确带 `old`、`backup`、`copy` 的核心脚本；`.gitignore` 已忽略 `backup_*` 和 `*.bak`。

## 9. 风险清单

| 风险 | 发现位置 | 影响 | 优先级 | 建议 |
| --- | --- | --- | --- | --- |
| Windows 绝对路径硬编码 | 多数脚本顶部，尤其 radio、xray_dem、configs 示例 | 他人无法直接运行，README 复现困难 | 高 | 路径全部经 `paths.local.yaml` 或 CLI 覆盖 |
| 坐标方向 / 上下翻转风险 | radio `extent`, `origin`, `preserve_fits_wcs_orientation`, DEM/Tb `origin="lower"` | 科学图像坐标可能错位或翻转 | 高 | 将 extent/origin 转换写成单元测试覆盖的公共函数 |
| AIA/HMI/radio 时间匹配阈值分散 | `radio_time_threshold`, `hmi_time_threshold`, time tolerance | 错配不同时间帧 | 高 | 统一单位、输出匹配诊断表 |
| 高斯拟合函数重复 | radio 主脚本、AIA/radio/HMI、tools | 不同脚本结果可能不一致 | 高 | 统一拟合核心与质量判据 |
| 根目录大图已被 Git 跟踪 | `HXR.png`, `SXR to HXR.png`, `SXR to HXR enhance.png` | 仓库膨胀，README 资产位置混乱 | 中 | 人工确认是否迁入 `docs/assets/images/` 并压缩 |
| `spectrogram_drift_rate_manual_selection.json` 跟踪在脚本目录 | `scripts/radio/` | 本地绝对路径进入仓库 | 中 | 改为示例 JSON 或移入 ignored output |
| 中文文档/注释编码异常 | `docs/MAIN_FILES.md`, `docs/PROJECT_CLEANUP_REPORT.md`, 部分脚本注释显示乱码 | GitHub 阅读体验差 | 中 | 统一 UTF-8 重新保存文档 |
| 可选 GUI/下载依赖 | `cso_radio_spectra_gui.py`, `soho_lasco_data_download.py` | 用户安装/运行失败或联网副作用 | 中 | README 标注 optional extras 与不要默认运行下载 |
| 裸 `except:` | 扫描未发现明显裸 `except:` 输出，但存在大量 broad exception 可能 | 隐藏错误 | 中 | 后续用 Ruff/人工 review 缩小异常范围 |
| 内存占用大循环 | AIA mosaic、radio multi-band、CSO FITS | 大 FITS 批处理可能占用高内存 | 中 | 默认 worker 保守，增加 dry-run/preview 模式 |
| 子图间距异常 | AIA mosaic、radio multi-band 有大量 manual layout 和 `subplots_adjust` | 图像白边、标签重叠 | 中 | 以截图/小样例回归测试布局 |
| 配置重复 | `AIA_CONFIG`, `USER_CONFIG`, `DEFAULT_CONFIG`, dataclass Config | 后续修改易漏 | 中 | 分模块配置模板 + 公共 schema |

## 10. GitHub 上传前检查

### 10.1 当前忽略规则评价

`.gitignore` 已覆盖：

- FITS/JP2/NetCDF/NumPy/HDF5 等科学数据
- 生成输出图像/视频目录
- Excel/CSV/SQLite 等本地结果
- Python 缓存、pytest/Ruff/mypy/cache
- `configs/paths.local.yaml`
- README assets 占位 `.gitkeep`

建议补充或确认：

- `spectrogram_drift_rate_manual_selection*.json` 是否应忽略，或改为 `*.example.json`
- `*_diagnostics.csv`、`*_selection_metadata.json`、`*_selection_preview.png`
- 根目录输出图片是否迁移后再忽略根目录 `*.png`，但需避免误伤 README 资产
- `solar_physics_toolkit.egg-info/` 若后续出现，应忽略

### 10.2 不建议上传的目录

- `.pytest_tmp/`
- `.ruff_cache/`
- `.vscode/`
- `outputs/generated/` 或任何真实输出子目录
- 真实数据目录：`data/`, `observations/`, `downloads/`
- 批处理产生的 `plot/`, `multi_band/`, `difference/`, `video/`

### 10.3 建议保留的示例目录

- `examples/`
- `examples/input/.gitkeep`
- `examples/output/.gitkeep`
- `docs/assets/images/.gitkeep`
- `docs/assets/videos/.gitkeep`
- 后续可放 1-5 个压缩、脱敏、可说明来源的展示资产

### 10.4 README 应展示的核心功能

1. AIA 单波段和多波段 mosaic。
2. AIA base/running difference。
3. AIA/HMI 磁场叠加。
4. 射电源多频图和 RR/LL/RR+LL 处理。
5. 射电高斯拟合、中心/FWHM/诊断 CSV。
6. CSO 动态频谱和频漂率手动选择。
7. GOES/HXR/DEM/LASCO 作为事件上下文诊断。
8. 本地路径配置和数据不入仓库政策。

### 10.5 大文件

当前仓库中超过 500 KB 的文件：

| 文件 | 大小 |
| --- | --- |
| `HXR.png` | 1,760,031 bytes |
| `SXR to HXR.png` | 1,722,957 bytes |
| `SXR to HXR enhance.png` | 1,150,783 bytes |

当前超过 1 MB 的文件：

- `HXR.png`
- `SXR to HXR.png`
- `SXR to HXR enhance.png`

pre-commit 的 `check-added-large-files --maxkb=2000` 阈值约 2 MB；上述文件低于 2 MB，但已接近大文件资产范围。后续若新增未压缩图片、视频或 FITS，可能触发检查或显著膨胀仓库。

## 11. 后续修改路线图

### 高优先级：影响正确性、坐标、科学结果

1. 统一 radio FITS 的 `extent/origin/CDELT` 坐标转换逻辑，并为正负 `CDELT2`、roundtrip、AIA/radio 叠加增加测试。
2. 统一高斯拟合核心函数、质量阈值、FWHM/中心/原始峰值诊断字段，避免不同脚本给出不同科学结果。
3. 统一 AIA/HMI/radio 时间匹配逻辑和单位，输出每张图使用的 AIA、radio、HMI 时间差诊断。

### 中优先级：影响维护性、项目结构、README 展示

1. 把硬编码本地路径从核心脚本迁移到 `configs/paths.local.yaml`、CLI 参数或示例配置中。
2. 明确推荐入口：AIA 用 `sdo_aia_euv_processor.py`，radio 用 `radio_source_map_plot_gaussian_overlay.py`，CSO 用 `cso_radio_spectrogram_plot.py`。
3. 修复 `docs/MAIN_FILES.md`、`docs/PROJECT_CLEANUP_REPORT.md` 和部分注释的 UTF-8 编码显示问题。
4. 整理根目录 PNG：确认是否为 README 示例，若保留则迁入 `docs/assets/images/` 并压缩。
5. 给 `scripts/radio/spectrogram_drift_rate_manual_selection.json` 定位：示例、结果、还是本地输出。
6. 将差分图、频谱图、射电叠加图的典型输出图加入 README 展示。

### 低优先级：命名、格式、注释、轻微重复

1. 把 `cso_spectrogram_class.py`、GUI 和示例中的重复 CSO 读取逻辑统一。
2. 为旧脚本添加 `legacy` 说明或迁入 `examples/legacy/`。
3. 清理脚本顶部过长注释和乱码注释，保留中文/英文一致说明。
4. 将小型通用函数从脚本迁入 `solar_toolkit/`。
5. 增加 `docs/assets/README.md`，说明 README 图片/视频尺寸和来源。

## 12. 最终结论

### 12.1 项目核心文件

核心包：

- `solar_toolkit/path_config.py`
- `solar_toolkit/solar_analysis_utils.py`
- `solar_toolkit/__init__.py`

核心工作流：

- `scripts/aia_hmi/sdo_aia_euv_processor.py`
- `scripts/radio/radio_source_map_plot_gaussian_overlay.py`
- `scripts/radio/sdo_aia_radio_hmi_overlay.py`
- `scripts/radio/cso_radio_spectrogram_plot.py`
- `scripts/tools/gaussian_source_fitting.py`

重要辅助：

- `scripts/aia_hmi/sdo_aia_hmi_fits_rename.py`
- `scripts/tools/image_sequence_to_video.py`
- `configs/paths.example.yaml`
- `README.md`
- `docs/script_index.md`
- `tests/`

### 12.2 后续最应该先修改的 3 个问题

1. 坐标一致性：radio FITS `extent/origin/WCS`、AIA/HMI/radio 叠加和上下翻转风险。
2. 配置集中化：把路径、频率、阈值、色标、输出目录从脚本硬编码迁到统一配置模板。
3. GitHub 展示资产和输出清理：处理根目录大图、手动选择 JSON、本地输出策略和 README 示例图。

### 12.3 暂时不要动的文件

- `scripts/radio/sdo_aia_radio_hmi_overlay_bgcorrected.py`：实验版，可能包含未验证但重要的背景扣除逻辑。
- `scripts/radio/spectrogram_drift_rate_manual_selection.json`：可能是手动选点结果，需人工确认用途。
- 根目录 `HXR.png`, `SXR.png`, `SXR to HXR.png`, `SXR to HXR enhance.png`：可能是论文/README 展示图，先确认再迁移或删除。
- `AIA.xlsx`, `CSO.xlsx`：可能是科研表格或中间数据，先确认来源和用途。
- `examples/radio_aia_hmi/*`：可能保留历史参数和论文图复现线索。

### 12.4 可能可合并或删除但需要人工确认

- `sdo_aia_base_difference.py` 和 `sdo_aia_running_difference.py` 可并入 `sdo_aia_euv_processor.py` 的文档化入口。
- `radio_source_map_plot.py` 可作为简化版保留，也可逐步由 `radio_source_map_plot_gaussian_overlay.py` 覆盖。
- `cso_spectrogram_class.py`、`cso_radio_spectra_gui.py`、CSO 示例中的读取逻辑可合并。
- 多处 `fit_elliptical_gaussian` 可统一到公共工具。
- `examples/radio_aia_hmi/aia_radio_overlay_variant0_example.py` 与 `variant1_example.py` 功能相近，可保留一个精简示例。
