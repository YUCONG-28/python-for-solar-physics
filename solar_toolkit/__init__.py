"""太阳物理数据处理工具包的包元数据。

当前项目的主要科研流程仍以仓库根目录中的独立脚本为主。这里仅暴露包版本、
作者等元数据，避免导入尚未迁移到 ``solar_toolkit`` 包内的脚本模块。
"""

import warnings

__version__ = "0.1.0"
__author__ = "Solar Physics Research Team"
__email__ = "solar-physics@example.com"

warnings.filterwarnings("ignore", category=UserWarning, module="astropy")

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "path_config",
    "solar_analysis_utils",
]
