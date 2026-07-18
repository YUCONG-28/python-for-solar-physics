from __future__ import annotations

import io
import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from solar_apps.workflows.radio.artifacts import (
    save_figure_artifact,
    sha256_file,
)
from solar_apps.frontends.radio.source_map.server import create_app

matplotlib.use("Agg")


def _artifact(tmp_path: Path) -> tuple[Path, Path]:
    fig, axis = plt.subplots(figsize=(4, 3))
    image = axis.imshow(
        np.arange(64).reshape(8, 8), extent=[-40, 40, -30, 30], origin="lower"
    )
    cbar = fig.colorbar(image, ax=axis)
    cbar.set_label("Intensity [K]")
    path = tmp_path / "source.png"
    _, sidecar = save_figure_artifact(
        fig,
        path,
        dpi=100,
        radio_axes=[axis],
        panel_metadata=[
            {
                "id": "radio-1",
                "frequency_mhz": 149.0,
                "polarization": "RR",
                "transform": "linear",
                "colorbar_label": "Intensity [K]",
                "unit": {"unit": "K", "source": "fits_bunit", "warnings": []},
            }
        ],
        mode="single_band",
        polarization="RR",
        source_files=["frame.fits"],
        write_sidecar=True,
    )
    plt.close(fig)
    assert sidecar is not None
    return path, sidecar


def test_open_and_export_preserve_original_image(tmp_path: Path) -> None:
    image_path, sidecar_path = _artifact(tmp_path)
    original_hash = sha256_file(image_path)
    app = create_app([tmp_path], stop_on_client_close=False)
    client = app.test_client()
    opened = client.post(
        "/api/artifacts/open",
        json={"image_path": str(image_path), "sidecar_path": str(sidecar_path)},
    )
    assert opened.status_code == 200
    artifact = opened.get_json()["artifact"]
    assert artifact["metadata"]["panels"][0]["colorbar_label"] == "Intensity [K]"

    roi_set = {
        "schema_version": 1,
        "coordinate_system": "HPLN/HPLT arcsec",
        "image_sha256": original_hash,
        "rois": [
            {
                "id": "roi-1",
                "name": "Burst",
                "type": "rectangle",
                "geometry": {"left": -10, "right": 10, "bottom": -5, "top": 5},
                "visible": True,
                "style": {"color": "#00d4ff", "line_width": 3, "show_label": True},
            }
        ],
    }
    response = client.post(
        "/api/exports/save",
        data={
            "artifact_id": artifact["id"],
            "output_dir": str(tmp_path),
            "roi_set": json.dumps(roi_set),
            "annotated_image": (io.BytesIO(image_path.read_bytes()), "annotated.png"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200, response.get_json()
    exported = response.get_json()
    exported_name = Path(exported["annotated_image_path"]).name
    assert exported_name == exported["suggested_filename"]
    assert exported_name.startswith("0001_")
    assert "_generated_radio_source_map_annotated.png" in exported_name
    assert Path(exported["roi_set_path"]).name == exported_name.replace(
        ".png", ".roi-set.json"
    )
    assert sha256_file(image_path) == original_hash


def test_open_rejects_sidecar_from_another_image(tmp_path: Path) -> None:
    image_path, sidecar_path = _artifact(tmp_path)
    other = tmp_path / "other.png"
    other.write_bytes(image_path.read_bytes())
    app = create_app([tmp_path], stop_on_client_close=False)
    response = app.test_client().post(
        "/api/artifacts/open",
        json={"image_path": str(other), "sidecar_path": str(sidecar_path)},
    )
    assert response.status_code == 400
    assert "filename" in response.get_json()["error"]


def test_file_browser_rejects_path_outside_allowed_root(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    app = create_app([allowed], stop_on_client_close=False)
    response = app.test_client().post("/api/files/list", json={"path": str(outside)})
    assert response.status_code == 403
