"""Flask API for source-map generation and Canvas ROI annotation."""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from datetime import datetime, timezone

from solar_apps.platform.paths.native_dialog import validate_allowed_path
from solar_apps.ui.flask_dialog import register_native_path_dialog
from solar_apps.ui.flask_state import register_ui_state
from solar_apps.ui.theme import register_theme_assets
from solar_apps.workflows.common.image_naming import build_scientific_image_filename

from .artifacts import sidecar_path_for, validate_roi_set
from .export_jobs import ExportJobRegistry
from .exporting import (
    ExportConflictError,
    preflight_export_destination,
    validate_roi_template,
)
from .jobs import ArtifactRegistry, JobRegistry
from .lifecycle import ClientLifecycle
from .service import (
    PathPolicy,
    discover_candidates,
    parse_request_config,
    public_candidate,
)


def create_app(
    allowed_roots: Sequence[str | Path],
    *,
    stop_on_client_close: bool = True,
    shutdown_callback: Callable[[], None] | None = None,
    native_dialog_service=None,
):
    from flask import Flask, Response, jsonify, render_template, request, send_file

    package_dir = Path(__file__).resolve().parent
    app = Flask(
        __name__,
        template_folder=str(package_dir / "templates"),
        static_folder=str(package_dir / "static"),
    )
    register_theme_assets(app)
    app.config["MAX_CONTENT_LENGTH"] = 128 * 1024 * 1024
    policy = PathPolicy(allowed_roots)
    register_ui_state(app, frontend_id="source-map", allowed_roots=policy.roots)
    register_native_path_dialog(
        app,
        allowed_roots=policy.roots,
        service=native_dialog_service,
        memory=app.extensions["ui_state"]["recent_paths"],
    )
    artifacts = ArtifactRegistry(policy)
    jobs = JobRegistry(policy=policy, artifacts=artifacts)
    export_jobs = ExportJobRegistry()
    discoveries: dict[str, dict[str, Any]] = {}
    discovery_lock = threading.Lock()
    lifecycle = ClientLifecycle(
        stop_on_client_close=stop_on_client_close,
        shutdown_callback=shutdown_callback,
    )
    app.extensions["source_map_policy"] = policy
    app.extensions["source_map_artifacts"] = artifacts
    app.extensions["source_map_jobs"] = jobs
    app.extensions["source_map_export_jobs"] = export_jobs

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/favicon.ico")
    def favicon():
        return Response(status=204)

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True, "service": "source-map-frontend"})

    @app.get("/api/config")
    def config():
        from solar_apps.workflows.radio.configs import DEFAULT_CONFIG_NAME

        return jsonify(
            {
                "ok": True,
                "default_config": DEFAULT_CONFIG_NAME,
                "allowed_roots": [str(root) for root in policy.roots],
                "modes": ["single_band", "multi_band"],
                "polarizations": ["RR", "LL", "RR+LL"],
                "colormaps": [
                    "hot",
                    "inferno",
                    "magma",
                    "viridis",
                    "plasma",
                    "jet",
                    "cividis",
                ],
            }
        )

    @app.post("/api/files/list")
    def list_files():
        try:
            payload = request.get_json(force=True, silent=True) or {}
            path = payload.get("path") or str(policy.roots[0])
            return jsonify(
                {
                    "ok": True,
                    "path": str(policy.resolve(path, must_exist=True)),
                    "items": policy.list_directory(path),
                }
            )
        except Exception as exc:
            return _error(exc)

    @app.post("/api/source-maps/discover")
    def discover():
        try:
            payload = request.get_json(force=True, silent=False) or {}
            cfg = parse_request_config(payload, policy=policy)
            candidates = discover_candidates(cfg, policy=policy)
            if not candidates:
                raise RuntimeError("No compatible source-map candidates were found")
            discovery_id = uuid.uuid4().hex
            with discovery_lock:
                _prune_discoveries(discoveries)
                discoveries[discovery_id] = {
                    "created": time.monotonic(),
                    "config": cfg,
                    "candidates": {item["id"]: item for item in candidates},
                    "candidate_order": [item["id"] for item in candidates],
                }
            return jsonify(
                {
                    "ok": True,
                    "discovery_id": discovery_id,
                    "candidates": [public_candidate(item) for item in candidates],
                }
            )
        except Exception as exc:
            return _error(exc)

    @app.post("/api/render-jobs")
    def create_job():
        try:
            payload = request.get_json(force=True, silent=False) or {}
            discovery_id = str(payload.get("discovery_id") or "")
            candidate_id = str(payload.get("candidate_id") or "")
            with discovery_lock:
                discovery = discoveries.get(discovery_id)
            if discovery is None:
                raise KeyError("Discovery expired; scan the source again")
            candidate = discovery["candidates"].get(candidate_id)
            if candidate is None:
                raise KeyError("Candidate is not part of this discovery")
            Path(discovery["config"]["output_dir"]).mkdir(parents=True, exist_ok=True)
            return jsonify(
                {"ok": True, "job": jobs.start(discovery["config"], candidate)}
            )
        except Exception as exc:
            return _error(exc)

    @app.get("/api/render-jobs/<job_id>")
    def render_job(job_id: str):
        try:
            return jsonify({"ok": True, "job": jobs.public(job_id)})
        except Exception as exc:
            return _error(exc, missing_status=404)

    @app.delete("/api/render-jobs/<job_id>")
    def cancel_job(job_id: str):
        try:
            return jsonify({"ok": True, "job": jobs.cancel(job_id)})
        except Exception as exc:
            return _error(exc, missing_status=404)

    @app.post("/api/sequence-jobs")
    def create_sequence_job():
        try:
            payload = request.get_json(force=True, silent=False) or {}
            discovery_id = str(payload.get("discovery_id") or "")
            with discovery_lock:
                discovery = discoveries.get(discovery_id)
            if discovery is None:
                raise KeyError("Discovery expired; scan the source again")
            order = list(discovery.get("candidate_order") or [])
            start_frame, end_frame = _inclusive_frame_range(
                payload.get("start_frame", payload.get("start_index")),
                payload.get("end_frame", payload.get("end_index")),
                len(order),
            )
            selected: list[dict[str, Any]] = []
            for ordinal, candidate_id in enumerate(order, start=1):
                if start_frame <= ordinal <= end_frame:
                    candidate = dict(discovery["candidates"][candidate_id])
                    candidate["sequence"] = ordinal
                    selected.append(candidate)
            Path(discovery["config"]["output_dir"]).mkdir(parents=True, exist_ok=True)
            job = jobs.start_sequence(discovery["config"], selected)
            return jsonify({"ok": True, "job": job}), 202
        except Exception as exc:
            return _error(exc)

    @app.get("/api/sequence-jobs/<job_id>")
    def sequence_job(job_id: str):
        try:
            job = jobs.public(job_id)
            if job.get("kind") != "sequence":
                raise KeyError("Sequence job not found or expired")
            return jsonify({"ok": True, "job": job})
        except Exception as exc:
            return _error(exc, missing_status=404)

    @app.delete("/api/sequence-jobs/<job_id>")
    def cancel_sequence_job(job_id: str):
        try:
            job = jobs.public(job_id)
            if job.get("kind") != "sequence":
                raise KeyError("Sequence job not found or expired")
            return jsonify({"ok": True, "job": jobs.cancel(job_id)})
        except Exception as exc:
            return _error(exc, missing_status=404)

    @app.post("/api/artifacts/open")
    def open_artifact():
        try:
            payload = request.get_json(force=True, silent=False) or {}
            image = policy.resolve(
                payload.get("image_path"), must_exist=True, kind="file"
            )
            supplied_sidecar = payload.get("sidecar_path")
            sidecar = policy.resolve(
                supplied_sidecar or sidecar_path_for(image),
                must_exist=True,
                kind="file",
            )
            record = artifacts.register(image, sidecar)
            roi_path = str(payload.get("roi_set_path") or "").strip()
            if roi_path:
                roi_payload = json.loads(
                    policy.resolve(roi_path, must_exist=True, kind="file").read_text(
                        encoding="utf-8"
                    )
                )
                template_mode = bool(payload.get("roi_template_mode", False))
                record["roi_set"] = (
                    validate_roi_template(
                        roi_payload,
                        expected_image_sha256=record["metadata"]["image"]["sha256"],
                        template_mode=True,
                    )
                    if template_mode
                    else validate_roi_set(
                        roi_payload,
                        expected_image_sha256=record["metadata"]["image"]["sha256"],
                    )
                )
            return jsonify({"ok": True, "artifact": _public_artifact(record)})
        except Exception as exc:
            return _error(exc)

    @app.get("/api/artifacts/<artifact_id>/image")
    def artifact_image(artifact_id: str):
        try:
            return send_file(
                artifacts.get(artifact_id)["image_path"],
                conditional=True,
                max_age=0,
                as_attachment=bool(request.args.get("download")),
                download_name=artifacts.get(artifact_id)["image_path"].name,
            )
        except Exception as exc:
            return _error(exc, missing_status=404)

    @app.get("/api/artifacts/<artifact_id>/metadata")
    def artifact_metadata(artifact_id: str):
        try:
            return jsonify(
                {"ok": True, "artifact": _public_artifact(artifacts.get(artifact_id))}
            )
        except Exception as exc:
            return _error(exc, missing_status=404)

    @app.post("/api/exports/save")
    def save_export():
        try:
            artifact = artifacts.get(str(request.form.get("artifact_id") or ""))
            output_dir = policy.resolve(
                request.form.get("output_dir"), must_exist=False
            )
            output_dir.mkdir(parents=True, exist_ok=True)
            roi_payload = json.loads(str(request.form.get("roi_set") or "{}"))
            roi_set = validate_roi_set(
                roi_payload,
                expected_image_sha256=artifact["metadata"]["image"]["sha256"],
            )
            upload = request.files.get("annotated_image")
            if upload is None:
                raise ValueError("annotated_image is required")
            annotated_bytes = upload.read()
            _validate_annotated_png(annotated_bytes, artifact["metadata"])
            image_path, roi_path = _unique_export_paths(
                output_dir,
                Path(
                    artifact.get("annotated_suggested_filename")
                    or _annotated_filename(artifact["image_path"].name)
                ).stem,
            )
            _atomic_write_bytes(image_path, annotated_bytes)
            _atomic_write_json(roi_path, roi_set)
            if artifact["metadata"]["image"]["sha256"] != _sha256(
                artifact["image_path"]
            ):
                raise RuntimeError("Original source image changed during export")
            return jsonify(
                {
                    "ok": True,
                    "annotated_image_path": str(image_path),
                    "roi_set_path": str(roi_path),
                    "suggested_filename": image_path.name,
                }
            )
        except Exception as exc:
            return _error(exc)

    @app.post("/api/export-jobs")
    def create_export_job():
        try:
            payload = request.get_json(force=True, silent=False) or {}
            export_kind = str(payload.get("export_kind") or "").strip().lower()
            content = str(payload.get("content") or "").strip().lower()
            source_type = str(payload.get("source_type") or "").strip().lower()
            destination = _validated_export_destination(
                payload.get("destination"), export_kind=export_kind, policy=policy
            )
            overwrite = bool(payload.get("overwrite", False))
            preflight_export_destination(
                export_kind=export_kind,
                content=content,
                destination=destination,
                overwrite=overwrite,
            )

            roi_template = _export_roi_template(payload, policy=policy)
            sources: list[dict[str, Any]] | None = None
            source_directory: Path | None = None
            if source_type == "artifact":
                sources = [artifacts.get(str(payload.get("artifact_id") or ""))]
            elif source_type == "sequence_job":
                sequence = jobs.public(str(payload.get("sequence_job_id") or ""))
                if sequence.get("kind") != "sequence":
                    raise KeyError("Sequence job not found or expired")
                if sequence.get("status") != "completed":
                    raise RuntimeError("Sequence render must complete before export")
                sources = [artifacts.get(item) for item in sequence["artifact_ids"]]
            elif source_type == "directory":
                source_directory = policy.resolve(
                    payload.get("source_directory"),
                    must_exist=True,
                    kind="directory",
                )
            else:
                raise ValueError(
                    "source_type must be artifact, sequence_job, or directory"
                )

            total = len(sources) if sources is not None else None
            start_index, end_index = (
                _sequence_relative_export_range(payload, sources)
                if source_type == "sequence_job" and sources is not None
                else _export_frame_range(payload, total=total)
            )
            kwargs = {
                "export_kind": export_kind,
                "content": content,
                "destination": destination,
                "roi_template": roi_template,
                "start_index": start_index,
                "end_index": end_index,
                "fps": payload.get("fps", 10.0),
                "quality": str(payload.get("quality") or "high"),
                "overwrite": overwrite,
            }
            job = (
                export_jobs.start(sources, **kwargs)
                if sources is not None
                else export_jobs.start_from_directory(source_directory, **kwargs)
            )
            return jsonify({"ok": True, "job": job}), 202
        except Exception as exc:
            return _error(exc, missing_status=404)

    @app.get("/api/export-jobs/<job_id>")
    def export_job(job_id: str):
        try:
            return jsonify({"ok": True, "job": export_jobs.public(job_id)})
        except Exception as exc:
            return _error(exc, missing_status=404)

    @app.delete("/api/export-jobs/<job_id>")
    def cancel_export_job(job_id: str):
        try:
            return jsonify({"ok": True, "job": export_jobs.cancel(job_id)})
        except Exception as exc:
            return _error(exc, missing_status=404)

    @app.get("/api/client-config")
    def client_config():
        return jsonify(lifecycle.config())

    @app.post("/api/client-heartbeat")
    def client_heartbeat():
        payload = request.get_json(force=True, silent=True) or {}
        return jsonify(lifecycle.heartbeat(str(payload.get("client_id") or "")))

    @app.post("/api/client-close")
    def client_close():
        payload = request.get_json(force=True, silent=True) or {}
        return jsonify(
            lifecycle.close(
                str(payload.get("client_id") or ""),
                client_requests_stop=bool(payload.get("stop_on_close", True)),
            )
        )

    return app


def _validated_export_destination(
    value: Any, *, export_kind: str, policy: PathPolicy
) -> Path:
    if export_kind == "image_sequence":
        return policy.resolve(value, must_exist=True, kind="directory")
    suffix = (
        ".png" if export_kind == "image" else ".mp4" if export_kind == "video" else ""
    )
    if not suffix:
        raise ValueError("export_kind must be image, image_sequence, or video")
    destination = validate_allowed_path(
        value,
        allowed_roots=policy.roots,
        kind="save_file",
        default_suffix=suffix,
    )
    if destination.suffix.casefold() != suffix:
        raise ValueError(f"{export_kind} destination must end with {suffix}")
    return destination


def _export_roi_template(payload: Mapping[str, Any], *, policy: PathPolicy):
    inline = payload.get("roi_set")
    template_path = str(payload.get("roi_set_path") or "").strip()
    if inline is not None and template_path:
        raise ValueError("Provide roi_set or roi_set_path, not both")
    if template_path:
        if not bool(payload.get("roi_template_mode", False)):
            raise ValueError("Historical ROI JSON requires explicit template mode")
        path = policy.resolve(template_path, must_exist=True, kind="file")
        if path.suffix.casefold() != ".json":
            raise ValueError("ROI template path must end with .json")
        try:
            inline = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"ROI template JSON is invalid: {exc.msg}") from exc
        return validate_roi_template(inline, template_mode=True)
    if inline is not None and not isinstance(inline, Mapping):
        raise ValueError("roi_set must be a JSON object")
    return dict(inline) if isinstance(inline, Mapping) else None


def _export_frame_range(
    payload: Mapping[str, Any], *, total: int | None
) -> tuple[int, int | None]:
    scope = str(payload.get("scope") or "range").strip().lower()
    if scope == "current":
        raw = payload.get("current_frame", 1)
        try:
            current = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("current_frame must be an integer") from exc
        if current < 1 or (total is not None and current > total):
            raise ValueError("current_frame is outside the available source frames")
        return current, current
    if scope != "range":
        raise ValueError("scope must be current or range")
    raw_start = payload.get("start_frame", 1)
    raw_end = payload.get("end_frame", total)
    try:
        start = int(raw_start)
        end = None if raw_end in (None, "") else int(raw_end)
    except (TypeError, ValueError) as exc:
        raise ValueError("Export frame range values must be integers") from exc
    if start < 1 or (end is not None and end < start):
        raise ValueError("Export range must satisfy 1 <= start <= end")
    if total is not None and (start > total or end is None or end > total):
        raise ValueError(f"Export range must be within 1..{total}")
    return start, end


def _sequence_relative_export_range(
    payload: Mapping[str, Any], sources: Sequence[Mapping[str, Any]]
) -> tuple[int, int]:
    ordinals = [
        int(source.get("source_index") or index)
        for index, source in enumerate(sources, start=1)
    ]
    scope = str(payload.get("scope") or "range").strip().lower()
    if scope == "current":
        first_absolute = last_absolute = int(
            payload.get("current_frame") or ordinals[0]
        )
    elif scope == "range":
        first_absolute = int(payload.get("start_frame") or ordinals[0])
        last_absolute = int(payload.get("end_frame") or ordinals[-1])
    else:
        raise ValueError("scope must be current or range")
    try:
        return ordinals.index(first_absolute) + 1, ordinals.index(last_absolute) + 1
    except ValueError as exc:
        raise ValueError(
            "Export range must use frame numbers from the prepared sequence"
        ) from exc


def _public_artifact(record: dict[str, Any]) -> dict[str, Any]:
    metadata = {
        key: value
        for key, value in record["metadata"].items()
        if not key.startswith("_")
    }
    annotated_name = record.setdefault(
        "annotated_suggested_filename",
        _annotated_filename(record["image_path"].name),
    )
    return {
        "id": record["id"],
        "image_url": f"/api/artifacts/{record['id']}/image",
        "metadata_url": f"/api/artifacts/{record['id']}/metadata",
        "suggested_filename": record["image_path"].name,
        "annotated_suggested_filename": annotated_name,
        "metadata": metadata,
        "roi_set": record.get("roi_set"),
    }


def _error(exc: Exception, *, missing_status: int = 400):
    from flask import jsonify

    if isinstance(exc, ExportConflictError):
        return (
            jsonify(
                {
                    "ok": False,
                    "error": str(exc),
                    "code": exc.code,
                    "paths": list(exc.paths),
                    "conflict_paths": list(exc.paths),
                }
            ),
            409,
        )
    status = (
        missing_status
        if isinstance(exc, KeyError)
        else 403 if isinstance(exc, PermissionError) else 400
    )
    return jsonify({"ok": False, "error": str(exc).strip("'\"")}), status


def _prune_discoveries(discoveries: dict[str, dict[str, Any]]) -> None:
    now = time.monotonic()
    for key in [
        key for key, item in discoveries.items() if now - item["created"] > 3600.0
    ]:
        discoveries.pop(key, None)


def _inclusive_frame_range(start: Any, end: Any, total: int) -> tuple[int, int]:
    if total <= 0:
        raise ValueError("The discovery contains no source-map candidates")
    try:
        first = int(start if start not in (None, "") else 1)
        last = int(end if end not in (None, "") else total)
    except (TypeError, ValueError) as exc:
        raise ValueError("Frame range values must be integers") from exc
    if first < 1 or last < first or last > total:
        raise ValueError(f"Frame range must satisfy 1 <= start <= end <= {total}")
    return first, last


def _validate_annotated_png(data: bytes, metadata: dict[str, Any]) -> None:
    from io import BytesIO
    from PIL import Image

    with Image.open(BytesIO(data)) as image:
        if image.format != "PNG":
            raise ValueError("Annotated image must be PNG")
        if list(image.size) != [
            metadata["image"]["width"],
            metadata["image"]["height"],
        ]:
            raise ValueError(
                "Annotated PNG must preserve the original pixel dimensions"
            )


def _unique_export_paths(output_dir: Path, stem: str) -> tuple[Path, Path]:
    safe_stem = "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in stem
    )
    for index in range(1, 10000):
        suffix = "" if index == 1 else f"_{index}"
        image = output_dir / f"{safe_stem}{suffix}.png"
        roi = output_dir / f"{safe_stem}{suffix}.roi-set.json"
        if not image.exists() and not roi.exists():
            return image, roi
    raise RuntimeError("Could not allocate a unique annotation export name")


_SCIENTIFIC_IMAGE_STEM = re.compile(r"^\d{4}_\d{8}T\d{6}Z(?:-\d{8}T\d{6}Z)?_")


def _annotated_filename(image_name: str) -> str:
    stem = Path(image_name).stem
    if _SCIENTIFIC_IMAGE_STEM.match(stem):
        return f"{stem}_annotated.png"
    generated_at = datetime.now(timezone.utc)
    return build_scientific_image_filename(
        sequence=1,
        start_time=None,
        instrument="radio",
        product="source_map",
        qualifiers="annotated",
        generated_at=generated_at,
    )


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.stem}-", suffix=path.suffix, delete=False
    ) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_bytes(
        path, (json.dumps(payload, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
    )


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
