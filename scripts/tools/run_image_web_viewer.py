"""Run the local image sequence web viewer.

English: Thin CLI for the Flask app factory in
`solar_toolkit.visualization.image_web_viewer`.

中文: 本文件只负责解析命令行参数并启动 Flask 服务, 具体扫描、显示和导出逻辑位于
`solar_toolkit.visualization.image_web_viewer`。
"""

from __future__ import annotations

import argparse
import os
import sys
import webbrowser
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a local multi-folder image sequence web viewer."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Flask bind host.")
    parser.add_argument("--port", type=int, default=7865, help="Flask bind port.")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode.")
    parser.add_argument(
        "--allowed-roots",
        default=None,
        help=(
            "Optional local folder boundary. Separate multiple roots with the "
            f"platform path separator ({os.pathsep!r})."
        ),
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open the viewer URL in the default browser after startup.",
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
        from solar_toolkit.visualization.image_web_viewer.server import create_app
    except ImportError as exc:
        print(
            "Flask is required to start the viewer. Install the app extra with "
            'python -m pip install -e ".[app]".',
            file=sys.stderr,
        )
        print(f"Import error: {exc}", file=sys.stderr)
        return 2

    allowed_roots = parse_allowed_roots(args.allowed_roots)
    app = create_app(allowed_roots=allowed_roots)
    url = f"http://{args.host}:{args.port}/"
    if args.open_browser:
        webbrowser.open(url)
    print(f"Image web viewer: {url}")
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
