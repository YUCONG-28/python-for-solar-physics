"""Entrypoint for radio source-map plotting with Gaussian overlay."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.radio.configs import DEFAULT_CONFIG_NAME, load_radio_user_config
    from scripts.radio.legacy import (
        radio_source_map_plot_gaussian_overlay as legacy_radio,
    )
else:
    from .configs import DEFAULT_CONFIG_NAME, load_radio_user_config
    from .legacy import radio_source_map_plot_gaussian_overlay as legacy_radio


def _parse_args():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--config", default=DEFAULT_CONFIG_NAME)
    args, _unknown = parser.parse_known_args()
    return args


def main(config_name: str | None = None):
    """Run the legacy source-map workflow through the stable root entrypoint."""
    args = _parse_args() if config_name is None else None
    selected_config = config_name or args.config
    user_config, _newkirk_config = load_radio_user_config(selected_config)
    return legacy_radio.main(user_config=user_config)


if __name__ == "__main__":
    main()
