"""Application launcher for the PySide6 image composer."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from solar_apps.platform.paths import (
    AllowedRootPolicyError,
    configured_allowed_roots,
)
from solar_apps.platform.layout import RuntimeLayout


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the local PySide6 free image composer."
    )
    parser.add_argument(
        "--project",
        type=Path,
        default=None,
        help="Optional .fic.json project to open at startup.",
    )
    parser.add_argument(
        "--allowed-roots",
        default=None,
        help=(
            "Path-separated directories that may be opened or written. "
            "Defaults to the private Local configuration."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        configured_roots = configured_allowed_roots(cli_value=args.allowed_roots)
    except AllowedRootPolicyError as exc:
        print(f"Invalid allowed-root configuration: {exc}", file=sys.stderr)
        return 2
    layout = RuntimeLayout.discover()
    allowed_roots = tuple(
        dict.fromkeys((*configured_roots, layout.workspaces_dir, layout.outputs_dir))
    )
    if not configured_roots:
        print(
            "No application allowed roots are configured. Add apps.allowed_roots "
            "to the private Local config or pass --allowed-roots with "
            f"{os.pathsep!r} separators.",
            file=sys.stderr,
        )
        return 2
    try:
        from PySide6.QtWidgets import QApplication

        from .ui import create_window
    except ImportError as exc:
        print(
            "PySide6 is required to run the image composer. Install the Apps "
            "package in the selected Miniforge environment with its app extra.",
            file=sys.stderr,
        )
        print(f"Import error: {exc}", file=sys.stderr)
        return 2
    app = QApplication.instance() or QApplication(["free-image-composer"])
    app.setApplicationName("Free Image Composer")
    window = create_window(args.project, allowed_roots=allowed_roots)
    window.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
