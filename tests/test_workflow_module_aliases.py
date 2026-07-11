"""Identity checks for workflows moved out of compatibility scripts."""

from __future__ import annotations

import importlib


def test_cso_workflow_old_path_is_canonical_module():
    canonical = importlib.import_module("solar_toolkit.radio.cso_workflow")
    compatibility = importlib.import_module(
        "scripts.radio.legacy.cso_radio_spectrogram_plot"
    )

    assert compatibility is canonical


def test_radio_source_app_old_paths_are_canonical_modules():
    app = importlib.import_module("solar_toolkit.radio.source_app")
    old_app = importlib.import_module("scripts.radio.run_radio_source_app")
    launcher = importlib.import_module("solar_toolkit.radio.source_app_launcher")
    old_launcher = importlib.import_module("scripts.radio.run_radio_source_app_managed")

    assert old_app is app
    assert old_launcher is launcher


def test_image_sequence_video_old_path_is_canonical_module():
    canonical = importlib.import_module("solar_toolkit.visualization.video_cli")
    compatibility = importlib.import_module("scripts.tools.image_sequence_to_video")

    assert compatibility is canonical


def test_stereo_suvi_recipe_paths_are_canonical_modules():
    aliases = {
        "scripts.stereo_suvi.stereo_euvi_manifest_by_wavelength": (
            "solar_toolkit.data.stereo_manifest"
        ),
        "scripts.stereo_suvi.stereo_euvi_0448_overview_plot": (
            "solar_toolkit.visualization.stereo_euvi_overview"
        ),
        "scripts.stereo_suvi.stereo_euvi_roi_movie": (
            "solar_toolkit.visualization.stereo_euvi_roi_movie"
        ),
        "scripts.stereo_suvi.goes_suvi_0448_quadrant_plot": (
            "solar_toolkit.visualization.suvi_quadrant"
        ),
    }

    for old_name, canonical_name in aliases.items():
        assert importlib.import_module(old_name) is importlib.import_module(
            canonical_name
        )


def test_hmi_overlay_cli_old_path_is_canonical_module():
    canonical = importlib.import_module("solar_toolkit.hmi.overlay_cli")
    compatibility = importlib.import_module("scripts.aia_hmi.sdo_aia_hmi_overlay")

    assert compatibility is canonical
