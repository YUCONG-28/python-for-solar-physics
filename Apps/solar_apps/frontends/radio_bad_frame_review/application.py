"""Command-line launcher for the standalone bad-frame review web application."""

from __future__ import annotations

import argparse
import os
import sys
import threading
import webbrowser
from pathlib import Path

from solar_apps.platform.layout import RuntimeLayout

__all__ = ["build_parser", "main", "parse_allowed_roots"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the standalone radio bad-frame review web application."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Flask bind host.")
    parser.add_argument("--port", type=int, default=7866, help="Flask bind port.")
    parser.add_argument(
        "--allowed-roots",
        required=True,
        help=(
            "Filesystem boundary for radio inputs. Separate multiple roots with "
            f"the platform path separator ({os.pathsep!r})."
        ),
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help="Review storage root. Defaults to Local/outputs/bad_frame_reviews.",
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open the review application in the default browser after startup.",
    )
    parser.add_argument(
        "--keep-alive-after-close",
        action="store_true",
        help="Keep the server running after the final browser page closes.",
    )
    return parser


def parse_allowed_roots(raw: str) -> list[Path]:
    return [Path(item.strip()) for item in raw.split(os.pathsep) if item.strip()]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        from werkzeug.serving import make_server

        from .server import create_app
    except ImportError as exc:
        print(
            "Flask and the Local application dependencies are required to start "
            "the bad-frame reviewer.",
            file=sys.stderr,
        )
        print(f"Import error: {exc}", file=sys.stderr)
        return 2

    local_root = RuntimeLayout.discover().local_root
    output_root = (
        Path(args.output_root).expanduser()
        if args.output_root
        else local_root / "outputs" / "bad_frame_reviews"
    )
    server = None

    def request_shutdown() -> None:
        if server is not None:
            threading.Thread(target=server.shutdown, daemon=True).start()

    app = create_app(
        allowed_roots=parse_allowed_roots(args.allowed_roots),
        output_root=output_root,
        stop_on_client_close=not args.keep_alive_after_close,
        shutdown_callback=request_shutdown,
    )
    url = f"http://{args.host}:{args.port}/"
    server = make_server(args.host, args.port, app, threaded=True)
    if args.open_browser:
        webbrowser.open(url)
    print(f"Radio bad-frame review: {url}")
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
