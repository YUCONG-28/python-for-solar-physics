"""Focused guards for the canonical AIA processor and CLI layers."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from solar_toolkit.aia import processor

REPO_ROOT = Path(__file__).resolve().parents[1]


def _top_level_functions(relative_path: str) -> set[str]:
    path = REPO_ROOT / relative_path
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _config(**overrides):
    values = {
        "use_test_mode": False,
        "mode": "single",
        "multi_band_composite": False,
        "draw_original": True,
        "draw_difference": False,
        "difference_output_mode": "auto",
        "mosaic_difference_inline": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _executor(calls):
    return SimpleNamespace(
        _run_test_mode=lambda cfg: calls.append(("test", cfg)),
        _run_single_batch=lambda cfg: calls.append(("single", cfg)),
        _run_mosaic_batch=lambda cfg: calls.append(("mosaic", cfg)),
        _run_difference_batch=lambda cfg: calls.append(("difference", cfg)),
    )


def test_dispatch_and_cli_functions_have_one_canonical_definition():
    processor_functions = _top_level_functions("solar_toolkit/aia/processor.py")
    cli_functions = _top_level_functions("solar_toolkit/aia/cli.py")
    executor_functions = _top_level_functions(
        "solar_toolkit/aia/_euv_processor_impl.py"
    )

    assert {"_actual_mode", "process_aia_fits"} <= processor_functions
    assert {"build_parser", "config_from_args", "main"} <= cli_functions
    assert {
        "_actual_mode",
        "process_aia_fits",
        "build_parser",
        "config_from_args",
        "main",
        "_configure_matplotlib_backend",
    }.isdisjoint(executor_functions)
    assert {
        "_run_test_mode",
        "_run_single_batch",
        "_run_mosaic_batch",
        "_run_difference_batch",
    } <= executor_functions


def test_historical_private_executor_path_is_a_true_module_alias():
    executor = importlib.import_module("solar_toolkit.aia._euv_processor_impl")
    compatibility = importlib.import_module(
        "scripts.aia_hmi.core._aia_euv_processor_impl"
    )

    assert compatibility is executor


@pytest.mark.parametrize(
    ("config", "expected_mode", "expected_batches"),
    [
        (_config(mode="single"), "single", ["single"]),
        (
            _config(mode="single", draw_difference=True),
            "single",
            ["single", "difference"],
        ),
        (
            _config(mode="test", draw_difference=True),
            "test",
            ["test"],
        ),
        (
            _config(
                mode="mosaic",
                multi_band_composite=True,
                draw_difference=True,
                difference_output_mode="both",
            ),
            "mosaic",
            ["mosaic", "difference"],
        ),
        (
            _config(
                mode="single",
                multi_band_composite=True,
                draw_difference=False,
            ),
            "mosaic",
            ["mosaic"],
        ),
    ],
)
def test_processor_preserves_mode_dispatch(
    monkeypatch, config, expected_mode, expected_batches
):
    calls = []
    monkeypatch.setattr(
        processor,
        "_configure_matplotlib_backend",
        lambda mode: calls.append(("backend", mode)),
    )
    monkeypatch.setattr(processor, "_load_impl", lambda: _executor(calls))

    assert processor.process_aia_fits(config) is None

    assert calls[0] == ("backend", expected_mode)
    assert [name for name, _cfg in calls[1:]] == expected_batches
    if expected_mode == "mosaic" and config.draw_difference:
        assert config.mosaic_difference_inline is True


def test_processor_rejects_empty_draw_request_before_loading_executor(monkeypatch):
    loaded = False

    def load_executor():
        nonlocal loaded
        loaded = True
        return _executor([])

    monkeypatch.setattr(processor, "_configure_matplotlib_backend", lambda _mode: None)
    monkeypatch.setattr(processor, "_load_impl", load_executor)

    with pytest.raises(ValueError, match="Nothing to draw"):
        processor.process_aia_fits(_config(draw_original=False, draw_difference=False))

    assert loaded is False
