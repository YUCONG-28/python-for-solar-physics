"""Internal editable-install probe used exclusively by ``Apps/run.ps1``."""

from __future__ import annotations

import argparse
import json
from importlib import metadata
from pathlib import Path


def _editable_distribution(name: str) -> bool:
    """Accept an editable installation even when cwd exposes a shadow egg-info."""

    for distribution in metadata.distributions(name=name):
        direct_url = distribution.read_text("direct_url.json")
        if not direct_url:
            continue
        try:
            payload = json.loads(direct_url)
        except json.JSONDecodeError:
            continue
        if payload.get("dir_info", {}).get("editable"):
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--apps-root", type=Path, required=True)
    parser.add_argument("--python-root", type=Path, required=True)
    args = parser.parse_args(argv)

    import solar_apps
    import solar_toolkit

    apps_root = args.apps_root.resolve()
    python_root = args.python_root.resolve()
    if not Path(solar_apps.__file__).resolve().is_relative_to(apps_root):
        parser.exit(2, "solar_apps is not the Apps editable installation\n")
    if not Path(solar_toolkit.__file__).resolve().is_relative_to(python_root):
        parser.exit(2, "solar_toolkit is not the Python editable installation\n")
    for name in ("solarphysics-apps", "solar-physics-toolkit"):
        if not _editable_distribution(name):
            parser.exit(2, f"{name} is not installed editable\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
