"""Contracts for the installable Radio pipeline and source-map workflows."""

from __future__ import annotations

import ast
import importlib
from copy import deepcopy
from pathlib import Path

from solar_toolkit.radio import (
    pipeline_cli,
    pipeline_workflow,
    source_map_cli,
    source_map_workflow,
)


def test_pipeline_cli_uses_package_runner_by_default(monkeypatch):
    observed = []
    monkeypatch.setattr(
        pipeline_workflow,
        "run_pipeline",
        lambda argv: observed.append(argv) or 0,
    )

    assert pipeline_cli.main(["--output-dir", "products"]) == 0
    assert observed == [["--output-dir", "products"]]


def test_source_map_cli_uses_package_runner_and_forwards_workflow_options(
    monkeypatch,
):
    observed = []
    monkeypatch.setattr(
        source_map_cli,
        "load_radio_user_config",
        lambda _source: ({"output": {}, "gaussian": {}}, {}),
    )
    monkeypatch.setattr(
        source_map_workflow,
        "run_source_map",
        lambda config, *, argv: observed.append((config, argv)) or 0,
    )
    monkeypatch.setattr(
        source_map_cli,
        "resolve_provenance_output_dir",
        lambda _config: None,
    )

    assert source_map_cli.main(["--analysis-subdir", "analysis", "--select-drift"]) == 0
    assert observed == [
        (
            {
                "output": {"analysis_subdir": "analysis"},
                "gaussian": {},
            },
            ["--select-drift"],
        )
    ]


def test_source_map_explicit_config_overrides_path_config(monkeypatch):
    path_config = deepcopy(source_map_workflow.DEFAULT_CONFIG)
    path_config["output_dir"] = "path-config-output"
    monkeypatch.setattr(
        source_map_workflow,
        "load_script_config",
        lambda _key, _defaults: deepcopy(path_config),
    )
    monkeypatch.setattr(source_map_workflow, "run_self_tests", lambda: None)

    source_map_workflow._run_source_map_workflow(
        user_config={"output": {"output_dir": "explicit-output"}},
        argv=["--self-test"],
    )

    assert source_map_workflow.CONFIG["output_dir"] == "explicit-output"


def test_package_workflows_have_no_repository_only_imports():
    repo_root = Path(__file__).resolve().parents[1]
    violations = []
    for relative in (
        "solar_toolkit/radio/pipeline_workflow.py",
        "solar_toolkit/radio/source_map_workflow.py",
    ):
        path = repo_root / relative
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                if name.partition(".")[0] in {"examples", "legacy", "scripts"}:
                    violations.append((relative, node.lineno, name))

    assert violations == []


def test_historical_source_map_module_forwards_to_packaged_workflow(monkeypatch):
    from scripts.radio.legacy import radio_source_map_plot_gaussian_overlay as legacy

    observed = []
    monkeypatch.setattr(
        legacy,
        "_run_source_map_workflow",
        lambda *, user_config, argv: observed.append((user_config, argv)),
    )

    assert legacy.main({"event": "test"}, argv=["--self-test"]) == 0
    assert observed == [({"event": "test"}, ["--self-test"])]
    assert legacy.build_config is source_map_workflow.build_config


def test_default_event_configs_are_package_owned_and_legacy_paths_are_aliases():
    from solar_toolkit.radio.config import load_radio_config_module

    for name in ("radio_20250124_config", "radio_20250503_config"):
        canonical = load_radio_config_module(name)
        historical = importlib.import_module(f"scripts.radio.configs.{name}")

        assert canonical.__name__ == f"solar_toolkit.radio.configs.{name}"
        assert historical is canonical
        assert canonical.EVENT_CONFIG["user"] is canonical.USER_CONFIG
