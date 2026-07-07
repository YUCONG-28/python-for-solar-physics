"""Flask app factory for the unified local web workbench."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from solar_toolkit.visualization.image_web_viewer.server import ClientLifecycle

from .registry import default_registry
from .runner import JobContext, JobRunner, default_python_executable


def create_app(
    allowed_roots: list[str | Path] | None = None,
    *,
    python_executable: str | Path | None = None,
    repo_root: str | Path | None = None,
    stop_on_client_close: bool = True,
    shutdown_callback=None,
    runner: JobRunner | None = None,
):
    """Create the Flask app. Flask is imported lazily because it is optional."""

    from flask import Flask, jsonify, render_template, request

    package_dir = Path(__file__).resolve().parent
    resolved_repo = (
        Path(repo_root).resolve() if repo_root is not None else package_dir.parents[1]
    )
    registry = default_registry(resolved_repo)
    context = JobContext(
        repo_root=resolved_repo,
        allowed_roots=[Path(root) for root in allowed_roots or []],
        python_executable=python_executable or default_python_executable(),
    )
    job_runner = runner or JobRunner(registry, context)
    lifecycle = ClientLifecycle(
        stop_on_client_close=stop_on_client_close,
        shutdown_callback=shutdown_callback,
    )

    app = Flask(
        __name__,
        template_folder=str(package_dir / "templates"),
        static_folder=str(package_dir / "static"),
    )

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True})

    @app.get("/api/modules")
    def modules():
        payload = registry.to_public_dict()
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
        return jsonify(lifecycle.config())

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
