# 模块用途: 通过 Helioviewer 下载 SOHO/LASCO 日冕仪数据。
# 主要输入: 观测时间、仪器通道和下载目录。
# 主要输出/运行说明: 保存 LASCO 数据文件，供 CME 成像和差分分析使用。
"""
Created on Mon Mar 31 11:06:15 2025

@author: 李
"""

from datetime import datetime, timedelta
from pathlib import Path

import hvpy
from hvpy.datasource import DataSource

from solar_toolkit.path_config import load_script_config

# 定义起始时间和结束时间
start_time = datetime(2024, 8, 8, 19, 00)
end_time = datetime(2024, 8, 8, 23, 00)

time_interval = timedelta(seconds=720)

# 确保保存文件的目录存在
PATH_CONFIG = load_script_config(
    "soho_lasco_data_download", {"save_dir": "D:/LASCO/data/"}
)
save_dir = Path(PATH_CONFIG["save_dir"])
save_dir.mkdir(parents=True, exist_ok=True)

# 当前时间初始化为起始时间
current_time = start_time

while current_time <= end_time:
    try:
        # 下载 JP2 图像
        lasco_jp2_file = hvpy.save_file(
            hvpy.getJP2Image(current_time, DataSource.LASCO_C2.value),
            filename=str(
                save_dir / f'LASCO_C2_{current_time.strftime("%Y%m%d_%H%M%S")}.jp2'
            ),
            overwrite=True,
        )
        print(f"成功保存文件: LASCO_C2_{current_time.strftime('%Y%m%d_%H%M%S')}.jp2")
    except Exception as e:
        print(f"处理 {current_time} 时出现错误: {e}")
    # 更新当前时间

    current_time += time_interval
