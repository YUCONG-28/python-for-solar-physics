"""CME and coronagraph helper namespace.

English: Reusable LASCO/CME helpers for timestamp parsing, local file scanning,
and simple running-difference products.

中文：可复用的 LASCO/CME 时间解析、本地文件扫描和 running-difference 基础工具。
"""

from .files import extract_lasco_timestamp, scan_lasco_files
from .processing import running_difference

__all__ = [
    "extract_lasco_timestamp",
    "running_difference",
    "scan_lasco_files",
]
