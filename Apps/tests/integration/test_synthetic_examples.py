from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from solar_apps.platform.layout import RuntimeLayout

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES_ROOT = REPO_ROOT / "Apps" / "examples"


def _load_example(name: str) -> ModuleType:
    path = EXAMPLES_ROOT / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"apps_example_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _layout(tmp_path: Path) -> RuntimeLayout:
    root = tmp_path / "workspace"
    (root / "Apps").mkdir(parents=True)
    (root / "Python").mkdir()
    return RuntimeLayout.discover(root, environ={}).ensure()


def test_examples_are_import_safe_and_write_only_private_outputs(
    tmp_path: Path,
) -> None:
    layout = _layout(tmp_path)
    radio = _load_example("synthetic_radio_display")
    state = _load_example("synthetic_state_and_paths")

    assert list(layout.outputs_dir.rglob("*")) == []

    radio_result = radio.run_demo(layout=layout, size=48)
    state_result = state.run_demo(layout=layout)

    assert radio_result["image"].is_file()
    assert radio_result["sidecar"].is_file()
    assert state_result["summary"].is_file()
    assert radio_result["image"].is_relative_to(layout.outputs_dir)
    assert state_result["summary"].is_relative_to(layout.outputs_dir)
    assert list(layout.apps_root.rglob("*")) == []


@pytest.mark.parametrize(
    ("example_name", "argument_name", "filename"),
    (
        ("synthetic_radio_display", "output", "blocked.png"),
        ("synthetic_state_and_paths", "output_dir", "blocked"),
    ),
)
def test_examples_reject_outputs_inside_apps(
    tmp_path: Path,
    example_name: str,
    argument_name: str,
    filename: str,
) -> None:
    layout = _layout(tmp_path)
    module = _load_example(example_name)

    with pytest.raises(ValueError, match="inside Apps"):
        module.run_demo(layout=layout, **{argument_name: layout.apps_root / filename})
