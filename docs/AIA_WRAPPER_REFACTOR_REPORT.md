# AIA Wrapper Refactor Report

Date: 2026-05-22

## Scope

Phase 2A converts legacy AIA difference scripts into compatibility wrappers
only where the shared AIA processor already covers the scientific operation.
No files were deleted, moved, renamed, staged, committed, or pushed. No real
FITS batch processing or image generation was run during this phase.

## AIA Main Code

- `scripts/aia_hmi/sdo_aia_euv_processor.py`

This is the primary implementation for exposure-normalized AIA single-band
images, mosaics, base differences, and running differences.

## Basic Code Retention

- `scripts/aia_hmi/sdo_aia_multichannel_panel.py`

Recommendation: keep this file for now as a teaching/basic multi-wavelength
panel example. It contains a compact synchronization workflow around a 171 A
base channel, auto percentile display ranges, and a fixed six-panel plotting
style that remains useful for explanation even though the main processor is the
recommended production entry point.

## Wrapper Candidates Converted

- `scripts/aia_hmi/sdo_aia_base_difference.py`
- `scripts/aia_hmi/sdo_aia_running_difference.py`

Both files are now compatibility wrappers. Their previous important defaults
are preserved in `LEGACY_DEFAULTS` dictionaries, and execution is delegated to
`scripts/aia_hmi/sdo_aia_euv_processor.py`. The wrappers use lazy imports for
the main processor so importing the wrapper modules remains lightweight and
does not load the FITS-processing stack until a wrapper is actually executed.

## Legacy Parameter Comparison

| 参数/行为 | base difference 旧脚本 | running difference 旧脚本 | 主处理器是否覆盖 | 处理方式 |
| --- | --- | --- | --- | --- |
| 主科学操作 | `current_data - base_data` | `current_data - prev_data` | 是 | wrapper 设置 `difference_method="base"` 或 `"running"` |
| 参考帧/参考时间 | `sliced_files[0]`，即选中范围内第一帧；旧配置 `start_idx=99`, `end_idx=200` | 每一帧减去选中序列中前一帧；旧配置 `start_idx=150`, `end_idx=450` | 是 | base wrapper 使用 `difference_base_index=None`，与主处理器“选中范围第一帧”为 base 的逻辑一致；running wrapper 使用主处理器相邻帧规则 |
| 单波段目录结构 | `data_dir` 直接指向单个波段 FITS 目录 `D:/Flare/JSOCdata/All/AIA_131_pro/` | `data_dir` 直接指向单个波段 FITS 目录 `D:/spike_topping_type_III/20250124/All/94/1/` | 是，通过程序接口覆盖 | wrapper 设置 `use_band_subdirs=False`，避免主处理器默认寻找 `data_path/<wave>/` |
| 波段 | 131 A | 94 A | 是 | wrapper 设置 `multi_band_wavelengths` 和 `difference_wavelengths` 为单波段 |
| ROI/submap | `(Tx 180, 520; Ty -340, 20)` | `(Tx 600, 1210; Ty -280, 100)` | 是 | wrapper 设置 `roi_bounds=(xmin, xmax, ymin, ymax)` |
| vmin/vmax | `Normalize(vmin=-888, vmax=888)` | `Normalize(vmin=-777, vmax=777)` | 是 | wrapper 设置 `difference_norm_mode="fixed"`，并保留对应 `difference_vmin`/`difference_vmax` |
| colormap | `sdoaia131` 用于差分图 | `sdoaia94` 用于差分图 | 是 | wrapper 设置 `difference_cmap_mode="band"`，由主处理器按 AIA 波段选择 colormap |
| percentile scaling | 无；固定 vmin/vmax | 无；固定 vmin/vmax | 是 | wrapper 不使用主处理器自动 percentile 模式 |
| exposure correction | `map.data / map.exposure_time` | `map.data / map.exposure_time` | 是 | 主处理器 `_load_exposure_normalized_map` 统一处理 |
| derotation/reprojection | 对 cutout 使用 `propagate_with_solar_surface()` 后 reproject 到 base cutout WCS | 注释称删除消自转；直接把 cutout reproject 到 first cutout WCS | 部分覆盖 | 主处理器支持 `difference_derotate`，但语义是 full-map derotation 后 ROI cutout。wrapper 保持 `difference_derotate=False`，避免引入新的 full-map derotation行为；旧 base 的 cutout-level propagate 作为复现风险记录 |
| 输出目录 | `D:/Flare/JSOCdata/All/AIA_131_pro/difference_two_plot_min/` | `D:/spike_topping_type_III/20250124/All/94/1/differnce_plot/` | 部分覆盖 | 旧路径保存在 `LEGACY_DEFAULTS` 和本文档；主处理器使用标准 `difference/<wave>/<method>_difference` 输出布局 |
| 输出命名 | base 参考图保存语句被注释；差分为 `{current_filename}_diff_from_base.png` | 第一帧保存为 `{first_filename}.png`；差分为 `{current_filename}_diff.png` | 部分覆盖 | 主处理器标准命名为 `{current_time}_base_diff.png` 或 `{current_time}_running_diff.png`；旧命名保存在 `LEGACY_DEFAULTS` 和本文档，不在 wrapper 中重写主输出逻辑 |
| show_plot | `False` | `False` | 是 | 主处理器默认非交互后端运行，wrapper 不打开 GUI/交互显示 |
| 输出 DPI | 300 | 300 | 是 | 主处理器默认 `dpi=300` |
| 错误处理 | 单帧失败后继续处理 | 单帧/帧对失败后继续处理 | 是 | 主处理器 worker 收集并报告失败帧 |

## Functions That Cannot Be Wrapper-Mapped Exactly

The scientific subtraction modes are covered, so wrapper conversion is safe for
the core AIA difference operation. The following historical behaviors are not
mapped exactly because doing so would require modifying the main processor or
reintroducing custom output code into the wrappers:

- Exact legacy output directories as final leaf directories.
- Exact legacy output filename patterns based on full FITS filename.
- The running-difference script's first-frame PNG, which was an original
  exposure-normalized image rather than a true difference frame.
- The base-difference script's cutout-level `propagate_with_solar_surface()`
  behavior. The main processor supports derotation, but intentionally applies
  full-map reprojection before ROI cutout when enabled.

These are documented rather than silently discarded.

## Publication Reproducibility Risks

Parameters that may affect reproduction of old figures:

- Base-difference ROI: `(180, 520, -340, 20)`.
- Running-difference ROI: `(600, 1210, -280, 100)`.
- Base-difference fixed display range: `[-888, 888]`.
- Running-difference fixed display range: `[-777, 777]`.
- Base-difference band colormap: `sdoaia131`.
- Running-difference band colormap: `sdoaia94`.
- Base selected range: `start_idx=99`, `end_idx=200`.
- Running selected range: `start_idx=150`, `end_idx=450`.
- Legacy output folder and filename conventions.
- Old base-difference cutout-level derotation/reprojection behavior.

If a paper figure depends on pixel-exact reproduction, compare old saved output
against the main processor output before deleting or archiving the historical
implementation.

## Wrapper Test Coverage

Added `tests/test_aia_difference_wrappers.py` for lightweight compatibility
wrapper coverage.

The tests:

- Import the base and running wrapper modules and verify they do not auto-run
  real processing at import time.
- Verify pure processor keyword arguments through `build_legacy_config_kwargs()`
  without importing the main AIA processor or reading real FITS files.
- Verify `build_legacy_config()` with a fake processor config class, avoiding
  the real FITS-processing dependency stack.
- Monkeypatch `process_aia_fits` when checking wrapper `main()` delegation, so
  the real AIA processor is not executed.
- Do not create PNG, CSV, MP4, or other output products.
- Cover the preserved legacy parameters:
  - base `difference_method="base"`, wavelength `131`, ROI
    `(180, 520, -340, 20)`, fixed limits `[-888, 888]`, `start_idx=99`,
    `end_idx=200`;
  - running `difference_method="running"`, wavelength `94`, ROI
    `(600, 1210, -280, 100)`, fixed limits `[-777, 777]`, `start_idx=150`,
    `end_idx=450`;
  - `use_band_subdirs=False` and `difference_derotate=False` for both wrappers.

Still requiring real-data manual comparison:

- Exact legacy output naming.
- Exact legacy output directory behavior.
- Base-difference cutout-level derotation/reprojection behavior.
- Running-difference first-frame original-image save behavior.

## Next Steps

1. Keep the lightweight wrapper configuration tests in place and extend them if
   future wrapper options are added.
2. Decide whether exact legacy output naming is still needed. If yes, add a
   supported naming option to the main processor rather than custom code in the
   wrappers.
3. Decide whether the base script's historical cutout-level derotation should
   remain documented only or become an explicit compatibility option.
4. Keep `sdo_aia_multichannel_panel.py` unchanged until a separate teaching
   example pass.
5. Do not delete the old wrapper files until at least one real-data comparison
   has been reviewed manually.
