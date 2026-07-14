from __future__ import annotations

import ast
import inspect

import numpy as np

from solar_toolkit.modeling import gaussian as gaussian_model
from solar_toolkit.radio import (
    coordinates,
    gaussian,
    gaussian_background,
    gaussian_masks,
)
from solar_toolkit.radio import (
    overlay_workflow as overlay,
)


def test_overlay_pure_adapters_match_canonical_arrays_and_coordinates():
    assert overlay.GaussianFitResult is gaussian.GaussianFitResult

    x, y = np.meshgrid(np.linspace(-3.0, 3.0, 11), np.linspace(-2.0, 2.0, 9))
    params = (7.0, 0.4, -0.3, 1.2, 0.8, 0.25)
    amplitude, x0, y0, sigma_x, sigma_y, theta = params
    cos_t = np.cos(theta)
    sin_t = np.sin(theta)
    legacy_x_rot = (x - x0) * cos_t + (y - y0) * sin_t
    legacy_y_rot = -(x - x0) * sin_t + (y - y0) * cos_t
    legacy_exponent = (legacy_x_rot**2) / (2 * sigma_x**2) + (legacy_y_rot**2) / (
        2 * sigma_y**2
    )
    legacy_values = amplitude * np.exp(-legacy_exponent)
    actual_values = overlay.elliptical_gaussian_2d((x, y), *params)
    np.testing.assert_allclose(
        actual_values,
        gaussian_model.elliptical_gaussian_2d((x, y), *params),
        rtol=0.0,
        atol=0.0,
    )
    np.testing.assert_allclose(actual_values, legacy_values, rtol=1e-12, atol=0.0)

    extent = [-1200.0, 800.0, -700.0, 900.0]
    shape = (80, 100)
    for origin in ("upper", "lower"):
        expected_world = coordinates.pixel_to_data_coord(
            17.25, 31.5, extent, shape, origin
        )
        assert (
            overlay.pixel_to_data_coord(17.25, 31.5, extent, shape, origin)
            == expected_world
        )
        assert overlay.data_coord_to_pixel(
            *expected_world, extent, shape, origin
        ) == coordinates.data_coord_to_pixel(*expected_world, extent, shape, origin)
        assert overlay.coordinate_roundtrip_error_pixel(
            17.25, 31.5, extent, shape, origin
        ) == coordinates.coordinate_roundtrip_error_pixel(
            17.25, 31.5, extent, shape, origin
        )


def test_overlay_background_and_component_adapters_preserve_numeric_contract():
    data = np.array([1.0, 2.0, 100.0, np.nan])
    integer_exclusion = np.array([0, 0, 2, 0])
    assert overlay.estimate_background_noise(
        data, integer_exclusion
    ) == gaussian_background.estimate_background_noise(
        data, integer_exclusion.astype(bool)
    )

    rms = np.array([np.nan, -1.0, 0.0, 1e-15, 4.0])
    np.testing.assert_array_equal(
        overlay._safe_rms_map(rms),
        np.maximum(gaussian_background._safe_rms_map(rms), 1e-12),
    )

    core = np.zeros((7, 7), dtype=bool)
    core[1, 1] = True
    core[5, 5] = True
    work = np.zeros((7, 7), dtype=float)
    work[1, 1] = 2.0
    work[5, 5] = 4.0
    expected = gaussian_masks._select_peak_connected_mask(
        core, core, peak_y=3, peak_x=3, work=work
    )
    actual = overlay._select_peak_connected_mask(
        core, core, peak_y=3, peak_x=3, work=work
    )
    np.testing.assert_array_equal(actual, expected)


def test_overlay_shared_fit_helpers_match_canonical_results():
    cfg = {
        "gaussian_fit_maxfev": 321,
        "gaussian_quality_requirements": {"min_snr": 7.0},
    }
    assert overlay._gaussian_fit_diag_defaults(
        cfg
    ) == gaussian._gaussian_fit_diag_defaults(cfg)
    assert overlay._gaussian_quality_config(cfg) == gaussian._gaussian_quality_config(
        cfg
    )

    mask = np.zeros((8, 9), dtype=bool)
    mask[2:5, 3:7] = True
    assert overlay._roi_slices_from_mask(
        mask, mask.shape, 1
    ) == gaussian._roi_slices_from_mask(mask, mask.shape, 1)

    x = np.arange(8, dtype=float)
    y = np.arange(8, dtype=float)[::-1]
    z = np.array([1.0, 8.0, 3.0, 7.0, 2.0, 6.0, 4.0, 5.0])
    actual = overlay._limit_fit_pixels(x, y, z, 3.0, 4.0, 4)
    expected = gaussian._limit_fit_pixels(x, y, z, 3.0, 4.0, 4)
    for actual_item, expected_item in zip(actual[:3], expected[:3], strict=True):
        np.testing.assert_array_equal(actual_item, expected_item)
    assert actual[3:] == expected[3:]


def test_overlay_monkeypatch_anchors_remain_local(monkeypatch):
    calls = []

    def fake_model(xy, *_params):
        calls.append(xy)
        return np.full_like(np.asarray(xy[0], dtype=float), 3.0)

    monkeypatch.setattr(overlay, "elliptical_gaussian_2d", fake_model)
    x, y = np.meshgrid(np.arange(2, dtype=float), np.arange(2, dtype=float))
    actual = overlay.elliptical_gaussian_2d_with_constant_bg(
        (x, y), 1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 2.0
    )
    np.testing.assert_array_equal(actual, np.full((2, 2), 5.0))
    assert calls

    coordinate_calls = []

    def fake_pixel_to_data(*_args, **_kwargs):
        coordinate_calls.append("forward")
        return 12.0, 34.0

    def fake_data_to_pixel(*_args, **_kwargs):
        coordinate_calls.append("inverse")
        return 4.0, 5.0

    monkeypatch.setattr(overlay, "pixel_to_data_coord", fake_pixel_to_data)
    monkeypatch.setattr(overlay, "data_coord_to_pixel", fake_data_to_pixel)
    assert (
        overlay.coordinate_roundtrip_error_pixel(
            4.0, 5.0, [-1.0, 1.0, -1.0, 1.0], (2, 2)
        )
        == 0.0
    )
    assert coordinate_calls == ["forward", "inverse"]


def test_overlay_specific_mask_and_fit_contracts_are_not_aliased():
    """Overlay calibration cannot be replaced by the generic fitter unchanged."""

    assert overlay.create_source_mask is not gaussian_masks.create_source_mask
    assert (
        overlay.fit_elliptical_gaussian_on_radio_image
        is not gaussian.fit_elliptical_gaussian_on_radio_image
    )

    overlay_fit = inspect.signature(overlay.fit_elliptical_gaussian_on_radio_image)
    canonical_fit = inspect.signature(gaussian.fit_elliptical_gaussian_on_radio_image)
    assert "source_mask_override" not in overlay_fit.parameters
    assert "source_mask_override" in canonical_fit.parameters

    overlay_defaults = _cfg_get_defaults(overlay.create_source_mask)
    canonical_defaults = _cfg_get_defaults(gaussian_masks.create_source_mask)
    assert overlay_defaults["fit_peak_fraction_threshold"] == 0.40
    assert canonical_defaults["fit_peak_fraction_threshold"] == 0.60
    assert overlay_defaults["fit_grow_peak_fraction_threshold"] == 0.22
    assert canonical_defaults["fit_grow_peak_fraction_threshold"] == 0.25
    assert overlay_defaults["fit_min_mask_pixels"] == 12
    assert canonical_defaults["fit_min_mask_pixels"] == 20


def _cfg_get_defaults(function):
    tree = ast.parse(inspect.getsource(function))
    defaults = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or len(node.args) < 2:
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "get":
            continue
        if not isinstance(node.func.value, ast.Name) or node.func.value.id != "cfg":
            continue
        if isinstance(node.args[0], ast.Constant) and isinstance(
            node.args[1], ast.Constant
        ):
            defaults[str(node.args[0].value)] = node.args[1].value
    return defaults
