# Quickstart for New Users / 新用户快速开始

This guide is the safest first path through the project. It focuses on commands
that do not require local observation data, then points to the scripts that do
need configured FITS, FTS, JP2, NetCDF, CSV, or image folders.

本指南先运行无需本地观测数据的导入和帮助命令，再进入需要 FITS、FTS、JP2、NetCDF、CSV
或图像目录的科学流程。

## 1. Create the Environment

The repository targets Python 3.10+ and is usually developed in the Miniforge
environment named `solarphysics_env`.

```powershell
conda create -n solarphysics_env python=3.11
conda activate solarphysics_env
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e ".[dev,full]"
```

Optional browser and frontend tools use the `app` extra:

```powershell
python -m pip install -e ".[app]"
```

On this Windows workstation, use the explicit project interpreter when running
checks from a non-activated shell:

```powershell
$env:PATH="D:\miniforge3\envs\solarphysics_env;D:\miniforge3\envs\solarphysics_env\Library\mingw-w64\bin;D:\miniforge3\envs\solarphysics_env\Library\usr\bin;D:\miniforge3\envs\solarphysics_env\Library\bin;D:\miniforge3\envs\solarphysics_env\Scripts;$env:PATH"
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
D:\miniforge3\envs\solarphysics_env\python.exe -m compileall -q solar_toolkit scripts tests examples
D:\miniforge3\envs\solarphysics_env\python.exe -m pytest -q tests\test_imports.py tests\test_public_package_boundaries.py tests\test_project_docs_current_paths.py
```

## 2. Try the Library Layer First

These imports are data-independent and safe to run before any local archive is
configured:

```python
from solar_toolkit.time import extract_time_from_filename, nearest_by_time
from solar_toolkit.io import scan_files, scan_fits, read_fits_data_header
from solar_toolkit.map import get_display_extent, normalize_image
from solar_toolkit.timeseries import normalize_time_column, smooth_series
from solar_toolkit.net import download_url, collect_links
from solar_toolkit.cme import extract_lasco_timestamp, running_difference
from solar_toolkit.xray_dem import load_sxr_data, calculate_derivative
```

The root package is lazy: this imports `radio` only when requested.

```python
import solar_toolkit

radio = solar_toolkit.radio
```

根包使用懒加载；`import solar_toolkit` 不会启动工作流、扫描数据或立即导入全部科学依赖。

The package layout follows a lightweight SunPy-style boundary:

- `solar_toolkit.time`, `io`, `data`, `map`, and `timeseries` hold shared
  helpers for local files, timestamps, image metadata, and light-curve tables.
- `solar_toolkit.aia`, `hmi`, `radio`, `xray_dem`, and `cme` hold
  instrument- or domain-specific helpers.
- `solar_toolkit.net`, `modeling`, and `visualization` hold archive access,
  science-model, plotting, browser, and video-export helpers.

Use `solar_toolkit.modeling.gaussian`, `solar_toolkit.map.coordinates`, and
`solar_toolkit.radio.cso` for new code. The old root paths are compatibility
aliases deprecated from `0.2.0`; they remain through 0.x and are not considered
for removal before `1.0.0` plus real-data equivalence review.

新代码应使用上述规范路径。旧根路径从 `0.2.0` 起进入弃用期，0.x 期间继续保留，最早在
`1.0.0` 且完成真实数据等价复核后才会评估移除。

## 3. Configure Local Data Only When Needed

Most science workflows need local observation files. Copy the path template and
edit the local copy:

```powershell
Copy-Item configs\paths.example.yaml configs\paths.local.yaml
```

`configs/paths.local.yaml` is ignored by Git. You can also point to an external
YAML file:

```powershell
$env:SOLAR_PHYSICS_CONFIG="D:\my_project\solar_paths.yaml"
```

See `docs/path_configuration.md` for the expected YAML shape.

Radio runs that resolve an analysis output can write
`radio_run_provenance.json` through `solar_toolkit.radio.provenance`. The file
records the resolved ROI, thresholds, Gaussian/WCS/Newkirk assumptions and the
CLI → explicit config → path-only environment → defaults precedence. It is a
reproducibility record, not a full-pipeline parity claim.

射电流程在解析出分析输出目录后，可通过 `solar_toolkit.radio.provenance` 写入
`radio_run_provenance.json`，记录最终 ROI、阈值、Gaussian/WCS/Newkirk 假设与配置优先级。
该文件用于复现，不代表完整 pipeline 已完成等价验证。

## 4. Safe Entrypoint Checks

After installation, these package commands only show help and should not start
a real data run:

```powershell
solar-aia --help
solar-radio --help
solar-radio centers --help
solar-radio pipeline --help
solar-radio source-map --help
solar-radio overlay --help
solar-radio quicklook --help
solar-radio raw-quality --help
solar-radio roi-lightcurve --help
solar-radio trajectory --help
solar-image-viewer --help
solar-webapp --help
```

安装后的四个主命令及全部八个 `solar-radio` 子命令都支持无数据的 `--help` 检查；
`pipeline/source-map/overlay` 的实现和默认事件配置均包含在 wheel 中。

Source-checkout compatibility commands remain available:

```powershell
D:\miniforge3\envs\solarphysics_env\python.exe scripts\aia_hmi\run_aia_euv_processor.py --help
D:\miniforge3\envs\solarphysics_env\python.exe scripts\aia_hmi\sdo_aia_hmi_fits_rename.py --help
D:\miniforge3\envs\solarphysics_env\python.exe scripts\data_download\solo_eui_soar_query_download.py --help
D:\miniforge3\envs\solarphysics_env\python.exe scripts\radio\run_radio_burst_pipeline.py --help
D:\miniforge3\envs\solarphysics_env\python.exe scripts\tools\run_image_web_viewer.py --help
D:\miniforge3\envs\solarphysics_env\python.exe scripts\tools\run_solar_webapp.py --help
```

For the current public script inventory, use `docs/script_index.md`.

## 5. Open the Modular Radio Workspace

After declaring the local folders that the application may access, start the
existing workbench and open `/radio` on the same host and port:

```powershell
solar-webapp `
  --allowed-roots "D:\radio_data;D:\analysis_outputs" `
  --radio-output-root D:\analysis_outputs `
  --open-browser
```

The Radio Workspace does not assume a full pipeline run. Select only the needed
modules, then use an action's Preview or Run button. Presets only change the
module layout, and Run Selected requires explicit action checkboxes plus a
confirmation review. Disabled or collapsed modules are not run as hidden
dependencies. See [`radio_workspace.md`](radio_workspace.md) for the complete
module inventory, persistence layout, API, and compatibility details.

## 6. First Real Workflows

Use these only after local data paths are configured:

- AIA EUV products: `solar-aia` or `scripts/aia_hmi/run_aia_euv_processor.py`
- Full radio burst processing: `solar-radio pipeline` or `scripts/radio/run_radio_burst_pipeline.py`
- Radio source maps and overlays: `solar-radio source-map` / `solar-radio overlay`
- Radio-source center extraction: `scripts/radio/extract_radio_centers.py`
- Radio-source trajectory playback plus MP4/WebM browser recording and
  MP4/GIF/WebM backend export: `scripts/radio/run_radio_source_app.py`
- Radio ROI selection and light-curve export: `solar-radio roi-lightcurve` or
  `scripts/radio/run_radio_roi_lightcurve_app.py`
- Multi-folder image review and MP4/GIF/WebM recording or export:
  `scripts/tools/run_image_web_viewer.py`
- Unified local English web GUI:
  `scripts/tools/run_solar_webapp.py`
- Selective integrated radio analysis on the same workbench port:
  `http://127.0.0.1:7870/radio`

The installed commands and source scripts call the same package-owned Radio
workflows. Real-data equivalence evidence and its precise scope are recorded in
[`validation/astropy_sunpy_reorg_parity.md`](validation/astropy_sunpy_reorg_parity.md).

安装命令与源码薄脚本调用同一包内 Radio 工作流；真实数据等价证据及其精确范围见上述记录。

Raw observations, generated figures, videos, CSV/XLSX products, and local cache
folders should stay outside Git unless they are explicitly reviewed and moved
under `docs/assets/` as small documentation assets.
