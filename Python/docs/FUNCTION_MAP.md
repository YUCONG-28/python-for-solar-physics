# Function Map / 功能映射

This map distinguishes the canonical implementation, public aggregation
surface, runnable command, and compatibility alias for each functional family.
New reusable code should import only from `solar_toolkit.*`.

本表区分每个功能族的规范实现、公共聚合入口、可执行命令和兼容别名。新增可复用代码只应从
`solar_toolkit.*` 导入。

## Base Layer / 基础层

| Functional family / 功能族 | Canonical modules / 规范模块 | Notes / 说明 |
| --- | --- | --- |
| Time / 时间 | `solar_toolkit.time.parsing`, `formatting`, `selection` | Filename/ISO time parsing, formatting, nearest-time and range selection. |
| File and FITS I/O / 文件与 FITS | `solar_toolkit.io.discovery`, `fits`, `manifest`, `sorting` | Local scanning, deterministic ordering, FITS reads, manifest writes. |
| Local data inventory / 本地数据清单 | `solar_toolkit.data.inventory`, `stereo_manifest` | Lightweight observation records and explicit STEREO manifest generation. |
| Map/WCS/HPC / 图像与坐标 | `solar_toolkit.map.coordinates`, `metadata`, `image`, `operations` | Coordinate conversion, display extent, ROI, normalization, map operations. |
| Time series / 时间序列 | `solar_toolkit.timeseries.processing`, `tables` | Time normalization, clipping, smoothing, finite differences. |
| Network / 网络 | `solar_toolkit.net.downloads`, `links`, `jsoc`, `soar`, `stereo`, `suvi` | Explicit archive operations and downloads. |

Each package `__init__.py` precisely re-exports its documented public API; the
implementation does not live in `__init__.py`.

各包的 `__init__.py` 只精确重导出公共 API，实现位于语义明确的子模块中。

## Science and Application Layer / 科学与应用层

| Functional family / 功能族 | Canonical implementation / 规范实现 | Public or command surface / 公共或命令入口 |
| --- | --- | --- |
| AIA processing | `solar_toolkit.aia.config`, `io`, `difference`, `mosaic`, `processor`; internal executor `_euv_processor_impl` | `solar_toolkit.aia`, `solar-aia`, thin scripts under `scripts/aia_hmi/` |
| AIA light curves | `solar_toolkit.aia.lightcurve_extraction`, `lightcurve_plot` | Package workflows plus old script aliases |
| HMI rename/plot/overlay | `solar_toolkit.hmi.fits_rename`, `magnetogram`, `processing`, `overlay`, `overlay_cli` | Thin scripts under `scripts/aia_hmi/` |
| Radio event config | `solar_toolkit.radio.config.RadioEventConfig`; installable modules in `solar_toolkit.radio.configs` | Old `scripts.radio.configs.*` paths are module aliases; CLI/config object/mapping inputs |
| Radio run provenance | `solar_toolkit.radio.provenance` | Writes `radio_run_provenance.json` with resolved ROI, thresholds, Gaussian/WCS/Newkirk assumptions, config source, CLI overrides, and precedence. / 写入最终科学假设与优先级。 |
| Radio coordinates and FITS I/O | `solar_toolkit.radio.coordinates`, `io` | `solar_toolkit.radio` lazy namespace |
| Pure Gaussian model | `solar_toolkit.modeling.gaussian` | `solar_toolkit.modeling.gaussian` |
| Radio Gaussian domain logic | `solar_toolkit.radio.gaussian_models`, `gaussian_background`, `gaussian_masks`, plus the fit engine in `solar_toolkit.radio.gaussian` | Focused `gaussian_fit`, `gaussian_diagnostics`, and `gaussian_io` facades; `radio.gaussian` aggregation surface |
| Radio orchestration | `solar_toolkit.radio.pipeline_workflow`, `source_map_workflow`, `overlay_workflow` | Installable `solar-radio pipeline/source-map/overlay`; thin legacy aliases |
| CSO and spectrogram | `solar_toolkit.radio.cso`, `spectrogram`, `cso_workflow` | Package API and old CSO script alias |
| Drift/Newkirk products | `solar_toolkit.radio.drift_rate`, `drift_products`, `newkirk`, `height_comparison`, `height_plots`, `frequency_priority_diagnostics` | Radio library API and package pipeline |
| Radio centers/quality/trajectory | `solar_toolkit.radio.centers`, `raw_quality`, `trajectory`, `quicklook` | `solar-radio centers/raw-quality/trajectory/quicklook` |
| Radio ROI light curves | `solar_toolkit.radio.roi_lightcurve`, `roi_lightcurve_app`, `roi_lightcurve_launcher` | `solar-radio roi-lightcurve`; managed Streamlit workflow |
| Independent Radio selections/media/context | `solar_toolkit.radio.roi_selection_cli`, `drift_selection_cli`, `trajectory_media_cli`, `existing_fit_overlay`, `existing_fit_overlay_cli` | Structured `/radio` actions; same-page Plotly selection/playback, local media export, and static AIA-backed overlays from persisted center/Gaussian tables |
| Radio Workspace contracts/services | `solar_toolkit.webapp.radio_workspace.contracts`, `catalog`, `store`, `native_previews`, `figure_time` | Versioned module/action/workspace/run/artifact and Figure Studio schemas, allowed-root persistence, native previews, UTC matching, and export preflight |
| Radio Workspace orchestration | `solar_toolkit.webapp.radio_workspace.runner`, `api` | Selected-action queue, cancellation, provenance, artifact reuse, Figure Studio persistence/export, and `/api/radio/*`; never auto-runs upstream modules |
| LASCO/CME | `solar_toolkit.cme.files`, `lasco`, `processing` | Thin scripts under `scripts/lasco_cme/` |
| X-ray/DEM | `solar_toolkit.xray_dem.sxr`, `hxi`, `processing`, `aia_dem_inversion`, `aia_hxi_overlay`, `dem_radio_source_overlay`, `dem_radio_cli`, `hxi_image`, `hxi_lightcurve`, `hxi_sxr_comparison` | Thin aliases under `scripts/xray_dem/`; structured non-interactive DEM/radio adapter for `/radio` |
| Plotting and media | `solar_toolkit.visualization.plotting`, `frames`, `media`, `video_cli`, `radio_source_trajectory`, `radio_source_video`, STEREO/SUVI modules | `solar-image-viewer`, package APIs, and thin script aliases |
| Radio trajectory app | `solar_toolkit.radio.source_app`, `source_app_launcher` | Package-owned Streamlit workflow and old script aliases |
| Local workbench | `solar_toolkit.webapp.registry`, `runner`, `server`, `cli`, `radio_workspace` | `solar-webapp`; integrated `/radio` on the same port, with source-only non-radio recipes reported unavailable when absent |

## Compatibility Alias Map / 兼容别名表

Compatibility aliases are deprecated from `0.2.0`, remain available throughout
0.x, and are not candidates for removal before `1.0.0` plus real-data
equivalence review.

兼容别名自 `0.2.0` 起进入弃用期，0.x 期间继续保留；最早只能在 `1.0.0` 且真实数据等价复核
完成后评估移除。

| Old path / 旧路径 | Use instead / 规范路径 | Compatibility behavior / 兼容行为 |
| --- | --- | --- |
| `solar_toolkit.coordinates` | `solar_toolkit.map.coordinates` | Real module alias. |
| `solar_toolkit.cso` | `solar_toolkit.radio.cso` | Real module alias. |
| `solar_toolkit.gaussian` | `solar_toolkit.modeling.gaussian` | Real module alias for pure Gaussian helpers. |
| `solar_toolkit.solar_analysis_utils` | Focused base/HMI/visualization modules | Deprecated forwarding facade. |
| `solar_toolkit.visualization.media_assets` | `solar_toolkit.visualization._media_assets` | Private resource-package alias; not in public `__all__`. |
| `scripts.radio.core.radio_*` | Matching `solar_toolkit.radio.*` module | Module alias, not a copied implementation. |
| `scripts.aia_hmi.core.aia_*` | Matching `solar_toolkit.aia.*` module | Module alias, not a copied implementation. |
| `scripts.aia_hmi.core._aia_euv_processor_impl` | `solar_toolkit.aia._euv_processor_impl` | Real private-module alias; removes dual maintenance. |
| `scripts.radio.configs.*` | `solar_toolkit.radio.configs.*` | Real module aliases; default configs ship in the wheel. |
| `scripts.radio.legacy.radio_source_map_plot_gaussian_overlay` | `solar_toolkit.radio.source_map_workflow` | Real module alias. |
| `scripts.radio.legacy.sdo_aia_radio_hmi_overlay` | `solar_toolkit.radio.overlay_workflow` | Real module alias. |
| Moved AIA/HMI, X-ray/DEM, media, CSO, app, and STEREO/SUVI scripts | Matching `solar_toolkit.*` workflow module | Thin command or real module alias. |

`scripts/` contains no second scientific implementation. Compatibility paths
may import the package, but the package never imports `scripts`, `legacy`, or
`examples`.

`scripts/` 不再保存第二份科学实现；兼容入口可以导入包，包不得反向依赖
`scripts`、`legacy` 或 `examples`。

## Installed CLI Map / 安装后命令映射

| Command | Subcommands or role | Current boundary |
| --- | --- | --- |
| `solar-aia` | AIA single/mosaic/difference workflow | Fully package-owned command surface. |
| `solar-radio` | `centers`, `pipeline`, `source-map`, `overlay`, `quicklook`, `raw-quality`, `roi-lightcurve`, `trajectory` | All eight subcommands are package-owned and wheel-installable. |
| `solar-image-viewer` | Local multi-folder image viewer | Fully package-owned command surface. |
| `solar-webapp` | Local English workbench plus modular `/radio` workspace | Package-owned single-port shell; Radio modules run only explicitly selected actions, while absent source-only recipes remain disabled. |

The source scripts and installed commands dispatch to the same package-owned
workflows; choose either surface according to how the project is installed.

源码脚本与安装命令调用同一包内工作流，可按安装方式选择入口。

## Configuration Precedence / 配置优先级

The intended order is CLI arguments, then an explicit configuration
file/object/mapping, then path-only environment configuration, then defaults.
Scientific ROI, threshold, Gaussian, and Newkirk assumptions are not inferred
from environment variables. Unknown `RadioEventConfig` sections raise an error.
When a radio runner resolves an output directory, the resolved assumptions and
precedence can be written by `solar_toolkit.radio.provenance` to
`radio_run_provenance.json` beside the products.

优先级为：CLI 参数 → 显式配置文件/对象/映射 → 仅路径类环境配置 → 默认值。ROI、阈值、
Gaussian 和 Newkirk 等科学假设不从环境变量推断；未知 Radio 配置段会直接报错。解析输出目录后，
`solar_toolkit.radio.provenance` 可在产品旁写入 `radio_run_provenance.json`，保存最终假设与优先级。

This metadata supports reproducibility; it is not by itself evidence that the
complete radio pipeline or every legacy orchestration has baseline parity.

The Radio Workspace has a separate, action-scoped order from lowest to highest:
package defaults, event preset, workspace shared paths, workspace/request
Advanced JSON, and the current action form or artifact binding. Each layer is
written to the run manifest. Module selection and presets are not configuration
execution triggers. Full details are in
[`radio_workspace.md`](radio_workspace.md).

该元数据用于复现，本身不构成完整射电 pipeline 或全部 legacy 编排已经达到基线等价的证据。

## Validation Boundary / 验证边界

Focused real-data structural parity is recorded in
[`validation/astropy_sunpy_reorg_parity.md`](validation/astropy_sunpy_reorg_parity.md).
It covers selected AIA and Radio/CSO products. The same record separately
documents a successful packaged 2025-01-24 pipeline run and exact
package/compatibility overlay outputs; that operational evidence is not a
byte-for-byte baseline claim for every pipeline artifact or legacy workflow.

真实数据分项验证见上述记录；其中另行记录了包内 2025-01-24 pipeline 成功运行，以及包入口/兼容
入口 overlay 输出完全一致。该运行证据不表示全部 pipeline 产物或所有 legacy 工作流均已与基线
逐字节一致。
