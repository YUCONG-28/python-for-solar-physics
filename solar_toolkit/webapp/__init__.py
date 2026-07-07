"""Local English web workbench for the solar physics toolkit."""

from __future__ import annotations

from importlib import import_module

_SUBMODULES = {
    "registry": "solar_toolkit.webapp.registry",
    "runner": "solar_toolkit.webapp.runner",
    "server": "solar_toolkit.webapp.server",
}

__all__ = [
    "FeatureModule",
    "JobContext",
    "JobRunner",
    "create_app",
    "default_registry",
    *_SUBMODULES,
]


def __getattr__(name: str):
    if name == "FeatureModule":
        from .registry import FeatureModule

        return FeatureModule
    if name == "default_registry":
        from .registry import default_registry

        return default_registry
    if name in {"JobContext", "JobRunner"}:
        from .runner import JobContext, JobRunner

        return {"JobContext": JobContext, "JobRunner": JobRunner}[name]
    if name == "create_app":
        from .server import create_app

        return create_app
    if name in _SUBMODULES:
        module = import_module(_SUBMODULES[name])
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
