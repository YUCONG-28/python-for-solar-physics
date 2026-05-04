# -*- coding: utf-8 -*-
# 模块用途: 测试观测时间解析和时间差计算。
# 主要输入: 示例时间字符串。
# 主要输出/运行说明: 在控制台打印解析后的时间和差值。
"""
Created on Sun Mar 16 20:15:09 2025

@author: 李
"""

from datetime import datetime, timedelta

# 解析第一个文件的时间
time_str0 = "20250124043739681"
dt0 = datetime.strptime(time_str0, "%Y%m%d%H%M%S%f")
# 结果: 2025-01-24 04:37:39.681000

# 解析第二个文件的时间
time_str1 = "2025-01-24T033001Z"
dt1 = datetime.strptime(time_str1, "%Y-%m-%dT%H%M%SZ")
# 结果: 2025-01-24 03:30:01

# 计算时间差
time_diff = dt0 - dt1

print(f"文件1观测时间: {dt0}")
print(f"文件2观测时间: {dt1}")
print(f"时间差: {time_diff}")
print(f"时间差（秒）: {time_diff.total_seconds():.3f} 秒")
