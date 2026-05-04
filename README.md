# Python for Solar Physics

本仓库是一个面向太阳物理事件分析的 Python 脚本集合，用于处理和绘制 SDO/AIA、SDO/HMI、GOES、ASO-S/HXI、CSO 射电和 SOHO/LASCO 等多波段观测数据。项目当前采用“独立脚本 + 共享工具包”的结构：科研脚本按功能放在 `scripts/`，可复用工具放在 `solar_toolkit/`。

GitHub 仓库：<https://github.com/YUCONG-28/python-for-solar-physics>

## 运行环境

推荐使用 Miniforge 环境 `solarphysics_env`：

```powershell
conda activate solarphysics_env
D:\miniforge3\envs\solarphysics_env\python.exe --version
```

本机验证解释器为 `Python 3.11.15`。核心依赖包括 `numpy`, `scipy`, `astropy`, `sunpy`, `matplotlib`, `pandas`, `reproject`, `scikit-image`, `PyYAML`, `tqdm`, `drms`, `PyQt5`, `opencv-python` 等。

如需按项目元数据安装基础依赖：

```powershell
D:\miniforge3\envs\solarphysics_env\python.exe -m pip install -e .
```

## 目录结构

```text
scripts/
  aia_hmi/      SDO/AIA 与 SDO/HMI 成像、差分、光变、时间-距离和叠加脚本
  radio/        CSO 动态频谱、射电源图、AIA/射电/HMI 综合叠加脚本
  xray_dem/     GOES SXR、HXR、ASO-S/HXI、DEM 和多波段综合诊断脚本
  lasco_cme/    SOHO/LASCO 下载、绘图和 CME 差分成像脚本
  tools/        通用工具，例如图像序列转视频和高斯拟合
  dev_tests/    历史开发验证脚本，不作为正式 pytest 测试入口
solar_toolkit/
  solar_analysis_utils.py  共享时间解析、文件排序、内存管理和坐标辅助函数
  path_config.py           可选本地路径配置加载器
configs/
  paths.example.yaml       本地数据路径配置模板
```

## 主要脚本

### SDO/AIA 与 HMI

| 文件 | 功能 |
| --- | --- |
| `scripts/aia_hmi/sdo_aia_euv_processor.py` | AIA EUV FITS 批处理，支持单波段、多波段拼图、ROI 和并行绘图。 |
| `scripts/aia_hmi/sdo_aia_multichannel_panel.py` | AIA 多波段六联图。 |
| `scripts/aia_hmi/sdo_aia_base_difference.py` | AIA 基准差分成像。 |
| `scripts/aia_hmi/sdo_aia_running_difference.py` | AIA 运行差分成像。 |
| `scripts/aia_hmi/sdo_aia_lightcurve_extraction.py` | 从 AIA 图像序列提取光变/流量数据。 |
| `scripts/aia_hmi/sdo_aia_lightcurve_plot.py` | 绘制 AIA 光变曲线。 |
| `scripts/aia_hmi/sdo_aia_time_distance_diagram.py` | 生成 AIA 时间-距离图。 |
| `scripts/aia_hmi/sdo_aia_fits_rename.py` | 批量规范化 AIA FITS 文件名。 |
| `scripts/aia_hmi/sdo_aia_time_file_selector.py` | 按目标时间筛选 AIA 文件。 |
| `scripts/aia_hmi/sdo_hmi_magnetogram_plot.py` | 读取和绘制 SDO/HMI 磁图。 |
| `scripts/aia_hmi/sdo_aia_hmi_overlay.py` | AIA 与 HMI 共配准叠加。 |

### 射电数据

| 文件 | 功能 |
| --- | --- |
| `scripts/radio/cso_radio_spectrogram_plot.py` | 绘制 CSO 动态频谱，支持通道选择和降采样。 |
| `scripts/radio/cso_spectrogram_class.py` | 可复用的 CSO 频谱绘图类。 |
| `scripts/radio/cso_radio_spectra_gui.py` | CSO 射电频谱交互式 GUI。 |
| `scripts/radio/radio_source_map_plot.py` | 射电源图像/频谱处理、绘图和高斯拟合。 |
| `scripts/radio/sdo_aia_radio_hmi_overlay.py` | AIA、射电源和可选 HMI 的综合叠加图。 |

### X 射线、DEM 与综合诊断

| 文件 | 功能 |
| --- | --- |
| `scripts/xray_dem/goes_sxr_lightcurve_plot.py` | GOES 软 X 射线 NetCDF 光变绘图。 |
| `scripts/xray_dem/hessi_hxr_lightcurve_plot.py` | RHESSI/HESSI 风格硬 X 射线光变绘图。 |
| `scripts/xray_dem/asos_hxi_image_plot.py` | ASO-S/HXI FITS 图像读取和绘图。 |
| `scripts/xray_dem/asos_hxi_goes_sxr_comparison.py` | ASO-S/HXI 与 GOES SXR 时间序列对比。 |
| `scripts/xray_dem/sdo_aia_asos_hxi_overlay.py` | AIA 图像叠加 HXI 硬 X 射线轮廓。 |
| `scripts/xray_dem/flare_aia_sxr_hxr_summary_plot.py` | AIA、GOES SXR 和 HXR 三面板诊断图。 |
| `scripts/xray_dem/neupert_sxr_derivative_hxr_comparison.py` | Neupert 效应分析：SXR 导数与 HXR 对比。 |
| `scripts/xray_dem/neupert_timing_error_analysis.py` | Neupert 效应时序误差/相关性探索。 |
| `scripts/xray_dem/sdo_aia_dem_inversion.py` | 基于 AIA 多波段数据的 DEM 反演。 |
| `scripts/xray_dem/dem_radio_source_overlay.py` | DEM 诊断与射电源形态叠加。 |

### LASCO/CME 与工具

| 文件 | 功能 |
| --- | --- |
| `scripts/lasco_cme/soho_lasco_data_download.py` | 通过 Helioviewer 下载 SOHO/LASCO 数据。 |
| `scripts/lasco_cme/soho_lasco_image_plot.py` | 基础 LASCO 图像绘制。 |
| `scripts/lasco_cme/soho_lasco_running_difference.py` | LASCO 运行差分图像，用于 CME 前沿追踪。 |
| `scripts/tools/image_sequence_to_video.py` | 将图像序列合成为视频。 |
| `scripts/tools/gaussian_source_fitting.py` | 一维/二维高斯源区拟合工具。 |

## 本地路径配置

依赖本地观测数据的脚本支持可选 YAML 配置。没有配置文件时，脚本继续使用文件内默认路径。

```powershell
Copy-Item configs\paths.example.yaml configs\paths.local.yaml
notepad configs\paths.local.yaml
```

也可以通过环境变量指定其它配置文件：

```powershell
$env:SOLAR_PHYSICS_CONFIG="D:\my_project\solar_paths.yaml"
```

配置文件按脚本名分段，例如：

```yaml
scripts:
  sdo_aia_euv_processor:
    data_path: D:\solar_data\AIA
    output_dir: D:\solar_output\AIA
```

`configs/paths.local.yaml` 已加入 `.gitignore`，用于保存个人数据路径。

## 运行示例

```powershell
# AIA 多波段/批处理绘图
D:\miniforge3\envs\solarphysics_env\python.exe scripts\aia_hmi\sdo_aia_euv_processor.py

# CSO 动态频谱绘图
D:\miniforge3\envs\solarphysics_env\python.exe scripts\radio\cso_radio_spectrogram_plot.py

# Neupert 效应 SXR-HXR 对比
D:\miniforge3\envs\solarphysics_env\python.exe scripts\xray_dem\neupert_sxr_derivative_hxr_comparison.py

# AIA 与 HXI 叠加
D:\miniforge3\envs\solarphysics_env\python.exe scripts\xray_dem\sdo_aia_asos_hxi_overlay.py

# 历史时间解析验证脚本
D:\miniforge3\envs\solarphysics_env\python.exe scripts\dev_tests\test_observation_time_parsing.py
```

## 数据与输出约定

- 大型观测数据如 `*.fits`, `*.fits.gz`, `*.fits.fz` 默认不纳入 Git。
- 生成图像、视频、表格和缓存文件通常可由脚本重建，应放在本地数据或输出目录中。
- 新增个人路径配置请写入 `configs/paths.local.yaml` 或环境变量指定的 YAML 文件，不要提交个人路径配置。
- 历史 `test_*.py` 已移入 `scripts/dev_tests/`，用于开发验证；正式自动化测试后续可单独迁入 `tests/`。

## 验证

```powershell
D:\miniforge3\envs\solarphysics_env\python.exe -m compileall -q .
D:\miniforge3\envs\solarphysics_env\python.exe scripts\dev_tests\test_observation_time_parsing.py
D:\miniforge3\envs\solarphysics_env\python.exe -c "from solar_toolkit import solar_analysis_utils; import solar_toolkit; print(solar_toolkit.__version__)"
```

部分脚本依赖真实观测数据路径，不能脱离本地数据直接完整运行。

## License

本项目采用 MIT License，详见 `LICENSE`。

## Citation

Li, Y. (2025). *Python for Solar Physics: Multi-wavelength Data Processing Toolkit*. Shandong University. <https://github.com/YUCONG-28/python-for-solar-physics>
