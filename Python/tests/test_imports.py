"""Lightweight import checks for package metadata and utilities."""

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

from solar_toolkit.exceptions import SolarToolkitDeprecationWarning


def test_package_imports():
    from importlib.metadata import version

    import solar_toolkit

    sys.modules.pop("solar_toolkit.solar_analysis_utils", None)
    vars(solar_toolkit).pop("solar_analysis_utils", None)
    with pytest.warns(
        SolarToolkitDeprecationWarning,
        match=r"deprecated since .*0\.2\.0.*1\.0\.0",
    ):
        solar_analysis_utils = importlib.import_module(
            "solar_toolkit.solar_analysis_utils"
        )

    assert solar_toolkit.__version__ == version("solar-physics-toolkit")
    assert "path_config" not in solar_toolkit.__all__
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("solar_toolkit.path_config")
    assert callable(solar_analysis_utils.extract_time_from_filename)


def test_required_sunpy_runtime_imports():
    """Required SunPy surfaces load without network access or TLS workarounds."""

    code = """
import ssl

ssl.create_default_context()
import sunpy.map
from sunpy.net import Fido

assert sunpy.map.Map is not None
assert Fido is not None
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
