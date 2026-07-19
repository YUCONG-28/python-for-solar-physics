"""Flask adapter for the shared native path-dialog service."""

from __future__ import annotations

import secrets
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .memory import RecentPathMemory
from .native_dialog import NativeDialogError, NativePathDialogService

__all__ = ["register_native_path_dialog"]


def _request_is_local(request: Any) -> bool:
    return str(request.remote_addr or "") in {"127.0.0.1", "::1"}


def register_native_path_dialog(
    app: Any,
    *,
    allowed_roots: Iterable[str | Path],
    python_executable: str | Path | None = None,
    service: NativePathDialogService | Any | None = None,
    memory: RecentPathMemory | None = None,
    client_script_source: str | bytes | None = None,
    route: str = "/api/native-path-dialog",
) -> NativePathDialogService | Any:
    """Register token-protected config, selection, and shared-client routes."""

    from flask import Response, jsonify, request

    roots = tuple(allowed_roots)
    selected_service = service or NativePathDialogService(
        roots,
        python_executable=python_executable,
        memory=memory or RecentPathMemory.default(roots),
    )
    token = secrets.token_urlsafe(32)
    app.extensions["native_path_dialog"] = {
        "service": selected_service,
        "token": token,
        "route": route,
    }

    def client_script():
        if client_script_source is None:
            return Response(status=404)
        payload = (
            client_script_source.encode("utf-8")
            if isinstance(client_script_source, str)
            else client_script_source
        )
        return Response(
            payload,
            content_type="application/javascript",
        )

    def dialog_config():
        if not _request_is_local(request):
            return jsonify({"ok": False, "error": "Local requests only."}), 403
        response = jsonify(
            {
                "ok": True,
                "token": token,
                "supported": bool(getattr(selected_service, "supported", True)),
            }
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    def select_path():
        if not _request_is_local(request):
            return jsonify({"ok": False, "error": "Local requests only."}), 403
        if not secrets.compare_digest(
            request.headers.get("X-Native-Dialog-Token", ""), token
        ):
            return jsonify({"ok": False, "error": "Invalid dialog token."}), 403
        payload = request.get_json(force=False, silent=True)
        if not isinstance(payload, dict):
            return jsonify({"ok": False, "error": "JSON object required."}), 400
        try:
            selection = selected_service.select(payload)
        except NativeDialogError as exc:
            return jsonify({"ok": False, "error": str(exc)}), exc.status_code
        except Exception as exc:  # Keep desktop/backend failures explicit to the UI.
            return jsonify({"ok": False, "error": str(exc)}), 503
        return jsonify(selection.to_dict())

    endpoint_prefix = f"native_path_dialog_{len(app.url_map._rules)}"
    if client_script_source is not None:
        app.add_url_rule(
            f"{route}/client.js",
            endpoint=f"{endpoint_prefix}_client",
            view_func=client_script,
            methods=["GET"],
        )
    app.add_url_rule(
        route,
        endpoint=f"{endpoint_prefix}_config",
        view_func=dialog_config,
        methods=["GET"],
    )
    app.add_url_rule(
        route,
        endpoint=f"{endpoint_prefix}_select",
        view_func=select_path,
        methods=["POST"],
    )
    return selected_service
