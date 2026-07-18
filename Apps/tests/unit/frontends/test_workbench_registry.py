from __future__ import annotations

import importlib

import pytest

from solar_apps.frontends.workbench.registry import MODULE_SPECS, default_registry


def test_active_registry_targets_are_callable_and_help_safe() -> None:
    registry = default_registry()
    assert len(registry.modules) == len(MODULE_SPECS)
    for feature in registry.runnable_modules():
        module = importlib.import_module(feature.command_module)
        entry = getattr(module, "main", None)
        assert callable(entry), feature.command_module
        try:
            result = entry(["--help"])
        except SystemExit as exc:
            assert exc.code in (None, 0), feature.command_module
        except pytest.skip.Exception:
            raise
        else:
            assert result in (None, 0), feature.command_module


def test_archived_registry_references_are_not_executable() -> None:
    registry = default_registry()
    for reference in registry.archived_references:
        payload = reference.to_public_dict()
        assert payload["read_only"] is True
        assert "command_module" not in payload
