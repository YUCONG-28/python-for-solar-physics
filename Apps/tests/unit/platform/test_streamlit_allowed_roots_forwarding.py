"""Allowed-root forwarding for the managed Streamlit launchers."""

from __future__ import annotations

import pytest

from solar_apps.frontends.radio.composite_figure import composite_figure_launcher
from solar_apps.frontends.radio.dart_spectrogram import dart_spectrogram_launcher
from solar_apps.frontends.radio.roi_lightcurve import roi_lightcurve_launcher
from solar_apps.frontends.radio.source_trajectory import source_app_launcher


@pytest.mark.parametrize(
    ("launcher", "extra_args"),
    [
        (composite_figure_launcher, []),
        (dart_spectrogram_launcher, []),
        (roi_lightcurve_launcher, []),
        (source_app_launcher, []),
    ],
)
def test_managed_launcher_forwards_allowed_roots(launcher, extra_args) -> None:
    roots = r"D:\data;D:\results"
    args = launcher.build_parser().parse_args(
        ["--allowed-roots", roots, "--no-browser", *extra_args]
    )

    command = launcher.build_streamlit_command(args, port=8765)

    assert command[command.index("--allowed-roots") + 1] == roots
