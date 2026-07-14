"""Reusable numerical processing for HMI magnetograms."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import astropy.units as u
    import sunpy.map


def process_hmi_magnetic_field(
    hmi_map: sunpy.map.GenericMap,
    threshold: u.Quantity | None = None,
    sigma: float = 3,
) -> sunpy.map.GenericMap:
    """Apply a magnetic-field threshold and Gaussian smoothing to an HMI map."""

    import astropy.units as u
    import numpy as np
    import sunpy.map
    from scipy.ndimage import gaussian_filter

    if threshold is None:
        threshold = 0 * u.Gauss
    if hmi_map.unit is None:
        hmi_map.meta["bunit"] = "G"
        hmi_unit = u.Gauss
    else:
        hmi_unit = hmi_map.unit

    hmi_data = hmi_map.data * hmi_unit
    hmi_data[np.abs(hmi_data) < threshold] = 0 * u.Gauss
    smoothed_data = gaussian_filter(hmi_data.value, sigma=sigma) * hmi_data.unit
    return sunpy.map.Map(smoothed_data, hmi_map.meta)


def create_magnetic_contour_levels(
    base_level: u.Quantity | None = None,
) -> u.Quantity:
    """Return symmetric negative and positive magnetic contour levels."""

    import astropy.units as u

    if base_level is None:
        base_level = 50 * u.Gauss
    return u.Quantity([-base_level.value, base_level.value], base_level.unit)


__all__ = ["create_magnetic_contour_levels", "process_hmi_magnetic_field"]
