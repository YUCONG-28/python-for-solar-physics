"""Compatibility helpers for historical ``scripts.aia_hmi.core`` paths."""

from __future__ import annotations

import sys
from importlib import import_module
from types import ModuleType
from typing import Any


def reexport_module(module_name: str, namespace: dict[str, Any]) -> ModuleType:
    """Populate a compatibility namespace and alias it to the public module."""
    module = import_module(module_name)
    alias_name = namespace.get("__name__")
    export_names = getattr(module, "__all__", None)
    if export_names is None:
        export_names = [
            name
            for name in dir(module)
            if not (name.startswith("__") and name.endswith("__"))
        ]
    for name in export_names:
        namespace[name] = getattr(module, name)
    namespace["__all__"] = list(export_names)
    namespace["__doc__"] = module.__doc__
    if isinstance(alias_name, str):
        sys.modules[alias_name] = module
    return module
