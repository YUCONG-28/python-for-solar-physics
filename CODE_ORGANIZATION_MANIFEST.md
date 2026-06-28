# 项目代码整理清单

本文档记录本次实际执行后的文件命名、功能分类、配置化入口和验证方式。旧的根目录脚本已按功能移动到 `scripts/`，共享工具已迁入 `solar_toolkit/`。

## 当前结构

- `scripts/aia_hmi/`：SDO/AIA 与 SDO/HMI 成像、差分、光变、时间-距离和叠加脚本。
- `scripts/radio/`：CSO 动态频谱、射电源图和 AIA/射电/HMI 综合叠加脚本。
- `solar_toolkit/radio/`：射电工作流中已迁移的可复用 Gaussian、Newkirk、坐标、I/O、quicklook 和诊断辅助模块。
- `scripts/radio/core/`：旧导入兼容层，并继续承载尚未迁移的频漂、频谱等模块。
- `scripts/xray_dem/`：GOES SXR、HXR、ASO-S/HXI、DEM 和综合诊断脚本。
- `scripts/lasco_cme/`：SOHO/LASCO 下载、绘图和 CME 差分成像脚本。
- `scripts/tools/`：通用工具脚本。
- `examples/`：依赖本地观测数据的历史开发验证脚本和示例工作流；其中 `examples/gaussian_newkirk_quicklook/` 是薄 CLI 示例，核心逻辑位于 `solar_toolkit.radio.quicklook`。
- `tests/`：不依赖本地观测数据的轻量 pytest 测试。
- `solar_toolkit/solar_analysis_utils.py`：共享时间解析、文件排序、内存管理和坐标辅助函数。
- `solar_toolkit/path_config.py`：可选本地 YAML 路径配置加载器。
- `configs/paths.example.yaml`：路径配置模板；个人配置写入 `configs/paths.local.yaml`。

## 迁移表

### SDO/AIA 与 HMI

| 旧文件 | 当前文件 | 功能说明 |
| --- | --- | --- |
| `AIA.py` | `scripts/aia_hmi/sdo_aia_euv_processor.py` | AIA EUV FITS 主处理流程，支持单波段、多波段拼图、ROI 和批量绘图。 |
| `aia_multipanel.py` | `scripts/aia_hmi/sdo_aia_multichannel_panel.py` | AIA 多波段六联图。 |
| `AIA_difference_base.py` | `scripts/aia_hmi/sdo_aia_base_difference.py` | AIA 基准差分成像。 |
| `AIA_difference_running.py` | `scripts/aia_hmi/sdo_aia_running_difference.py` | AIA 运行差分成像。 |
| `AIA_Flux_data.py` | `scripts/aia_hmi/sdo_aia_lightcurve_extraction.py` | AIA 光变/流量数据提取。 |
| `AIA_Flux_data_plot.py` | `scripts/aia_hmi/sdo_aia_lightcurve_plot.py` | AIA 光变曲线绘制。 |
| `AIA_time_distance.py` | `scripts/aia_hmi/sdo_aia_time_distance_diagram.py` | AIA 时间-距离图分析。 |
| `AIA_rename.py` | `scripts/aia_hmi/sdo_aia_hmi_fits_rename.py` | AIA/HMI FITS 文件批量规范命名。 |
| `AIA_select_files.py` | `scripts/aia_hmi/sdo_aia_time_file_selector.py` | 按目标时间筛选 AIA 文件。 |
| `HMI.py` | `scripts/aia_hmi/sdo_hmi_magnetogram_plot.py` | HMI 磁图读取和绘制。 |
| `AIA_HMI.py` | `scripts/aia_hmi/sdo_aia_hmi_overlay.py` | AIA 与 HMI 共配准叠加图。 |

### 射电数据

| 旧文件 | 当前文件 | 功能说明 |
| --- | --- | --- |
| `CSO_PLOT.py` | `scripts/radio/cso_radio_spectrogram_plot.py` | CSO 动态频谱绘制，支持通道和降采样配置。 |
| `plot_cso_spectrogram.py` | `scripts/radio/cso_spectrogram_class.py` | 可复用的 CSO 频谱绘图类。 |
| `csoSpectraGUIV09.py` | `scripts/radio/cso_radio_spectra_gui.py` | CSO 射电频谱 GUI。 |
| `RS_plot.py` | `scripts/radio/radio_source_map_plot.py` | 射电源图像/频谱绘制和高斯拟合。 |
| `AIA_RS.py` | `scripts/radio/sdo_aia_radio_hmi_overlay.py` | AIA、射电源和可选 HMI 的综合叠加图。 |

### X 射线、DEM 与综合诊断

| 旧文件 | 当前文件 | 功能说明 |
| --- | --- | --- |
| `SXR.py` | `scripts/xray_dem/goes_sxr_lightcurve_plot.py` | GOES 软 X 射线光变绘图。 |
| `HXR.py` | `scripts/xray_dem/hessi_hxr_lightcurve_plot.py` | RHESSI/HESSI 风格硬 X 射线光变绘图。 |
| `HXI.py` | `scripts/xray_dem/asos_hxi_image_plot.py` | ASO-S/HXI 硬 X 射线图像读取与绘制。 |
| `HXI_SXR.py` | `scripts/xray_dem/asos_hxi_goes_sxr_comparison.py` | HXI 与 GOES SXR 时间序列对比。 |
| `AIA_HXI.py` | `scripts/xray_dem/sdo_aia_asos_hxi_overlay.py` | AIA 图像叠加 ASO-S/HXI 轮廓。 |
| `AIA_SXR_HXR_plot.py` | `scripts/xray_dem/flare_aia_sxr_hxr_summary_plot.py` | AIA、GOES SXR 和 HXR 三面板综合诊断图。 |
| `from SXR to HXR.py` | `scripts/xray_dem/neupert_sxr_derivative_hxr_comparison.py` | Neupert 效应：SXR 导数与 HXR 对比。 |
| `from SXR to HXR_finderro.py` | `scripts/xray_dem/neupert_timing_error_analysis.py` | Neupert 效应时序误差和相关性探索。 |
| `DEM.py` | `scripts/xray_dem/sdo_aia_dem_inversion.py` | AIA 多波段 DEM 反演。 |
| `DEM_RS.py` | `scripts/xray_dem/dem_radio_source_overlay.py` | DEM 诊断与射电源形态叠加。 |

### LASCO/CME 与工具

| 旧文件 | 当前文件 | 功能说明 |
| --- | --- | --- |
| `LASCO_data.py` | `scripts/lasco_cme/soho_lasco_data_download.py` | 通过 Helioviewer 下载 LASCO 数据。 |
| `LOSCO_plot.py` | `scripts/lasco_cme/soho_lasco_image_plot.py` | LASCO 基础图像绘制，并修正历史拼写。 |
| `LASCO_difference_plot.py` | `scripts/lasco_cme/soho_lasco_running_difference.py` | LASCO 运行差分 CME 成像。 |
| `M_V.py` | `scripts/tools/image_sequence_to_video.py` | 图像序列转视频。 |
| `Gauss_method.py` | `scripts/tools/gaussian_source_fitting.py` | 高斯源区拟合工具。 |
| `utils_solar.py` | `solar_toolkit/solar_analysis_utils.py` | 时间解析、文件排序、内存管理、配置和坐标辅助工具。 |

### 示例与测试迁移

| 旧文件 | 当前文件 | 功能说明 |
| --- | --- | --- |
| `test.py` | `examples/radio_aia_hmi/aia_radio_hmi_overlay_demo.py` | 综合叠加流程开发示例。 |
| `test_AIA_RS_0.py` | `examples/radio_aia_hmi/aia_radio_overlay_variant0_example.py` | AIA-射电叠加示例变体。 |
| `test_AIA_RS_1.py` | `examples/radio_aia_hmi/aia_radio_overlay_variant1_example.py` | AIA-射电叠加示例变体。 |
| `test_AIA_RS_3.py` | `examples/radio_aia_hmi/aia_radio_hmi_overlay_extended_example.py` | AIA-射电-HMI 扩展示例。 |
| `test_CSO.py` | `examples/radio/cso_spectrogram_processing_example.py` | CSO 频谱处理示例。 |
| `test_header.py` | `examples/radio/fits_header_metadata_example.py` | FITS 头信息和 map 元数据示例。 |
| `test_sun_contour.py` | `examples/aia_hmi/solar_limb_contour_example.py` | 日面轮廓提取示例。 |
| `test_time.py` | `tests/test_observation_time_parsing.py` | 观测时间解析正式轻量测试。 |
| `examples/gaussian_newkirk_quicklook/test_quicklook_gaussian_newkirk.py` | `tests/test_radio_quicklook.py` | Gaussian/Newkirk quicklook 的正式轻量测试，使用 synthetic CSV，不要求本机观测数据存在。 |

## 路径配置

依赖本地观测数据路径的脚本已接入 `solar_toolkit.path_config.load_script_config` 或 `apply_config_to_object`。读取顺序为：脚本内默认值，然后用 `configs/paths.local.yaml` 或环境变量 `SOLAR_PHYSICS_CONFIG` 指向的 YAML 文件覆盖。

`configs/paths.local.yaml` 已加入 `.gitignore`。提交仓库时只保留 `configs/paths.example.yaml`。

## 验证命令

```powershell
D:\miniforge3\envs\solarphysics_env\python.exe -m compileall -q solar_toolkit scripts tests examples
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD="1"; D:\miniforge3\envs\solarphysics_env\python.exe -m pytest -q tests
D:\miniforge3\envs\solarphysics_env\python.exe -m ruff check solar_toolkit scripts tests examples
D:\miniforge3\envs\solarphysics_env\python.exe -c "from solar_toolkit import solar_analysis_utils; import solar_toolkit; print(solar_toolkit.__version__)"
```

`compileall` 只验证语法，不保证依赖本地观测数据的脚本可以完整运行。
