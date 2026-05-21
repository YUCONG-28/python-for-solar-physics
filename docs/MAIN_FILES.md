# Main Files

## Core Package

- `solar_toolkit/`
  - 项目核心 Python 包。
  - `path_config.py` 提供本地路径配置读取与脚本参数覆盖。
  - `solar_analysis_utils.py` 提供太阳物理数据处理共享工具，包括文件时间解析、FITS 文件排序、内存管理、坐标转换和可视化辅助函数。

## Scripts

- `scripts/aia_hmi/`
  - SDO/AIA 与 SDO/HMI 相关脚本。
  - 包括 AIA EUV 单波段处理、多波段面板、基准差分、运行差分、光变曲线提取与绘制、AIA/HMI FITS 规范命名、AIA/HMI 叠加和 HMI 磁图绘制。

- `scripts/radio/`
  - 射电频谱与射电源可视化脚本。
  - 包括 CSO 动态频谱绘图、CSO 交互式 GUI、射电源图像绘制、射电源高斯叠加、AIA/射电/HMI 多仪器叠加。

- `scripts/xray_dem/`
  - X 射线、DEM 和多波段诊断脚本。
  - 包括 GOES SXR、HESSI/HXI 光变、ASO-S/HXI 图像、AIA/HXI 叠加、flare 多面板诊断、Neupert 效应分析、DEM 反演和 DEM/射电源叠加。

- `scripts/lasco_cme/`
  - SOHO/LASCO CME 相关脚本。
  - 包括 LASCO 数据下载、基础图像绘制和运行差分图像生成。

- `scripts/tools/`
  - 通用科研工具脚本。
  - `gaussian_source_fitting.py` 用于二维高斯源拟合。
  - `image_sequence_to_video.py` 用于将图片序列转换为视频。

## Configs

- `configs/paths.example.yaml`
  - 用户可复制为 `configs/paths.local.yaml` 的本地配置模板。
  - 用于配置本地观测数据路径、输出路径和脚本参数。

## Examples

- `examples/`
  - 后续放置最小可运行示例、输入示例和输出示例。
  - `examples/input/` 用于小型示例输入数据。
  - `examples/output/` 用于示例运行结果。
  - 大型 FITS、视频和完整科研数据不建议直接提交到 GitHub。

## Docs

- `docs/script_index.md`
  - 主要脚本索引和用途说明。
- `docs/project_structure.md`
  - 项目结构说明。
- `docs/path_configuration.md`
  - 本地路径配置说明。
- `docs/PROJECT_CLEANUP_REPORT.md`
  - 发布前清理审计报告。

## Output Directories

- `outputs/`
  - 运行输出目录说明保留。
  - 实际运行结果默认不建议提交，尤其是大型图片、FITS、视频和中间数据。

## README Assets

- `docs/assets/images/`
  - README 展示图片目录，可放置压缩后的运行结果图、AIA 图像、射电源叠加图、频谱图等。
  - 空目录通过 `.gitkeep` 保留。

- `docs/assets/videos/`
  - README 展示视频目录，可放置压缩后的动画、时间序列视频和太阳事件演化视频。
  - 空目录通过 `.gitkeep` 保留。
