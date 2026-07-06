"""Public package-boundary tests for the project-wide refactor."""

from __future__ import annotations

import importlib


def test_domain_packages_import_without_loading_science_data():
    """The public library layer exposes science-domain packages."""
    for module_name in [
        "solar_toolkit.aia",
        "solar_toolkit.hmi",
        "solar_toolkit.time",
        "solar_toolkit.io",
        "solar_toolkit.data",
        "solar_toolkit.map",
        "solar_toolkit.timeseries",
        "solar_toolkit.xray_dem",
        "solar_toolkit.cme",
        "solar_toolkit.net",
        "solar_toolkit.modeling",
        "solar_toolkit.visualization",
    ]:
        module = importlib.import_module(module_name)
        assert module.__doc__


def test_sunpy_style_base_helpers_are_public():
    """SunPy-style base packages expose the stable helper functions."""
    from solar_toolkit import (
        cme,
        data,
        io,
        map,
        net,
        time,
        timeseries,
        visualization,
        xray_dem,
    )

    assert time.extract_time_from_filename is not None
    assert io.scan_fits is not None
    assert data.ObservationFile is not None
    assert map.get_display_extent is not None
    assert timeseries.normalize_time_column is not None
    assert net.download_url is not None
    assert cme.running_difference is not None
    assert xray_dem.load_sxr_data is not None
    assert visualization.configure_chinese_fonts is not None


def test_radio_core_compatibility_aliases_point_to_public_modules():
    """Historical radio core imports remain aliases of solar_toolkit.radio."""
    pairs = {
        "scripts.radio.core.radio_raw_quality": "solar_toolkit.radio.raw_quality",
        "scripts.radio.core.radio_spectrogram": "solar_toolkit.radio.spectrogram",
        "scripts.radio.core.radio_drift_rate": "solar_toolkit.radio.drift_rate",
        "scripts.radio.core.radio_drift_products": "solar_toolkit.radio.drift_products",
    }

    for old_name, new_name in pairs.items():
        old_module = importlib.import_module(old_name)
        new_module = importlib.import_module(new_name)
        assert old_module is new_module


def test_aia_core_compatibility_aliases_point_to_public_modules():
    """Historical AIA core imports remain aliases of solar_toolkit.aia."""
    pairs = {
        "scripts.aia_hmi.core.aia_config": "solar_toolkit.aia.config",
        "scripts.aia_hmi.core.aia_io": "solar_toolkit.aia.io",
        "scripts.aia_hmi.core.aia_difference": "solar_toolkit.aia.difference",
        "scripts.aia_hmi.core.aia_mosaic": "solar_toolkit.aia.mosaic",
        "scripts.aia_hmi.core.aia_processor": "solar_toolkit.aia.processor",
        "scripts.aia_hmi.core.aia_cli": "solar_toolkit.aia.cli",
    }

    for old_name, new_name in pairs.items():
        old_module = importlib.import_module(old_name)
        new_module = importlib.import_module(new_name)
        assert old_module is new_module


def test_radio_gaussian_split_facades_export_existing_api():
    """Gaussian helper facades document the planned functional split."""
    from solar_toolkit.radio import (
        gaussian_background,
        gaussian_diagnostics,
        gaussian_fit,
        gaussian_io,
        gaussian_masks,
        gaussian_models,
    )

    assert gaussian_models.elliptical_gaussian_2d is not None
    assert gaussian_background.estimate_background_noise is not None
    assert gaussian_masks.create_source_mask is not None
    assert gaussian_fit.fit_elliptical_gaussian_on_radio_image is not None
    assert gaussian_diagnostics._gaussian_quality_config is not None
    assert gaussian_io.save_gaussian_diagnostics_row is not None
