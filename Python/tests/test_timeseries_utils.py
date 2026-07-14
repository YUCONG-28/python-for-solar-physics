from __future__ import annotations

import numpy as np
import pandas as pd


def test_normalize_time_column_and_crop_range():
    from solar_toolkit.timeseries import crop_time_range, normalize_time_column

    frame = pd.DataFrame(
        {
            "time_tag": ["2025-01-24T04:48:00Z", "2025-01-24T04:49:00Z"],
            "flux": [1.0, 3.0],
        }
    )
    normalized = normalize_time_column(frame, source_column="time_tag")
    cropped = crop_time_range(
        normalized, "2025-01-24T04:48:30Z", "2025-01-24T04:49:30Z"
    )

    assert "obs_time" in normalized.columns
    assert cropped["flux"].tolist() == [3.0]


def test_smooth_and_derivative_series_are_shape_stable():
    from solar_toolkit.timeseries import derivative_series, smooth_series

    values = pd.Series([0.0, 2.0, 4.0, 6.0, 8.0])

    assert np.allclose(
        smooth_series(values, window_length=3), [2 / 3, 2.0, 4.0, 6.0, 14 / 3]
    )
    assert np.allclose(
        derivative_series(values, spacing_seconds=2.0), [1.0, 1.0, 1.0, 1.0, 1.0]
    )
