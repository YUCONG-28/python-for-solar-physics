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
| Local data inventory / 本地数据清单 | `solar_toolkit.data.inventory` | Lightweight observation records; no network side effects. |
| Map/WCS/HPC / 图像与坐标 | `solar_toolkit.map.coordinates`, `metadata`, `image`, `operations` | Coordinate conversion, display extent, ROI, normalization, map operations. |
| Time series / 时间序列 | `solar_toolkit.timeseries.processing`, `tables` | Time normalization, clipping, smoothing, finite differences. |
| Network / 网络 | `solar_toolkit.net.downloads`, `links`, `soar`, `stereo`, `suvi` | Explicit archive operations and downloads. |

Each package `__init__.py` precisely re-exports its documented public API; the
implementation does not live in `__init__.py`.

各包的 `__init__.py` 只精确重导出公共 API，实现位于语义明确的子模块中。

## Science and Application Layer / 科学与应用层

| Functional family / 功能族 | Canonical implementation / 规范实现 | Public or command surface / 公共或命令入口 |
| --- | --- | --- |
| AIA processing | `solar_toolkit.aia.config`, `io`, `difference`, `mosaic`, `processor`; internal executor `_euv_processor_impl` | `solar_toolkit.aia`, `solar-aia`, `scripts/aia_hmi/run_aia_euv_processor.py` |
| HMI rename/plot/overlay | `solar_toolkit.hmi.fits_rename`, `magnetogram`, `processing`, `overlay` | Thin scripts under `scripts/aia_hmi/` |
| Radio event config | `solar_toolkit.radio.config.RadioEventConfig` and loaders | Event adapters under `scripts.radio.configs`; CLI/config object/mapping inputs |
| Radio run provenance | `solar_toolkit.radio.provenance` | Writes `radio_run_provenance.json` with resolved ROI, thresholds, Gaussian/WCS/Newkirk assumptions, config source, CLI overrides, and precedence. / 写入最终科学假设与优先级。 |
| Radio coordinates and FITS I/O | `solar_toolkit.radio.coordinates`, `io` | `solar_toolkit.radio` lazy namespace |
| Pure Gaussian model | `solar_toolkit.modeling.gaussian` | `solar_toolkit.modeling.gaussian` |
| Radio Gaussian domain logic | `solar_toolkit.radio.gaussian_models`, `gaussian_background`, `gaussian_masks`, plus the fit engine in `solar_toolkit.radio.gaussian` | Focused `gaussian_fit`, `gaussian_diagnostics`, and `gaussian_io` facades; `radio.gaussian` aggregation surface |
| CSO and spectrogram | `solar_toolkit.radio.cso`, `spectrogram` | `solar_toolkit.radio.cso`, `solar_toolkit.radio.spectrogram` |
| Drift/Newkirk products | `solar_toolkit.radio.drift_rate`, `drift_products`, `newkirk`, `height_comparison`, `height_plots`, `frequency_priority_diagnostics` | Radio library API and source-checkout pipeline |
| Radio centers/quality/trajectory | `solar_toolkit.radio.centers`, `raw_quality`, `trajectory`, `quicklook` | `solar-radio centers/raw-quality/trajectory/quicklook` |
| LASCO/CME | `solar_toolkit.cme.files`, `lasco`, `processing` | Thin scripts under `scripts/lasco_cme/` |
| X-ray/DEM | `solar_toolkit.xray_dem.sxr`, `hxi`, `processing` and packaged CLI helpers | Thin scripts under `scripts/xray_dem/` |
| Plotting and media | `solar_toolkit.visualization.plotting`, `frames`, `media`, `radio_source_trajectory`, `radio_source_video` | `solar-image-viewer` and package visualization APIs |
| Local workbench | `solar_toolkit.webapp.registry`, `runner`, `server`, `cli` | `solar-webapp`; missing source-only recipes are reported unavailable |

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
| `scripts.radio.configs` loader helpers | `solar_toolkit.radio.config` | Event modules remain valid adapters. |

`scripts/radio/legacy/` still contains large compatibility workflow
orchestration. It may call the package, but the package does not import it.

`scripts/radio/legacy/` 仍保留大型兼容工作流编排；它可以调用公共包，但公共包不反向导入它。

## Installed CLI Map / 安装后命令映射

| Command | Subcommands or role | Current boundary |
| --- | --- | --- |
| `solar-aia` | AIA single/mosaic/difference workflow | Fully package-owned command surface. |
| `solar-radio` | `centers`, `pipeline`, `source-map`, `overlay`, `quicklook`, `raw-quality`, `trajectory` | `centers/quicklook/raw-quality/trajectory` are package runners. `pipeline/source-map/overlay` return `2` without an explicitly supplied source compatibility runner. |
| `solar-image-viewer` | Local multi-folder image viewer | Fully package-owned command surface. |
| `solar-webapp` | Local English workbench | Package-owned shell; source-only recipes are disabled when absent from an installed wheel. |

For full `pipeline`, `source-map`, and AIA/radio/HMI `overlay` execution, use
the thin scripts in a source checkout until their complete orchestration has
separate end-to-end parity evidence.

完整 `pipeline/source-map/overlay` 在端到端等价证据完成前，仍应在源码仓库中通过对应薄脚本运行。

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

This metadata supports reproducibility; it is not evidence that the complete
radio pipeline or every legacy orchestration has parity.

该元数据用于复现，不构成完整射电 pipeline 或全部 legacy 编排已经等价的证据。

## Validation Boundary / 验证边界

Focused real-data structural parity is recorded in
[`validation/astropy_sunpy_reorg_parity.md`](validation/astropy_sunpy_reorg_parity.md).
It covers selected AIA and Radio/CSO products, not the complete radio pipeline
or every legacy workflow.

真实数据分项验证见上述记录；它不覆盖完整射电 pipeline，也不覆盖所有 legacy 工作流。
