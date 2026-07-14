from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from solar_toolkit.webapp.radio_workspace import (
    FIGURE_SCHEMA_VERSION,
    RadioArtifact,
    RadioFigureDraft,
    RadioRunManifest,
    RadioWorkspaceStore,
)
from solar_toolkit.webapp.radio_workspace.catalog import MODULES

TOKEN = "figure-test-token"


class _StoreRunManager:
    def __init__(self, store: RadioWorkspaceStore) -> None:
        self.store = store

    def list_runs(self, workspace_id: str):
        return self.store.list_runs(workspace_id)

    def status(self, workspace_id: str, run_id: str):
        return self.store.load_run(workspace_id, run_id)


def _png_bytes(width: int = 4, height: int = 3) -> bytes:
    target = io.BytesIO()
    Image.new("RGB", (width, height), "#4488aa").save(target, format="PNG")
    return target.getvalue()


def _animated_png_bytes() -> bytes:
    target = io.BytesIO()
    first = Image.new("RGB", (4, 3), "#4488aa")
    second = Image.new("RGB", (4, 3), "#aa8844")
    first.save(
        target,
        format="PNG",
        save_all=True,
        append_images=[second],
        duration=100,
        loop=0,
    )
    return target.getvalue()


def _animated_webp_bytes() -> bytes:
    target = io.BytesIO()
    first = Image.new("RGB", (4, 3), "#4488aa")
    second = Image.new("RGB", (4, 3), "#aa8844")
    first.save(
        target,
        format="WEBP",
        save_all=True,
        append_images=[second],
        duration=100,
        loop=0,
    )
    return target.getvalue()


def _client(tmp_path: Path):
    flask = pytest.importorskip(
        "flask",
        reason="Flask is optional; install the app extra to test HTTP routes.",
    )

    from solar_toolkit.webapp.radio_workspace import create_radio_blueprint

    store = RadioWorkspaceStore(tmp_path, allowed_roots=(tmp_path,))
    workspace = store.create_workspace(workspace_id="figure-workspace")
    app = flask.Flask(__name__)
    app.register_blueprint(
        create_radio_blueprint(
            store=store,
            run_manager=_StoreRunManager(store),
            root_update_token=TOKEN,
        )
    )
    app.testing = True
    return app.test_client(), store, workspace


def _register_preview(client, *, temporal_binding=None, metadata=None):
    preview_metadata = {
        "title": "Source map",
        "temporal_binding": temporal_binding or {"kind": "timeless"},
    }
    preview_metadata.update(metadata or {})
    response = client.post(
        "/api/radio/workspaces/figure-workspace/figures/sources/previews",
        headers={"X-Radio-Root-Token": TOKEN},
        data={
            "metadata": json.dumps(preview_metadata),
            "file": (io.BytesIO(_png_bytes()), "preview.png", "image/png"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()["source"]


def _draft(source: dict, *, background: str = "#ffffff") -> dict:
    return {
        "figure_schema_version": FIGURE_SCHEMA_VERSION,
        "workspace_id": "figure-workspace",
        "id": "active",
        "name": "Test Figure",
        "mode": "mosaic",
        "canvas": {
            "width": 4,
            "height": 3,
            "background": background,
            "export_scale": 1,
        },
        "timeline": {
            "mode": "still",
            "selected_time_iso": "2025-01-24T04:00:00Z",
            "animation_format": "mp4",
        },
        "layers": [
            {
                "id": "source-map",
                "title": "Source map",
                "source": source,
                "temporal_binding": {"kind": "timeless"},
                "frame": {"x": 0, "y": 0, "width": 4, "height": 3},
            }
        ],
    }


def test_workspace_layout_v2_defaults_and_migrates_old_layout_once(tmp_path: Path):
    store = RadioWorkspaceStore(tmp_path, allowed_roots=(tmp_path,))
    workspace = store.create_workspace(
        workspace_id="layout-workspace",
        advanced_config={"preserved": True},
    )
    always_available = [item.id for item in MODULES if item.always_available]
    module_ids = [item.id for item in MODULES]
    assert workspace.ui_layout_version == 2
    assert workspace.enabled_modules == always_available
    assert workspace.collapsed_modules == module_ids

    path = store.workspace_dir(workspace.id) / "workspace.json"
    legacy = json.loads(path.read_text(encoding="utf-8"))
    legacy.pop("ui_layout_version")
    legacy["enabled_modules"] = ["data-configuration", *always_available]
    legacy["collapsed_modules"] = []
    legacy["pinned_modules"] = ["imaging-localization"]
    path.write_text(json.dumps(legacy), encoding="utf-8")

    migrated = store.load_workspace(workspace.id)
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert migrated.ui_layout_version == 2
    assert migrated.enabled_modules == always_available
    assert migrated.collapsed_modules == module_ids
    assert migrated.pinned_modules == []
    assert migrated.advanced_config == {"preserved": True}
    assert persisted["ui_layout_version"] == 2
    assert (
        store.update_layout(workspace.id, {"ui_layout_version": 2}).ui_layout_version
        == 2
    )
    with pytest.raises(ValueError, match="ui_layout_version must be 2"):
        store.update_layout(workspace.id, {"ui_layout_version": 1})


def test_series_sources_canonically_bind_one_frame_to_each_unique_utc_sample():
    payload = {
        "figure_schema_version": 1,
        "workspace_id": "series-workspace",
        "id": "active",
        "mode": "mosaic",
        "canvas": {"width": 100, "height": 100},
        "timeline": {
            "mode": "still",
            "selected_time_iso": "2025-01-24T04:00:00Z",
        },
        "layers": [
            {
                "id": "series-layer",
                "source": {
                    "type": "series",
                    "frames": [
                        {
                            "type": "preview",
                            "preview_id": "preview-one",
                            "observed_at": "2025-01-24T12:00:00+08:00",
                            "mime_type": "image/png",
                            "metadata": {"note": "not persisted in a source"},
                        },
                        {
                            "type": "preview",
                            "preview_id": "preview-two",
                            "time_iso": "2025-01-24T04:00:05Z",
                        },
                    ],
                },
                "temporal_binding": {"kind": "series"},
            }
        ],
    }
    draft = RadioFigureDraft.from_dict(payload)
    layer = draft.layers[0]
    assert [item["frame_index"] for item in layer.source["frames"]] == [0, 1]
    assert layer.source["frames"] == [
        {
            "type": "preview",
            "preview_id": "preview-one",
            "time_iso": "2025-01-24T04:00:00Z",
            "frame_index": 0,
        },
        {
            "type": "preview",
            "preview_id": "preview-two",
            "time_iso": "2025-01-24T04:00:05Z",
            "frame_index": 1,
        },
    ]
    assert [item["time_iso"] for item in layer.temporal_binding.samples] == [
        "2025-01-24T04:00:00Z",
        "2025-01-24T04:00:05Z",
    ]
    assert [item["frame_index"] for item in layer.temporal_binding.samples] == [
        0,
        1,
    ]

    injected = json.loads(json.dumps(payload))
    injected["layers"][0]["temporal_binding"]["samples"] = [
        {
            "time_iso": "2025-01-24T04:00:00Z",
            "type": "artifact",
            "run_id": "unfingerprinted-run",
            "artifact_id": "unfingerprinted-artifact",
        },
        {
            "time_iso": "2025-01-24T04:00:05Z",
            "type": "artifact",
            "run_id": "unfingerprinted-run",
            "artifact_id": "unfingerprinted-artifact-two",
        },
    ]
    sanitized = RadioFigureDraft.from_dict(injected)
    assert sanitized.layers[0].temporal_binding.samples == [
        {"time_iso": "2025-01-24T04:00:00Z", "frame_index": 0},
        {"time_iso": "2025-01-24T04:00:05Z", "frame_index": 1},
    ]

    mismatched = json.loads(json.dumps(payload))
    mismatched["layers"][0]["temporal_binding"]["samples"] = [
        {"time_iso": "2025-01-24T04:00:00Z"}
    ]
    with pytest.raises(ValueError, match="equal length"):
        RadioFigureDraft.from_dict(mismatched)

    duplicate = json.loads(json.dumps(payload))
    duplicate["layers"][0]["source"]["frames"][1]["time_iso"] = "2025-01-24T04:00:00Z"
    with pytest.raises(ValueError, match="must be unique"):
        RadioFigureDraft.from_dict(duplicate)

    disguised = json.loads(json.dumps(payload))
    disguised["layers"][0]["source"] = {
        "type": "preview",
        "preview_id": "preview-one",
    }
    with pytest.raises(ValueError, match="requires a controlled series source"):
        RadioFigureDraft.from_dict(disguised)

    artifact_payload = json.loads(json.dumps(payload))
    artifact_payload["layers"][0]["source"] = {
        "type": "artifact",
        "run_id": "controlled-run",
        "artifact_id": "controlled-artifact",
        "mime_type": "image/png",
        "metadata": {"note": "not persisted"},
    }
    artifact_payload["layers"][0]["temporal_binding"] = {"kind": "timeless"}
    artifact_draft = RadioFigureDraft.from_dict(artifact_payload)
    assert artifact_draft.layers[0].source == {
        "type": "artifact",
        "run_id": "controlled-run",
        "artifact_id": "controlled-artifact",
    }


def test_figure_draft_preview_snapshot_preflight_and_png_export_api(tmp_path: Path):
    client, store, _workspace = _client(tmp_path)
    draft_url = "/api/radio/workspaces/figure-workspace/figures/draft"

    initial = client.get(draft_url)
    assert initial.status_code == 200
    assert initial.get_json()["draft"]["layers"] == []

    source = _register_preview(
        client,
        metadata={
            "coverage_gaps": [
                {
                    "start_time_iso": "2025-01-24T03:59:58Z",
                    "end_time_iso": "2025-01-24T03:59:59Z",
                }
            ],
            "x_axis_mapping": {
                "type": "utc-linear",
                "start_time_iso": "2025-01-24T04:00:00Z",
                "end_time_iso": "2025-01-24T04:00:10Z",
            },
        },
    )
    assert source["metadata"]["x_axis_mapping"]["type"] == "utc-linear"
    preview = client.get(
        "/api/radio/workspaces/figure-workspace/figures/sources/previews/"
        f"{source['preview_id']}"
    )
    assert preview.status_code == 200
    assert preview.mimetype == "image/png"
    assert preview.headers["X-Content-Type-Options"] == "nosniff"
    preview.close()

    draft = _draft(source)
    denied = client.put(draft_url, json=draft)
    assert denied.status_code == 403
    hostile_host = client.put(
        draft_url,
        json=draft,
        headers={"X-Radio-Root-Token": TOKEN},
        base_url="http://example.test",
    )
    assert hostile_host.status_code == 403
    remote_peer = client.put(
        draft_url,
        json=draft,
        headers={"X-Radio-Root-Token": TOKEN},
        environ_overrides={"REMOTE_ADDR": "192.0.2.10"},
    )
    assert remote_peer.status_code == 403
    saved_response = client.put(
        draft_url,
        json=draft,
        headers={"X-Radio-Root-Token": TOKEN},
    )
    assert saved_response.status_code == 200
    saved = saved_response.get_json()["draft"]
    assert saved["timeline"]["animation_format"] == "mp4"
    assert "data_url" not in json.dumps(saved)
    assert saved["layers"][0]["source"] == {
        "type": "preview",
        "preview_id": source["preview_id"],
        "fingerprint": source["fingerprint"],
    }

    snapshot = client.post(
        "/api/radio/workspaces/figure-workspace/figures/snapshots",
        json={"draft": saved, "name": "Before export"},
        headers={"X-Radio-Root-Token": TOKEN},
    )
    assert snapshot.status_code == 201
    snapshot_id = snapshot.get_json()["snapshot"]["id"]
    assert (
        store.figure_studio_dir("figure-workspace")
        / "snapshots"
        / f"{snapshot_id}.json"
    ).is_file()

    preflight_response = client.post(
        "/api/radio/workspaces/figure-workspace/figures/preflight",
        json={"draft": saved},
    )
    assert preflight_response.status_code == 200
    preflight = preflight_response.get_json()["preflight"]
    assert preflight["status"] == "ready"
    assert preflight["ready"] is True
    assert (
        preflight["source_fingerprints"]["source-map"]["references"][0]["preview_id"]
        == source["preview_id"]
    )

    exported_response = client.post(
        "/api/radio/workspaces/figure-workspace/figures/exports",
        headers={"X-Radio-Root-Token": TOKEN},
        data={
            "figure": json.dumps(saved),
            "preflight": json.dumps(preflight),
            "manifest": json.dumps({"width": 4, "height": 3, "frame_count": 1}),
            "preflight_revision": preflight["preflight_revision"],
            "file": (io.BytesIO(_png_bytes()), "figure.png", "image/png"),
        },
        content_type="multipart/form-data",
    )
    assert exported_response.status_code == 201, exported_response.get_json()
    exported = exported_response.get_json()["export"]
    export_id = exported["id"]

    listing = client.get(
        "/api/radio/workspaces/figure-workspace/figures/exports"
    ).get_json()
    assert [item["id"] for item in listing["exports"]] == [export_id]
    base = "/api/radio/workspaces/figure-workspace/figures/exports/" + export_id
    persisted_manifest = client.get(base).get_json()["manifest"]
    assert persisted_manifest["timeline"]["mode"] == "still"
    assert persisted_manifest["frame_times"] == preflight["sample_times_iso"]
    assert persisted_manifest["mime_type"] == "image/png"
    assert persisted_manifest["sha256"] == exported["sha256"]
    assert (
        persisted_manifest["layer_decisions"][0]["source"]
        == saved["layers"][0]["source"]
    )
    export_preview = client.get(base + "/preview")
    assert export_preview.mimetype == "image/png"
    export_preview.close()
    thumbnail = client.get(base + "/thumbnail")
    assert thumbnail.mimetype == "image/png"
    thumbnail.close()
    download = client.get(base + "/download")
    assert "attachment" in download.headers["Content-Disposition"]
    download.close()
    assert client.delete(base).status_code == 403
    deleted = client.delete(base, headers={"X-Radio-Root-Token": TOKEN})
    assert deleted.status_code == 200, deleted.get_json()
    assert client.get(base + "/preview").status_code == 404


def test_figure_api_rejects_stale_preflight_unsafe_sources_and_bad_png(
    tmp_path: Path,
):
    client, _store, _workspace = _client(tmp_path)
    source = _register_preview(client)
    saved = client.put(
        "/api/radio/workspaces/figure-workspace/figures/draft",
        json=_draft(source),
        headers={"X-Radio-Root-Token": TOKEN},
    ).get_json()["draft"]
    preflight = client.post(
        "/api/radio/workspaces/figure-workspace/figures/preflight",
        json={"draft": saved},
    ).get_json()["preflight"]

    changed = dict(saved)
    changed["canvas"] = {**saved["canvas"], "background": "#000000"}
    stale = client.post(
        "/api/radio/workspaces/figure-workspace/figures/exports",
        headers={"X-Radio-Root-Token": TOKEN},
        data={
            "figure": json.dumps(changed),
            "preflight": json.dumps(preflight),
            "manifest": json.dumps({"width": 4, "height": 3}),
            "preflight_revision": preflight["preflight_revision"],
            "file": (io.BytesIO(_png_bytes()), "figure.png", "image/png"),
        },
        content_type="multipart/form-data",
    )
    assert stale.status_code == 409
    assert "run preflight again" in stale.get_json()["error"]

    unsafe = _draft({"type": "preview", "preview_id": source["preview_id"]})
    unsafe["layers"][0]["source"]["data_url"] = "data:image/png;base64,..."
    rejected = client.put(
        "/api/radio/workspaces/figure-workspace/figures/draft",
        json=unsafe,
        headers={"X-Radio-Root-Token": TOKEN},
    )
    assert rejected.status_code == 400
    assert "data_url" in rejected.get_json()["error"]

    bad_preview = client.post(
        "/api/radio/workspaces/figure-workspace/figures/sources/previews",
        headers={"X-Radio-Root-Token": TOKEN},
        data={
            "metadata": json.dumps({"temporal_binding": {"kind": "timeless"}}),
            "file": (io.BytesIO(b"not a png"), "preview.png", "image/png"),
        },
        content_type="multipart/form-data",
    )
    assert bad_preview.status_code == 400

    animated_preview = client.post(
        "/api/radio/workspaces/figure-workspace/figures/sources/previews",
        headers={"X-Radio-Root-Token": TOKEN},
        data={
            "metadata": json.dumps({"temporal_binding": {"kind": "timeless"}}),
            "file": (
                io.BytesIO(_animated_png_bytes()),
                "animated.png",
                "image/png",
            ),
        },
        content_type="multipart/form-data",
    )
    assert animated_preview.status_code == 400
    assert "static single-frame" in animated_preview.get_json()["error"]

    leaked_path = client.post(
        "/api/radio/workspaces/figure-workspace/figures/sources/previews",
        headers={"X-Radio-Root-Token": TOKEN},
        data={
            "metadata": json.dumps(
                {
                    "temporal_binding": {"kind": "timeless"},
                    "source_path": "D:/private/source.fits",
                    "metadata_path": "D:/private/metadata.json",
                }
            ),
            "file": (io.BytesIO(_png_bytes()), "preview.png", "image/png"),
        },
        content_type="multipart/form-data",
    )
    assert leaked_path.status_code == 400
    assert "source_path" in leaked_path.get_json()["error"]

    unsafe_path = _draft(
        {
            "type": "preview",
            "preview_id": source["preview_id"],
            "source_path": "D:/private/source.fits",
        }
    )
    rejected_path = client.put(
        "/api/radio/workspaces/figure-workspace/figures/draft",
        json=unsafe_path,
        headers={"X-Radio-Root-Token": TOKEN},
    )
    assert rejected_path.status_code == 400
    assert "source_path" in rejected_path.get_json()["error"]

    unsafe_metadata = _draft(source)
    unsafe_metadata["metadata"] = {"metadata_path": "D:/private/meta.json"}
    rejected_metadata = client.put(
        "/api/radio/workspaces/figure-workspace/figures/draft",
        json=unsafe_metadata,
        headers={"X-Radio-Root-Token": TOKEN},
    )
    assert rejected_metadata.status_code == 400
    assert "metadata_path" in rejected_metadata.get_json()["error"]

    unsafe_layer_metadata = _draft(source)
    unsafe_layer_metadata["layers"][0]["metadata"] = {
        "data_url": "data:image/png;base64,..."
    }
    rejected_layer_metadata = client.put(
        "/api/radio/workspaces/figure-workspace/figures/draft",
        json=unsafe_layer_metadata,
        headers={"X-Radio-Root-Token": TOKEN},
    )
    assert rejected_layer_metadata.status_code == 400
    assert "data_url" in rejected_layer_metadata.get_json()["error"]


def test_figure_raster_validation_rejects_animated_webp(tmp_path: Path):
    from solar_toolkit.webapp.radio_workspace.figure_media import (
        validate_raster_image,
    )

    path = tmp_path / "animated.webp"
    try:
        path.write_bytes(_animated_webp_bytes())
    except OSError:
        pytest.skip("This Pillow build cannot encode animated WebP")
    with pytest.raises(ValueError, match="static single-frame"):
        validate_raster_image(path, "image/webp")


def test_figure_multipart_limits_are_checked_before_field_use(tmp_path: Path):
    from solar_toolkit.webapp.radio_workspace.api import (
        _MAX_EXPORT_MULTIPART_BYTES,
        _MAX_FIGURE_JSON_REQUEST_BYTES,
        _MAX_PREVIEW_METADATA_JSON_BYTES,
        _MAX_PREVIEW_MULTIPART_BYTES,
        _require_bounded_multipart,
    )

    client, _store, _workspace = _client(tmp_path)
    url = "/api/radio/workspaces/figure-workspace/figures/sources/previews"
    oversized_request = client.post(
        url,
        headers={"X-Radio-Root-Token": TOKEN},
        data=b"--figure-boundary--\r\n",
        content_type="multipart/form-data; boundary=figure-boundary",
        environ_overrides={"CONTENT_LENGTH": str(_MAX_PREVIEW_MULTIPART_BYTES + 1)},
    )
    assert oversized_request.status_code == 413
    assert "request limit" in oversized_request.get_json()["error"]

    oversized_export = client.post(
        "/api/radio/workspaces/figure-workspace/figures/exports",
        headers={"X-Radio-Root-Token": TOKEN},
        data=b"--figure-boundary--\r\n",
        content_type="multipart/form-data; boundary=figure-boundary",
        environ_overrides={"CONTENT_LENGTH": str(_MAX_EXPORT_MULTIPART_BYTES + 1)},
    )
    assert oversized_export.status_code == 413
    assert "request limit" in oversized_export.get_json()["error"]

    oversized_metadata = client.post(
        url,
        headers={"X-Radio-Root-Token": TOKEN},
        data={
            "metadata": json.dumps(
                {
                    "title": "x" * _MAX_PREVIEW_METADATA_JSON_BYTES,
                    "temporal_binding": {"kind": "timeless"},
                }
            ),
            "file": (io.BytesIO(_png_bytes()), "preview.png", "image/png"),
        },
        content_type="multipart/form-data",
    )
    assert oversized_metadata.status_code == 413
    assert "metadata" in oversized_metadata.get_json()["error"]

    with pytest.raises(ValueError, match="Content-Length"):
        _require_bounded_multipart(
            SimpleNamespace(mimetype="multipart/form-data", content_length=None),
            max_bytes=100,
            label="Test upload",
        )

    draft_url = "/api/radio/workspaces/figure-workspace/figures/draft"
    oversized_json = client.put(
        draft_url,
        headers={"X-Radio-Root-Token": TOKEN},
        data=b"{}",
        content_type="application/json",
        environ_overrides={"CONTENT_LENGTH": str(_MAX_FIGURE_JSON_REQUEST_BYTES + 1)},
    )
    assert oversized_json.status_code == 413
    assert "request limit" in oversized_json.get_json()["error"]


def test_figure_preflight_is_local_bounded_and_requires_a_known_workspace(
    tmp_path: Path,
):
    client, _store, _workspace = _client(tmp_path)
    draft = RadioFigureDraft.empty("figure-workspace").to_dict()
    url = "/api/radio/workspaces/figure-workspace/figures/preflight"

    remote = client.post(
        url,
        json={"draft": draft},
        environ_overrides={"REMOTE_ADDR": "192.0.2.10"},
    )
    assert remote.status_code == 403

    missing = RadioFigureDraft.empty("missing-workspace").to_dict()
    unknown = client.post(
        "/api/radio/workspaces/missing-workspace/figures/preflight",
        json={"draft": missing},
    )
    assert unknown.status_code == 404


def test_sequence_export_derives_duration_from_samples_and_playback_fps(
    tmp_path: Path,
):
    client, _store, _workspace = _client(tmp_path)
    source = _register_preview(client)
    draft = _draft(source)
    draft["timeline"] = {
        "mode": "sequence",
        "start_time_iso": "2025-01-24T04:00:00Z",
        "end_time_iso": "2025-01-24T04:00:02Z",
        "sample_interval_s": 1,
        "playback_fps": 4,
        "animation_format": "mp4",
    }
    draft["metadata"] = {
        "timeline_decisions": [
            {
                "action": "trim_range",
                "applied_at": "2025-01-24T04:01:00Z",
            }
        ],
        "layer_decisions": [
            {
                "action": "remove_layer",
                "layer_id": "old-layer",
                "applied_at": "2025-01-24T04:01:01Z",
            }
        ],
    }
    saved = client.put(
        "/api/radio/workspaces/figure-workspace/figures/draft",
        json=draft,
        headers={"X-Radio-Root-Token": TOKEN},
    ).get_json()["draft"]
    preflight = client.post(
        "/api/radio/workspaces/figure-workspace/figures/preflight",
        json={"draft": saved},
    ).get_json()["preflight"]
    assert len(preflight["sample_times_iso"]) == 3
    fake_mp4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isommp42"
    submitted_preflight = json.loads(json.dumps(preflight))
    submitted_preflight["layers"] = [
        {"layer_id": "client-claim", "matches": [{"resolved": False}]}
    ]
    submitted_preflight["warnings"] = [{"code": "client-claim"}]
    base_form = {
        "figure": json.dumps(saved),
        "preflight": json.dumps(submitted_preflight),
        "preflight_revision": preflight["preflight_revision"],
    }
    wrong_frames = client.post(
        "/api/radio/workspaces/figure-workspace/figures/exports",
        headers={"X-Radio-Root-Token": TOKEN},
        data={
            **base_form,
            "manifest": json.dumps(
                {
                    "frame_times": ["2025-01-24T04:00:00Z"],
                    "duration_s": 99,
                }
            ),
            "file": (io.BytesIO(fake_mp4), "figure.mp4", "video/mp4"),
        },
        content_type="multipart/form-data",
    )
    assert wrong_frames.status_code == 400
    assert "frame_times" in wrong_frames.get_json()["error"]

    exported_response = client.post(
        "/api/radio/workspaces/figure-workspace/figures/exports",
        headers={"X-Radio-Root-Token": TOKEN},
        data={
            **base_form,
            "manifest": json.dumps(
                {
                    "width": 999,
                    "height": 999,
                    "frame_count": 999,
                    "duration_s": 99,
                    "frame_times": preflight["sample_times_iso"],
                    "preflight_layer_matches": [{"client_claim": True}],
                    "client_only": "must not persist",
                }
            ),
            "file": (io.BytesIO(fake_mp4), "figure.mp4", "video/mp4"),
        },
        content_type="multipart/form-data",
    )
    assert exported_response.status_code == 201, exported_response.get_json()
    exported = exported_response.get_json()["export"]
    assert exported["frame_count"] == 3
    assert exported["duration_s"] == 0.75
    detail = client.get(
        "/api/radio/workspaces/figure-workspace/figures/exports/" + exported["id"]
    ).get_json()
    manifest = detail["manifest"]
    assert manifest["width"] == 4
    assert manifest["height"] == 3
    assert manifest["frame_count"] == 3
    assert manifest["duration_s"] == 0.75
    assert manifest["frame_times"] == preflight["sample_times_iso"]
    assert "client_only" not in manifest
    assert manifest["preflight_layer_matches"] == preflight["layers"]
    assert manifest["source_fingerprints"] == preflight["source_fingerprints"]
    assert manifest["common_valid_intervals"] == preflight["common_valid_intervals"]
    assert manifest["applied_decisions"] == {
        "timeline": saved["metadata"]["timeline_decisions"],
        "layers": saved["metadata"]["layer_decisions"],
    }


def test_image_artifact_series_uses_full_filename_times_and_product_pattern(
    tmp_path: Path,
):
    client, store, workspace = _client(tmp_path)
    run_id = "series-run"
    artifacts = []
    for index, timestamp in enumerate(("20250124_040000", "20250124_040005")):
        relative_path = f"maps/rr_2990mhz_source_{timestamp}.png"
        artifacts.append(
            RadioArtifact(
                id=f"artifact-{index}",
                relative_path=relative_path,
                kind="image",
                mime_type="image/png",
                artifact_type="source-map",
                source_run_id=run_id,
                previewable=True,
            )
        )
    manifest = RadioRunManifest(
        schema_version=1,
        id=run_id,
        workspace_id=workspace.id,
        module_id="imaging-localization",
        action_id="inspect-source-map",
        status="succeeded",
        command=[],
        cwd=str(tmp_path),
        request={},
        resolved_config={"time_iso": "2025-01-24T00:00:00Z"},
        input_sources=[],
        provenance={},
        artifacts=artifacts,
        progress=1,
    )
    store.create_run(manifest)
    artifact_root = store.run_dir(workspace.id, run_id) / "artifacts"
    for artifact in artifacts:
        path = artifact_root / artifact.relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_png_bytes())

    response = client.get("/api/radio/workspaces/figure-workspace/artifacts")
    assert response.status_code == 200
    items = sorted(response.get_json()["artifacts"], key=lambda item: item["id"])
    assert [item["observed_at"] for item in items] == [
        "2025-01-24T04:00:00Z",
        "2025-01-24T04:00:05Z",
    ]
    assert items[0]["series_key"] == items[1]["series_key"]
    assert "rr_2990mhz_source_{time}.png" in items[0]["series_key"]
    run_items = client.get(
        "/api/radio/workspaces/figure-workspace/runs/series-run/artifacts"
    ).get_json()["artifacts"]
    assert {item["observed_at"] for item in run_items} == {
        "2025-01-24T04:00:00Z",
        "2025-01-24T04:00:05Z",
    }
    assert len({item["series_key"] for item in run_items}) == 1

    date_only = SimpleNamespace(relative_path="maps/summary_20250124.png")
    run_without_time = SimpleNamespace(
        id="date-only-run",
        module_id="imaging-localization",
        action_id="inspect-source-map",
        resolved_config={},
        provenance={},
        request={},
    )
    from solar_toolkit.webapp.radio_workspace.api import _artifact_time_info

    observed_at, series_key = _artifact_time_info(run_without_time, date_only)
    assert observed_at is None
    assert series_key is None


def test_figure_artifact_source_rejects_svg_and_mime_spoofing(tmp_path: Path):
    _client_instance, store, workspace = _client(tmp_path)
    artifact = RadioArtifact(
        id="vector-source",
        relative_path="source.svg",
        kind="image",
        mime_type="image/svg+xml",
        artifact_type="source-map",
        source_run_id="vector-run",
        previewable=True,
    )
    manifest = RadioRunManifest(
        schema_version=1,
        id="vector-run",
        workspace_id=workspace.id,
        module_id="imaging-localization",
        action_id="inspect-source-map",
        status="succeeded",
        command=[],
        cwd=str(tmp_path),
        request={},
        resolved_config={},
        input_sources=[],
        provenance={},
        artifacts=[artifact],
        progress=1,
    )
    store.create_run(manifest)
    path = store.run_dir(workspace.id, manifest.id) / "artifacts" / "source.svg"
    path.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
    draft = RadioFigureDraft.from_dict(
        {
            "figure_schema_version": 1,
            "workspace_id": workspace.id,
            "id": "active",
            "mode": "single",
            "canvas": {"width": 100, "height": 100},
            "timeline": {
                "mode": "still",
                "selected_time_iso": "2025-01-24T04:00:00Z",
            },
            "layers": [
                {
                    "id": "vector",
                    "source": {
                        "type": "artifact",
                        "run_id": manifest.id,
                        "artifact_id": artifact.id,
                    },
                    "temporal_binding": {"kind": "timeless"},
                }
            ],
        }
    )
    with pytest.raises(ValueError, match="PNG, JPEG, or WebP"):
        store.figure_source_fingerprints(workspace.id, draft)

    # Tamper only the persisted manifest to exercise byte-level MIME verification
    # after the allowlist check.
    run_json = store.run_dir(workspace.id, manifest.id) / "run.json"
    payload = json.loads(run_json.read_text(encoding="utf-8"))
    payload["artifacts"][0]["mime_type"] = "image/png"
    run_json.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="valid raster image"):
        store.figure_source_fingerprints(workspace.id, draft)


def test_workbench_resolution_rejects_directory_redirection_even_without_link_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    output_root = tmp_path / "output"
    output_root.mkdir()
    external = tmp_path / "external-workbench"
    external.mkdir()
    redirected = output_root / "radio_workbench"
    try:
        redirected.symlink_to(external, target_is_directory=True)
    except OSError:
        pytest.skip("Directory links are unavailable in this environment")

    monkeypatch.setattr(Path, "is_symlink", lambda _path: False)
    with pytest.raises(PermissionError, match="escaped the output root"):
        RadioWorkspaceStore(output_root)


def test_figure_and_artifact_directory_symlink_swaps_are_rejected(tmp_path: Path):
    preview_client, preview_store, _workspace = _client(tmp_path / "preview-case")
    source = _register_preview(preview_client)
    source_root = preview_store.figure_studio_dir("figure-workspace") / "sources"
    external_sources = tmp_path / "external-sources"
    source_root.rename(external_sources)
    try:
        source_root.symlink_to(external_sources, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks are unavailable in this environment")
    preview_response = preview_client.get(
        "/api/radio/workspaces/figure-workspace/figures/sources/previews/"
        f"{source['preview_id']}"
    )
    assert preview_response.status_code == 403

    export_client, export_store, _workspace = _client(tmp_path / "export-case")
    export_source = _register_preview(export_client)
    saved = export_client.put(
        "/api/radio/workspaces/figure-workspace/figures/draft",
        json=_draft(export_source),
        headers={"X-Radio-Root-Token": TOKEN},
    ).get_json()["draft"]
    preflight = export_client.post(
        "/api/radio/workspaces/figure-workspace/figures/preflight",
        json={"draft": saved},
    ).get_json()["preflight"]
    export = export_client.post(
        "/api/radio/workspaces/figure-workspace/figures/exports",
        headers={"X-Radio-Root-Token": TOKEN},
        data={
            "figure": json.dumps(saved),
            "preflight": json.dumps(preflight),
            "manifest": json.dumps({"width": 4, "height": 3, "frame_count": 1}),
            "preflight_revision": preflight["preflight_revision"],
            "file": (io.BytesIO(_png_bytes()), "figure.png", "image/png"),
        },
        content_type="multipart/form-data",
    ).get_json()["export"]
    exports_root = export_store.figure_studio_dir("figure-workspace") / "exports"
    external_exports = tmp_path / "external-exports"
    exports_root.rename(external_exports)
    exports_root.symlink_to(external_exports, target_is_directory=True)
    export_base = (
        "/api/radio/workspaces/figure-workspace/figures/exports/" + export["id"]
    )
    assert export_client.get(export_base).status_code == 403
    assert export_client.get(export_base + "/preview").status_code == 403
    assert export_client.get(export_base + "/download").status_code == 403

    artifact_client, artifact_store, artifact_workspace = _client(
        tmp_path / "artifact-case"
    )
    artifact = RadioArtifact(
        id="source-image",
        relative_path="source.png",
        kind="image",
        mime_type="image/png",
        artifact_type="source-map",
        source_run_id="artifact-run",
        previewable=True,
    )
    manifest = RadioRunManifest(
        schema_version=1,
        id="artifact-run",
        workspace_id=artifact_workspace.id,
        module_id="imaging-localization",
        action_id="inspect-source-map",
        status="succeeded",
        command=[],
        cwd=str(tmp_path),
        request={},
        resolved_config={},
        input_sources=[],
        provenance={},
        artifacts=[artifact],
        progress=1,
    )
    artifact_store.create_run(manifest)
    artifacts_root = (
        artifact_store.run_dir(artifact_workspace.id, manifest.id) / "artifacts"
    )
    (artifacts_root / artifact.relative_path).write_bytes(_png_bytes())
    external_artifacts = tmp_path / "external-artifacts"
    artifacts_root.rename(external_artifacts)
    artifacts_root.symlink_to(external_artifacts, target_is_directory=True)
    response = artifact_client.get(
        "/api/radio/workspaces/figure-workspace/runs/artifact-run/artifacts/"
        "source-image"
    )
    assert response.status_code == 403
