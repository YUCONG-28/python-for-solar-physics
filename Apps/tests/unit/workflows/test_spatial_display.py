from __future__ import annotations

import numpy as np
import pytest

from solar_apps.workflows.radio.spatial_display import (
    SOURCE_MAP_DISPLAY_DEFAULT,
    SpatialRadioDisplay,
    spatial_display_for_reference,
)


def test_precedence_is_constraints_ui_event_saved_defaults() -> None:
    resolved = SpatialRadioDisplay.resolve(
        source_map_defaults={"cmap": "hot", "bad_color": "navy"},
        saved={"cmap": "plasma", "percentiles": [10, 90]},
        event={"cmap": "inferno", "range_scope": "global"},
        ui_cli={"cmap": "viridis", "transform": "linear"},
        scientific_constraints={"transform": "log10"},
    )

    assert resolved.cmap == "viridis"
    assert resolved.transform == "log10"
    assert resolved.range_scope == "global"
    assert resolved.percentiles == (10.0, 90.0)


def test_synthetic_array_transform_range_and_colormap_need_no_fits() -> None:
    raw = np.array([[-1.0, 0.0, 1.0], [10.0, 100.0, np.nan]])
    display = SpatialRadioDisplay(
        cmap="viridis",
        bad_color="#123456",
        transform="log10",
        range_mode="fixed",
        vmin=1.0,
        vmax=100.0,
    )

    transformed = display.transformed(raw)
    assert np.isnan(transformed[0, 0])
    assert np.isnan(transformed[0, 1])
    np.testing.assert_allclose(transformed[0, 2], 0.0)
    np.testing.assert_allclose(transformed[1, :2], [1.0, 2.0])
    assert display.display_limits(raw) == (0.0, 2.0)
    assert display.matplotlib_cmap().name == "viridis"
    np.testing.assert_array_equal(raw[:1, :2], [[-1.0, 0.0]])


def test_legacy_source_map_keys_roundtrip_without_theme() -> None:
    display = SpatialRadioDisplay.from_mapping(
        {
            "radio_cmap": "magma",
            "background_bad_color": "black",
            "color_range_mode": "fixed",
            "fixed_vmin": 2.0,
            "fixed_vmax": 20.0,
            "radio_colorbar_unit": "K",
            "use_custom_lim": True,
            "custom_xlim": [-200, 300],
            "custom_ylim": [-100, 400],
            "ui_theme": "dark",
        }
    )

    assert display.cmap == "magma"
    assert display.bad_color == "black"
    assert display.unit == "K"
    assert display.fov == (-200.0, 300.0, -100.0, 400.0)
    assert "theme" not in display.sidecar_payload()
    assert "ui_theme" not in display.cache_payload()


def test_ui_theme_does_not_change_cache_signature() -> None:
    light = SpatialRadioDisplay.from_mapping(
        {**SOURCE_MAP_DISPLAY_DEFAULT.to_dict(), "ui_theme": "light"}
    )
    dark = SpatialRadioDisplay.from_mapping(
        {**SOURCE_MAP_DISPLAY_DEFAULT.to_dict(), "ui_theme": "dark"}
    )
    changed = SpatialRadioDisplay.from_mapping(
        {**SOURCE_MAP_DISPLAY_DEFAULT.to_dict(), "cmap": "plasma"}
    )

    assert light.cache_signature() == dark.cache_signature()
    assert light.cache_signature() != changed.cache_signature()


def test_roi_reference_config_maps_to_shared_contract() -> None:
    display = spatial_display_for_reference(
        {
            "colormap": "Hot",
            "transform": "Log10 positive",
            "range_mode": "Manual min/max",
            "range_scope": "Per frequency",
            "limits_by_frequency": {"149": [1.25, 2.75]},
            "bad_color": "#000080",
            "use_custom_fov": True,
            "x_min_arcsec": -200,
            "x_max_arcsec": 300,
            "y_min_arcsec": -100,
            "y_max_arcsec": 400,
        }
    )

    assert display.transform == "log10"
    assert display.range_mode == "fixed"
    assert display.range_scope == "per_band"
    assert display.band_limits == (("149", 1.25, 2.75),)
    assert display.display_limits(np.array([1, 10]), band=149) == (1.25, 2.75)
    assert display.fov == (-200.0, 300.0, -100.0, 400.0)
    assert display.render_profile == "preview"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"percentiles": (90, 90)},
        {"range_mode": "fixed", "vmin": None, "vmax": 2},
        {"transform": "log10", "range_mode": "fixed", "vmin": 1, "vmax": 0},
        {"fov": (1, 1, -1, 1)},
    ],
)
def test_invalid_display_contract_fails_closed(kwargs) -> None:
    with pytest.raises(ValueError):
        SpatialRadioDisplay(**kwargs)
