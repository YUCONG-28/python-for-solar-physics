"""Deprecated compatibility imports for historical shared utilities.

The implementations now live in focused time, I/O, map, HMI, visualization,
and internal utility modules. Existing imports remain available through version
0.x to support staged migration.
"""

from __future__ import annotations

from ._deprecation import warn_deprecated as _warn_deprecated
from ._utils.logging import SolarLogger, timing_decorator
from ._utils.memory import monitor_memory_usage, optimized_gc_collect, safe_delete
from ._utils.validation import (
    SolarDataConfig,
    validate_frequency_range,
    validate_time_range,
)
from .hmi.processing import create_magnetic_contour_levels, process_hmi_magnetic_field
from .io.discovery import (
    filter_files_by_time_range,
    find_closest_file_by_time,
    get_sorted_fits_files,
)
from .map.operations import (
    align_maps_to_reference,
    create_aia_submap,
    normalize_aia_exposure,
)
from .time.formatting import format_time_for_display, format_time_for_filename
from .time.parsing import extract_time_from_filename, parse_isot_time
from .visualization.plotting import (
    add_frequency_highlight_lines,
    create_figure_with_white_background,
    get_aia_wavelength_config,
    setup_chinese_font,
)

_warn_deprecated(
    "solar_toolkit.solar_analysis_utils",
    since="0.2.0",
    alternative="the corresponding solar_toolkit.time/io/map/hmi/visualization API",
    removal="1.0.0",
    stacklevel=2,
)

__all__ = [
    "SolarDataConfig",
    "SolarLogger",
    "add_frequency_highlight_lines",
    "align_maps_to_reference",
    "create_aia_submap",
    "create_figure_with_white_background",
    "create_magnetic_contour_levels",
    "extract_time_from_filename",
    "filter_files_by_time_range",
    "find_closest_file_by_time",
    "format_time_for_display",
    "format_time_for_filename",
    "get_aia_wavelength_config",
    "get_sorted_fits_files",
    "monitor_memory_usage",
    "normalize_aia_exposure",
    "optimized_gc_collect",
    "parse_isot_time",
    "process_hmi_magnetic_field",
    "safe_delete",
    "setup_chinese_font",
    "timing_decorator",
    "validate_frequency_range",
    "validate_time_range",
]
