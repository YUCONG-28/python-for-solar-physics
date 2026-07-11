"""Contract tests for the installable ``solar-radio`` command."""

from __future__ import annotations

import subprocess
import sys

from solar_toolkit.radio import cli, overlay_cli, source_map_cli

EXPECTED_COMMANDS = {
    "centers",
    "overlay",
    "pipeline",
    "quicklook",
    "raw-quality",
    "source-map",
    "trajectory",
}


def test_radio_cli_lists_exactly_the_supported_command_contract():
    parser = cli.build_parser()
    command_action = next(
        action for action in parser._actions if action.dest == "command"
    )

    assert set(command_action.choices) == EXPECTED_COMMANDS


def test_all_radio_subcommand_help_surfaces_are_import_safe():
    for command in sorted(EXPECTED_COMMANDS):
        result = subprocess.run(
            [sys.executable, "-m", "solar_toolkit.radio.cli", command, "--help"],
            text=True,
            capture_output=True,
            check=False,
        )

        assert result.returncode == 0, f"{command}: {result.stderr}"
        assert "usage:" in result.stdout.lower()
        assert f"solar-radio {command}" in result.stdout.splitlines()[0]


def test_source_map_compatibility_wrapper_uses_the_packaged_runner(monkeypatch):
    from scripts.radio import run_radio_source_map
    from solar_toolkit.radio import source_map_workflow

    observed = {}
    monkeypatch.setattr(
        source_map_cli,
        "load_radio_user_config",
        lambda _name: ({"output": {}, "gaussian": {}}, {}),
    )
    monkeypatch.setattr(
        source_map_workflow,
        "run_source_map",
        lambda config, *, argv: observed.update(config) or None,
    )

    assert (
        run_radio_source_map.main(
            config_name="event_config",
            argv=["--analysis-subdir", "analysis", "--ignored-legacy-option"],
        )
        == 0
    )
    assert observed["output"]["analysis_subdir"] == "analysis"


def test_overlay_compatibility_wrapper_uses_the_packaged_runner(monkeypatch):
    from scripts.radio import run_aia_radio_hmi_overlay
    from solar_toolkit.radio import overlay_workflow

    observed = {}
    monkeypatch.setattr(
        overlay_cli,
        "load_aia_radio_overlay_user_config",
        lambda name, *, section: {"config": name, "section": section},
    )
    monkeypatch.setattr(
        overlay_workflow,
        "run_overlay_workflow",
        lambda config: observed.update(config) or None,
    )

    assert (
        run_aia_radio_hmi_overlay.main(
            config_name="event_config",
            overlay_section="overlay_event",
            argv=[],
        )
        == 0
    )
    assert observed == {"config": "event_config", "section": "overlay_event"}


def test_pipeline_compatibility_wrapper_forwards_argv_without_importing_legacy(
    monkeypatch,
):
    from scripts.radio import run_radio_burst_pipeline

    observed = []
    monkeypatch.setattr(
        run_radio_burst_pipeline,
        "_run_pipeline",
        lambda argv: observed.extend(argv) or None,
    )

    assert (
        run_radio_burst_pipeline.main(
            config_name="event_config",
            argv=["--output-dir", "products"],
        )
        == 0
    )
    assert observed == ["--output-dir", "products", "--config", "event_config"]
