from __future__ import annotations

import importlib

from solar_apps.cli.router import FRONTEND_TARGETS
from solar_apps.frontends.catalog import FRONTENDS, INTERFACES


def test_catalog_matches_router_and_has_nine_apps_ten_interfaces() -> None:
    assert len(FRONTENDS) == 9
    assert len(INTERFACES) == 10
    assert {item.id for item in FRONTENDS} == set(FRONTEND_TARGETS)
    assert {item.id: item.entry_module for item in FRONTENDS} == FRONTEND_TARGETS
    assert len({item.id for item in INTERFACES}) == 10


def test_every_catalog_entry_has_callable_main() -> None:
    for frontend in FRONTENDS:
        module = importlib.import_module(frontend.entry_module)
        assert callable(getattr(module, "main", None)), frontend.entry_module
