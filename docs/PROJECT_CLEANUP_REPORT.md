# Project Cleanup Report

生成时间：2026-05-22

## 当前目录结构概览

项目根目录是一个太阳物理科研 Python 项目，当前主结构如下：

```text
project_root/
├── .github/
├── configs/
├── docs/
├── examples/
├── outputs/
├── scripts/
├── solar_toolkit/
├── tests/
├── README.md
├── LICENSE
├── CITATION.cff
├── pyproject.toml
└── requirements.txt
```

审计时还发现大量可再生成缓存与临时目录：

- `.automated-tool.tags.cache.v4/`
- `.pytest_tmp/`
- `.ruff_cache/`
- `__pycache__/`
- `tmp/`
- `pytest-cache-files-*`
- 多处子目录中的 `__pycache__/`

## 核心源码文件

- `solar_toolkit/`
  - `solar_toolkit/__init__.py`：包元数据与公开模块声明。
  - `solar_toolkit/path_config.py`：本地 YAML 路径配置加载与对象参数覆盖工具。
  - `solar_toolkit/solar_analysis_utils.py`：太阳物理数据处理共享工具，包括时间解析、文件排序、内存管理、坐标和可视化辅助功能。

## 主程序入口与主要脚本

- `scripts/aia_hmi/`：SDO/AIA 与 SDO/HMI 处理、差分、光变、FITS 规范命名和叠加绘图。
- `scripts/radio/`：CSO 动态频谱、射电源图像、高斯拟合叠加、AIA/射电/HMI 多仪器叠加。
- `scripts/xray_dem/`：GOES SXR、HESSI/HXI、AIA/HXI 叠加、DEM 反演、Neupert 效应分析。
- `scripts/lasco_cme/`：SOHO/LASCO 数据下载、图像绘制、运行差分 CME 图像。
- `scripts/tools/`：图像序列转视频、二维高斯源拟合工具。

## 配置文件

- `configs/paths.example.yaml`：本地数据路径与脚本参数配置模板。
- `pyproject.toml`：项目元数据、依赖、打包配置、ruff/black/pytest/mypy 配置。
- `requirements.txt`：运行依赖列表。
- `.pre-commit-config.yaml`：pre-commit 钩子配置。
- `.gitignore`：忽略缓存、大型科学数据、生成媒体和临时输出。

## 文档文件

- `README.md`
- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `CODE_ORGANIZATION_MANIFEST.md`
- `docs/project_structure.md`
- `docs/script_index.md`
- `docs/path_configuration.md`

## 示例脚本

- `examples/aia_hmi/solar_limb_contour_example.py`
- `examples/radio/cso_spectrogram_processing_example.py`
- `examples/radio/fits_header_metadata_example.py`
- `examples/radio_aia_hmi/*.py`

## 测试文件

正式单元测试文件已纳入保留项：

- `tests/test_aia_hmi_fits_rename.py`
- `tests/test_imports.py`
- `tests/test_observation_time_parsing.py`
- `tests/test_path_config.py`

审计时发现 `tests/Guass_fits/` 是未跟踪目录，包含独立 `pyproject.toml`、README、脚本、图片、视频、zip 包、日志、`__MACOSX` 和多级 `__pycache__`。其结构不像当前项目的正式 pytest 单元测试，更像历史/临时高斯拟合实验包与输出结果，建议删除。

## 建议保留的主要文件/文件夹

- `.git/`
- `.github/`
- `configs/`
- `docs/`
- `examples/`
- `scripts/`
- `solar_toolkit/`
- `tests/` 中正式 pytest 单元测试文件
- `README.md`
- `LICENSE`
- `CITATION.cff`
- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `CODE_ORGANIZATION_MANIFEST.md`
- `pyproject.toml`
- `requirements.txt`
- `.pre-commit-config.yaml`

## 建议删除的测试文件/缓存文件/临时文件

明确可删除：

- 所有 `__pycache__/`
- 所有 `*.pyc`
- 所有 `*.pyo`
- `.pytest_cache/`
- `.pytest_tmp/`
- `pytest-cache-files-*`
- `.ruff_cache/`
- `.automated-tool.tags.cache.v4/`
- `.automated-tool.chat.history.md`
- `.automated-tool.input.history`
- `tmp/`
- `tests/Guass_fits/`
- `scripts/dev_tests/`，若清理 `__pycache__` 后为空

## 大型图片、视频、FITS 或运行结果文件

发现的大型/科研结果类文件：

- 根目录图片：`HXR.png`、`SXR.png`、`SXR to HXR.png`、`SXR to HXR enhance.png`
- 根目录表格：`AIA.xlsx`、`CSO.xlsx`
- `outputs/README.md`
- `tests/Guass_fits/` 下的 zip、mp4、png、日志与输出目录
- `pytest-cache-files-aia-hmi-rename-2/` 下有测试生成的 FITS 文件

## 人工确认项

以下项目不在本轮自动删除范围，建议人工确认后再决定是否迁移、压缩或移除：

- 根目录 `HXR.png`、`SXR.png`、`SXR to HXR.png`、`SXR to HXR enhance.png`：可能是 README 或论文展示图，也可能是历史输出图。
- 根目录 `AIA.xlsx`、`CSO.xlsx`：可能是科研表格数据或中间数据。
- `outputs/README.md`：当前是受版本控制的输出目录说明文件，保留。
- `.automated-tool-conventions.md`、`.automated-tool.conf.yml`、`.automated-tool.model.settings.yml`、`.aiderignore`：属于 automated-tool 配置/约定文件，不按缓存处理；如项目发布不希望保留 AI 工具配置，可人工确认后移除。
- `.vscode/`：本地 IDE 配置，当前不按核心文件处理，但本轮不主动删除。
- `solar_physics_toolkit.egg-info/`：打包生成元数据，通常可再生成；因不在用户明确删除清单中，本轮不主动删除。
- `scripts/radio/sdo_aia_radio_hmi_overlay_bgcorrected.py`：未跟踪的新脚本，疑似背景扣除实验版，建议人工确认是否纳入正式脚本。
- `scripts/radio/spectrogram_drift_rate_manual_selection.json`：未跟踪 JSON，可能是手工选点结果，建议人工确认是否保留为示例/配置/结果。

## 潜在风险说明

- 删除缓存目录不会影响核心算法，但会移除本地测试运行状态和 Python 编译缓存。
- 删除 `pytest-cache-files-*` 会移除测试生成的临时 FITS 文件；这些应由测试重新生成，不应作为科研数据来源。
- 删除 `tests/Guass_fits/` 会移除未跟踪的历史实验目录和大型媒体/压缩包；该目录未纳入 Git 正式测试文件，且包含大量运行结果和独立项目文件。
- README 后续展示用资源应放入 `docs/assets/images/` 和 `docs/assets/videos/`，少量压缩示例图片可按需手动加入版本控制。

## 清理执行备注

清理过程中，以下目录在 Windows 文件系统层面返回 `Access denied`，无法由当前进程删除。它们仍属于测试缓存/临时目录，建议后续用管理员权限、关闭占用进程后，或重启后手工删除：

- `.pytest_tmp/`
- `pytest-cache-files-aia-hmi-rename/`
- `pytest-cache-files-final-submit/`
- `pytest-cache-files-ll5v3iu2/`
- `pytest-cache-files-pbnenyrm/`
- `pytest-cache-files-ruff-batch1/`
- `pytest-cache-files-ruff-batch2/`
- `pytest-cache-files-ruff-batch3/`
- `pytest-cache-files-ruff-batch4/`
- `pytest-cache-files-ruff-batch5/`
- `pytest-cache-files-ruff-batch6/`
- `pytest-cache-files-ruff-batch7/`
- `pytest-cache-files-ruff-final/`
