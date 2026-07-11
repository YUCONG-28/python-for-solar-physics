"""Focused tests for the Astropy/SunPy-style package API contract."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_root_import_is_lazy_and_does_not_change_warning_filters():
    """Importing the root package has no domain imports or warning filters."""

    code = """
import sys
import warnings

before = list(warnings.filters)
import solar_toolkit

assert warnings.filters == before
assert not [
    target
    for target in solar_toolkit._SUBMODULES.values()
    if target in sys.modules
]
assert dir(solar_toolkit) == sorted(solar_toolkit.__all__)
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_root_version_comes_from_distribution_metadata():
    """The source-tree package and installed metadata report one version."""
    from importlib.metadata import version

    import solar_toolkit

    assert solar_toolkit.__version__ == version("solar-physics-toolkit")


def test_root_public_submodules_are_lazy_and_accessible():
    """Every advertised root namespace resolves through ``__getattr__``."""
    import solar_toolkit

    deprecated_targets = {
        "solar_toolkit.coordinates",
        "solar_toolkit.cso",
        "solar_toolkit.gaussian",
        "solar_toolkit.solar_analysis_utils",
    }
    for name, target_name in solar_toolkit._SUBMODULES.items():
        if target_name in deprecated_targets:
            from solar_toolkit.exceptions import SolarToolkitDeprecationWarning

            sys.modules.pop(target_name, None)
            vars(solar_toolkit).pop(name, None)
            with pytest.warns(SolarToolkitDeprecationWarning, match="deprecated since"):
                target = importlib.import_module(target_name)
        else:
            target = importlib.import_module(target_name)

        assert getattr(solar_toolkit, name) is target
        assert name in solar_toolkit.__all__
        assert name in dir(solar_toolkit)


def test_public_namespaces_do_not_leak_import_helpers():
    """Implementation imports are not presented as public package APIs."""
    import solar_toolkit
    from solar_toolkit import exceptions, visualization

    for module in [solar_toolkit, exceptions, visualization]:
        allowed = set(module.__all__)
        allowed.update(vars(module).get("_COMPATIBILITY_SUBMODULES", {}))
        allowed.add("annotations")  # ``from __future__`` compiler feature
        visible = {name for name in vars(module) if not name.startswith("_")}

        assert visible <= allowed


def test_deprecated_helper_uses_toolkit_warning_category():
    """Deprecated callables emit a filterable, information-rich warning."""
    from solar_toolkit._deprecation import deprecated
    from solar_toolkit.exceptions import SolarToolkitDeprecationWarning

    @deprecated(
        since="0.2.0",
        alternative="new_api",
        removal="1.0.0",
    )
    def old_api(value: int) -> int:
        return value + 1

    with pytest.warns(
        SolarToolkitDeprecationWarning,
        match=r"deprecated since .*0\.2\.0.*new_api.*1\.0\.0",
    ):
        assert old_api(1) == 2

    assert old_api.__name__ == "old_api"


def test_media_assets_old_path_is_a_private_package_alias():
    """The historical resource import resolves to the internal package."""
    from solar_toolkit import visualization

    canonical = importlib.import_module("solar_toolkit.visualization._media_assets")
    legacy = importlib.import_module("solar_toolkit.visualization.media_assets")

    assert legacy is canonical
    assert visualization.media_assets is canonical
    assert "media_assets" not in visualization.__all__
    assert canonical.read_asset_bytes("NOTICE.txt")
