"""Focused contracts for retained source-only radio workflow entry points."""

from __future__ import annotations

import ast
import inspect
from importlib import import_module
from pathlib import Path
from typing import get_type_hints

import pytest


@pytest.mark.parametrize(
    ("module_name", "workflow_name"),
    (
        (
            "scripts.radio.legacy.radio_source_map_plot_gaussian_overlay",
            "_run_source_map_workflow",
        ),
        (
            "scripts.radio.legacy.sdo_aia_radio_hmi_overlay",
            "_run_overlay_workflow",
        ),
    ),
)
def test_legacy_main_preserves_user_config_and_returns_status(
    monkeypatch,
    module_name,
    workflow_name,
):
    module = import_module(module_name)
    calls = []
    user_config = {"event": "test"}

    def fake_workflow(*, user_config, argv):
        calls.append((user_config, argv))
        return ["retained-workflow-result"]

    monkeypatch.setattr(module, workflow_name, fake_workflow)

    signature = inspect.signature(module.main)
    assert signature.parameters["user_config"].default is None
    assert signature.parameters["argv"].default is None
    assert signature.parameters["argv"].kind is inspect.Parameter.KEYWORD_ONLY
    assert get_type_hints(module.main)["return"] is int
    assert module.main(user_config, argv=["--test-option"]) == 0
    assert calls == [(user_config, ["--test-option"])]


def test_streamlit_main_returns_status_after_normal_completion(monkeypatch):
    module = import_module("scripts.radio.run_radio_source_app")
    calls = []
    monkeypatch.setattr(
        module,
        "_run_streamlit_app",
        lambda argv: calls.append(argv),
    )

    signature = inspect.signature(module.main)
    assert signature.parameters["argv"].default is None
    assert get_type_hints(module.main)["return"] is int
    assert module.main(["--settings-file", "settings.json"]) == 0
    assert calls == [["--settings-file", "settings.json"]]


def test_streamlit_main_does_not_swallow_control_flow(monkeypatch):
    module = import_module("scripts.radio.run_radio_source_app")

    class StreamlitControlFlow(BaseException):
        pass

    def stop_or_rerun(_argv):
        raise StreamlitControlFlow

    monkeypatch.setattr(module, "_run_streamlit_app", stop_or_rerun)

    with pytest.raises(StreamlitControlFlow):
        module.main([])


@pytest.mark.parametrize(
    "relative_path",
    (
        "scripts/radio/legacy/radio_source_map_plot_gaussian_overlay.py",
        "scripts/radio/legacy/sdo_aia_radio_hmi_overlay.py",
        "solar_toolkit/radio/source_app.py",
    ),
)
def test_retained_workflow_module_exits_with_main_status(relative_path):
    repo_root = Path(__file__).resolve().parents[1]
    tree = ast.parse((repo_root / relative_path).read_text(encoding="utf-8"))
    main_guards = [
        node
        for node in tree.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
    ]

    assert len(main_guards) == 1
    assert len(main_guards[0].body) == 1
    statement = main_guards[0].body[0]
    assert isinstance(statement, ast.Raise)
    assert isinstance(statement.exc, ast.Call)
    assert isinstance(statement.exc.func, ast.Name)
    assert statement.exc.func.id == "SystemExit"
    assert isinstance(statement.exc.args[0], ast.Call)
    assert isinstance(statement.exc.args[0].func, ast.Name)
    assert statement.exc.args[0].func.id == "main"
