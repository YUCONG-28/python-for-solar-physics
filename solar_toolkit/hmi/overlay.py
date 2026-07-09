"""AIA/HMI overlay facade.

English: Lightweight public facade for the retained AIA/HMI overlay script.
Importing this module does not read local observation data; call
``run_overlay_workflow`` to execute the historical script workflow.

中文: AIA/HMI 叠加绘图工作流的轻量公共门面。导入本模块不会读取本地观测
数据；需要运行保留脚本时再调用 ``run_overlay_workflow``。
"""

from __future__ import annotations

from types import ModuleType

__all__ = ["run_overlay_workflow"]


def run_overlay_workflow() -> ModuleType:
    """Import and execute the retained script-style AIA/HMI overlay workflow."""

    import scripts.aia_hmi.sdo_aia_hmi_overlay as workflow

    return workflow
