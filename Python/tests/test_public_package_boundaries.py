"""Public package-boundary tests for the project-wide refactor."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_PACKAGE_ROOT = REPO_ROOT / "solar_toolkit"
MOJIBAKE_MARKERS = (
    "\ufffd",
    "涓",
    "鐨",
    "锛",
    "鈥",
    "鍥",
    "鏃",
    "鏂",
    "杩",
    "缁",
    "璇",
    "瀵",
    "鎴",
    "鍔",
    "浠",
    "鐢",
    "閫",
    "€",
    "Â",
    "Ã",
    "â€",
)
LAZY_PUBLIC_PACKAGES = [
    "aia",
    "data",
    "hmi",
    "net",
    "radio",
    "visualization",
    "webapp",
    "xray_dem",
]


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


def _public_python_module_paths() -> list[Path]:
    """Return source paths for public package modules, excluding internals."""
    paths = []
    for path in PUBLIC_PACKAGE_ROOT.rglob("*.py"):
        relative = path.relative_to(PUBLIC_PACKAGE_ROOT)
        if any(
            part.startswith("_") and part != "__init__.py" for part in relative.parts
        ):
            continue
        paths.append(path)
    return sorted(paths)


def _wrapper_target(path: Path) -> str | None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "reexport_module":
            continue
        if node.args and isinstance(node.args[0], ast.Constant):
            return str(node.args[0].value)
    return None


def test_root_public_names_match_existing_modules_or_packages():
    """Top-level __all__ names resolve to real public files or packages."""
    import solar_toolkit

    for name in solar_toolkit.__all__:
        if name.startswith("__"):
            continue
        package_path = REPO_ROOT / "solar_toolkit" / name / "__init__.py"
        module_path = REPO_ROOT / "solar_toolkit" / f"{name}.py"

        assert package_path.exists() or module_path.exists(), name


def test_root_lazy_submodules_cover_real_public_files():
    """The root lazy map covers every real public module and package."""
    import solar_toolkit

    expected = _public_module_names(REPO_ROOT / "solar_toolkit")

    assert expected == set(solar_toolkit._SUBMODULES)
    assert set(solar_toolkit._SUBMODULES) <= set(solar_toolkit.__all__)


def test_lazy_public_submodules_cover_real_public_files():
    """Lazy public namespaces should expose their real public modules."""
    for package_name in LAZY_PUBLIC_PACKAGES:
        package = importlib.import_module(f"solar_toolkit.{package_name}")
        package_dir = REPO_ROOT / "solar_toolkit" / package_name
        expected = _public_module_names(package_dir)
        submodules = package._SUBMODULES
        compatibility = vars(package).get("_COMPATIBILITY_SUBMODULES", {})

        assert expected - set(submodules) - set(compatibility) == set(), package_name
        assert set(submodules).isdisjoint(compatibility), package_name

        for public_name, target_name in submodules.items():
            assert target_name.startswith("solar_toolkit.")
            target = importlib.import_module(target_name)
            assert target.__doc__, public_name

        for old_name, target_name in compatibility.items():
            old_module = importlib.import_module(f"{package.__name__}.{old_name}")
            target = importlib.import_module(target_name)

            assert old_module is target, old_name


def test_core_compatibility_wrappers_alias_public_modules():
    """Core compatibility wrappers remain true module aliases."""
    wrapper_roots = [
        REPO_ROOT / "scripts" / "radio" / "core",
        REPO_ROOT / "scripts" / "aia_hmi" / "core",
    ]

    for root in wrapper_roots:
        for path in sorted(root.glob("*.py")):
            if path.name in {"__init__.py", "_compat.py"} or path.name.startswith("_"):
                continue
            target_name = _wrapper_target(path)
            assert target_name is not None, path

            wrapper_name = ".".join(path.relative_to(REPO_ROOT).with_suffix("").parts)
            wrapper = importlib.import_module(wrapper_name)
            target = importlib.import_module(target_name)

            assert wrapper is target, wrapper_name


def test_public_module_docstrings_are_readable():
    """Every public module docstring avoids common UTF-8/GBK mojibake."""
    for module_path in _public_python_module_paths():
        text = module_path.read_text(encoding="utf-8")
        docstring = ast.get_docstring(ast.parse(text))
        relative_path = module_path.relative_to(REPO_ROOT)

        assert docstring, relative_path
        assert [
            marker for marker in MOJIBAKE_MARKERS if marker in docstring
        ] == [], relative_path


def test_domain_packages_import_without_loading_science_data():
    """The public library layer exposes science-domain packages."""
    for module_name in [
        "solar_toolkit.aia",
        "solar_toolkit.hmi",
        "solar_toolkit.time",
        "solar_toolkit.io",
        "solar_toolkit.data",
        "solar_toolkit.map",
        "solar_toolkit.timeseries",
        "solar_toolkit.xray_dem",
        "solar_toolkit.cme",
        "solar_toolkit.net",
        "solar_toolkit.modeling",
        "solar_toolkit.visualization",
    ]:
        module = importlib.import_module(module_name)
        assert module.__doc__


def test_sunpy_style_base_helpers_are_public():
    """SunPy-style base packages expose the stable helper functions."""
    from solar_toolkit import (
        cme,
        data,
        io,
        map,
        net,
        time,
        timeseries,
        visualization,
        xray_dem,
    )

    assert time.extract_time_from_filename is not None
    assert io.scan_fits is not None
    assert data.ObservationFile is not None
    assert map.get_display_extent is not None
    assert timeseries.normalize_time_column is not None
    assert net.download_url is not None
    assert cme.running_difference is not None
    assert xray_dem.load_sxr_data is not None
    assert visualization.configure_chinese_fonts is not None


def test_radio_core_compatibility_aliases_point_to_public_modules():
    """Historical radio core imports remain aliases of solar_toolkit.radio."""
    pairs = {
        "scripts.radio.core.radio_raw_quality": "solar_toolkit.radio.raw_quality",
        "scripts.radio.core.radio_spectrogram": "solar_toolkit.radio.spectrogram",
        "scripts.radio.core.radio_drift_rate": "solar_toolkit.radio.drift_rate",
        "scripts.radio.core.radio_drift_products": "solar_toolkit.radio.drift_products",
    }

    for old_name, new_name in pairs.items():
        old_module = importlib.import_module(old_name)
        new_module = importlib.import_module(new_name)
        assert old_module is new_module


def test_aia_core_compatibility_aliases_point_to_public_modules():
    """Historical AIA core imports remain aliases of solar_toolkit.aia."""
    pairs = {
        "scripts.aia_hmi.core.aia_config": "solar_toolkit.aia.config",
        "scripts.aia_hmi.core.aia_io": "solar_toolkit.aia.io",
        "scripts.aia_hmi.core.aia_difference": "solar_toolkit.aia.difference",
        "scripts.aia_hmi.core.aia_mosaic": "solar_toolkit.aia.mosaic",
        "scripts.aia_hmi.core.aia_processor": "solar_toolkit.aia.processor",
        "scripts.aia_hmi.core.aia_cli": "solar_toolkit.aia.cli",
    }

    for old_name, new_name in pairs.items():
        old_module = importlib.import_module(old_name)
        new_module = importlib.import_module(new_name)
        assert old_module is new_module


def test_radio_gaussian_split_facades_export_existing_api():
    """Gaussian helper facades document the planned functional split."""
    from solar_toolkit.radio import (
        gaussian_background,
        gaussian_diagnostics,
        gaussian_fit,
        gaussian_io,
        gaussian_masks,
        gaussian_models,
    )

    assert gaussian_models.elliptical_gaussian_2d is not None
    assert gaussian_background.estimate_background_noise is not None
    assert gaussian_masks.create_source_mask is not None
    assert gaussian_fit.fit_elliptical_gaussian_on_radio_image is not None
    assert gaussian_diagnostics._gaussian_quality_config is not None
    assert gaussian_io.save_gaussian_diagnostics_row is not None
