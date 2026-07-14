"""Smoke checks for maintained public-API examples."""

from __future__ import annotations

import ast
import importlib
import importlib.util
import inspect
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_ROOT = REPO_ROOT / "examples"

NO_DATA_EXAMPLES = [
    "public_api/time_matching_example.py",
    "public_api/gaussian_model_example.py",
]
REAL_DATA_RECIPES = [
    "aia_hmi/solar_limb_contour_example.py",
    "radio/fits_header_metadata_example.py",
    "gaussian_newkirk_quicklook/quicklook_gaussian_newkirk.py",
    "radio_aia_hmi/aia_radio_hmi_overlay_demo.py",
]
MAINTAINED_EXAMPLES = NO_DATA_EXAMPLES + REAL_DATA_RECIPES


def _load_example(relative_path: str):
    path = EXAMPLES_ROOT / relative_path
    module_name = "_example_" + relative_path.replace("/", "_").replace(".", "_")
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("relative_path", MAINTAINED_EXAMPLES)
def test_maintained_examples_are_import_safe_and_have_integer_main(relative_path):
    module = _load_example(relative_path)

    assert callable(module.main)
    assert inspect.signature(module.main).return_annotation in {int, "int"}


@pytest.mark.parametrize("relative_path", NO_DATA_EXAMPLES)
def test_no_data_examples_are_marked_for_smoke_execution(relative_path):
    module = _load_example(relative_path)

    assert module.REQUIRES_LOCAL_DATA is False


@pytest.mark.parametrize("relative_path", REAL_DATA_RECIPES)
def test_real_data_recipes_are_marked_and_not_executed(relative_path):
    module = _load_example(relative_path)

    assert module.REQUIRES_LOCAL_DATA is True


def test_time_matching_example_runs_without_external_data(capsys):
    module = _load_example(NO_DATA_EXAMPLES[0])

    assert module.find_nearest_observation("2024-01-10T06:29:33Z").endswith(
        "2024-01-10T062937Z.171.image_lev1.fits"
    )
    assert module.main([]) == 0
    assert "2024-01-10T062937Z" in capsys.readouterr().out


def test_gaussian_model_example_runs_without_external_data(capsys):
    module = _load_example(NO_DATA_EXAMPLES[1])

    image = module.build_gaussian_image(9)
    assert image.shape == (9, 9)
    assert np.isfinite(image).all()
    assert image.max() == pytest.approx(1.0)
    assert module.main([]) == 0
    assert "shape=(9, 9)" in capsys.readouterr().out


@pytest.mark.parametrize("relative_path", MAINTAINED_EXAMPLES)
def test_maintained_examples_use_only_public_solar_toolkit_surfaces(relative_path):
    path = EXAMPLES_ROOT / relative_path
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(("scripts", "legacy", "examples"))
                if alias.name.startswith("solar_toolkit"):
                    assert not any(
                        part.startswith("_") for part in alias.name.split(".")
                    )
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            assert not module_name.startswith(("scripts", "legacy", "examples"))
            if module_name.startswith("solar_toolkit"):
                assert not any(part.startswith("_") for part in module_name.split("."))
                public_module = importlib.import_module(module_name)
                exported = set(public_module.__all__)
                for alias in node.names:
                    assert not alias.name.startswith("_")
                    assert alias.name in exported


def test_large_overlay_workflow_is_preserved_as_history():
    legacy_path = (
        EXAMPLES_ROOT / "history" / "radio_aia_hmi" / "aia_radio_hmi_overlay_legacy.py"
    )
    text = legacy_path.read_text(encoding="utf-8")

    assert len(text.splitlines()) >= 1797
    assert 'warnings.filterwarnings("ignore")' in text
    assert (
        "historical"
        in (legacy_path.parent / "README.md").read_text(encoding="utf-8").lower()
    )
