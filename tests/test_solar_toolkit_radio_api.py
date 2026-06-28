from __future__ import annotations


def test_solar_toolkit_radio_public_modules_match_compatibility_imports():
    from scripts.radio.core import (
        radio_coordinates,
        radio_gaussian_fit,
        radio_io,
        radio_newkirk_extrapolation,
        radio_quicklook,
    )
    from solar_toolkit import radio
    from solar_toolkit.radio import coordinates, gaussian, io, newkirk, quicklook

    assert set(radio.__all__) >= {
        "coordinates",
        "gaussian",
        "io",
        "newkirk",
        "quicklook",
    }
    assert coordinates.arcsec_to_rsun is radio_coordinates.arcsec_to_rsun
    assert io.truthy is radio_io.truthy
    assert (
        newkirk.newkirk_height_from_frequency_mhz
        is radio_newkirk_extrapolation.newkirk_height_from_frequency_mhz
    )
    assert (
        gaussian.fit_elliptical_gaussian_on_radio_image
        is radio_gaussian_fit.fit_elliptical_gaussian_on_radio_image
    )
    assert (
        quicklook.run_gaussian_newkirk_quicklook
        is radio_quicklook.run_gaussian_newkirk_quicklook
    )


def test_radio_entrypoints_remain_lightweight_imports():
    from scripts.radio import (
        run_radio_burst_pipeline,
        run_radio_raw_quality,
        run_radio_source_map,
    )

    assert callable(run_radio_burst_pipeline.main)
    assert callable(run_radio_raw_quality.main)
    assert callable(run_radio_source_map.main)
