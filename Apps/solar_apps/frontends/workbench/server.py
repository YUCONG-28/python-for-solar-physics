"""Flask app factory for the unified local web workbench."""

from __future__ import annotations

import secrets
import threading
from pathlib import Path
from typing import Any

from solar_apps.frontends.image_viewer.server import ClientLifecycle
from solar_apps.platform.layout import RuntimeLayout
from solar_apps.ui.flask_dialog import register_native_path_dialog
from solar_apps.ui.flask_state import register_ui_state
from solar_apps.ui.theme import register_theme_assets

from .registry import default_registry
from .runner import JobContext, JobRunner, default_python_executable

__all__ = ["create_app"]

_RADIO_WORKSPACE_REPLACED_MODULE_IDS = frozenset(
    {
        "radio-burst-pipeline",
        "radio-source-map",
        "radio-center-extraction",
        "radio-source-trajectory-app",
        "radio-roi-lightcurve-app",
        "rrll-percentile-preview-comparison",
        "radio-trajectory-html-export",
        "aia-radio-hmi-overlay",
        "cso-spectrogram-legacy",
        "radio-raw-quality",
        "dem-radio-overlay",
        "example-gaussian-newkirk-quicklook",
        "example-aia-radio-hmi-overlay",
    }
)


def create_app(
    allowed_roots: list[str | Path] | None = None,
    *,
    python_executable: str | Path | None = None,
    repo_root: str | Path | None = None,
    stop_on_client_close: bool = True,
    shutdown_callback=None,
    runner: JobRunner | None = None,
    radio_output_root: str | Path | None = None,
    radio_store=None,
    radio_run_manager=None,
    native_dialog_service=None,
):
    """Create the Flask app. Flask is imported lazily because it is optional."""

    from flask import Flask, jsonify, render_template, request

    package_dir = Path(__file__).resolve().parent
    resolved_repo = (
        Path(repo_root).resolve()
        if repo_root is not None
        else RuntimeLayout.discover().repo_root
    )
    registry = default_registry(resolved_repo)
    resolved_allowed_roots = [
        Path(root).expanduser().resolve() for root in allowed_roots or []
    ]
    context = JobContext(
        repo_root=resolved_repo,
        allowed_roots=resolved_allowed_roots,
        python_executable=python_executable or default_python_executable(),
    )
    job_runner = runner or JobRunner(registry, context)
    radio_root_token = secrets.token_urlsafe(32)

    from .radio_workspace.api import create_radio_blueprint, request_is_local

    radio_blueprint = create_radio_blueprint(
        output_root=radio_output_root or resolved_repo,
        allowed_roots=resolved_allowed_roots,
        repo_root=resolved_repo,
        python_executable=python_executable or default_python_executable(),
        store=radio_store,
        run_manager=radio_run_manager,
        root_update_token=radio_root_token,
    )
    radio_manager = radio_blueprint.radio_run_manager
    shutdown_lock = threading.Lock()
    radio_closed = False

    def close_radio_and_shutdown() -> None:
        nonlocal radio_closed
        with shutdown_lock:
            if not radio_closed:
                radio_closed = True
                radio_manager.close(cancel_running=True)
        if shutdown_callback is not None:
            shutdown_callback()

    lifecycle = ClientLifecycle(
        stop_on_client_close=stop_on_client_close,
        shutdown_callback=close_radio_and_shutdown,
    )

    app = Flask(
        __name__,
        template_folder=str(package_dir / "templates"),
        static_folder=str(package_dir / "static"),
    )
    register_theme_assets(app)
    dialog_roots = [
        resolved_repo,
        (
            Path(radio_output_root).expanduser().resolve(strict=False)
            if radio_output_root is not None
            else resolved_repo
        ),
        *resolved_allowed_roots,
    ]
    register_ui_state(app, frontend_id="workbench", allowed_roots=dialog_roots)
    register_native_path_dialog(
        app,
        allowed_roots=dialog_roots,
        service=native_dialog_service,
        memory=app.extensions["ui_state"]["recent_paths"],
    )
    app.register_blueprint(radio_blueprint)
    app.extensions["radio_workspace"] = {
        "store": radio_blueprint.radio_workspace_store,
        "run_manager": radio_manager,
        "close": close_radio_and_shutdown,
    }

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/radio")
    def radio_workspace():
        return render_template("radio.html")

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True})

    @app.get("/api/modules")
    def modules():
        payload = registry.to_public_dict()
        payload["modules"] = [
            item
            for item in payload["modules"]
            if item["id"] not in _RADIO_WORKSPACE_REPLACED_MODULE_IDS
        ]
        return jsonify({"ok": True, **payload})

    @app.get("/api/modules/<module_id>")
    def module_detail(module_id: str):
        try:
            module = registry.get(module_id)
        except KeyError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 404
        return jsonify({"ok": True, "module": module.to_public_dict()})

    @app.post("/api/jobs")
    def start_job():
        payload = request.get_json(force=True, silent=True) or {}
        module_id = str(payload.get("module_id", "")).strip()
        if not module_id:
            return jsonify({"ok": False, "error": "module_id is required"}), 400
        try:
            job = job_runner.start(
                module_id, _coerce_payload(payload.get("payload", {}))
            )
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "job": job.to_public_dict()})

    @app.get("/api/jobs/<job_id>")
    def job_status(job_id: str):
        try:
            return jsonify({"ok": True, "job": job_runner.status(job_id)})
        except KeyError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 404

    @app.post("/api/jobs/<job_id>/cancel")
    def cancel_job(job_id: str):
        try:
            return jsonify({"ok": True, "job": job_runner.cancel(job_id)})
        except KeyError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 404

    @app.get("/api/client-config")
    def client_config():
        payload = lifecycle.config()
        if request_is_local(request):
            payload["radio_root_token"] = radio_root_token
        response = jsonify(payload)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.post("/api/client-heartbeat")
    def client_heartbeat():
        payload = request.get_json(force=True, silent=True) or {}
        result = lifecycle.heartbeat(str(payload.get("client_id", "")))
        return jsonify(result), (200 if result.get("ok") else 400)

    @app.post("/api/client-close")
    def client_close():
        payload = request.get_json(force=True, silent=True) or {}
        result = lifecycle.close(
            str(payload.get("client_id", "")),
            client_requests_stop=bool(payload.get("stop_on_close", True)),
        )
        return jsonify(result)

    return app


def _coerce_payload(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError("payload must be a JSON object")
    return value
