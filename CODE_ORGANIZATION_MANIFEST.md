# 项目代码整理清单

本文档记录当前仓库的脚本功能分类、运行环境事实、验证方式和推荐文件命名方案。本次整理只更新注释与文档，不实际重命名脚本文件。

## 环境与仓库

- 推荐环境：`solarphysics_env`（Miniforge）
- 解释器路径：`D:\miniforge3\envs\solarphysics_env\python.exe`
- 已验证 Python 版本：`Python 3.11.15`
- 当前 Git 远端：`https://github.com/YUCONG-28/python-for-solar-physics.git`
- 当前分支：`main`

核心依赖已在环境中存在，包括 `numpy`, `scipy`, `astropy`, `sunpy`, `matplotlib`, `pandas`, `reproject`, `scikit-image`, `PyYAML`, `tqdm`, `drms`, `PyQt5`, `opencv-python` 等。

## 功能分类与推荐文件名

### SDO/AIA 与 HMI

| 当前文件 | 推荐文件名 | 功能说明 |
| --- | --- | --- |
| `AIA.py` | `sdo_aia_euv_processor.py` | AIA EUV FITS 主处理流程，支持单波段、多波段拼图、ROI 和批量绘图。 |
| `aia_multipanel.py` | `sdo_aia_multichannel_panel.py` | AIA 多波段六联图。 |
| `AIA_difference_base.py` | `sdo_aia_base_difference.py` | AIA 基准差分成像。 |
| `AIA_difference_running.py` | `sdo_aia_running_difference.py` | AIA 运行差分成像。 |
| `AIA_Flux_data.py` | `sdo_aia_lightcurve_extraction.py` | AIA 光变/流量数据提取。 |
| `AIA_Flux_data_plot.py` | `sdo_aia_lightcurve_plot.py` | AIA 光变曲线绘制。 |
| `AIA_time_distance.py` | `sdo_aia_time_distance_diagram.py` | AIA 时间-距离图分析。 |
| `AIA_rename.py` | `sdo_aia_fits_rename.py` | AIA FITS 文件批量规范命名。 |
| `AIA_select_files.py` | `sdo_aia_time_file_selector.py` | 按目标时间筛选 AIA 文件。 |
| `HMI.py` | `sdo_hmi_magnetogram_plot.py` | HMI 磁图读取和绘制。 |
| `AIA_HMI.py` | `sdo_aia_hmi_overlay.py` | AIA 与 HMI 共配准叠加图。 |

### 射电数据

| 当前文件 | 推荐文件名 | 功能说明 |
| --- | --- | --- |
| `CSO_PLOT.py` | `cso_radio_spectrogram_plot.py` | CSO 动态频谱绘制，支持通道和降采样配置。 |
| `plot_cso_spectrogram.py` | `cso_spectrogram_class.py` | 可复用的 CSO 频谱绘图类。 |
| `csoSpectraGUIV09.py` | `cso_radio_spectra_gui.py` | CSO 射电频谱 GUI。 |
| `RS_plot.py` | `radio_source_map_plot.py` | 射电源图像/频谱绘制和高斯拟合。 |
| `AIA_RS.py` | `sdo_aia_radio_hmi_overlay.py` | AIA、射电源和可选 HMI 的综合叠加图。 |

### X 射线、DEM 与综合诊断

| 当前文件 | 推荐文件名 | 功能说明 |
| --- | --- | --- |
| `SXR.py` | `goes_sxr_lightcurve_plot.py` | GOES 软 X 射线光变绘图。 |
| `HXR.py` | `hessi_hxr_lightcurve_plot.py` | RHESSI/HESSI 风格硬 X 射线光变绘图。 |
| `HXI.py` | `asos_hxi_image_plot.py` | ASO-S/HXI 硬 X 射线图像读取与绘制。 |
| `HXI_SXR.py` | `asos_hxi_goes_sxr_comparison.py` | HXI 与 GOES SXR 时间序列对比。 |
| `AIA_HXI.py` | `sdo_aia_asos_hxi_overlay.py` | AIA 图像叠加 ASO-S/HXI 轮廓。 |
| `AIA_SXR_HXR_plot.py` | `flare_aia_sxr_hxr_summary_plot.py` | AIA、GOES SXR 和 HXR 三面板综合诊断图。 |
| `from SXR to HXR.py` | `neupert_sxr_derivative_hxr_comparison.py` | Neupert 效应：SXR 导数与 HXR 对比。 |
| `from SXR to HXR_finderro.py` | `neupert_timing_error_analysis.py` | Neupert 效应时序误差和相关性探索。 |
| `DEM.py` | `sdo_aia_dem_inversion.py` | AIA 多波段 DEM 反演。 |
| `DEM_RS.py` | `dem_radio_source_overlay.py` | DEM 诊断与射电源形态叠加。 |

### LASCO/CME 与工具

| 当前文件 | 推荐文件名 | 功能说明 |
| --- | --- | --- |
| `LASCO_data.py` | `soho_lasco_data_download.py` | 通过 Helioviewer 下载 LASCO 数据。 |
| `LOSCO_plot.py` | `soho_lasco_image_plot.py` | LASCO 基础图像绘制；建议后续修正历史拼写 `LOSCO`。 |
| `LASCO_difference_plot.py` | `soho_lasco_running_difference.py` | LASCO 运行差分 CME 成像。 |
| `M_V.py` | `image_sequence_to_video.py` | 图像序列转视频。 |
| `Gauss_method.py` | `gaussian_source_fitting.py` | 高斯源区拟合工具。 |
| `utils_solar.py` | `solar_analysis_utils.py` | 时间解析、文件排序、内存管理、配置和坐标辅助工具。 |

### 测试与开发脚本

| 当前文件 | 推荐文件名 | 功能说明 |
| --- | --- | --- |
| `test.py` | `dev_aia_radio_hmi_overlay.py` | 综合叠加流程开发脚本，不建议作为正式测试保留。 |
| `test_AIA_RS_0.py` | `test_aia_radio_overlay_variant0.py` | AIA-射电叠加测试变体。 |
| `test_AIA_RS_1.py` | `test_aia_radio_overlay_variant1.py` | AIA-射电叠加测试变体。 |
| `test_AIA_RS_3.py` | `test_aia_radio_hmi_overlay_extended.py` | AIA-射电-HMI 扩展叠加测试。 |
| `test_CSO.py` | `test_cso_spectrogram_processing.py` | CSO 频谱处理测试。 |
| `test_header.py` | `test_fits_header_metadata.py` | FITS 头信息和 map 元数据测试。 |
| `test_sun_contour.py` | `test_solar_limb_contour.py` | 日面轮廓提取测试。 |
| `test_time.py` | `test_observation_time_parsing.py` | 观测时间解析测试。 |

## 验证计划

建议在提交前运行：

```powershell
D:\miniforge3\envs\solarphysics_env\python.exe -m compileall -q .
D:\miniforge3\envs\solarphysics_env\python.exe test_time.py
D:\miniforge3\envs\solarphysics_env\python.exe -c "import solar_toolkit; print(solar_toolkit.__version__)"
```

`compileall` 只验证语法，不保证依赖本地观测数据的脚本可以完整运行。AIA、HMI、HXI、CSO、LASCO 等脚本通常需要对应 FITS/NetCDF 数据路径存在。

## 后续整理建议

1. 文件实际重命名应单独提交，并同步更新 README、脚本互相引用和历史运行说明。
2. 将正式测试逐步移动到 `tests/`，将探索性脚本移动到 `examples/` 或 `scripts/`。
3. 待边界稳定后，再把共享函数迁移到 `solar_toolkit/` 包内，并为公共 API 增加单元测试。
4. 对依赖本地数据路径的脚本补充配置文件示例，减少硬编码路径。
