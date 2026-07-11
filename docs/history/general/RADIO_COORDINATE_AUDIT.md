# Radio Coordinate Audit

生成日期：2026-05-22

本审计记录 radio FITS 坐标方向、`extent`、`origin` 和 WCS 相关逻辑。目标是建立测试基线，不改变现有科研输出。

## 本轮边界

- 不修改现有绘图逻辑。
- 不接入真实 FITS 数据。
- 不运行绘图任务。
- 不更改 AIA/HMI/radio 坐标变换、高斯拟合、频漂率或差分算法。
- 仅新增纯函数和 mock header 单元测试，为后续重构提供基线。

## 现有脚本行为

| 文件 | Radio extent 计算 | `imshow` / `contour` origin | CDELT2 符号处理 | 风险 |
| --- | --- | --- | --- | --- |
| `scripts/radio/radio_source_map_plot.py` | `calc_extent(header, img_shape)` 使用 `CRVAL* + (1 - CRPIX*) * CDELT*` 到 `img_shape - CRPIX*`，返回 `[x_min, x_max, y_max, y_min]` | 单频和多频图使用 `origin="upper"` | 没有显式分支，符号隐含在返回的 y 顺序中 | 返回顺序不是 matplotlib 标准 `[left, right, bottom, top]`；依赖 `origin="upper"` 抵消 y 方向，后续维护容易误用 |
| `scripts/radio/radio_source_map_plot_gaussian_overlay.py` | `calc_image_extent_arcsec()` 使用半像素边界 `0.5` 和 `nx + 0.5`，标准返回 `[left, right, bottom, top]`；`preserve_fits_wcs_orientation=True` 时保留 CDELT 符号 | `get_radio_image_origin()` 在 preserve 模式下返回 `lower`，否则 `upper`；`imshow` 和 Gaussian `contour` 传入同一个 origin | 显式支持 `preserve_fits_wcs_orientation` 和 `radio_image_origin_mode` | 这是当前最完整逻辑，但只在该脚本内部；同名/相近逻辑未抽到公共函数 |
| `scripts/radio/sdo_aia_radio_hmi_overlay.py` | 不直接为原始 radio 图构造 display extent；在 `reproject_radio_via_gaussian_fit()` 中用 `CRPIX/CRVAL/CDELT` 将 radio 像素转 HPC，再用 AIA WCS 转像素；绘制 AIA cutout extent | AIA 底图和 radio contour 都使用 `origin="lower"`；radio contour 绘制在 AIA extent 上 | fallback header 路径使用 `x_angle = CRVAL1 + (xp + 1 - CRPIX1) * CDELT1` 和 y 同式 | RA/DEC map 与 FITS header fallback 两条路径可能有不同单位/方向假设；没有独立 mock 测试覆盖 CDELT 正负号 |
| `scripts/radio/sdo_aia_radio_hmi_overlay_bgcorrected.py` | 与正式 overlay 脚本类似，另有背景扣除和诊断逻辑 | AIA 底图、radio contour、HMI contour 使用 `origin="lower"` | fallback header 路径与正式 overlay 脚本类似 | 背景扣除会改变源区掩膜和拟合结果；本轮不接入公共函数，避免改变输出 |
| `solar_toolkit/solar_analysis_utils.py` | 暂无 radio FITS extent/origin 公共函数 | 不适用 | 不适用 | 公共工具缺口；适合新增纯函数或新增 `solar_toolkit/coordinates.py` |

## 上下翻转风险

1. `radio_source_map_plot.py` 使用旧式 extent 顺序 `[x_min, x_max, y_max, y_min]`，不是 matplotlib 标准顺序。该脚本当前配合 `origin="upper"` 使用，不应在未验证前直接替换。
2. `radio_source_map_plot_gaussian_overlay.py` 已经区分 preserve 与 normalized 模式，但逻辑散落在脚本内部，后续其它脚本复制时容易漏掉 origin 规则。
3. `sdo_aia_radio_hmi_overlay.py` 和 `sdo_aia_radio_hmi_overlay_bgcorrected.py` 的 radio-to-AIA fallback 使用 FITS header 的像素中心公式，没有独立测试覆盖 `CDELT2 < 0` 的情况。
4. AIA/radio/HMI 叠加依赖 AIA cutout WCS、radio RA/DEC map 或 radio header fallback。任何一处符号、单位或半像素边界变化，都可能导致上下翻转或中心偏移。

## AIA/radio/HMI 坐标错位风险

- RA/DEC map 路径把度转换为角秒后再构造 AIA HPC 坐标；header fallback 直接使用 `CRVAL/CDELT` 角秒。两者单位来源不同。
- HMI contour 使用 target WCS 的 `pixel_to_world()` 构造 extent，再 `origin="lower"` 绘制；这与 AIA/radio contour 共享同一 AIA extent，但没有统一测试断言。
- 高斯拟合中心、raw peak、FWHM ellipse 和 contour 在增强脚本中已使用同一 `pixel_to_data_coord()`，但该函数目前不是公共工具。

## 可抽成公共函数的逻辑

建议新增纯函数到 `solar_toolkit/coordinates.py`，不读取文件、不绘图、不依赖本地路径：

- `calculate_fits_extent_from_header(header, image_shape=None, preserve_orientation=True)`
- `infer_image_origin_from_header(header=None, preserve_orientation=True, mode="auto")`
- `normalize_radio_extent(extent)`
- `validate_extent_orientation(extent)`

设计原则：

1. 公共函数返回 matplotlib 标准 extent 顺序 `[left, right, bottom, top]`。
2. `preserve_orientation=True` 时保留 `CDELT1/CDELT2` 的符号，允许 inverted extent。
3. `preserve_orientation=True` 且 `mode="auto"` 时推荐 `origin="lower"`，使 row 0 的像素中心沿 FITS header 的 CDELT 符号自然映射。
4. `preserve_orientation=False` 时返回排序后的 extent；`mode="auto"` 返回 `origin="upper"`，以记录当前增强脚本的 legacy normalized 行为。
5. 函数只建立可测试基线，本轮不替换任何核心脚本调用。

## 暂时不能动的地方

- `scripts/radio/radio_source_map_plot.py` 的旧式 `calc_extent()` 与 `origin="upper"` 组合。
- `scripts/radio/radio_source_map_plot_gaussian_overlay.py` 的 `calc_image_extent_arcsec()`、`get_radio_image_origin()`、`pixel_to_data_coord()`、Gaussian overlay 绘制链路。
- `scripts/radio/sdo_aia_radio_hmi_overlay.py` 和 `scripts/radio/sdo_aia_radio_hmi_overlay_bgcorrected.py` 中的 radio-to-AIA 重投影和 HMI contour 绘制逻辑。
- 背景扣除实验版的源区掩膜、高斯拟合和诊断输出。

这些位置未来如需接入公共函数，应先用 mock header、合成数组和小型图像回归检查确认输出不变。
