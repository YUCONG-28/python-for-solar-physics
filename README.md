# Python for Solar Physics

本仓库是一个面向太阳物理事件分析的 Python 脚本集合，主要用于处理和绘制多波段观测数据，包括 SDO/AIA EUV 成像、SDO/HMI 磁场、GOES 软 X 射线、ASO-S/HXI 硬 X 射线、CSO 射电频谱/射电源以及 SOHO/LASCO 日冕仪数据。当前项目以独立科研脚本为主，`solar_toolkit/` 仅保留包元数据和后续模块化迁移入口。

GitHub 仓库：<https://github.com/YUCONG-28/python-for-solar-physics>

## 运行环境

本项目当前在 Miniforge 环境 `solarphysics_env` 下运行：

```powershell
conda activate solarphysics_env
python --version
```

本机验证到的解释器为：

```text
D:\miniforge3\envs\solarphysics_env\python.exe
Python 3.11.15
```

核心依赖包括：

- 科学计算：`numpy`, `scipy`, `pandas`, `scikit-image`
- 天文与太阳物理：`astropy`, `sunpy`, `reproject`, `drms`
- 绘图与交互：`matplotlib`, `plotly`, `seaborn`, `PyQt5`
- 数据与工具：`xarray`, `h5py`, `opencv-python`, `tqdm`, `PyYAML`

如需按项目元数据安装基础依赖，可在仓库根目录运行：

```powershell
D:\miniforge3\envs\solarphysics_env\python.exe -m pip install -e .
```

## 项目结构

### SDO/AIA 与 HMI

| 文件 | 功能 |
| --- | --- |
| `AIA.py` | AIA EUV FITS 批处理，支持单波段、多波段拼图、ROI 和并行绘图。 |
| `aia_multipanel.py` | 读取多个 AIA 波段并生成六联图。 |
| `AIA_difference_base.py` | AIA 基准差分成像。 |
| `AIA_difference_running.py` | AIA 运行差分成像。 |
| `AIA_Flux_data.py` | 从 AIA 图像序列提取光变/流量数据。 |
| `AIA_Flux_data_plot.py` | 绘制 AIA 光变曲线。 |
| `AIA_time_distance.py` | 沿指定路径生成 AIA 时间-距离图。 |
| `AIA_rename.py` | 批量规范化 AIA FITS 文件名。 |
| `AIA_select_files.py` | 按目标时间筛选 AIA 文件。 |
| `HMI.py` | 读取和绘制 SDO/HMI 磁图。 |
| `AIA_HMI.py` | AIA 与 HMI 共配准叠加。 |

### 射电数据

| 文件 | 功能 |
| --- | --- |
| `CSO_PLOT.py` | 绘制 CSO 动态频谱，支持通道选择和降采样。 |
| `plot_cso_spectrogram.py` | 可复用的 CSO 频谱绘图类。 |
| `csoSpectraGUIV09.py` | CSO 射电频谱交互式 GUI。 |
| `RS_plot.py` | 射电源图像/频谱处理、绘图和高斯拟合。 |
| `AIA_RS.py` | AIA、射电源和可选 HMI 的综合叠加图。 |

### X 射线、DEM 与多波段诊断

| 文件 | 功能 |
| --- | --- |
| `SXR.py` | GOES 软 X 射线 NetCDF 光变绘图。 |
| `HXR.py` | RHESSI/HESSI 风格硬 X 射线光变绘图。 |
| `HXI.py` | ASO-S/HXI FITS 图像读取和绘图。 |
| `HXI_SXR.py` | ASO-S/HXI 与 GOES SXR 时间序列对比。 |
| `AIA_HXI.py` | AIA 图像叠加 HXI 硬 X 射线轮廓。 |
| `AIA_SXR_HXR_plot.py` | AIA 图像、GOES SXR 和 HXR 光变三面板诊断图。 |
| `from SXR to HXR.py` | Neupert 效应分析：SXR 导数与 HXR 对比。 |
| `from SXR to HXR_finderro.py` | Neupert 效应时序误差/相关性探索。 |
| `DEM.py` | 基于 AIA 多波段数据的 DEM 反演。 |
| `DEM_RS.py` | DEM 诊断与射电源形态叠加。 |

### LASCO/CME 与通用工具

| 文件 | 功能 |
| --- | --- |
| `LASCO_data.py` | 通过 Helioviewer 下载 SOHO/LASCO 数据。 |
| `LOSCO_plot.py` | 基础 LASCO 图像绘制；文件名保留历史拼写。 |
| `LASCO_difference_plot.py` | LASCO 运行差分图像，用于 CME 前沿追踪。 |
| `M_V.py` | 将图像序列合成为视频。 |
| `Gauss_method.py` | 一维/二维高斯源区拟合工具。 |
| `utils_solar.py` | 共享工具：时间解析、FITS 文件排序、内存管理、配置和坐标辅助函数。 |

### 测试与开发脚本

| 文件 | 功能 |
| --- | --- |
| `test_time.py` | 时间字符串解析和时间差计算示例。 |
| `test_header.py` | FITS 头信息和 map 元数据检查。 |
| `test_sun_contour.py` | 日面轮廓/边界提取测试。 |
| `test_CSO.py` | CSO 频谱处理测试。 |
| `test_AIA_RS_0.py`, `test_AIA_RS_1.py`, `test_AIA_RS_3.py` | AIA/射电/HMI 叠加流程的开发变体。 |
| `test.py` | 综合叠加流程开发脚本，不作为正式单元测试入口。 |

## 使用方式

多数脚本仍使用文件顶部或配置类中的路径参数。运行前请先打开目标脚本，确认数据路径、输出目录、波段、时间范围和 ROI 设置。

示例：

```powershell
# AIA 多波段/批处理绘图
D:\miniforge3\envs\solarphysics_env\python.exe AIA.py

# CSO 动态频谱绘图
D:\miniforge3\envs\solarphysics_env\python.exe CSO_PLOT.py

# Neupert 效应 SXR-HXR 对比
D:\miniforge3\envs\solarphysics_env\python.exe "from SXR to HXR.py"

# AIA 与 HXI 叠加
D:\miniforge3\envs\solarphysics_env\python.exe AIA_HXI.py
```

## 数据与输出约定

- 大型观测数据如 `*.fits`, `*.fits.gz`, `*.fits.fz` 默认不纳入 Git。
- 生成图像、视频、表格和缓存文件通常可由脚本重建，应放在本地数据或输出目录中。
- 仓库中的 `*.png` 和 `*.xlsx` 文件属于历史示例/辅助材料；新增数据产品应优先保持在 Git 忽略范围内。
- 脚本文件名暂时保持原状。推荐的规范化文件名见 `CODE_ORGANIZATION_MANIFEST.md`，后续如需重命名应单独提交并同步更新引用。

## 验证

推荐在 `solarphysics_env` 中进行轻量验证：

```powershell
# 语法检查
D:\miniforge3\envs\solarphysics_env\python.exe -m compileall -q .

# 时间解析示例
D:\miniforge3\envs\solarphysics_env\python.exe test_time.py

# 包元数据导入
D:\miniforge3\envs\solarphysics_env\python.exe -c "import solar_toolkit; print(solar_toolkit.__version__)"
```

部分脚本依赖本地观测数据路径，不能脱离数据直接运行。若脚本报文件不存在，请先检查脚本内的 `data_path`、`output_dir` 或相关配置。

## License

本项目采用 MIT License，详见 `LICENSE`。

## Citation

如在科研工作中使用本项目，可引用：

Li, Y. (2025). *Python for Solar Physics: Multi-wavelength Data Processing Toolkit*. Shandong University. <https://github.com/YUCONG-28/python-for-solar-physics>
