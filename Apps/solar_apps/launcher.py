"""Shared Windows/macOS bootstrap for the public application launchers."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from solar_apps.cli.router import main as cli_main
from solar_apps.platform.environment import (
    SUPPORTED_ENVIRONMENTS,
    UnsupportedPythonEnvironment,
    inspect_miniforge_runtime,
)
from solar_apps.platform.environment_probe import main as probe_main
from solar_apps.platform.processes import (
    PYTHON_EXECUTABLE_ENV,
    miniforge_subprocess_environment,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--miniforge-root", type=Path, required=True)
    parser.add_argument(
        "--environment-name", choices=SUPPORTED_ENVIRONMENTS, required=True
    )
    parser.add_argument("--config-path", type=Path)
    parser.add_argument("--launcher-name", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        separator = arguments.index("--")
    except ValueError:
        bootstrap_arguments, command = arguments, []
    else:
        bootstrap_arguments, command = arguments[:separator], arguments[separator + 1 :]
    args = build_parser().parse_args(bootstrap_arguments)

    workspace = args.workspace_root.expanduser().resolve(strict=True)
    apps_root = workspace / "Apps"
    python_root = workspace / "Python"
    if not apps_root.is_dir() or not python_root.is_dir():
        raise SystemExit(
            "Workspace must contain adjacent Apps/ and Python/ directories."
        )

    try:
        runtime = inspect_miniforge_runtime(
            sys.executable,
            miniforge_root=args.miniforge_root,
        )
    except UnsupportedPythonEnvironment as exc:
        raise SystemExit(str(exc)) from exc
    if runtime.environment_name != args.environment_name:
        raise SystemExit(
            f"Selected interpreter belongs to {runtime.environment_name!r}, "
            f"not {args.environment_name!r}."
        )

    local_root = (
        Path(os.environ.get("SOLAR_APPS_LOCAL_ROOT", workspace / "Local"))
        .expanduser()
        .resolve(strict=False)
    )
    config_path = (
        args.config_path.expanduser().resolve(strict=False)
        if args.config_path
        else local_root / "configs" / "paths.local.yaml"
    )
    environment = miniforge_subprocess_environment(
        os.environ,
        python_executable=runtime.executable,
    )
    environment.update(
        {
            "SOLAR_APPS_REPO_ROOT": str(workspace),
            "SOLAR_APPS_LOCAL_ROOT": str(local_root),
            "SOLAR_APPS_CONFIG": str(config_path),
            "SOLAR_PHYSICS_CONFIG": str(config_path),
            PYTHON_EXECUTABLE_ENV: str(runtime.executable),
            "SOLAR_APPS_ENVIRONMENT": runtime.environment_name,
            "SOLAR_MINIFORGE_ROOT": str(runtime.miniforge_root),
            "SOLAR_APPS_LAUNCHER": args.launcher_name,
        }
    )
    os.environ.clear()
    os.environ.update(environment)

    probe_status = probe_main(
        ["--apps-root", str(apps_root), "--python-root", str(python_root)]
    )
    if probe_status:
        return probe_status
    return cli_main(command or ["--help"])


if __name__ == "__main__":
    raise SystemExit(main())
