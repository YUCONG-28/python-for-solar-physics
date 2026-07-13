"""Flask Blueprint for the modular Radio Workspace API."""

from __future__ import annotations

import ipaddress
import secrets
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .catalog import catalog_payload, get_action, presets_payload
from .runner import RadioRunManager
from .store import RadioWorkspaceStore


def create_radio_blueprint(
    output_root: str | Path | None = None,
    *,
    allowed_roots: Iterable[str | Path] = (),
    repo_root: str | Path | None = None,
    python_executable: str | Path | None = None,
    store: RadioWorkspaceStore | None = None,
    run_manager: RadioRunManager | None = None,
    root_update_token: str | None = None,
    name: str = "radio_workspace",
    url_prefix: str = "/api/radio",
):
    """Create a self-contained Blueprint without modifying the parent Flask app."""

    from flask import Blueprint, Response, jsonify, request, send_file

    if store is None:
        if output_root is None:
            resolved_repo = (
                Path(repo_root).resolve()
                if repo_root is not None
                else Path(__file__).resolve().parents[3]
            )
            output_root = resolved_repo
        store = RadioWorkspaceStore(output_root, allowed_roots=allowed_roots)
    manager = run_manager or RadioRunManager(
        store,
        repo_root=repo_root,
        python_executable=python_executable,
    )
    blueprint = Blueprint(name, __name__, url_prefix=url_prefix)
    blueprint.radio_workspace_store = store
    blueprint.radio_run_manager = manager

    @blueprint.errorhandler(KeyError)
    def _key_error(exc):
        return jsonify({"ok": False, "error": _error_text(exc)}), 404

    @blueprint.errorhandler(FileNotFoundError)
    @blueprint.errorhandler(NotADirectoryError)
    def _not_found(exc):
        return jsonify({"ok": False, "error": _error_text(exc)}), 404

    @blueprint.errorhandler(PermissionError)
    def _permission_error(exc):
        return jsonify({"ok": False, "error": _error_text(exc)}), 403

    @blueprint.errorhandler(FileExistsError)
    @blueprint.errorhandler(RuntimeError)
    def _conflict(exc):
        return jsonify({"ok": False, "error": _error_text(exc)}), 409

    @blueprint.errorhandler(TypeError)
    @blueprint.errorhandler(ValueError)
    def _bad_request(exc):
        return jsonify({"ok": False, "error": _error_text(exc)}), 400

    @blueprint.get("/health")
    def health():
        return jsonify({"ok": True, "schema_version": 1})

    @blueprint.get("/assets/plotly.js")
    def plotly_asset():
        try:
            from plotly.offline import get_plotlyjs
        except ImportError:
            return jsonify({"ok": False, "error": "Plotly is unavailable"}), 503
        response = Response(get_plotlyjs(), content_type="application/javascript")
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @blueprint.get("/assets/<asset_name>")
    def media_asset(asset_name: str):
        from solar_toolkit.visualization import _media_assets as media_assets

        allowed = {
            "mediabunny-1.50.8.cjs",
            "browser_media.js",
            "NOTICE.txt",
            "mediabunny-MPL-2.0.txt",
        }
        if asset_name not in allowed:
            return jsonify({"ok": False, "error": "Asset not found"}), 404
        content = media_assets.read_asset_bytes(asset_name)
        response = Response(
            content,
            content_type=media_assets.asset_mimetype(asset_name),
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @blueprint.get("/modules")
    def modules():
        return jsonify({"ok": True, **catalog_payload()})

    @blueprint.get("/presets")
    def presets():
        return jsonify({"ok": True, **presets_payload()})

    @blueprint.get("/allowed-roots")
    def allowed_roots():
        return jsonify({"ok": True, **store.allowed_roots_payload()})

    @blueprint.put("/allowed-roots")
    def update_allowed_roots():
        if not request_is_local(request):
            raise PermissionError("Allowed roots may only be changed locally")
        supplied_token = request.headers.get("X-Radio-Root-Token", "")
        if (
            not root_update_token
            or not supplied_token
            or not secrets.compare_digest(supplied_token, root_update_token)
        ):
            raise PermissionError("A valid local root-update token is required")
        payload = _json_object(request)
        roots = payload.get("roots")
        if not isinstance(roots, list):
            raise TypeError("roots must be a JSON array")
        store.replace_user_roots(roots)
        return jsonify({"ok": True, **store.allowed_roots_payload()})

    @blueprint.get("/workspaces")
    def workspaces():
        return jsonify(
            {
                "ok": True,
                "workspaces": [item.to_dict() for item in store.list_workspaces()],
            }
        )

    @blueprint.post("/workspaces")
    def create_workspace():
        payload = _json_object(request)
        workspace = store.create_workspace(
            name=str(payload.get("name", "Radio Workspace")),
            event_preset=_object_field(payload, "event_preset"),
            shared_paths=_object_field(payload, "shared_paths"),
            advanced_config=_object_field(payload, "advanced_config"),
            concurrency=payload.get("concurrency", 1),
            output_root=payload.get("output_root"),
        )
        return jsonify({"ok": True, "workspace": workspace.to_dict()}), 201

    @blueprint.get("/workspaces/<workspace_id>")
    def workspace_detail(workspace_id: str):
        workspace = store.load_workspace(workspace_id)
        return jsonify({"ok": True, "workspace": workspace.to_dict()})

    @blueprint.patch("/workspaces/<workspace_id>")
    def update_workspace(workspace_id: str):
        workspace = store.update_workspace(workspace_id, _json_object(request))
        return jsonify({"ok": True, "workspace": workspace.to_dict()})

    @blueprint.delete("/workspaces/<workspace_id>")
    def delete_workspace(workspace_id: str):
        active = [
            item
            for item in store.list_runs(workspace_id)
            if item.status in {"queued", "running"}
        ]
        if active:
            raise RuntimeError("Cancel active runs before deleting this workspace")
        store.delete_workspace(workspace_id)
        return jsonify({"ok": True, "deleted": workspace_id})

    @blueprint.patch("/workspaces/<workspace_id>/layout")
    def update_layout(workspace_id: str):
        workspace = store.update_layout(workspace_id, _json_object(request))
        return jsonify({"ok": True, "workspace": workspace.to_dict()})

    @blueprint.get("/files")
    def files():
        payload = store.browser.list_directory(request.args.get("path"))
        return jsonify({"ok": True, **payload})

    @blueprint.post(
        "/workspaces/<workspace_id>/modules/<module_id>/actions/<action_id>/preview"
    )
    def preview_action(workspace_id: str, module_id: str, action_id: str):
        preview = manager.preview(
            workspace_id,
            module_id,
            action_id,
            _json_object(request),
        )
        return jsonify({"ok": True, "preview": preview})

    @blueprint.get("/workspaces/<workspace_id>/runs")
    def list_runs(workspace_id: str):
        return jsonify(
            {
                "ok": True,
                "runs": [item.to_dict() for item in manager.list_runs(workspace_id)],
            }
        )

    @blueprint.post("/workspaces/<workspace_id>/runs")
    def start_run(workspace_id: str):
        payload = _json_object(request)
        module_id = str(payload.pop("module_id", "")).strip()
        action_id = str(payload.pop("action_id", "")).strip()
        if not module_id or not action_id:
            raise ValueError("module_id and action_id are required")
        run = manager.start(workspace_id, module_id, action_id, payload)
        return jsonify({"ok": True, "run": run.to_dict()}), 202

    @blueprint.post("/workspaces/<workspace_id>/runs/batch")
    def start_batch(workspace_id: str):
        payload = _json_object(request)
        if payload.get("confirmed") is not True:
            raise ValueError("confirmed must be true before running selected actions")
        actions = payload.get("actions")
        if not isinstance(actions, list) or not actions:
            raise ValueError("actions must be a non-empty JSON array")
        runs = manager.start_batch(workspace_id, actions)
        return jsonify({"ok": True, "runs": [item.to_dict() for item in runs]}), 202

    @blueprint.get("/workspaces/<workspace_id>/runs/<run_id>")
    @blueprint.get("/workspaces/<workspace_id>/runs/<run_id>/status")
    def run_status(workspace_id: str, run_id: str):
        run = manager.status(workspace_id, run_id)
        return jsonify({"ok": True, "run": run.to_dict()})

    @blueprint.get("/workspaces/<workspace_id>/runs/<run_id>/log")
    def run_log(workspace_id: str, run_id: str):
        raw_offset = request.args.get("offset", "0")
        try:
            offset = int(raw_offset)
        except ValueError as exc:
            raise ValueError("offset must be an integer") from exc
        lines, next_offset = store.read_log(workspace_id, run_id, offset=offset)
        return jsonify({"ok": True, "lines": lines, "next_offset": next_offset})

    @blueprint.post("/workspaces/<workspace_id>/runs/<run_id>/cancel")
    def cancel_run(workspace_id: str, run_id: str):
        run = manager.cancel(workspace_id, run_id)
        return jsonify({"ok": True, "run": run.to_dict()})

    @blueprint.get("/workspaces/<workspace_id>/artifacts")
    def workspace_artifacts(workspace_id: str):
        artifacts: list[dict[str, Any]] = []
        for run in manager.list_runs(workspace_id):
            for artifact in run.artifacts:
                payload = artifact.to_dict()
                payload["run_id"] = run.id
                payload["module_id"] = run.module_id
                payload["action_id"] = run.action_id
                payload["declared_types"] = list(
                    get_action(run.module_id, run.action_id).produces_artifacts
                )
                artifacts.append(payload)
        return jsonify({"ok": True, "artifacts": artifacts})

    @blueprint.get("/workspaces/<workspace_id>/runs/<run_id>/artifacts")
    def run_artifacts(workspace_id: str, run_id: str):
        run = manager.status(workspace_id, run_id)
        return jsonify(
            {"ok": True, "artifacts": [item.to_dict() for item in run.artifacts]}
        )

    @blueprint.get("/workspaces/<workspace_id>/runs/<run_id>/artifacts/<artifact_id>")
    def artifact_file(workspace_id: str, run_id: str, artifact_id: str):
        artifact, path = store.artifact_path(workspace_id, run_id, artifact_id)
        response = send_file(
            path,
            mimetype=artifact.mime_type,
            as_attachment=request.args.get("download") in {"1", "true", "yes"},
            conditional=True,
            download_name=path.name,
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        if artifact.kind == "html":
            response.headers["Content-Security-Policy"] = "sandbox"
        return response

    return blueprint


def _json_object(request) -> dict[str, Any]:
    payload = request.get_json(force=True, silent=True)
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise TypeError("request body must be a JSON object")
    return dict(payload)


def _object_field(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError(f"{key} must be a JSON object")
    return dict(value)


def _error_text(exc: Exception) -> str:
    return str(exc.args[0]) if exc.args else str(exc)


def request_is_local(request) -> bool:
    """Return whether both the peer and Host header identify this machine."""

    remote_addr = str(request.remote_addr or "").strip()
    if not remote_addr:
        return False
    try:
        if not ipaddress.ip_address(remote_addr).is_loopback:
            return False
    except ValueError:
        return False

    raw_host = str(request.host or "").strip()
    if not raw_host:
        return False
    try:
        hostname = (urlsplit(f"//{raw_host}").hostname or "").rstrip(".").casefold()
    except ValueError:
        return False
    if hostname == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


__all__ = ["create_radio_blueprint", "request_is_local"]
