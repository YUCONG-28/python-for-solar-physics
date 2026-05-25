from __future__ import annotations


def test_refactored_radio_modules_import_public_api():
    from scripts.radio import radio_drift_rate, radio_gaussian_fit, radio_spectrogram

    assert radio_gaussian_fit.GaussianFitResult is not None
    assert callable(radio_gaussian_fit.fit_elliptical_gaussian_on_radio_image)
    assert radio_spectrogram.SpectrogramCache is not None
    assert callable(radio_spectrogram.build_spectrogram_cache)
    assert radio_drift_rate.DriftRateResult is not None
    assert callable(radio_drift_rate.calculate_drift_rate_from_line)
