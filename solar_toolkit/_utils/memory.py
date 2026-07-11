"""Internal memory-monitoring and garbage-collection helpers."""

from __future__ import annotations

import gc
import warnings


def optimized_gc_collect() -> None:
    """Collect garbage only when process-wide memory pressure warrants it."""

    if gc.isenabled():
        import psutil

        memory_percent = psutil.virtual_memory().percent
        if memory_percent > 70:
            gc.collect()
        elif memory_percent > 50 and gc.get_count()[0] > 700:
            gc.collect(0)


def safe_delete(variable_names: list[str], locals_dict: dict) -> None:
    """Delete named entries from a supplied local-variable mapping, then collect."""

    for variable_name in variable_names:
        if variable_name in locals_dict:
            del locals_dict[variable_name]
    optimized_gc_collect()


def monitor_memory_usage(description: str = "") -> dict[str, float]:
    """Return current process memory metrics and optionally print a summary."""

    try:
        import os

        import psutil

        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        result = {
            "rss_mb": memory_info.rss / 1024 / 1024,
            "vms_mb": memory_info.vms / 1024 / 1024,
            "percent": process.memory_percent(),
        }
        if description:
            print(
                f"{description}: RSS={result['rss_mb']:.1f}MB, "
                f"VMS={result['vms_mb']:.1f}MB, {result['percent']:.1f}%"
            )
        return result
    except ImportError:
        warnings.warn(
            "psutil is not installed; memory usage cannot be monitored",
            stacklevel=2,
        )
        return {}


__all__ = ["monitor_memory_usage", "optimized_gc_collect", "safe_delete"]
