# -*- coding: utf-8 -*-
"""
Created on Mon Mar 31 11:06:15 2025

@author: 李
"""

import os
import hvpy
from datetime import datetime, timedelta
from hvpy.datasource import DataSource

# 定义起始时间和结束时间
start_time = datetime(2024, 8, 8, 19, 00)
end_time = datetime(2024, 8, 8, 23, 00)

time_interval = timedelta(seconds=720)

# 确保保存文件的目录存在
save_dir = '<DATA_ROOT>/data/'
if not os.path.exists(save_dir):
    os.makedirs(save_dir)

# 当前时间初始化为起始时间
current_time = start_time

while current_time <= end_time:
    try:
        # 下载 JP2 图像
        lasco_jp2_file = hvpy.save_file(
            hvpy.getJP2Image(current_time, DataSource.LASCO_C2.value),
            filename=os.path.join(save_dir, f'LASCO_C2_{current_time.strftime("%Y%m%d_%H%M%S")}.jp2'),
            overwrite=True
        )
        print(f"成功保存文件: LASCO_C2_{current_time.strftime('%Y%m%d_%H%M%S')}.jp2")
    except Exception as e:
        print(f"处理 {current_time} 时出现错误: {e}")
    # 更新当前时间
    current_time += time_interval