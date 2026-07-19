from __future__ import annotations

from pathlib import Path

import pandas as pd

from solar_toolkit.visualization.radio_source_overlay import (
    render_radio_source_overlay_png,
)


def test_static_radio_source_overlay_renders_without_application_imports(
    tmp_path: Path,
) -> None:
    centers = pd.DataFrame(
        {
            "obs_time": ["2025-01-01T00:00:00", "2025-01-01T00:00:01"],
            "freq_mhz": [150.0, 150.0],
            "polarization": ["R", "R"],
            "center_method": ["gaussian", "gaussian"],
            "center_x_arcsec": [10.0, 12.0],
            "center_y_arcsec": [-4.0, -2.0],
        }
    )

    output = render_radio_source_overlay_png(
        centers,
        tmp_path / "overlay.png",
        frame_time="2025-01-01T00:00:01",
        width=400,
        height=300,
        theme_mode="dark",
    )

    assert output.is_file()
    assert output.stat().st_size > 0
