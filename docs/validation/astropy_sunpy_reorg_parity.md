# Astropy/SunPy Reorganization Parity Record / 重构等价验证记录

## Scope / 范围

This record summarizes focused real-data comparisons made while moving
implementations from scripts and compatibility modules into `solar_toolkit`.
The reference code state was commit `301765a`. Structural migration requires
exact numerical equality; image comparisons reported here used exact file SHA
equality, which is stricter than the fallback SSIM threshold.

本记录汇总把实现从脚本和兼容模块迁入 `solar_toolkit` 时完成的真实数据分项对比。参考代码版本为
`301765a`。结构迁移要求数值完全一致；本文图像结果达到文件 SHA 完全一致，严格于备用的 SSIM
阈值。

## Verified Products / 已验证产品

| Dataset / 数据集 | Compared behavior / 对比内容 | Result / 结果 |
| --- | --- | --- |
| AIA 2024-01-10, all eight local bands: 94, 131, 171, 193, 211, 304, 335, 1600 | Input selection and time-slot grouping; ROI cutout and WCS; original, running-difference, and base-difference arrays | Exact array and metadata equality. / 数组与元数据完全一致。 |
| AIA 2024-01-10, all eight local bands | Single-image PNG check; 8-band original, running-difference, and base-difference mosaic PNGs | Exact SHA equality for the checked single image and all three mosaics. / 已检查单图及三类 mosaic 的文件 SHA 完全一致。 |
| Radio/CSO 2025-01-24 | Spectrogram data, time axis, and frequency axis | Exact array/axis equality and identical hashes. / 数组、坐标轴与哈希完全一致。 |
| Radio/CSO 2025-01-24 | Gaussian centers, FWHM, residuals, quality flags, and model arrays | Exact value equality and identical model hashes. / 数值与模型哈希完全一致。 |
| Radio/CSO 2025-01-24 | Focused overlay PNG and Newkirk/drift tables | Exact PNG SHA and table hashes. / PNG 与表格哈希完全一致。 |
| Radio/CSO 2025-05-03 | Spectrogram data/time/frequency, Gaussian center/FWHM/residual/quality/model, focused overlay, and Newkirk table | Exact values and identical array, image, model, and Newkirk-table hashes. / 数值、数组、图像、模型与 Newkirk 表哈希完全一致。 |

For 2025-05-03, the existing drift-speed output contained zero rows. The empty
output condition was observed, but no non-empty drift-speed table was available
for a content-parity comparison.

对于 2025-05-03，现有 drift-speed 输出为零行。本次记录确认了该空输出状态，但没有可用于
内容等价对比的非空 drift-speed 表，因此不宣称完成了非空 drift 表比较。

The comparisons cover the stated scientific products after structural routing
changes. They support the canonical module moves for AIA selection/difference/
mosaic behavior and for Radio/CSO spectrogram, Gaussian, overlay, Newkirk, and
drift product helpers.

这些对比支持 AIA 选择、差分、mosaic 以及 Radio/CSO 频谱、高斯、分项 overlay、Newkirk 和
drift 产品的结构迁移结论。

## Explicit Exclusions / 明确未覆盖项

- This is **not** an end-to-end parity claim for
  `scripts/radio/run_radio_burst_pipeline.py`.
- The complete source-map orchestration and complete AIA/radio/HMI overlay
  orchestration still use source-checkout compatibility runners.
- Interactive drift selection, GUI/browser behavior, network downloads, and
  every event-specific or historical recipe were not covered by these hashes.
- The result does not authorize changing scientific defaults or deleting
  compatibility paths.

- 本记录不宣称 `scripts/radio/run_radio_burst_pipeline.py` 已完成端到端等价。
- 完整 source-map 与 AIA/radio/HMI overlay 编排仍使用源码兼容 runner。
- 交互式 drift 选择、GUI/浏览器行为、网络下载以及全部事件或历史 recipe 未纳入本次哈希对比。
- 该结果不授权修改科学默认值，也不授权删除兼容路径。

Accordingly, installed `solar-radio pipeline`, `solar-radio source-map`, and
`solar-radio overlay` report the boundary and return status `2` unless an
explicit source compatibility runner is supplied. This makes the unverified
boundary visible instead of silently changing behavior.

因此，安装后的 `solar-radio pipeline/source-map/overlay` 在未显式提供源码兼容 runner 时会
说明边界并返回状态码 `2`，避免把未验证部分误表示为已迁移完成。
