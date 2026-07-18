"""Local image-viewer command adapter with a fail-closed root policy."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

from solar_apps.platform.paths.allowed_roots import (
    AllowedRootPolicyError,
    prepare_allowed_root_args,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="Apps/run.ps1 frontend image-viewer",
        description="Run the local image-sequence web viewer.",
        epilog="Additional arguments are forwarded to the image-viewer parser.",
    )
    parser.add_argument(
        "--allowed-roots",
        metavar="PATHS",
        help=f"Required filesystem boundary, separated by {os.pathsep!r}.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if any(item in {"-h", "--help"} for item in args):
        build_parser().print_help()
        return 0
    try:
        forwarded = prepare_allowed_root_args(args)
    except AllowedRootPolicyError as exc:
        print(f"image_viewer: error: {exc}", file=sys.stderr)
        return 2
    from .application import main as application_main

    return int(application_main(forwarded))


if __name__ == "__main__":
    raise SystemExit(main())
