"""Command-line launcher for the unified local web workbench."""

from __future__ import annotations

import argparse
import os
import sys
import threading
import webbrowser
from pathlib import Path

from .runner import default_python_executable

__all__ = ["build_parser", "main", "parse_allowed_roots"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the local Solar Physics Workbench web GUI."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Flask bind host.")
    parser.add_argument("--port", type=int, default=7870, help="Flask bind port.")
    parser.add_argument(
        "--allowed-roots",
        default=None,
        help=(
            "Optional local folder boundary. Separate multiple roots with the "
            f"platform path separator ({os.pathsep!r})."
        ),
    )
    parser.add_argument(
        "--python-executable",
        default=default_python_executable(),
        help="Python executable used for launched project workflows.",
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open the workbench URL in the default browser after startup.",
    )
    parser.add_argument(
        "--keep-alive-after-close",
        action="store_true",
        help="Keep the Flask server running after the last browser page closes.",
    )
    return parser


def parse_allowed_roots(raw: str | None) -> list[Path] | None:
    if not raw:
        return None
    return [Path(item.strip()) for item in raw.split(os.pathsep) if item.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    try:
        from werkzeug.serving import make_server

        from solar_toolkit.webapp.server import create_app
    except ImportError as exc:
        print(
            "Flask is required to start the workbench. Install the app extra with "
            'python -m pip install -e ".[app]".',
            file=sys.stderr,
        )
        print(f"Import error: {exc}", file=sys.stderr)
        return 2

    server = None

    def request_shutdown() -> None:
        if server is not None:
            threading.Thread(target=server.shutdown, daemon=True).start()

    app = create_app(
        allowed_roots=parse_allowed_roots(args.allowed_roots),
        python_executable=args.python_executable,
        repo_root=repo_root,
        stop_on_client_close=not args.keep_alive_after_close,
        shutdown_callback=request_shutdown,
    )
    url = f"http://{args.host}:{args.port}/"
    if args.open_browser:
        webbrowser.open(url)
    print(f"Solar Physics Workbench: {url}")
    server = make_server(args.host, args.port, app, threaded=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
