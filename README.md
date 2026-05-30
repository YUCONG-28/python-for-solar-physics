# Solar Radio and SDO/AIA-HMI Analysis Toolkit

[English](#english-version) | [中文](#中文版本)

GitHub: <https://github.com/YUCONG-28/python-for-solar-physics>

## English Version

### Project Overview

This repository is a research-oriented Python toolkit for multi-wavelength solar
event analysis. It focuses on script-based workflows for SDO/AIA and SDO/HMI
visualization, CSO radio spectrogram plotting, radio source image overlays,
Gaussian source fitting and center diagnostics, JSOC/STEREO/SUVI data download
helpers, and publication-quality figure output.

The project is designed for flare, jet, CME, and radio-burst studies where local
observational data need to be turned into figures, overlay maps, light curves,
source-center diagnostics, and time-evolution products.

### Main Features

- SDO/AIA EUV image visualization, mosaics, previews, and difference products.
- SDO/HMI magnetogram plotting and magnetic-field contour overlays.
- CSO radio dynamic spectrogram plotting with memory-aware downsampling.
- Radio source image plotting, contour overlays, Gaussian fitting, and
  source-center diagnostics.
- Manual drift-rate selection and reuse of saved drift-rate JSON selections.
- Newkirk density-model extrapolation, drift-speed tables,
  Gaussian-Newkirk height residuals, and optional illustrative plane-of-sky
  projection on AIA 171 context.
- AIA/radio/HMI overlay workflows for source-region comparison.
- Event-specific JSOC/AIA, STEREO-A/EUVI, GOES/SUVI, and Solar Orbiter/EUI data
  acquisition helpers.
- STEREO-A/EUVI processing: manifest generation by wavelength, overview plots,
  and region-of-interest (ROI) time-evolution movies.
- GOES/SUVI context image generation with quadrant plotting.
- Solar Orbiter/EUI SOAR query and FITS download workflow.
- Modular configuration templates for AIA, radio, CSO, and overlay workflows.
- Image-sequence to MP4 conversion for time-evolution products.
- Local path configuration without committing machine-specific data paths.

### Recommended Entry Points

| Purpose | Recommended Script | Notes |
|---|---|---|
| SDO/AIA and HMI visualization | `scripts/aia_hmi/run_aia_euv_processor.py` | Main AIA processor for single-band views, mosaics, previews, and difference products. Use `scripts/radio/run_aia_radio_hmi_overlay.py` for AIA/radio/HMI overlays. |
| JSOC / AIA / HMI data download and preparation | `scripts/aia_hmi/sdo_aia_jsoc_download_20250124.py` | Event-specific AIA JSOC downloader. Use `scripts/aia_hmi/sdo_aia_hmi_fits_rename.py` for local FITS filename normalization. |
| STEREO / SUVI data download | `scripts/data_download/stereo_a_euvi_download_20250124.py`; `scripts/data_download/goes_suvi_download_20250124.py` | Event-specific download helpers for the 2025-01-24 context data. |
| Solar Orbiter / EUI data download | `scripts/data_download/solo_eui_soar_query_download.py` | Query SOAR for EUI observations and download FITS files. |
| STEREO-A/EUVI processing | `scripts/stereo_suvi/stereo_euvi_manifest_by_wavelength.py`; `scripts/stereo_suvi/stereo_euvi_0448_overview_plot.py`; `scripts/stereo_suvi/stereo_euvi_roi_movie.py` | EUVI wavelength manifest generation, multi-band overview plots, and ROI time-evolution MP4 generation. |
| GOES/SUVI context imaging | `scripts/stereo_suvi/goes_suvi_0448_quadrant_plot.py` | Generate GOES/SUVI quadrant layout plots for context images. |
| Radio spectrogram plotting | `scripts/radio/legacy/cso_radio_spectrogram_plot.py` | Compatibility CSO dynamic spectrum plotting workflow; no `run_*.py` wrapper exists yet. |
| Full radio burst analysis | `scripts/radio/run_radio_burst_pipeline.py` | Main full pipeline for source maps, Gaussian diagnostics, spectrogram/drift support, Newkirk height comparison, Gaussian-Newkirk height residuals, and optional illustrative AIA 171 plane-of-sky projection. |
| Radio source image overlay | `scripts/radio/run_radio_source_map.py` | Quick radio source map workflow with Gaussian overlay. |
| Gaussian fitting and diagnostics | `scripts/radio/run_radio_source_map.py` | Produces fitted centers, FWHM overlays, quality diagnostics, and CSV outputs through the compatibility source-map workflow. |
| AIA/radio/HMI overlays | `scripts/radio/run_aia_radio_hmi_overlay.py` | Main context overlay workflow for AIA, radio contours, and optional HMI contours. |
| Image to video | `scripts/tools/image_sequence_to_video.py` | General utility for converting vetted PNG/JPG frame sequences to MP4. |
| Path configuration and shared helpers | `solar_toolkit/path_config.py` | Use `configs/paths.example.yaml` as the template for local path configuration. |

The historical AIA command `scripts/aia_hmi/sdo_aia_euv_processor.py` remains
available as a compatibility wrapper for existing local workflows.

### Quick Start

1. Clone the repository:

   ```powershell
   git clone https://github.com/YUCONG-28/python-for-solar-physics.git
   cd python-for-solar-physics
   ```

2. Create environment:

   ```powershell
   conda create -n solarphysics_env python=3.11
   conda activate solarphysics_env
   python -m pip install --upgrade pip
   ```

3. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   python -m pip install -e ".[dev,full]"
   ```

   Optional GUI tools may also need:

   ```powershell
   python -m pip install -e ".[gui]"
   ```

4. Run smoke tests:

   ```powershell
   ruff check .
   python -m compileall scripts tests
   pytest tests/test_path_config.py tests/test_imports.py
   ```

   Full pytest is not currently used as the release criterion because the local
   Windows environment may trigger a NumPy BLAS-related fatal exception during
   import.

5. Run selected scripts:

   Full science workflows require local observation data and event-specific path
   configuration before they can produce research products.

   ```powershell
   # AIA single-band or mosaic processing
   python scripts\aia_hmi\run_aia_euv_processor.py --mode single --waves 171 193 304

   # Normalize AIA/HMI FITS filenames without modifying files
   python scripts\aia_hmi\sdo_aia_hmi_fits_rename.py D:\solar_data\SDO --dry-run

   # Download event-specific AIA JSOC data
   python scripts\aia_hmi\sdo_aia_jsoc_download_20250124.py

   # Download STEREO-A/EUVI and GOES/SUVI event context data
   python scripts\data_download\stereo_a_euvi_download_20250124.py
   python scripts\data_download\goes_suvi_download_20250124.py

   # Solar Orbiter / EUI SOAR query and download
   python scripts\data_download\solo_eui_soar_query_download.py

   # STEREO-A/EUVI manifest, overview, and ROI movie
   python scripts\stereo_suvi\stereo_euvi_manifest_by_wavelength.py
   python scripts\stereo_suvi\stereo_euvi_0448_overview_plot.py
   python scripts\stereo_suvi\stereo_euvi_roi_movie.py

   # GOES/SUVI quadrant context plot
   python scripts\stereo_suvi\goes_suvi_0448_quadrant_plot.py

   # CSO dynamic spectrum plotting
   python scripts\radio\legacy\cso_radio_spectrogram_plot.py

   # Radio source maps with Gaussian diagnostics
   python scripts\radio\run_radio_source_map.py

   # Full radio burst pipeline with Gaussian, drift, Newkirk height comparison, and optional AIA 171 projection schematic
   python scripts\radio\run_radio_burst_pipeline.py --config radio_20250124_config

   # AIA, radio source, and HMI overlay workflow
   python scripts\radio\run_aia_radio_hmi_overlay.py

   # Convert generated PNG sequence to MP4
   python scripts\tools\image_sequence_to_video.py
   ```

### Data Policy

- Raw observational data are not tracked by Git.
- Generated products are not tracked by Git.
- ZIP archives are ignored.
- Local legacy folders such as `data dowload/` are ignored.
- Users should place large data products under ignored data directories such as
  `data/raw/`, `data/products/`, `outputs/`, or other local-only folders.
- Local path files such as `configs/paths.local.yaml` should not be committed.

Typical ignored products include FITS/FTS files, JP2 files, NetCDF/CDF files,
NumPy arrays, HDF5 files, batch plot folders, videos, CSV/XLSX products, cache
folders, and local archives.

### Project Structure

```text
Python/
  README.md
  requirements.txt
  pyproject.toml
  .github/workflows/ci.yml   # automated CI (compileall, lightweight tests, import checks)
  scripts/                   # runnable research workflows
    aia_hmi/                 # SDO/AIA, HMI visualization and JSOC download
    data_download/           # STEREO, GOES/SUVI, Solar Orbiter/EUI download
    lasco_cme/               # LASCO CME detection utilities
    radio/                   # CSO spec, radio source maps, AIA/radio/HMI overlay
    stereo_suvi/             # STEREO-A/EUVI and GOES/SUVI processing & plots
    tools/                   # image-to-video and other general utilities
    xray_dem/                # X-ray/DEM temperature analysis utilities
  solar_toolkit/             # shared helper package
    coordinates.py           # solar coordinate transforms
    cso.py                   # CSO spectrogram reader
    gaussian.py              # 2D Gaussian fitting utilities
    path_config.py           # local path configuration loader
    solar_analysis_utils.py  # common analysis helpers (aia, hmi, radio, etc.)
  docs/                      # project documentation & refactor reports
  configs/                   # example YAML configuration templates
    aia.example.yaml         # AIA workflow config template
    cso.example.yaml         # CSO spectrogram config template
    overlay.example.yaml     # AIA/radio/HMI overlay config template
    paths.example.yaml       # local data paths config template
    radio.example.yaml       # radio source map config template
  examples/                  # small examples; larger outputs stay local
  tests/                     # lightweight data-independent tests
  legacy/                    # high-risk historical scripts kept for review
  archive/                   # ignored local archive area, not public GitHub content
  data/products/             # ignored generated products
```

**Key directories explained:**

- **`solar_toolkit/`** — shared helper package with modules for coordinate
  transforms (`coordinates.py`), CSO spectrogram I/O (`cso.py`), 2D Gaussian
  fitting (`gaussian.py`), local path configuration (`path_config.py`), and
  common analysis utilities (`solar_analysis_utils.py`).
- **`configs/`** — YAML configuration templates for AIA, CSO, radio source map,
  and overlay workflows plus local path settings. Copy and adapt these for your
  environment instead of hard-coding paths in scripts.
- **`scripts/`** — organized by instrument/workflow:
  `aia_hmi/` (SDO), `data_download/` (multi-instrument), `radio/` (CSO + LOFAR
  source maps), `stereo_suvi/` (STEREO/EUVI + GOES/SUVI), `lasco_cme/` (LASCO),
  `xray_dem/` (X-ray), and `tools/` (utilities).
- **`.github/workflows/ci.yml`** — GitHub Actions CI that runs YAML example
  validation, `compileall`, lightweight pytest, and a package import check on
  push and PR.

### Example Outputs

Example output placeholders live under `docs/assets/`, `examples/images/`, and
`examples/videos/`.
`examples/images/` and `examples/videos/` currently only contain `.gitkeep`
placeholders.
Curated example images or videos can be added later after size reduction and
source documentation.
The current repository does not fabricate example outputs, and full research
products should remain local.

### Documentation

- `docs/README.md`: documentation index separating current guidance from
  historical refactor reports.
- `docs/script_index.md`: current script index with `main`, `utility`,
  `archived`, and `deprecated` labels.
- `docs/project_structure.md`: repository layout and data policy details.
- `docs/MAIN_FILES.md`: curated list of main production scripts and their roles.
- `docs/PROJECT_OVERVIEW.md`: high-level project architecture and module map.
- `CODE_ORGANIZATION_MANIFEST.md`: code organization rules and retention
  policy after project restructuring.
- `docs/data_download/event_20250124_inventory.md`: 2025-01-24 event download
  and visualization workflow.
- `CHANGELOG.md`: versioned release notes and change log.

### Environment and Dependencies

The project is developed with Miniforge/conda on Windows, but the core package
can be installed in any Python 3.10+ environment that supports SunPy and
AstroPy. The canonical package metadata lives in `pyproject.toml`; the
`requirements.txt` file is provided as a convenient environment checklist.

Core dependencies include NumPy, SciPy, AstroPy, SunPy, Matplotlib, Reproject,
Scikit-image, PyYAML, Pandas, and tqdm. Optional workflows may require DRMS,
Requests, OpenCV, ImageIO, PyQt5, pyqtgraph, Helioviewer-related packages, or
other archive-specific libraries.

### Validation Status

Current release-check commands:

```powershell
ruff check .
python -m compileall solar_toolkit scripts tests examples
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest -q --basetemp .pytest_tmp_codex_validation tests/test_path_config.py tests/test_imports.py tests/test_project_docs_current_paths.py tests/test_aia_hmi_radio_style_structure.py tests/test_radio_20250503_config.py
```

These checks are the lightweight cleanup gate. Full science workflows still
require local observation data and are not expected to run from a fresh clone
without user data paths.

### Notes and Limitations

- The repository is a research toolkit, not a turnkey data portal.
- Most scripts expect local FITS, FTS, JP2, NetCDF, CSV, or NumPy products.
- Some scripts are event-specific and currently target the 2025-01-24 event.
- GUI and download scripts may require optional dependencies and network access.
- High-risk scientific scripts are kept for review rather than deleted.
- Full pytest is not treated as a release gate in this local Windows setup due
  to the known NumPy BLAS-related fatal exception during import.

## 中文版本

### 项目简介

本仓库是一个面向太阳物理多波段事件分析的 Python 研究工具箱。项目以脚本式工作流为主，
覆盖 SDO/AIA 与 SDO/HMI 可视化、CSO 射电动态频谱图绘制、射电源图像叠加、
高斯拟合与源中心诊断、JSOC/STEREO/SUVI 数据下载辅助脚本，以及论文级图像输出。

该项目主要服务于耀斑、喷流、CME 和射电暴研究场景，用于把本地观测数据转换为图像、
叠加图、光变曲线、源中心诊断和时间演化产品。

### 主要功能

- SDO/AIA EUV 图像可视化、多波段拼图、预览图和差分产品。
- SDO/HMI 磁图绘制与磁场等值线叠加。
- CSO 射电动态频谱图绘制，并支持内存友好的下采样。
- 射电源图像绘制、等值线叠加、高斯拟合和源中心诊断。
- 手动频漂率选点，并复用已保存的频漂率 JSON 结果。
- Newkirk 密度模型外推、频漂速度表、Gaussian-Newkirk 高度残差，
  以及可选的 AIA 171 Å 背景下平面径向投影示意图。
- AIA/radio/HMI 叠加工作流，用于源区对比。
- 面向 2025-01-24 事件的 JSOC/AIA、STEREO-A/EUVI、GOES/SUVI 和
  Solar Orbiter/EUI 数据获取辅助脚本。
- STEREO-A/EUVI 处理：按波长生成清单、多波段概览图和 ROI 时间演化动画。
- GOES/SUVI 背景图像生成与象限排布图绘制。
- Solar Orbiter/EUI SOAR 查询与 FITS 下载工作流。
- AIA、射电、CSO 和叠加工作流的模块化配置模板（YAML）。
- 图片序列转 MP4，用于时间演化产品。
- 本地路径配置，避免把个人机器路径提交到仓库。

### 推荐主入口

| 用途 | 推荐脚本 | 说明 |
|---|---|---|
| SDO/AIA 与 HMI 可视化 | `scripts/aia_hmi/run_aia_euv_processor.py` | AIA 主处理脚本，用于单波段图像、多波段拼图、预览和差分产品。AIA/radio/HMI 叠加使用 `scripts/radio/run_aia_radio_hmi_overlay.py`。 |
| JSOC / AIA / HMI 数据下载与准备 | `scripts/aia_hmi/sdo_aia_jsoc_download_20250124.py` | 面向事件的 AIA JSOC 下载脚本。本地 FITS 文件名规范化使用 `scripts/aia_hmi/sdo_aia_hmi_fits_rename.py`。 |
| STEREO / SUVI 数据下载 | `scripts/data_download/stereo_a_euvi_download_20250124.py`; `scripts/data_download/goes_suvi_download_20250124.py` | 面向 2025-01-24 事件背景数据的下载辅助脚本。 |
| Solar Orbiter / EUI 数据下载 | `scripts/data_download/solo_eui_soar_query_download.py` | 查询 SOAR 获取 EUI 观测并下载 FITS 文件。 |
| STEREO-A/EUVI 处理 | `scripts/stereo_suvi/stereo_euvi_manifest_by_wavelength.py`; `scripts/stereo_suvi/stereo_euvi_0448_overview_plot.py`; `scripts/stereo_suvi/stereo_euvi_roi_movie.py` | EUVI 按波长生成清单、多波段概览图和 ROI 时间演化 MP4 生成。 |
| GOES/SUVI 背景图绘制 | `scripts/stereo_suvi/goes_suvi_0448_quadrant_plot.py` | 生成 GOES/SUVI 象限排布图。 |
| 射电频谱图绘制 | `scripts/radio/legacy/cso_radio_spectrogram_plot.py` | CSO 动态频谱图兼容流程；当前还没有 `run_*.py` wrapper。 |
| 完整射电爆发分析 | `scripts/radio/run_radio_burst_pipeline.py` | 射电源图、Gaussian 诊断、频谱/频漂支持、Newkirk 高度比较、Gaussian-Newkirk 高度残差，以及可选 AIA 171 平面投影示意的完整主流程。 |
| 射电源图像叠加 | `scripts/radio/run_radio_source_map.py` | 快速射电源图流程，支持 Gaussian 叠加。 |
| 高斯拟合与诊断 | `scripts/radio/run_radio_source_map.py` | 通过兼容 source-map 工作流输出拟合中心、FWHM 叠加、质量诊断和 CSV 结果。 |
| AIA/radio/HMI 叠加 | `scripts/radio/run_aia_radio_hmi_overlay.py` | AIA、射电等值线和可选 HMI 等值线的主叠加流程。 |
| 图片转视频 | `scripts/tools/image_sequence_to_video.py` | 将已检查的 PNG/JPG 图片序列转换为 MP4。 |
| 路径配置与工具函数 | `solar_toolkit/path_config.py` | 使用 `configs/paths.example.yaml` 作为本地路径配置模板。 |

历史 AIA 命令 `scripts/aia_hmi/sdo_aia_euv_processor.py` 仍作为兼容入口保留，
用于已有本地流程。

### 快速开始

1. 克隆仓库：

   ```powershell
   git clone https://github.com/YUCONG-28/python-for-solar-physics.git
   cd python-for-solar-physics
   ```

2. 创建环境：

   ```powershell
   conda create -n solarphysics_env python=3.11
   conda activate solarphysics_env
   python -m pip install --upgrade pip
   ```

3. 安装依赖：

   ```powershell
   python -m pip install -r requirements.txt
   python -m pip install -e ".[dev,full]"
   ```

   可选 GUI 工具可能还需要：

   ```powershell
   python -m pip install -e ".[gui]"
   ```

4. 运行快速测试：

   ```powershell
   ruff check .
   python -m compileall scripts tests
   pytest tests/test_path_config.py tests/test_imports.py
   ```

   当前不将全量 pytest 作为发布成功标准，因为本地 Windows 环境可能在导入 NumPy
   时触发与 BLAS 相关的 fatal exception。

5. 运行指定脚本：

   完整科学工作流需要本地观测数据和面向事件的路径配置，才能生成可用于研究的产品。

   ```powershell
   # AIA 单波段或拼图处理
   python scripts\aia_hmi\run_aia_euv_processor.py --mode single --waves 171 193 304

   # 只预览 AIA/HMI FITS 重命名结果，不实际改名
   python scripts\aia_hmi\sdo_aia_hmi_fits_rename.py D:\solar_data\SDO --dry-run

   # 下载事件相关 AIA JSOC 数据
   python scripts\aia_hmi\sdo_aia_jsoc_download_20250124.py

   # 下载 STEREO-A/EUVI 和 GOES/SUVI 事件背景数据
   python scripts\data_download\stereo_a_euvi_download_20250124.py
   python scripts\data_download\goes_suvi_download_20250124.py

   # Solar Orbiter / EUI SOAR 查询与下载
   python scripts\data_download\solo_eui_soar_query_download.py

   # STEREO-A/EUVI 清单、概览图与 ROI 动画
   python scripts\stereo_suvi\stereo_euvi_manifest_by_wavelength.py
   python scripts\stereo_suvi\stereo_euvi_0448_overview_plot.py
   python scripts\stereo_suvi\stereo_euvi_roi_movie.py

   # GOES/SUVI 象限背景图
   python scripts\stereo_suvi\goes_suvi_0448_quadrant_plot.py

   # 绘制 CSO 动态频谱图
   python scripts\radio\legacy\cso_radio_spectrogram_plot.py

   # 绘制射电源图并输出高斯拟合诊断
   python scripts\radio\run_radio_source_map.py

   # 完整射电爆发流程：Gaussian、频漂、Newkirk 高度比较和可选 AIA 171 投影示意
   python scripts\radio\run_radio_burst_pipeline.py --config radio_20250124_config

   # AIA、射电源和 HMI 叠加
   python scripts\radio\run_aia_radio_hmi_overlay.py

   # 将生成的 PNG 序列转为 MP4
   python scripts\tools\image_sequence_to_video.py
   ```

### 数据管理策略

- 原始观测数据不进入 Git。
- 生成产品不进入 Git。
- 压缩包不进入 Git。
- 旧本地目录 `data dowload/` 已被忽略。
- 大型数据产品应放在被忽略的数据目录下，例如 `data/raw/`、`data/products/`、
  `outputs/` 或其他仅本地使用的目录。
- 本地路径文件，例如 `configs/paths.local.yaml`，不应提交。

常见忽略对象包括 FITS/FTS 文件、JP2 文件、NetCDF/CDF 文件、NumPy 数组、HDF5
文件、批量绘图目录、视频、CSV/XLSX 产品、缓存目录和本地归档目录。

### 项目结构

```text
Python/
  README.md
  requirements.txt
  pyproject.toml
  .github/workflows/ci.yml   # 自动化 CI（compileall、轻量测试、导入检查）
  scripts/                   # 可运行科研脚本
    aia_hmi/                 # SDO/AIA、HMI 可视化与 JSOC 下载
    data_download/           # STEREO、GOES/SUVI、Solar Orbiter/EUI 下载
    lasco_cme/               # LASCO CME 检测工具
    radio/                   # CSO 频谱、射电源图、AIA/radio/HMI 叠加
    stereo_suvi/             # STEREO-A/EUVI 与 GOES/SUVI 处理与绘图
    tools/                   # 图片转视频与其他通用工具
    xray_dem/                # X 射线/DEM 温度分析工具
  solar_toolkit/             # 共享工具包
    coordinates.py           # 太阳坐标变换
    cso.py                   # CSO 频谱图读取
    gaussian.py              # 二维高斯拟合工具
    path_config.py           # 本地路径配置加载
    solar_analysis_utils.py  # 通用分析辅助函数（aia、hmi、radio 等）
  docs/                      # 项目文档与整理报告
  configs/                   # YAML 配置模板
    aia.example.yaml         # AIA 工作流配置模板
    cso.example.yaml         # CSO 频谱图配置模板
    overlay.example.yaml     # AIA/radio/HMI 叠加配置模板
    paths.example.yaml       # 本地数据路径配置模板
    radio.example.yaml       # 射电源图配置模板
  examples/                  # 小型示例；大型输出保留在本地
  tests/                     # 不依赖观测数据的轻量测试
  legacy/                    # 高风险历史脚本，保留用于审查
  archive/                   # 被忽略的本地归档目录，不作为 GitHub 公开内容
  data/products/             # 被忽略的生成产品目录
```

**主要目录说明：**

- **`solar_toolkit/`** — 共享工具包，包含坐标变换（`coordinates.py`）、CSO
  频谱图 I/O（`cso.py`）、二维高斯拟合（`gaussian.py`）、本地路径配置
  （`path_config.py`）和通用分析辅助函数（`solar_analysis_utils.py`）。
- **`configs/`** — AIA、CSO、射电源图和叠加工作流的 YAML 配置模板，以及本地
  路径设置。请将这些模板复制并适配到自己的环境中使用，而不是在脚本中硬编码路径。
- **`scripts/`** — 按仪器/工作流组织：`aia_hmi/`（SDO）、`data_download/`
  （多仪器）、`radio/`（CSO + LOFAR 射电源图）、`stereo_suvi/`
  （STEREO/EUVI + GOES/SUVI）、`lasco_cme/`（LASCO）、`xray_dem/`
  （X 射线）和 `tools/`（通用工具）。
- **`.github/workflows/ci.yml`** — GitHub Actions CI，在 push 和 PR 时执行
  YAML 示例验证、`compileall`、轻量 pytest 和包导入检查。

### 示例输出

示例输出占位目录位于 `docs/assets/`、`examples/images/` 和 `examples/videos/`。
目前 `examples/images/` 与 `examples/videos/` 仅保留 `.gitkeep`，还没有精选示例文件。
后续可在压缩体积并补充来源说明后加入代表性示例图片或视频。
当前仓库不虚构示例输出，完整科研产品应保留在本地。

### 文档索引

- `docs/README.md`：文档目录入口，区分当前说明和历史整理报告。
- `docs/script_index.md`：当前脚本索引，并标记 `main`、`utility`、`archived`、
  `deprecated`。
- `docs/project_structure.md`：仓库结构与数据管理策略说明。
- `docs/MAIN_FILES.md`：主要生产脚本及其用途的精选列表。
- `docs/PROJECT_OVERVIEW.md`：项目架构与模块关系的高级概览。
- `CODE_ORGANIZATION_MANIFEST.md`：项目重构后的代码组织规则与保留策略。
- `docs/data_download/event_20250124_inventory.md`：2025-01-24 事件下载与可视化流程。
- `CHANGELOG.md`：版本化发布说明与变更日志。

### 环境与依赖

项目主要在 Windows + Miniforge/conda 环境下开发，但核心包可安装在支持 SunPy 和
AstroPy 的 Python 3.10+ 环境中。`pyproject.toml` 是主要包元数据文件，
`requirements.txt` 作为便捷依赖清单。

核心依赖包括 NumPy、SciPy、AstroPy、SunPy、Matplotlib、Reproject、
Scikit-image、PyYAML、Pandas 和 tqdm。可选工作流可能需要 DRMS、Requests、
OpenCV、ImageIO、PyQt5、pyqtgraph、Helioviewer 相关依赖或其他数据源相关库。

### 验证状态

当前发布前检查命令：

```powershell
ruff check .
python -m compileall solar_toolkit scripts tests examples
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest -q --basetemp .pytest_tmp_codex_validation tests/test_path_config.py tests/test_imports.py tests/test_project_docs_current_paths.py tests/test_aia_hmi_radio_style_structure.py tests/test_radio_20250503_config.py
```

这些检查是轻量级整理门槛。完整科研工作流仍需要本地观测数据，不能假设从全新克隆
仓库后无需配置即可运行。

### 注意事项与限制

- 本仓库是研究工具箱，不是开箱即用的数据门户。
- 大多数脚本需要本地 FITS、FTS、JP2、NetCDF、CSV 或 NumPy 产品。
- 部分脚本是事件专用脚本，当前主要面向 2025-01-24 事件。
- GUI 和下载脚本可能需要可选依赖和网络访问。
- 高风险科研脚本优先保留审查，不直接删除。
- 在当前本地 Windows 环境中，全量 pytest 不是发布门槛，因为导入 NumPy 时存在已知的
  BLAS 相关 fatal exception 风险。

## Citation

Citation metadata is provided in `CITATION.cff`.

Li, Y. (2025). *Python for Solar Physics: Multi-wavelength Data Processing
Toolkit*. Shandong University.
<https://github.com/YUCONG-28/python-for-solar-physics>

## License

MIT License. See `LICENSE`.
