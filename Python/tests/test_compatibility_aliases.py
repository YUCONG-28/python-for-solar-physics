"""Compatibility-path identity and deprecation tests."""

from __future__ import annotations

import importlib
import sys

import pytest

from solar_toolkit.exceptions import SolarToolkitDeprecationWarning


@pytest.mark.parametrize(
    ("legacy_name", "canonical_name"),
    [
        ("solar_toolkit.coordinates", "solar_toolkit.map.coordinates"),
        ("solar_toolkit.cso", "solar_toolkit.radio.cso"),
        ("solar_toolkit.gaussian", "solar_toolkit.modeling.gaussian"),
    ],
)
def test_root_compatibility_modules_warn_and_alias(legacy_name, canonical_name):
    parent_name, attribute = legacy_name.rsplit(".", 1)
    parent = importlib.import_module(parent_name)
    sys.modules.pop(legacy_name, None)
    parent.__dict__.pop(attribute, None)

    with pytest.warns(SolarToolkitDeprecationWarning, match="deprecated since"):
        legacy = importlib.import_module(legacy_name)

    canonical = importlib.import_module(canonical_name)
    assert legacy is canonical
