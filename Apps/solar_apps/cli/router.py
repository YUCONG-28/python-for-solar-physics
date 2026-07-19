"""Canonical command router for all public application entry points."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from solar_apps.platform.environment import (
    UnsupportedPythonEnvironment,
    inspect_miniforge_runtime,
)
from solar_apps.platform.dispatch import forward_main

FRONTEND_TARGETS = {
    "bad-frame-review": "solar_apps.frontends.radio_bad_frame_review.cli",
    "dart-spectrogram": (
        "solar_apps.frontends.radio.dart_spectrogram.dart_spectrogram_launcher"
    ),
    "image-composer": "solar_apps.frontends.image_composer.cli",
    "image-viewer": "solar_apps.frontends.image_viewer.cli",
    "roi-lightcurve": (
        "solar_apps.frontends.radio.roi_lightcurve.roi_lightcurve_launcher"
    ),
    "source-map": "solar_apps.frontends.radio.source_map.cli",
    "source-trajectory": (
        "solar_apps.frontends.radio.source_trajectory.source_app_launcher"
    ),
    "workbench": "solar_apps.frontends.workbench.cli",
}

WORKFLOW_TARGETS = {
    "aia": "solar_apps.workflows.aia.cli",
    "radio": "solar_apps.workflows.radio.cli",
}

WORKFLOW_COMMAND_TARGETS = {
    "data": {
        "stereo-manifest": "solar_apps.workflows.data.stereo_manifest_cli",
    },
    "hmi": {
        "fits-rename": "solar_apps.workflows.hmi.fits_rename_cli",
        "overlay": "solar_apps.workflows.hmi.overlay_cli",
    },
    "net": {
        "jsoc": "solar_apps.workflows.net.jsoc_cli",
    },
    "visualization": {
        "video": "solar_apps.workflows.visualization.video_cli",
    },
    "xray-dem": {
        "dem-radio": "solar_apps.workflows.xray_dem.dem_radio_cli",
    },
}

TOOL_TARGETS = {
    "bad-frame-ml": "solar_apps.frontends.radio_bad_frame_review.ml_cli",
}

LEGACY_FRONTENDS = {
    "webapp": "workbench",
    "image_viewer": "image-viewer",
    "image_composer": "image-composer",
    "bad_frame_review": "bad-frame-review",
}

LEGACY_RADIO_FRONTENDS = {
    "dart-spectrogram": "dart-spectrogram",
    "roi-lightcurve": "roi-lightcurve",
    "source-map-app": "source-map",
    "source-trajectory-app": "source-trajectory",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="Apps/run.ps1",
        description="Run Solar Physics frontends and workflows through Miniforge.",
    )
    parser.add_argument(
        "group",
        nargs="?",
        choices=("frontend", "workflow", "admin", "tools"),
        help="Command group.",
    )
    return parser


def _print_group_help(group: str) -> None:
    if group == "frontend":
        values = sorted(FRONTEND_TARGETS)
        usage = "frontend <frontend-id> [arguments]"
    elif group == "workflow":
        values = sorted({*WORKFLOW_TARGETS, *WORKFLOW_COMMAND_TARGETS})
        usage = "workflow <domain> [command] [arguments]"
    elif group == "tools":
        values = sorted(TOOL_TARGETS)
        usage = "tools <tool-id> [arguments]"
    else:
        print("usage: Apps/run.ps1 admin init [--force-config]")
        return
    print(f"usage: Apps/run.ps1 {usage}")
    print("\navailable:")
    for value in values:
        print(f"  {value}")


def _error(message: str) -> int:
    print(f"solar-apps: error: {message}", file=sys.stderr)
    return 2


def _translate_legacy(arguments: list[str]) -> list[str]:
    if not arguments:
        return arguments
    command = arguments[0]
    if command in LEGACY_FRONTENDS:
        return ["frontend", LEGACY_FRONTENDS[command], *arguments[1:]]
    if command == "bad_frame_ml":
        return ["tools", "bad-frame-ml", *arguments[1:]]
    if command == "aia":
        return ["workflow", "aia", *arguments[1:]]
    if command == "radio":
        if len(arguments) > 1 and arguments[1] in LEGACY_RADIO_FRONTENDS:
            return [
                "frontend",
                LEGACY_RADIO_FRONTENDS[arguments[1]],
                *arguments[2:],
            ]
        return ["workflow", "radio", *arguments[1:]]
    return arguments


def _dispatch_frontend(arguments: list[str]) -> int:
    if not arguments or arguments[0] in {"-h", "--help"}:
        _print_group_help("frontend")
        return 0
    frontend = arguments.pop(0)
    target = FRONTEND_TARGETS.get(frontend)
    if target is None:
        return _error(f"unknown frontend {frontend!r}")
    return forward_main(
        target,
        arguments,
        program=f"Apps/run.ps1 frontend {frontend}",
    )


def _dispatch_workflow(arguments: list[str]) -> int:
    if not arguments or arguments[0] in {"-h", "--help"}:
        _print_group_help("workflow")
        return 0
    domain = arguments.pop(0)
    if domain in WORKFLOW_TARGETS:
        return forward_main(
            WORKFLOW_TARGETS[domain],
            arguments,
            program=f"Apps/run.ps1 workflow {domain}",
        )
    commands = WORKFLOW_COMMAND_TARGETS.get(domain)
    if commands is None:
        return _error(f"unknown workflow domain {domain!r}")
    if not arguments or arguments[0] in {"-h", "--help"}:
        print(f"usage: Apps/run.ps1 workflow {domain} <command> [arguments]")
        print("\navailable:")
        for command in sorted(commands):
            print(f"  {command}")
        return 0
    command = arguments.pop(0)
    target = commands.get(command)
    if target is None:
        return _error(f"unknown {domain} workflow {command!r}")
    return forward_main(
        target,
        arguments,
        program=f"Apps/run.ps1 workflow {domain} {command}",
    )


def _dispatch_tools(arguments: list[str]) -> int:
    if not arguments or arguments[0] in {"-h", "--help"}:
        _print_group_help("tools")
        return 0
    tool = arguments.pop(0)
    target = TOOL_TARGETS.get(tool)
    if target is None:
        return _error(f"unknown tool {tool!r}")
    return forward_main(
        target,
        arguments,
        program=f"Apps/run.ps1 tools {tool}",
    )


def main(argv: Sequence[str] | None = None) -> int:
    try:
        inspect_miniforge_runtime()
    except UnsupportedPythonEnvironment as exc:
        return _error(str(exc))
    arguments = _translate_legacy(list(sys.argv[1:] if argv is None else argv))
    if not arguments or arguments[0] in {"-h", "--help"}:
        build_parser().print_help()
        print(
            "\nlegacy aliases: aia, radio, webapp, image_viewer, image_composer, "
            "bad_frame_review, bad_frame_ml"
        )
        return 0
    group = arguments.pop(0)
    if group in {"frontend", "workflow", "tools"}:
        try:
            from .admin import initialize_runtime

            initialize_runtime()
        except OSError as exc:
            return _error(f"could not initialize the private Local runtime: {exc}")
    if group == "frontend":
        return _dispatch_frontend(arguments)
    if group == "workflow":
        return _dispatch_workflow(arguments)
    if group == "tools":
        return _dispatch_tools(arguments)
    if group == "admin":
        from .admin import main as admin_main

        if not arguments or arguments[0] in {"-h", "--help"}:
            _print_group_help("admin")
            return 0
        return admin_main(arguments)
    return _error(f"unknown command group or legacy alias {group!r}")


__all__ = [
    "FRONTEND_TARGETS",
    "LEGACY_FRONTENDS",
    "LEGACY_RADIO_FRONTENDS",
    "TOOL_TARGETS",
    "WORKFLOW_COMMAND_TARGETS",
    "WORKFLOW_TARGETS",
    "build_parser",
    "main",
]
