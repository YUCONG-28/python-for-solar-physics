"""SunPy map operations shared by AIA and HMI workflows.

The functions import SunPy lazily so importing this module remains lightweight.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sunpy.map


def create_aia_submap(
    aia_map: sunpy.map.GenericMap,
    roi_bounds: tuple[float, float, float, float],
) -> sunpy.map.GenericMap:
    """Create an AIA submap using the historical ROI interpretation.

    ``roi_bounds`` retains the compatibility order ``(xmin, xmax, ymin, ymax)``.
    """

    import astropy.units as u
    from astropy.coordinates import SkyCoord
    from sunpy.coordinates import propagate_with_solar_surface

    tx1, tx2, ty1, _ty2 = roi_bounds
    roi_bl_tx, roi_bl_ty = tx1 * u.arcsec, ty1 * u.arcsec
    roi_tr_tx = tx2 * u.arcsec

    with propagate_with_solar_surface():
        frame = aia_map.coordinate_frame
        bottom_left = SkyCoord(Tx=roi_bl_tx, Ty=roi_bl_ty, frame=frame)
        top_right = SkyCoord(Tx=roi_tr_tx, Ty=roi_bl_ty, frame=frame)
        return aia_map.submap(bottom_left, top_right=top_right)


def normalize_aia_exposure(aia_map: sunpy.map.GenericMap) -> sunpy.map.GenericMap:
    """Normalize an AIA map by its exposure time when valid."""

    import sunpy.map

    exposure_time = aia_map.exposure_time
    if exposure_time is not None and exposure_time.value > 0:
        normalized_data = aia_map.data / exposure_time.value
        return sunpy.map.Map(normalized_data, aia_map.meta)
    warnings.warn(
        f"Invalid exposure time {exposure_time}; returning the original AIA map",
        stacklevel=2,
    )
    return aia_map


def align_maps_to_reference(
    source_map: sunpy.map.GenericMap,
    target_wcs,
) -> sunpy.map.GenericMap:
    """Reproject ``source_map`` to ``target_wcs`` with solar-surface propagation."""

    from sunpy.coordinates import propagate_with_solar_surface

    with propagate_with_solar_surface():
        return source_map.reproject_to(target_wcs)


__all__ = ["align_maps_to_reference", "create_aia_submap", "normalize_aia_exposure"]
