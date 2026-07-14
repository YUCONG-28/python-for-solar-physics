# Examples / 示例

The maintained examples in this directory are import-safe and call public
`solar_toolkit` APIs. Examples marked `REQUIRES_LOCAL_DATA = False` need no
observation files and are covered by lightweight tests. Real-data recipes are
marked `REQUIRES_LOCAL_DATA = True` and are never executed by the smoke suite.

本目录中维护的示例均可安全导入，并只通过 `solar_toolkit` 公共接口调用仓库功能。
`REQUIRES_LOCAL_DATA = False` 的示例无需观测数据并纳入轻量测试；
`REQUIRES_LOCAL_DATA = True` 的真实数据 recipe 不会被 smoke 测试执行。

## Start here / 入门示例

- `public_api/time_matching_example.py`: match observation filenames by time.
- `public_api/gaussian_model_example.py`: evaluate the shared Gaussian model.

Run them after installing the project (for example, `pip install -e .`):

```powershell
D:\miniforge3\envs\solarphysics_env\python.exe examples\public_api\time_matching_example.py
D:\miniforge3\envs\solarphysics_env\python.exe examples\public_api\gaussian_model_example.py
```

## Real-data recipes / 真实数据配方

- `aia_hmi/solar_limb_contour_example.py`: compatibility-named HMI plotting recipe.
- `radio/fits_header_metadata_example.py`: inspect local FITS metadata.
- `gaussian_newkirk_quicklook/`: build Gaussian/Newkirk quicklook products.
- `radio_aia_hmi/aia_radio_hmi_overlay_demo.py`: short packaged overlay command recipe.

Use `configs/paths.example.yaml` as a starting point for local paths. Large
FITS, NetCDF, JP2, CSV, and generated products must not be committed.

## Historical reference / 历史参考

`history/radio_aia_hmi/aia_radio_hmi_overlay_legacy.py` preserves the complete
1797-line development workflow and its scientific parameters. It is not a
recommended API example and must not be imported by tests or application code.

完整的 1797 行 AIA/Radio/HMI 开发脚本保存在 `history/radio_aia_hmi/`，用于复现和参数追溯；
它不是推荐入口，也不应由测试或应用代码导入。

Generated example products belong under `output/` (or a recipe-specific ignored
output directory). README media belongs under `docs/assets/`.
