"""HMI magnetogram plotting facade.

English: Lightweight public facade for the historical HMI magnetogram plotting
workflow. Importing this module does not scan local FITS folders; call
``run_magnetogram_workflow`` to execute the retained script workflow.

中文: HMI 磁图绘制工作流的轻量公共门面。导入本模块不会扫描本地 FITS
目录；需要运行保留脚本时再调用 ``run_magnetogram_workflow``。
"""

from __future__ import annotations

from types import ModuleType

__all__ = ["run_magnetogram_workflow"]


def run_magnetogram_workflow() -> ModuleType:
    """Import and execute the retained script-style HMI magnetogram workflow."""

    import scripts.aia_hmi.sdo_hmi_magnetogram_plot as workflow

    return workflow
