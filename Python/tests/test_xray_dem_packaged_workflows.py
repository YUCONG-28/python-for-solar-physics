"""Contracts for package-owned X-ray/DEM workflow implementations."""

from __future__ import annotations

import ast
import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

WORKFLOW_ALIASES = (
    (
        "scripts.xray_dem.asos_hxi_goes_sxr_comparison",
        "solar_toolkit.xray_dem.hxi_sxr_comparison",
    ),
    (
        "scripts.xray_dem.asos_hxi_image_plot",
        "solar_toolkit.xray_dem.hxi_image",
    ),
    (
        "scripts.xray_dem.dem_radio_source_overlay",
        "solar_toolkit.xray_dem.dem_radio_source_overlay",
    ),
    (
        "scripts.xray_dem.hessi_hxr_lightcurve_plot",
        "solar_toolkit.xray_dem.hxi_lightcurve",
    ),
    (
        "scripts.xray_dem.sdo_aia_asos_hxi_overlay",
        "solar_toolkit.xray_dem.aia_hxi_overlay",
    ),
    (
        "scripts.xray_dem.sdo_aia_dem_inversion",
        "solar_toolkit.xray_dem.aia_dem_inversion",
    ),
)


@pytest.mark.parametrize(("legacy_name", "canonical_name"), WORKFLOW_ALIASES)
def test_workflow_script_imports_are_true_module_aliases(legacy_name, canonical_name):
    canonical = importlib.import_module(canonical_name)
    legacy = importlib.import_module(legacy_name)

    assert legacy is canonical
    assert callable(canonical.main)
    assert canonical.__all__
    assert all(hasattr(canonical, name) for name in canonical.__all__)


@pytest.mark.parametrize(
    "script_name",
    [legacy_name.rsplit(".", 1)[-1] + ".py" for legacy_name, _ in WORKFLOW_ALIASES],
)
def test_workflow_script_help_is_available(script_name):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "xray_dem" / script_name),
            "--help",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()


def test_all_xray_dem_scripts_are_thin_launchers():
    for script_path in (REPO_ROOT / "scripts" / "xray_dem").glob("*.py"):
        source = script_path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(script_path))

        assert len(source.splitlines()) <= 40, script_path.name
        assert not any(
            isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef)) for node in tree.body
        ), script_path.name


def test_package_workflows_do_not_depend_on_repository_script_trees():
    forbidden_roots = {"examples", "legacy", "scripts"}
    package_dir = REPO_ROOT / "solar_toolkit" / "xray_dem"

    for module_path in package_dir.glob("*.py"):
        tree = ast.parse(
            module_path.read_text(encoding="utf-8-sig"),
            filename=str(module_path),
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported = {alias.name.split(".", 1)[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = {node.module.split(".", 1)[0]}
            else:
                continue
            assert imported.isdisjoint(forbidden_roots), module_path.name
