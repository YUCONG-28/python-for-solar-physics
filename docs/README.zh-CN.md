# 中文项目说明

本文档提供 `python-for-solar-physics` 的中文概览。公开首页以英文为主，见
`../README.md`；脚本清单、仓库结构和路径配置以 `docs/` 下的当前指导文档为准。

## 项目定位

本仓库是一个面向太阳物理多波段事件分析的 Python 研究工具包。项目采用
“包内唯一实现 + 薄脚本兼容入口 + 数据无关测试”的组织方式，用于把本地观测数据
转化为论文或报告中的图像、叠加图、动态频谱、源中心诊断、光变曲线和时间演化
产品。

项目服务的主要研究场景包括太阳耀斑、喷流、CME、射电暴以及多仪器事件背景分析。
它不是开箱即用的数据门户；完整科学流程需要用户自行准备观测数据，并通过本地
配置文件指定数据路径。

## 科学范围

- **SDO/AIA 与 SDO/HMI**：EUV 图像可视化、多波段拼图、预览图、基准差分、
  运行差分、HMI 磁图和磁场等值线叠加。
- **射电源与动态频谱**：CSO 动态频谱绘制、射电源图像叠加、多频段源中心跟踪、
  二维高斯拟合、FWHM 轮廓、质量诊断和手动频漂率选点。
- **高度和密度模型诊断**：Newkirk 密度模型外推、频漂速度表、
  Gaussian-Newkirk 高度残差以及高度、时间、频率联合诊断。
- **多仪器事件背景**：STEREO-A/EUVI、GOES/SUVI、Solar Orbiter/EUI、
  SOHO/LASCO、GOES SXR、HXR/HXI 和 DEM/Tb 辅助工作流。

## 推荐入口

公开 README 只保留最小入口。更完整的脚本索引见 `script_index.md`。

```powershell
# 安装后的包入口
solar-aia --mode single --waves 171 193 304
solar-radio pipeline --config radio_20250124_config --output-dir outputs\radio-pipeline
solar-radio source-map --config radio_20250124_config --output-dir outputs\radio-map
solar-radio overlay --config radio_20250124_config --overlay-section aia_multi_wave_gaussian_spectrogram

# SDO/AIA 单波段、多波段、预览和差分产品
python scripts/aia_hmi/run_aia_euv_processor.py --mode single --waves 171 193 304

# 完整射电爆发流程：源图、高斯诊断、频漂和 Newkirk 产品
python scripts/radio/run_radio_burst_pipeline.py --config radio_20250124_config

# 快速射电源图和高斯叠加
python scripts/radio/run_radio_source_map.py

# AIA、射电源和 HMI 背景叠加
python scripts/radio/run_aia_radio_hmi_overlay.py
```

上述源码脚本只是包内同一实现的兼容入口。历史 recipe 统一保存在
`examples/history/` 或 `docs/history/`；新工作应优先使用安装命令或 `solar_toolkit.*` API。

## 安装与依赖

项目包元数据要求 Python 3.10+，主要在 Windows + Miniforge/conda 环境中开发。
公开用户可按下列方式创建环境：

```powershell
git clone https://github.com/YUCONG-28/python-for-solar-physics.git
cd python-for-solar-physics

conda create -n solarphysics_env python=3.11
conda activate solarphysics_env
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e ".[dev,full]"
```

可选 GUI 工作流可能需要：

```powershell
python -m pip install -e ".[gui]"
```

核心依赖包括 NumPy、SciPy、Astropy、SunPy、Matplotlib、Reproject、
Scikit-image、PyYAML、Pandas 和 tqdm。下载、GUI、视频或特定数据源工作流可能
需要额外可选依赖。

## 路径配置与数据政策

本仓库不跟踪原始观测数据和批量生成产品。请复制 `../configs/paths.example.yaml`
为 `../configs/paths.local.yaml`，并把本地数据根目录写入该文件。该本地配置文件
已被 Git 忽略。也可以通过 `SOLAR_PHYSICS_CONFIG` 环境变量指向外部 YAML。

不要提交以下内容：

- FITS、FTS、JP2、NetCDF、CDF、NumPy、HDF5 等原始或中间科学数据。
- 批量生成的 PNG/JPG/TIFF 图像、MP4/GIF 视频、CSV/XLSX 结果表。
- 本地缓存、临时测试目录、压缩包、个人路径配置和本地归档目录。

可公开展示的压缩示例图放在 `assets/images/`，并在 README 或文档中说明来源。

## 验证范围

轻量测试不依赖本地观测数据，主要覆盖导入、文档路径、路径配置、坐标辅助函数、
高斯拟合工具和部分管线模块：

```powershell
ruff check .
python -m compileall solar_toolkit scripts tests examples
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest -q tests
```

这些测试不能替代真实 FITS、JP2 或 CSO 数据上的科学输出一致性验证。删除历史脚本、
修改坐标/WCS 逻辑或调整绘图默认值前，应使用真实观测数据进行人工对比。

## 文档导航

- `../README.md`：英文公开首页、示例图、引用和最小运行入口。
- `README.md`：文档目录，区分当前指导和历史审计报告。
- `script_index.md`：当前公开脚本入口、工具脚本、示例和历史保留入口。
- `../CODE_ORGANIZATION_MANIFEST.md`：当前仓库结构、数据政策和脚本分组。
- `path_configuration.md`：本地路径配置说明。
- `assets/README.md`：README 展示图和视频的存放策略。

## 引用

如在研究中使用本工具包，请引用 `../CITATION.cff` 中的元数据：

Li, Y. (2025). *Python for Solar Physics: Multi-wavelength Data Processing
Toolkit*. Shandong University.
<https://github.com/YUCONG-28/python-for-solar-physics>

## 许可证

本项目采用 MIT License。详见 `../LICENSE`。
