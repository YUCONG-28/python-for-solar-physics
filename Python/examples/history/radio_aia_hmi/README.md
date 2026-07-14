# Historical AIA/Radio/HMI Overlay

`aia_radio_hmi_overlay_legacy.py` is the preserved 1797-line development
workflow. It contains historical scientific parameters and reproduction logic,
so it is retained intact as a reference rather than presented as a recommended
example. It may scan local data and configure plotting at import time; do not
import it from tests or application code.

`examples/radio_aia_hmi/aia_radio_hmi_overlay_demo.py` is the current short,
import-safe recipe and calls only the packaged `solar_toolkit` command contract.

## 中文说明

`aia_radio_hmi_overlay_legacy.py` 保留了原有 1797 行开发流程，其中包含历史科学参数与复现实验逻辑。
该文件仅作为历史参考，不应在测试或应用代码中导入。当前推荐的短示例位于
`examples/radio_aia_hmi/aia_radio_hmi_overlay_demo.py`，它只调用 `solar_toolkit` 公共接口。
