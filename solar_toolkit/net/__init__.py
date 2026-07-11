"""Network and archive helper namespace.

English: Small reusable helpers for collecting links, filtering archive
results, and downloading files into explicit user-selected locations.

中文：用于收集链接、筛选归档结果，并将文件下载到用户明确指定位置的轻量网络工具。
"""

from .downloads import DownloadResult, download_url
from .links import collect_links, filter_links

__all__ = [
    "DownloadResult",
    "collect_links",
    "download_url",
    "filter_links",
]
