"""ASO-S/HXI light-curve loading.

English: Read the four historical HXI quick-look energy channels and crop them
to an inclusive UTC interval.

中文：读取历史 HXI 快视产品的四个能段，并按 UTC 闭区间裁剪。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

DEFAULT_HXI_EPOCH = datetime(2018, 12, 31, 16, 0, 0)
HXI_ENERGY_CHANNELS = (
    "10-20 keV",
    "20-50 keV",
    "50-100 keV",
    "100-300 keV",
)


def load_hxi_lightcurve(
    file_path: str | Path,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    *,
    epoch: datetime = DEFAULT_HXI_EPOCH,
) -> dict:
    """Load four HXI count-rate channels from a quick-look FITS file."""

    from astropy.io import fits

    with fits.open(file_path) as hdul:
        offsets = np.asarray(hdul[1].data.TIME, dtype=float)
        counts = np.asarray(hdul[3].data["CTS_THINTHICK"])

    times = [epoch + timedelta(seconds=float(offset)) for offset in offsets]
    mask = np.ones(len(times), dtype=bool)
    if start_time is not None:
        mask &= np.asarray([time >= start_time for time in times])
    if end_time is not None:
        mask &= np.asarray([time <= end_time for time in times])

    filtered_times = [time for time, keep in zip(times, mask, strict=True) if keep]
    data = {
        label: np.asarray(counts[:, index])[mask]
        for index, label in enumerate(HXI_ENERGY_CHANNELS)
    }
    return {"times": filtered_times, "data": data}


__all__ = [
    "DEFAULT_HXI_EPOCH",
    "HXI_ENERGY_CHANNELS",
    "load_hxi_lightcurve",
]
