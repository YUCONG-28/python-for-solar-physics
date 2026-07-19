from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pytest

from solar_apps.workflows.radio.artifacts import (
    apply_colorbar_tick_notation,
    colorbar_label,
    data_to_image_pixel,
    image_pixel_to_data,
    resolve_colorbar_unit,
    save_figure_artifact,
    sidecar_path_for,
    validate_roi_set,
    validate_source_map_artifact,
)

matplotlib.use("Agg")


def test_colorbar_unit_precedence_and_labels() -> None:
    explicit = resolve_colorbar_unit([{"BUNIT": "Jy/beam"}], "K")
    assert explicit.unit == "K"
    assert explicit.source == "config_override"
    assert colorbar_label(explicit) == "Intensity [K]"
    assert colorbar_label(explicit, transform="log10") == "log10(I / 1 K)"
    assert (
        colorbar_label(explicit, transform="log10", tick_notation="power_of_ten")
        == "Intensity [K]"
    )

    fits_unit = resolve_colorbar_unit([{"BUNIT": "Jy/beam"}, {"BUNIT": " jy/BEAM "}])
    assert fits_unit.unit == "Jy/beam"
    assert fits_unit.source == "fits_bunit"

    fallback = resolve_colorbar_unit([{"BUNIT": "K"}, {"BUNIT": "Jy/beam"}])
    assert fallback.unit == "a.u."
    assert fallback.source == "fallback"
    assert fallback.warnings
    assert colorbar_label(fallback, transform="log10") == "log10 Intensity [a.u.]"
    assert (
        colorbar_label(fallback, transform="log10", tick_notation="power_of_ten")
        == "Intensity [a.u.]"
    )


def test_power_of_ten_ticks_preserve_log_color_limits() -> None:
    fig, axis = plt.subplots()
    image = axis.imshow(np.array([[-2.0, 0.0], [6.8, 7.5]]), vmin=-2.0, vmax=7.5)
    colorbar = fig.colorbar(image)
    colorbar.set_ticks([-2.0, 0.0, 6.8, 7.5])

    notation = apply_colorbar_tick_notation(colorbar, transform="log10")
    fig.canvas.draw()

    assert notation == "power_of_ten"
    assert [tick.get_text() for tick in colorbar.ax.get_yticklabels()] == [
        "$10^{-2}$",
        "$10^{0}$",
        "$10^{6.8}$",
        "$10^{7.5}$",
    ]
    assert (image.norm.vmin, image.norm.vmax) == (-2.0, 7.5)
    plt.close(fig)


@pytest.mark.parametrize("scale,exponent", [(1e5, "5"), (1e-7, "−7")])
def test_linear_ticks_use_mathtext_scientific_offset(
    scale: float, exponent: str
) -> None:
    fig, axis = plt.subplots()
    image = axis.imshow(
        np.array([[1.0, 2.0], [3.0, 4.0]]) * scale,
        vmin=scale,
        vmax=4.0 * scale,
    )
    colorbar = fig.colorbar(image)

    notation = apply_colorbar_tick_notation(colorbar, transform="linear")
    fig.canvas.draw()

    assert notation == "scientific_offset"
    offset = colorbar.ax.yaxis.get_offset_text().get_text()
    assert "\\times" in offset
    assert f"10^{{{exponent}}}" in offset
    assert (image.norm.vmin, image.norm.vmax) == pytest.approx((scale, 4.0 * scale))
    plt.close(fig)


@pytest.mark.parametrize(
    "invert_x,invert_y", [(False, False), (True, False), (False, True), (True, True)]
)
def test_tight_sidecar_pixel_coordinate_roundtrip(
    tmp_path: Path, invert_x: bool, invert_y: bool
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(7, 3))
    metadata = []
    for index, axis in enumerate(axes):
        axis.imshow(
            np.arange(100).reshape(10, 10), extent=[-50, 50, -40, 40], origin="lower"
        )
        axis.set_xlim((50, -50) if invert_x else (-50, 50))
        axis.set_ylim((40, -40) if invert_y else (-40, 40))
        axis.set_title(f"Panel {index + 1}")
        metadata.append(
            {
                "id": f"radio-{index + 1}",
                "frequency_mhz": 149.0 + index,
                "polarization": "RR",
                "transform": "linear",
                "tick_notation": "scientific_offset",
                "colorbar_label": "Intensity [K]",
                "unit": {"unit": "K", "source": "fits_bunit", "warnings": []},
            }
        )
    fig.tight_layout()
    image_path = tmp_path / "map.png"
    save_figure_artifact(
        fig,
        image_path,
        dpi=140,
        radio_axes=list(axes),
        panel_metadata=metadata,
        mode="multi_band",
        polarization="RR",
        source_files=["one.fits", "two.fits"],
        write_sidecar=True,
    )
    plt.close(fig)

    payload = validate_source_map_artifact(image_path)
    assert len(payload["panels"]) == 2
    for panel in payload["panels"]:
        pixel = data_to_image_pixel(payload, panel["id"], 12.5, -7.5)
        recovered = image_pixel_to_data(payload, panel["id"], *pixel)
        assert recovered == pytest.approx((12.5, -7.5), abs=1e-9)
        left, top, right, bottom = panel["bbox_normalized"]
        assert 0 <= left < right <= 1
        assert 0 <= top < bottom <= 1


def test_artifact_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    fig, axis = plt.subplots()
    axis.imshow(np.ones((3, 3)), extent=[0, 3, 0, 3])
    path = tmp_path / "map.png"
    save_figure_artifact(
        fig,
        path,
        dpi=80,
        radio_axes=[axis],
        panel_metadata=[{"id": "radio-1"}],
        mode="single_band",
        polarization="RR",
        source_files=["input.fits"],
        write_sidecar=True,
    )
    plt.close(fig)
    payload = json.loads(sidecar_path_for(path).read_text(encoding="utf-8"))
    payload["image"]["sha256"] = "0" * 64
    sidecar_path_for(path).write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        validate_source_map_artifact(path)


def test_named_roi_validation_normalizes_rectangles_and_lassos() -> None:
    payload = validate_roi_set(
        {
            "schema_version": 1,
            "coordinate_system": "HPLN/HPLT arcsec",
            "image_sha256": "abc",
            "rois": [
                {
                    "id": "box",
                    "name": "Burst",
                    "type": "rectangle",
                    "geometry": {"left": 20, "right": -10, "bottom": 5, "top": -5},
                    "visible": True,
                    "style": {"color": "#00d4ff", "line_width": 3, "show_label": True},
                },
                {
                    "id": "lasso",
                    "name": "Loop",
                    "type": "lasso",
                    "geometry": {"points": [[0, 0], [10, 0], [5, 8]]},
                },
            ],
        },
        expected_image_sha256="abc",
    )
    rectangle = payload["rois"][0]["geometry"]
    assert rectangle == {"left": -10.0, "bottom": -5.0, "right": 20.0, "top": 5.0}
    assert payload["rois"][1]["geometry"]["points"] == [
        [0.0, 0.0],
        [10.0, 0.0],
        [5.0, 8.0],
    ]

    payload["rois"][1]["name"] = "burst"
    with pytest.raises(ValueError, match="unique"):
        validate_roi_set(payload, expected_image_sha256="abc")
