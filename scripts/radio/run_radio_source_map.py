"""Entrypoint for radio source-map plotting with Gaussian overlay.

This wrapper keeps CLI/config handling separate from the retained legacy
plotter, so importing the entrypoint does not immediately load the scientific
plotting stack.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.radio.configs import DEFAULT_CONFIG_NAME, load_radio_user_config
    from scripts.radio.entrypoint_utils import (
        apply_output_overrides,
        parse_known_common_args,
    )
else:
    from .configs import DEFAULT_CONFIG_NAME, load_radio_user_config
    from .entrypoint_utils import apply_output_overrides, parse_known_common_args


def _parse_args():
    """Parse shared source-map options and ignore legacy-only arguments."""
    return parse_known_common_args(
        "Run radio source maps with Gaussian overlay.",
        default_config=DEFAULT_CONFIG_NAME,
    )


def main(config_name: str | None = None):
    """Run source-map plotting while keeping output tweaks at the entrypoint."""
    # The legacy module imports NumPy/Matplotlib/FITS dependencies, so keep it
    # inside main() where real processing starts.
    from scripts.radio.legacy import (
        radio_source_map_plot_gaussian_overlay as legacy_radio,
    )

    args = _parse_args()
    selected_config = config_name or args.config
    user_config, _newkirk_config = load_radio_user_config(selected_config)
    user_config = apply_output_overrides(user_config, args)
    return legacy_radio.main(user_config=user_config)


if __name__ == "__main__":
    main()
