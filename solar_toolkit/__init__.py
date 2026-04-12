"""
太阳物理数据处理工具包

一个用于多波段太阳数据处理的综合工具包，支持：
- SDO/AIA EUV 图像处理
- SDO/HMI 磁场数据
- 射电观测（CSO, DSRT）
- X射线数据（GOES, HXI）
- 日冕仪数据（LASCO）
"""

__version__ = "0.1.0"
__author__ = "Solar Physics Research Team"
__email__ = "solar-physics@example.com"

import warnings
warnings.filterwarnings('ignore', category=UserWarning, module='astropy')

# 导出主要模块
from . import processors
from . import utils
from . import visualization
from . import analysis

# 导出常用函数
from .processors.aia import AIAProcessor
from .processors.hmi import HMIProcessor
from .processors.radio import RadioProcessor
from .visualization.plotting import plot_multi_wavelength

__all__ = [
    'AIAProcessor',
    'HMIProcessor',
    'RadioProcessor',
    'plot_multi_wavelength',
    'processors',
    'utils',
    'visualization',
    'analysis',
]
