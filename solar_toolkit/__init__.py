"""Package metadata and lightweight public namespaces for solar analysis."""

from __future__ import annotations

import warnings

__version__ = "0.1.0"
__author__ = "Solar Physics Research Team"
__email__ = "solar-physics@example.com"

warnings.filterwarnings("ignore", category=UserWarning, module="astropy")

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "coordinates",
    "aia",
    "cme",
    "cso",
    "gaussian",
    "hmi",
    "modeling",
    "net",
    "path_config",
    "radio",
    "solar_analysis_utils",
    "visualization",
    "xray_dem",
]
