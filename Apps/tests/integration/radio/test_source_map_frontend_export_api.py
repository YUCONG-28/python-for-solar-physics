from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from solar_apps.workflows.radio.artifacts import save_figure_artifact
from solar_apps.frontends.radio.source_map.server import create_app

matplotlib.use("Agg")


def _artifact(
    tmp_path: Path, name: str = "source.png", *, value_offset: float = 0.0
) -> tuple[Path, Path]:
    figure, axis = plt.subplots(figsize=(4, 3))
    values = np.arange(64).reshape(8, 8) + value_offset
    if value_offset:
        values[0, 0] = values.max() * 10
    axis.imshow(
        values,
        extent=[-40, 40, -30, 30],
        origin="lower",
    )
    image, sidecar = save_figure_artifact(
        figure,
        tmp_path / name,
        dpi=80,
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
    plt.close(figure)
    assert sidecar is not None
    return image, sidecar


def _open(client, image: Path, sidecar: Path) -> dict:
    response = client.post(
        "/api/artifacts/open",
        json={"image_path": str(image), "sidecar_path": str(sidecar)},
    )
    assert response.status_code == 200, response.get_json()
    return response.get_json()["artifact"]


def test_single_image_export_job_and_conflict_are_reported_synchronously(
    tmp_path: Path,
) -> None:
    image, sidecar = _artifact(tmp_path)
    app = create_app([tmp_path], stop_on_client_close=False)
    client = app.test_client()
    artifact = _open(client, image, sidecar)
    destination = tmp_path / "saved.png"
    payload = {
        "source_type": "artifact",
        "artifact_id": artifact["id"],
        "scope": "current",
        "current_frame": 1,
        "export_kind": "image",
        "content": "original",
        "destination": str(destination),
        "overwrite": False,
    }
    response = client.post("/api/export-jobs", json=payload)
    assert response.status_code == 202, response.get_json()
    job_id = response.get_json()["job"]["id"]
    finished = app.extensions["source_map_export_jobs"].wait(job_id, timeout=20)
    assert finished["status"] == "completed", finished
    assert destination.is_file()
    assert destination.with_suffix(".source-map.json").is_file()
    assert destination.with_name("saved.source-map-export.json").is_file()

    conflict = client.post("/api/export-jobs", json=payload)
    assert conflict.status_code == 409
    assert conflict.get_json()["code"] == "target_exists"


def test_explicit_roi_template_open_allows_cross_image_sha(tmp_path: Path) -> None:
    first, first_sidecar = _artifact(tmp_path, "first.png")
    second, second_sidecar = _artifact(tmp_path, "second.png", value_offset=10)
    first_metadata = json.loads(first_sidecar.read_text(encoding="utf-8"))
    roi_path = tmp_path / "historical.roi-set.json"
    roi_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "coordinate_system": "HPLN/HPLT arcsec",
                "image_sha256": first_metadata["image"]["sha256"],
                "rois": [
                    {
                        "id": "roi-1",
                        "name": "Burst",
                        "type": "rectangle",
                        "geometry": {
                            "left": -10,
                            "right": 10,
                            "bottom": -5,
                            "top": 5,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    app = create_app([tmp_path], stop_on_client_close=False)
    client = app.test_client()
    strict = client.post(
        "/api/artifacts/open",
        json={
            "image_path": str(second),
            "sidecar_path": str(second_sidecar),
            "roi_set_path": str(roi_path),
        },
    )
    assert strict.status_code == 400
    template = client.post(
        "/api/artifacts/open",
        json={
            "image_path": str(second),
            "sidecar_path": str(second_sidecar),
            "roi_set_path": str(roi_path),
            "roi_template_mode": True,
        },
    )
    assert template.status_code == 200, template.get_json()
    provenance = template.get_json()["artifact"]["roi_set"]["provenance"]
    assert provenance["template_mode"] is True
    assert (
        provenance["template_source_image_sha256"] == first_metadata["image"]["sha256"]
    )


def test_external_directory_requires_valid_source_map_sidecars(tmp_path: Path) -> None:
    source = tmp_path / "external"
    source.mkdir()
    (source / "orphan.png").write_bytes(b"not-a-png")
    app = create_app([tmp_path], stop_on_client_close=False)
    response = app.test_client().post(
        "/api/export-jobs",
        json={
            "source_type": "directory",
            "source_directory": str(source),
            "scope": "range",
            "start_frame": 1,
            "export_kind": "image_sequence",
            "content": "original",
            "destination": str(tmp_path),
        },
    )
    assert response.status_code == 400
    assert "sidecar" in response.get_json()["error"].lower()
