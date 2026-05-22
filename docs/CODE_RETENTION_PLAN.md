# Code Retention Plan

Date: 2026-05-22

## Scope

Phase 1 classification of project scripts before legacy-code consolidation.
This document is analysis only. No files were deleted, moved, renamed, staged,
committed, pushed, or algorithmically modified.

Classification rules used here:

- Main code: the most complete and current script that should be recommended
  from the README as the primary runnable entry point.
- Basic code: the simplest understandable script for teaching, quick tests, or
  low-friction reproduction of the same workflow.
- Legacy code: code whose behavior is covered by the main code, code with
  duplicated implementation, or code kept mainly for historical/reference value.
- Do not auto-delete files that may preserve publication parameters, scientific
  experiments, GUI behavior, or unverified background-subtraction logic.

## Retention Table

| 功能模块 | 主代码 | 基础代码 | 可合并旧代码 | 暂不动文件 | 合并方式 | 删除风险 |
| --- | --- | --- | --- | --- | --- | --- |
| AIA 图像与差分 | `scripts/aia_hmi/sdo_aia_euv_processor.py` | `scripts/aia_hmi/sdo_aia_base_difference.py`; `scripts/aia_hmi/sdo_aia_running_difference.py`; `scripts/aia_hmi/sdo_aia_multichannel_panel.py` 中建议保留 `sdo_aia_multichannel_panel.py` 作为多波段教学示例，差分脚本后续改 wrapper | `scripts/aia_hmi/sdo_aia_base_difference.py`; `scripts/aia_hmi/sdo_aia_running_difference.py`; `scripts/aia_hmi/sdo_aia_multichannel_panel.py` | `scripts/aia_hmi/sdo_aia_hmi_overlay.py` 暂按 AIA/HMI 专用叠加工具保留，不并入 EUV processor | 将 base/running difference 参数映射到 `sdo_aia_euv_processor.py --draw-difference --difference-method ...`；将多波段面板收敛为 processor 的 `--mode mosaic` 示例或轻量 wrapper | 中到高。旧差分脚本可能保留论文图的 ROI、色标、参考帧、输出命名和人工调参；不能自动删除 |
| Radio source map | `scripts/radio/radio_source_map_plot_gaussian_overlay.py` | `scripts/radio/radio_source_map_plot.py` | 暂无直接删除项；基础脚本可长期作为无 Gaussian/无频谱联动的简化入口 | `scripts/radio/spectrogram_drift_rate_manual_selection.json` 暂不动，先确认是示例还是本地运行结果 | 主代码保留完整 Gaussian、CSO 频谱面板、漂移率和诊断功能；基础代码后续可改为调用主代码的简化配置 wrapper | 中。基础脚本降低学习门槛；JSON 可能包含手动选点结果或本地路径 |
| AIA + radio + HMI overlay | `scripts/radio/sdo_aia_radio_hmi_overlay.py` | 建议后续从 `examples/radio_aia_hmi/aia_radio_hmi_overlay_demo.py` 精简出一个最小示例；当前不要同时保留多个重复大示例 | `examples/radio_aia_hmi/aia_radio_hmi_overlay_demo.py`; `examples/radio_aia_hmi/aia_radio_hmi_overlay_extended_example.py`; `examples/radio_aia_hmi/aia_radio_overlay_variant0_example.py`; `examples/radio_aia_hmi/aia_radio_overlay_variant1_example.py` | `scripts/radio/sdo_aia_radio_hmi_overlay_bgcorrected.py` 绝对暂不动 | 把 demo/extended/variant 示例收敛为一个小 wrapper 或 README 示例配置；重复的时间解析、坐标、Gaussian fit 逻辑由主脚本或后续公共模块提供 | 高。背景扣除实验版可能改变射电强度、轮廓、掩膜和 Gaussian 结果；历史 variant 可能保存论文图参数 |
| CSO spectrogram | `scripts/radio/cso_radio_spectrogram_plot.py` | 建议保留 `scripts/radio/cso_spectrogram_class.py` 作为基础 reader/helper；`examples/radio/cso_spectrogram_processing_example.py` 后续改为调用该 helper 的短示例 | `examples/radio/cso_spectrogram_processing_example.py`; `scripts/radio/cso_spectrogram_class.py` 中与主代码重复的绘图/切片逻辑 | `scripts/radio/cso_radio_spectra_gui.py` 暂作为 optional GUI 保留 | 主代码负责内存友好绘图、降采样、多偏振和输出；基础 helper 只保留 FITS 读取、切片和最小绘图；示例文件后续 wrapper 化 | 中到高。GUI 有交互选择和 type-II 拟合行为；示例可能保存早期数据处理细节 |
| Gaussian fitting | 当前公共入口为 `scripts/tools/gaussian_source_fitting.py`；后续可迁移到 `solar_toolkit/gaussian.py` | `scripts/tools/gaussian_source_fitting.py` 本身也是基础实现，适合教学和单元测试 | `scripts/radio/radio_source_map_plot_gaussian_overlay.py` 中的 Gaussian 模型/背景/诊断实现；`scripts/radio/sdo_aia_radio_hmi_overlay.py` 中的 `fit_elliptical_gaussian`; `scripts/radio/sdo_aia_radio_hmi_overlay_bgcorrected.py` 中的 robust/background Gaussian；`examples/radio_aia_hmi/*.py` 中重复的 `fit_elliptical_gaussian` | `sdo_aia_radio_hmi_overlay_bgcorrected.py` 的 robust/background fitting 暂不动；`radio_source_map_plot_gaussian_overlay.py` 中带质量诊断和背景模型的实现暂不动 | 本阶段只分析。后续先把无背景的 `elliptical_gaussian_2d` 和基础 `fit_elliptical_gaussian` 迁到公共模块，再逐步抽象背景模型、mask、质量诊断和诊断 CSV | 高。不同脚本的 Gaussian fitting 已承担不同科学假设：无背景、常数背景、平面背景、source mask、局部背景扣除、质量标记等；不能机械去重 |

## Recommended Final Keep Set

These files should remain as normal, user-facing or developer-facing project
assets after consolidation:

- `scripts/aia_hmi/sdo_aia_euv_processor.py`
- `scripts/aia_hmi/sdo_aia_hmi_overlay.py`
- `scripts/radio/radio_source_map_plot_gaussian_overlay.py`
- `scripts/radio/radio_source_map_plot.py`
- `scripts/radio/sdo_aia_radio_hmi_overlay.py`
- `scripts/radio/sdo_aia_radio_hmi_overlay_bgcorrected.py`
- `scripts/radio/cso_radio_spectrogram_plot.py`
- `scripts/radio/cso_spectrogram_class.py`
- `scripts/radio/cso_radio_spectra_gui.py`
- `scripts/tools/gaussian_source_fitting.py`

Rationale:

- The README-facing main workflows already align with `docs/MAIN_FILES.md` and
  `docs/script_index.md`.
- `radio_source_map_plot.py` is valuable as the lower-complexity source-map
  entry point even though the Gaussian overlay script is the feature-complete
  main workflow.
- `cso_spectrogram_class.py` is the better CSO basic-code candidate than
  `examples/radio/cso_spectrogram_processing_example.py`, because it is shorter
  and shaped like a reusable helper.
- `sdo_aia_radio_hmi_overlay_bgcorrected.py` should be preserved separately
  until the background-correction science is reviewed.

## Recommended Wrapper Candidates

These files are good candidates to become thin wrappers or short examples in a
later phase:

- `scripts/aia_hmi/sdo_aia_base_difference.py`
  - Wrapper target: `sdo_aia_euv_processor.py` with base-difference mode.
  - Preserve old defaults in comments or example config before replacing logic.
- `scripts/aia_hmi/sdo_aia_running_difference.py`
  - Wrapper target: `sdo_aia_euv_processor.py` with running-difference mode.
  - Preserve old ROI, index range, color limits, and output naming first.
- `scripts/aia_hmi/sdo_aia_multichannel_panel.py`
  - Wrapper target: `sdo_aia_euv_processor.py --mode mosaic`.
  - Keep as the AIA teaching/basic example if one lightweight script is desired.
- `examples/radio/cso_spectrogram_processing_example.py`
  - Wrapper target: `scripts/radio/cso_spectrogram_class.py` or
    `scripts/radio/cso_radio_spectrogram_plot.py`.
  - Should become a short example rather than another full implementation.
- `examples/radio_aia_hmi/aia_radio_hmi_overlay_demo.py`
  - Wrapper target: `scripts/radio/sdo_aia_radio_hmi_overlay.py`.
  - Best candidate for the single kept overlay example after reduction.

## Recommended Legacy Candidates

These files should be considered legacy/reference after their unique parameters
are documented and compared against the main code:

- `scripts/aia_hmi/sdo_aia_base_difference.py`
- `scripts/aia_hmi/sdo_aia_running_difference.py`
- `examples/radio/cso_spectrogram_processing_example.py`
- `examples/radio_aia_hmi/aia_radio_hmi_overlay_extended_example.py`
- `examples/radio_aia_hmi/aia_radio_overlay_variant0_example.py`
- `examples/radio_aia_hmi/aia_radio_overlay_variant1_example.py`

Suggested legacy handling:

- Do not move in this phase.
- Before any future move, record whether each script was used for a figure,
  presentation, paper, or one-off event analysis.
- If kept, mark them clearly as historical examples and point users to the main
  script.

## Deletion Candidates Requiring Human Confirmation

No file should be deleted automatically in the next step. Potential future
deletion candidates, after wrapper conversion and manual review, are:

- `examples/radio_aia_hmi/aia_radio_overlay_variant0_example.py`
- `examples/radio_aia_hmi/aia_radio_overlay_variant1_example.py`
- `examples/radio_aia_hmi/aia_radio_hmi_overlay_extended_example.py`
- `examples/radio/cso_spectrogram_processing_example.py`

Deletion preconditions:

- Confirm the file is not referenced by README, docs, tests, or active research
  notes.
- Confirm unique ROI, plotting limits, timing assumptions, and local file
  conventions have been captured in config examples or documentation.
- Confirm no publication figure can only be reproduced by the old script.

## Files That Must Not Be Auto-Deleted

- `scripts/radio/sdo_aia_radio_hmi_overlay_bgcorrected.py`
  - Contains experimental background subtraction and robust/background Gaussian
    fitting logic. It may encode important scientific assumptions.
- `scripts/radio/cso_radio_spectra_gui.py`
  - Optional GUI with interactive behavior and type-II fitting utilities; GUI
    behavior is not covered by the batch CSO plotting script.
- `scripts/radio/radio_source_map_plot.py`
  - Basic source-map workflow and useful low-complexity entry point.
- `scripts/tools/gaussian_source_fitting.py`
  - Current reusable Gaussian fitting utility and best seed for a future
    `solar_toolkit/gaussian.py`.
- `scripts/radio/radio_source_map_plot_gaussian_overlay.py`
  - Feature-complete radio source-map main workflow with Gaussian, diagnostics,
    spectrogram, and drift-rate logic.
- `scripts/radio/sdo_aia_radio_hmi_overlay.py`
  - Main AIA/radio/HMI overlay workflow.
- `scripts/aia_hmi/sdo_aia_euv_processor.py`
  - Main AIA image, mosaic, and difference workflow.
- `scripts/radio/cso_radio_spectrogram_plot.py`
  - Main CSO spectrogram plotting workflow.

## Gaussian Duplication Notes

Observed duplicated or related Gaussian implementations:

- `scripts/tools/gaussian_source_fitting.py`
  - Minimal rotated 2D Gaussian model plus basic `fit_elliptical_gaussian`.
- `scripts/radio/sdo_aia_radio_hmi_overlay.py`
  - Duplicates the basic Gaussian fit and uses it for radio-to-AIA reprojection.
- `examples/radio_aia_hmi/aia_radio_hmi_overlay_demo.py`
  - Duplicates the basic Gaussian fit from the overlay workflow.
- `scripts/radio/sdo_aia_radio_hmi_overlay_bgcorrected.py`
  - Adds background subtraction, constant/plane background models, source masks,
    and robust diagnostics.
- `scripts/radio/radio_source_map_plot_gaussian_overlay.py`
  - Contains the most complete radio-map Gaussian stack: background models,
    masks, quality checks, coordinate conversion, overlay drawing, residual
    panels, and diagnostics CSV.

Recommended migration order for a later phase:

1. Move only the mathematically neutral helpers first:
   `elliptical_gaussian_2d`, `_unravel_2d_index`, `_true_indices`, and the
   simple no-background `fit_elliptical_gaussian`.
2. Add tests using synthetic Gaussian arrays before changing callers.
3. Only after parity checks, consider extracting background-model and diagnostic
   helpers from the radio-specific scripts.
4. Keep background-corrected overlay behavior separate until reviewed by the
   science owner.

## Phase 1 Recommendation

Proceed to the next planning step, but do not perform destructive cleanup yet.
The project has clear main-code candidates, but several legacy files likely
contain event-specific scientific parameters. The safest next phase is wrapper
conversion plus tests, not deletion.
