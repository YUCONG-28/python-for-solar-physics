"""Tests for pure radio FITS coordinate display helpers."""

from __future__ import annotations

import pytest

from solar_toolkit.map.coordinates import (
    calculate_fits_extent_from_header,
    infer_image_origin_from_header,
    normalize_radio_extent,
    validate_extent_orientation,
)


def _header(cdelt1: float, cdelt2: float, **overrides):
    header = {
        "NAXIS1": 4,
        "NAXIS2": 3,
        "CRPIX1": 1.0,
        "CRPIX2": 1.0,
        "CRVAL1": 0.0,
        "CRVAL2": 0.0,
        "CDELT1": cdelt1,
        "CDELT2": cdelt2,
    }
    header.update(overrides)
    return header


@pytest.mark.parametrize(
    ("cdelt1", "cdelt2", "expected"),
    [
        (2.0, 3.0, (-1.0, 7.0, -1.5, 7.5)),
        (2.0, -3.0, (-1.0, 7.0, 1.5, -7.5)),
        (-2.0, 3.0, (1.0, -7.0, -1.5, 7.5)),
        (-2.0, -3.0, (1.0, -7.0, 1.5, -7.5)),
    ],
)
def test_preserved_extent_keeps_cdelt_signs(cdelt1, cdelt2, expected):
    extent = calculate_fits_extent_from_header(_header(cdelt1, cdelt2))

    assert extent == pytest.approx(expected)


@pytest.mark.parametrize(
    ("cdelt1", "cdelt2"),
    [
        (2.0, 3.0),
        (2.0, -3.0),
        (-2.0, 3.0),
        (-2.0, -3.0),
    ],
)
def test_normalized_extent_sorts_axes(cdelt1, cdelt2):
    extent = calculate_fits_extent_from_header(
        _header(cdelt1, cdelt2), preserve_orientation=False
    )

    left, right, bottom, top = extent
    assert left < right
    assert bottom < top
    assert validate_extent_orientation(extent)["is_normalized"]


def test_non_center_crpix_extent():
    header = _header(
        0.5,
        -2.0,
        NAXIS1=5,
        NAXIS2=7,
        CRPIX1=3.0,
        CRPIX2=4.0,
        CRVAL1=10.0,
        CRVAL2=-20.0,
    )

    extent = calculate_fits_extent_from_header(header)

    assert extent == pytest.approx((8.75, 11.25, -13.0, -27.0))


def test_image_shape_overrides_naxis_for_rectangular_data():
    header = _header(1.5, 2.5, NAXIS1=99, NAXIS2=99)

    extent = calculate_fits_extent_from_header(header, image_shape=(2, 6))

    assert extent == pytest.approx((-0.75, 8.25, -1.25, 3.75))


def test_origin_auto_rule_is_explicit():
    header = _header(1.0, -1.0)

    assert infer_image_origin_from_header(header, preserve_orientation=True) == "lower"
    assert infer_image_origin_from_header(header, preserve_orientation=False) == "upper"
    assert infer_image_origin_from_header(header, mode="upper") == "upper"
    assert infer_image_origin_from_header(header, mode="lower") == "lower"


def test_origin_rejects_unknown_mode():
    with pytest.raises(ValueError):
        infer_image_origin_from_header(_header(1.0, 1.0), mode="sideways")


def test_normalize_radio_extent_and_orientation_flags():
    extent = (7.0, -1.0, 1.5, -7.5)

    assert validate_extent_orientation(extent) == {
        "x_increases": False,
        "y_increases": False,
        "x_inverted": True,
        "y_inverted": True,
        "is_normalized": False,
    }
    assert normalize_radio_extent(extent) == pytest.approx((-1.0, 7.0, -7.5, 1.5))


def test_missing_header_keyword_is_clear():
    header = _header(1.0, 1.0)
    del header["CRPIX1"]

    with pytest.raises(KeyError, match="CRPIX1"):
        calculate_fits_extent_from_header(header)
