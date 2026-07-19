"""Managed Flask launcher for the source-map frontend."""

from __future__ import annotations

import argparse
import os
import threading
import webbrowser
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the standalone radio source-map and ROI annotation app."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7875)
    parser.add_argument("--allowed-roots", required=True)
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument("--keep-alive-after-close", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from werkzeug.serving import make_server

    from .server import create_app

    roots = [
        Path(item) for item in args.allowed_roots.split(os.pathsep) if item.strip()
    ]
    server = None
    app = None

    def request_shutdown() -> None:
        if app is not None:
            app.extensions["source_map_jobs"].stop_all()
            app.extensions["source_map_export_jobs"].stop_all()
        if server is not None:
            threading.Thread(target=server.shutdown, daemon=True).start()

    app = create_app(
        roots,
        stop_on_client_close=not args.keep_alive_after_close,
        shutdown_callback=request_shutdown,
    )
    server = make_server(args.host, int(args.port), app, threaded=True)
    url = f"http://{args.host}:{int(args.port)}/"
    print(f"Source-map annotation app: {url}")
    if args.open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.extensions["source_map_jobs"].stop_all()
        app.extensions["source_map_export_jobs"].stop_all()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
