"""FITS input helpers.

English: Read a data array and copied header from a selected FITS HDU.

中文：从指定 FITS HDU 读取数据数组及其独立的 header 副本。
"""

from __future__ import annotations

from pathlib import Path


def read_fits_data_header(path: str | Path, *, hdu_index: int = 0):
    """Read FITS data and header from one HDU."""

    from astropy.io import fits

    with fits.open(path) as hdul:
        hdu = hdul[hdu_index]
        return hdu.data, hdu.header.copy()


__all__ = ["read_fits_data_header"]
