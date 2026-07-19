"""Local-only Flask API for latest UI state and recent-path resets."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .state import frontend_path_memory, frontend_state_store
from .theme import normalize_theme_mode

_FIELD_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$")
_MAX_FIELDS = 256
_MAX_VALUE_LENGTH = 32768


def _local_request(request: Any) -> bool:
    return str(request.remote_addr or "") in {"127.0.0.1", "::1"}


def _clean_fields(raw: object) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, Mapping) or len(raw) > _MAX_FIELDS:
        raise ValueError("fields must be a bounded object")
    cleaned: dict[str, Any] = {}
    for raw_key, value in raw.items():
        key = str(raw_key)
        if not _FIELD_RE.fullmatch(key):
            raise ValueError(f"Invalid UI field identifier: {key!r}")
        if isinstance(value, bool) or value is None:
            cleaned[key] = value
        elif isinstance(value, (str, int, float)):
            text = str(value)
            if len(text) > _MAX_VALUE_LENGTH:
                raise ValueError(f"UI field is too large: {key}")
            cleaned[key] = value
        elif isinstance(value, list) and len(value) <= 128:
            items = [str(item) for item in value]
            if any(len(item) > _MAX_VALUE_LENGTH for item in items):
                raise ValueError(f"UI field is too large: {key}")
            cleaned[key] = items
        else:
            raise ValueError(f"Unsupported UI field value: {key}")
    return cleaned


def register_ui_state(
    app: Any,
    *,
    frontend_id: str,
    allowed_roots: Iterable[str | Path],
    route: str = "/api/ui-state",
) -> None:
    """Expose get/update/reset for a frontend's latest state only."""

    from flask import jsonify, request

    store = frontend_state_store(frontend_id)
    paths = frontend_path_memory(allowed_roots)
    app.extensions["ui_state"] = {
        "frontend_id": frontend_id,
        "store": store,
        "recent_paths": paths,
    }

    def read_state():
        if not _local_request(request):
            return jsonify({"ok": False, "error": "Local requests only."}), 403
        found = store.path.is_file()
        return jsonify(
            {
                "ok": True,
                "found": found,
                "state": store.load({"theme": "auto", "fields": {}}),
            }
        )

    def update_state():
        if not _local_request(request):
            return jsonify({"ok": False, "error": "Local requests only."}), 403
        payload = request.get_json(force=False, silent=True)
        if not isinstance(payload, Mapping):
            return jsonify({"ok": False, "error": "JSON object required."}), 400
        current = store.load({"theme": "auto", "fields": {}})
        try:
            if "theme" in payload:
                current["theme"] = normalize_theme_mode(payload["theme"])
            if "fields" in payload:
                merged_fields = _clean_fields(current.get("fields"))
                merged_fields.update(_clean_fields(payload["fields"]))
                current["fields"] = merged_fields
            if payload.get("legacy_imported") is True:
                current["legacy_imported"] = True
            store.save(current)
        except (TypeError, ValueError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "state": current})

    def reset_state():
        if not _local_request(request):
            return jsonify({"ok": False, "error": "Local requests only."}), 403
        store.save({"theme": "auto", "fields": {}, "legacy_imported": True})
        paths.reset(frontend=frontend_id)
        return jsonify(
            {
                "ok": True,
                "state": {
                    "theme": "auto",
                    "fields": {},
                    "legacy_imported": True,
                },
            }
        )

    suffix = re.sub(r"[^A-Za-z0-9_]", "_", frontend_id)
    app.add_url_rule(
        route, endpoint=f"ui_state_{suffix}_get", view_func=read_state, methods=["GET"]
    )
    app.add_url_rule(
        route,
        endpoint=f"ui_state_{suffix}_patch",
        view_func=update_state,
        methods=["PATCH"],
    )
    app.add_url_rule(
        route,
        endpoint=f"ui_state_{suffix}_delete",
        view_func=reset_state,
        methods=["DELETE"],
    )


__all__ = ["register_ui_state"]
