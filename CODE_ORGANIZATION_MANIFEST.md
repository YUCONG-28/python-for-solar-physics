# Project Code Organization Manifest / 项目代码组织清单

This file records the current architecture after the Astropy/SunPy-style
reorganization. It is the maintained source of truth for package boundaries;
historical migration reports are archived under `docs/history/`.

本文记录 Astropy/SunPy 风格重构后的当前架构，是包边界的维护基准；历史迁移报告仍保留在
`docs/history/` 中。

## Dependency Direction / 依赖方向

The supported dependency direction is:

```text
base utilities -> science-domain packages -> visualization/apps -> scripts/compatibility
基础工具层 -> 科学领域包 -> 可视化与应用层 -> scripts/兼容入口
```

`solar_toolkit.*` is the implementation layer. Package code must not statically
import `scripts`, `legacy`, or `examples`; those trees may call the package but
not the reverse. Importing a public namespace must not scan data, create output
directories, launch a GUI, or execute a workflow.

`solar_toolkit.*` 是唯一实现层。包代码不得静态依赖 `scripts`、`legacy` 或
`examples`；后三者可以调用包，不能反向被包调用。导入公共命名空间不得扫描数据、创建输出目录、
启动 GUI 或执行工作流。

## Public Package Contract / 公共包契约

`import solar_toolkit` is lightweight. Public namespaces are advertised by an
explicit `__all__` and loaded on first attribute access through `__getattr__`;
`__dir__` exposes the same stable list. For example,
`import solar_toolkit; solar_toolkit.radio` works without eagerly importing the
radio scientific stack. The version comes from installed package metadata.

`import solar_toolkit` 保持轻量。公共命名空间由显式 `__all__` 声明，并通过
`__getattr__` 首次访问时加载；`__dir__` 返回同一稳定列表。版本号只读取安装元数据。

| Layer / 层级 | Canonical namespaces / 规范命名空间 | Responsibility / 职责 |
| --- | --- | --- |
| Base / 基础 | `solar_toolkit.time`, `io`, `data`, `map`, `timeseries`, `_utils` | Time parsing, FITS/file discovery, manifests, WCS/HPC helpers, table processing, and private generic utilities. / 时间、文件、WCS 与表格基础能力。 |
| Science / 科学 | `solar_toolkit.aia`, `hmi`, `radio`, `cme`, `xray_dem` | Instrument and science-domain implementations. / 仪器与科学领域实现。 |
| Models / 模型 | `solar_toolkit.modeling.gaussian`; `solar_toolkit.radio.newkirk` | Pure Gaussian model and radio density-model calculations. / 纯高斯模型与射电密度模型。 |
| Network / 网络 | `solar_toolkit.net` | Explicit archive link/query/download helpers; no import-time downloads. / 显式查询与下载，不在导入时联网。 |
| Presentation / 展示 | `solar_toolkit.visualization`, `solar_toolkit.webapp` | Plotting, media generation, image viewer, and local workbench. / 绘图、媒体、图像浏览器和本地工作台。 |

Domain details:

- AIA runs through `config -> io -> difference/mosaic -> processor -> cli`;
  `solar_toolkit.aia._euv_processor_impl` contains the remaining internal
  execution logic.
- HMI implementations live in `solar_toolkit.hmi.fits_rename`, `magnetogram`,
  `processing`, and `overlay`; matching scripts only parse arguments and call
  these modules.
- Radio configuration is canonical in `solar_toolkit.radio.config`.
  `RadioEventConfig` validates named sections and rejects unknown sections;
  installable event modules live in `solar_toolkit.radio.configs`, while
  `scripts.radio.configs` contains only compatibility aliases.
- Complete Radio orchestration is package-owned by
  `solar_toolkit.radio.pipeline_workflow`, `source_map_workflow`, and
  `overlay_workflow`; the matching scripts and legacy paths are thin commands
  or true module aliases.
- `solar_toolkit.radio.provenance` writes `radio_run_provenance.json` beside a
  resolved analysis output. It records the resolved ROI, thresholds,
  Gaussian choices, WCS policy, Newkirk assumptions, configuration source,
  CLI overrides, and precedence order. This reproducibility record does not
  imply full pipeline parity.
- The pure elliptical Gaussian is canonical in
  `solar_toolkit.modeling.gaussian`. Radio-specific analytic variants,
  background estimation, and masks live in `gaussian_models`,
  `gaussian_background`, and `gaussian_masks`. `solar_toolkit.radio.gaussian`
  remains the fit engine and aggregation surface; `gaussian_fit`,
  `gaussian_diagnostics`, and `gaussian_io` expose focused facades without
  copying implementations.
- Browser media resources are internal package data under
  `solar_toolkit.visualization._media_assets`.
- AIA light curves, JSOC download, STEREO/SUVI products, image-sequence video,
  the radio trajectory app, and X-ray/DEM recipes now have package-owned
  implementations. Source scripts are compatibility entry points; the
  network-backed AIA time-distance tutorial is archived under
  `examples/history/`.

领域说明：AIA、HMI、Radio 的实现与完整编排均位于 `solar_toolkit`。事件配置的规范位置为
`solar_toolkit.radio.configs`，旧配置路径只保留兼容别名。浏览器媒体资源的规范位置为私有包
`_media_assets`；源码脚本只负责参数入口或兼容转发。

`solar_toolkit.radio.provenance` 会在已解析的分析输出旁写入
`radio_run_provenance.json`，记录最终 ROI、阈值、Gaussian、WCS、Newkirk 假设及配置优先级；
该复现记录不代表完整 pipeline 已通过等价验证。

## Canonical and Compatibility Paths / 规范路径与兼容路径

Compatibility paths are deprecated from version `0.2.0`. They are retained
through the 0.x series and will not be considered for removal before `1.0.0`;
removal also requires real-data equivalence evidence. New code must use the
canonical path.

兼容路径自 `0.2.0` 起进入弃用期，在整个 0.x 系列保留，最早只能在 `1.0.0` 且真实数据等价
验证完成后评估移除。新代码必须使用规范路径。

| Compatibility path / 兼容路径 | Canonical implementation / 规范实现 |
| --- | --- |
| `solar_toolkit.coordinates` | `solar_toolkit.map.coordinates` |
| `solar_toolkit.cso` | `solar_toolkit.radio.cso` |
| `solar_toolkit.gaussian` | `solar_toolkit.modeling.gaussian` |
| `solar_toolkit.solar_analysis_utils` | Focused `time`, `io`, `map`, `hmi`, `visualization`, and `_utils` modules |
| `solar_toolkit.visualization.media_assets` | `solar_toolkit.visualization._media_assets` |
| `scripts.radio.core.*` | Matching `solar_toolkit.radio.*` module aliases |
| `scripts.aia_hmi.core.*` | Matching `solar_toolkit.aia.*` module aliases |
| `scripts.radio.configs.*` | Matching `solar_toolkit.radio.configs.*` module aliases |
| `scripts.radio.legacy.radio_source_map_plot_gaussian_overlay` | `solar_toolkit.radio.source_map_workflow` |
| `scripts.radio.legacy.sdo_aia_radio_hmi_overlay` | `solar_toolkit.radio.overlay_workflow` |
| Historical workflow scripts | Matching package modules in `aia`, `hmi`, `net`, `radio`, `visualization`, and `xray_dem` |

`scripts/radio/legacy/` contains compatibility aliases, not second scientific
implementations. All files under `scripts/` are thin parsers, launchers, or
module aliases; the package never imports them.

## Command Boundary / 命令边界

Installed commands are registered in `pyproject.toml`:

| Command | Package entry point | Installed behavior |
| --- | --- | --- |
| `solar-aia` | `solar_toolkit.aia.cli:main` | Packaged AIA processing CLI. |
| `solar-radio` | `solar_toolkit.radio.cli:main` | Dispatcher for `centers`, `pipeline`, `source-map`, `overlay`, `quicklook`, `raw-quality`, `roi-lightcurve`, and `trajectory`. |
| `solar-image-viewer` | `solar_toolkit.visualization.image_web_viewer.cli:main` | Packaged local image viewer. |
| `solar-webapp` | `solar_toolkit.webapp.cli:main` | Packaged local workbench; source-only recipes are shown as unavailable when their scripts are absent. |

All eight `solar-radio` subcommands dispatch to installable package runners.
They do not require a source checkout or `scripts.radio`; source scripts call
the same command/workflow modules for compatibility.

`solar-radio` 的八个子命令均直接调用 wheel 内的包实现，不再依赖源码仓库或
`scripts.radio`；旧脚本入口调用同一模块以保持兼容。

## Scientific Parity Status / 科学等价验证状态

The structural moves were checked against baseline commit `301765a` with local
observations. For AIA 2024-01-10, all eight local bands (94, 131, 171, 193,
211, 304, 335, and 1600) matched for selection, ROI cutout, WCS, and original/
running/base arrays; the checked single image and all three 8-band mosaic PNGs
had exact SHA equality. Focused Radio/CSO products for 2025-01-24 and
2025-05-03 also matched within the recorded scope. In addition, the packaged
2025-01-24 Radio pipeline completed with status `0`, and package/compatibility
overlay entry points produced 28 identical PNGs plus an identical diagnostics
CSV. The pipeline run proves the installed orchestration is operational; it is
not a byte-for-byte baseline claim for every end-to-end artifact. Evidence and
exclusions are recorded in
[`docs/validation/astropy_sunpy_reorg_parity.md`](docs/validation/astropy_sunpy_reorg_parity.md).

结构迁移以 `301765a` 为基线。AIA 2024-01-10 的八个本地波段（94、131、171、193、211、
304、335、1600）在选择、ROI 裁剪、WCS 及 original/running/base 数组上完全一致；已检查单图和
三类 8-band mosaic PNG 的 SHA 也完全一致。包内 2025-01-24 Radio pipeline 以状态 `0` 完成；包入口
与兼容入口的 28 张 overlay PNG 及诊断 CSV 完全一致。完整 pipeline 运行证明安装态编排可用，但不
表示所有端到端产物均已与基线逐字节一致；验证范围与未覆盖边界见上述记录。

## Data and Verification Policy / 数据与验证策略

Do not commit raw FITS/FTS/JP2/NetCDF/CDF/HDF5/NumPy observations, local path
configuration, or bulk generated products. Use the interpreter defined in
`AGENTS.md` for validation:

```powershell
$env:PATH="D:\miniforge3\envs\solarphysics_env;D:\miniforge3\envs\solarphysics_env\Library\mingw-w64\bin;D:\miniforge3\envs\solarphysics_env\Library\usr\bin;D:\miniforge3\envs\solarphysics_env\Library\bin;D:\miniforge3\envs\solarphysics_env\Scripts;$env:PATH"
D:\miniforge3\envs\solarphysics_env\python.exe -m compileall -q solar_toolkit scripts tests examples
D:\miniforge3\envs\solarphysics_env\python.exe -m ruff check solar_toolkit scripts tests examples
D:\miniforge3\envs\solarphysics_env\python.exe -m pytest -q tests
```

代码检查验证结构和无数据逻辑；真实数据科学等价必须单独记录，不能由单元测试结果代替。
