"""Entrypoint for AIA/HMI/radio overlay generation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.radio.configs import (
        DEFAULT_CONFIG_NAME,
        load_aia_radio_overlay_user_config,
    )
else:
    from .configs import DEFAULT_CONFIG_NAME, load_aia_radio_overlay_user_config


def _parse_args():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--config", default=DEFAULT_CONFIG_NAME)
    parser.add_argument(
        "--overlay-section",
        default="aia_radio_hmi",
        help=(
            "EVENT_CONFIG section to run. Defaults to the stable "
            "aia_radio_hmi overlay."
        ),
    )
    args, _unknown = parser.parse_known_args()
    return args


def main(config_name: str | None = None, overlay_section: str | None = None):
    """Execute the archived AIA/HMI/radio overlay script as a compatibility shim."""
    args = _parse_args() if config_name is None else None
    selected_config = config_name or args.config
    selected_section = overlay_section or (args.overlay_section if args else None)
    user_config = load_aia_radio_overlay_user_config(
        selected_config,
        section=selected_section or "aia_radio_hmi",
    )
    if __package__ in {None, ""}:
        from scripts.radio.legacy import sdo_aia_radio_hmi_overlay as legacy_aia
    else:
        from .legacy import sdo_aia_radio_hmi_overlay as legacy_aia

    return legacy_aia.main(user_config=user_config)


if __name__ == "__main__":
    main()
