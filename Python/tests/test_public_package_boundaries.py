"""Public package-boundary contracts for the partitioned repository."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

PYTHON_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = PYTHON_ROOT / "solar_toolkit"
LAZY_PACKAGES = ["aia", "data", "hmi", "net", "radio", "visualization", "xray_dem"]


def _public_module_names(package_dir: Path) -> set[str]:
    names = {
        path.stem
        for path in package_dir.glob("*.py")
        if path.name != "__init__.py" and not path.name.startswith("_")
    }
    names.update(
        path.name
        for path in package_dir.iterdir()
        if path.is_dir()
        and not path.name.startswith("_")
        and (path / "__init__.py").exists()
    )
    return names


def test_root_lazy_map_matches_real_public_modules():
    import solar_toolkit

    assert set(solar_toolkit._SUBMODULES) == _public_module_names(PACKAGE_ROOT)
    assert set(solar_toolkit._SUBMODULES) <= set(solar_toolkit.__all__)


def test_domain_lazy_maps_match_real_public_modules():
    for package_name in LAZY_PACKAGES:
        package = importlib.import_module(f"solar_toolkit.{package_name}")
        expected = _public_module_names(PACKAGE_ROOT / package_name)
        assert set(package._SUBMODULES) == expected, package_name
        assert set(package._SUBMODULES) <= set(package.__all__), package_name
        for target in package._SUBMODULES.values():
            assert target.startswith("solar_toolkit.")
            assert importlib.import_module(target).__doc__


def test_application_surfaces_are_absent_from_public_source():
    forbidden = [
        PACKAGE_ROOT / "path_config.py",
        PACKAGE_ROOT / "webapp",
        PACKAGE_ROOT / "radio" / "configs",
        PACKAGE_ROOT / "radio" / "cli.py",
        PACKAGE_ROOT / "visualization" / "image_web_viewer",
        PACKAGE_ROOT / "visualization" / "_media_assets",
    ]
    assert [path.relative_to(PYTHON_ROOT).as_posix() for path in forbidden if path.exists()] == []


def test_public_source_does_not_reference_local_namespaces():
    violations: list[str] = []
    for path in PACKAGE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            for name in names:
                if name.split(".", 1)[0] in {"solar_apps", "scripts", "legacy"}:
                    relative = path.relative_to(PYTHON_ROOT).as_posix()
                    violations.append(f"{relative}:{node.lineno} imports {name}")
    assert violations == []


def test_public_foundation_helpers_remain_available():
    from solar_toolkit import cme, data, io, map, net, time, timeseries, xray_dem

    assert time.extract_time_from_filename is not None
    assert io.scan_fits is not None
    assert data.ObservationFile is not None
    assert map.get_display_extent is not None
    assert timeseries.normalize_time_column is not None
    assert net.download_url is not None
    assert cme.running_difference is not None
    assert xray_dem.load_sxr_data is not None


def test_new_radio_computation_partitions_are_public():
    from solar_toolkit.radio import cso_processing, physical_diagnostics, reprojection

    assert cso_processing.__all__
    assert physical_diagnostics.__all__
    assert reprojection.__all__
