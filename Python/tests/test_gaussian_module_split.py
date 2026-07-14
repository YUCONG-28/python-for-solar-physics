"""Regression tests for the staged Radio Gaussian module split."""

from __future__ import annotations

import ast
import importlib
import inspect

import numpy as np

from solar_toolkit.modeling import gaussian as shared_gaussian
from solar_toolkit.radio import gaussian as gaussian_facade
from solar_toolkit.radio import (
    gaussian_background,
    gaussian_masks,
    gaussian_models,
)


def test_shared_gaussian_preserves_radio_operation_order_at_tight_tolerance():
    x, y = np.meshgrid(np.linspace(-3.0, 3.0, 17), np.linspace(-2.0, 2.0, 13))
    params = (7.25, 0.37, -0.19, 1.13, 0.74, 0.31)
    amplitude, x0, y0, sigma_x, sigma_y, theta = params

    cos_t = np.cos(theta)
    sin_t = np.sin(theta)
    x_shift = x - x0
    y_shift = y - y0
    x_rot = cos_t * x_shift + sin_t * y_shift
    y_rot = -sin_t * x_shift + cos_t * y_shift
    exponent = -0.5 * ((x_rot / sigma_x) ** 2 + (y_rot / sigma_y) ** 2)
    expected = amplitude * np.exp(exponent)

    actual = shared_gaussian.elliptical_gaussian_2d((x, y), *params)

    np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=0.0)
    assert gaussian_facade.elliptical_gaussian_2d is (
        shared_gaussian.elliptical_gaussian_2d
    )


def test_model_background_and_mask_helpers_have_canonical_module_identities():
    assert gaussian_facade.elliptical_gaussian_2d_with_constant_bg is (
        gaussian_models.elliptical_gaussian_2d_with_constant_bg
    )
    assert gaussian_facade.elliptical_gaussian_2d_with_plane_bg is (
        gaussian_models.elliptical_gaussian_2d_with_plane_bg
    )
    assert gaussian_facade.gaussian_only_from_popt is (
        gaussian_models.gaussian_only_from_popt
    )
    assert gaussian_facade.estimate_background_noise is (
        gaussian_background.estimate_background_noise
    )
    assert gaussian_facade._safe_rms_map is gaussian_background._safe_rms_map
    assert gaussian_facade._select_peak_connected_mask is (
        gaussian_masks._select_peak_connected_mask
    )
    assert gaussian_facade.create_source_mask is gaussian_masks.create_source_mask


def test_extracted_models_and_background_keep_legacy_numeric_behavior():
    x, y = np.meshgrid(np.array([-1.0, 0.5]), np.array([-2.0, 1.0]))
    params = (4.0, 0.2, -0.3, 1.1, 0.8, 0.15)
    gaussian_only = shared_gaussian.elliptical_gaussian_2d((x, y), *params)

    constant = gaussian_models.elliptical_gaussian_2d_with_constant_bg(
        (x, y), *params, 2.5
    )
    plane = gaussian_models.elliptical_gaussian_2d_with_plane_bg(
        (x, y), *params, 2.5, 0.2, -0.4
    )

    np.testing.assert_allclose(constant, gaussian_only + 2.5, rtol=1e-12, atol=0.0)
    np.testing.assert_allclose(
        plane,
        gaussian_only + 2.5 + 0.2 * x - 0.4 * y,
        rtol=1e-12,
        atol=0.0,
    )
    np.testing.assert_allclose(
        gaussian_models.gaussian_only_from_popt((x, y), (*params, 9.0), "constant"),
        gaussian_only,
        rtol=1e-12,
        atol=0.0,
    )

    background, noise = gaussian_background.estimate_background_noise(
        np.array([1.0, 2.0, 100.0, np.nan]),
        source_exclusion_mask=np.array([False, False, True, False]),
    )
    assert background == 1.5
    assert noise == 1.4826 * 0.5
    np.testing.assert_array_equal(
        gaussian_background._safe_rms_map(np.array([np.nan, 0.0, -1.0, 2.0, 4.0])),
        np.array([3.0, 3.0, 3.0, 2.0, 4.0]),
    )


def test_peak_connected_mask_keeps_component_containing_requested_peak():
    core = np.zeros((5, 5), dtype=bool)
    core[1, 1] = True
    core[3, 3] = True

    selected = gaussian_masks._select_peak_connected_mask(
        core,
        core,
        peak_y=3,
        peak_x=3,
        work=core.astype(float),
    )

    expected = np.zeros_like(core)
    expected[3, 3] = True
    np.testing.assert_array_equal(selected, expected)


def test_split_modules_do_not_import_the_compatibility_facade():
    for module in (gaussian_models, gaussian_background, gaussian_masks):
        tree = ast.parse(inspect.getsource(module))
        reverse_imports = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.level == 1
            and node.module == "gaussian"
        ]
        assert reverse_imports == []


def test_historical_radio_gaussian_module_is_a_real_alias(monkeypatch):
    historical = importlib.import_module("scripts.radio.core.radio_gaussian_fit")
    assert historical is gaussian_facade

    replacement = lambda *_args, **_kwargs: (123.0, 4.0)  # noqa: E731
    monkeypatch.setattr(historical, "estimate_background_noise", replacement)
    assert gaussian_facade.estimate_background_noise is replacement
