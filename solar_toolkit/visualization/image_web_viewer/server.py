"""Flask app factory and filesystem helpers for the image web viewer."""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Any

from . import export as export_mod
from .export import ExportConfig

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".gif",
    ".webp",
    ".tif",
    ".tiff",
}


def natural_key(path: Path) -> list[Any]:
    """Sort image names naturally, e.g. frame2 before frame10."""

    parts = re.split(r"(\d+)", path.name)
    return [int(part) if part.isdigit() else part.casefold() for part in parts]


def configured_roots() -> list[Path]:
    """Read optional allowed roots from IMAGE_VIEWER_ALLOWED_ROOTS."""

    raw = os.getenv("IMAGE_VIEWER_ALLOWED_ROOTS", "").strip()
    if not raw:
        return []
    return [
        Path(item.strip()).expanduser().resolve()
        for item in raw.split(os.pathsep)
        if item.strip()
    ]


def normalize_allowed_roots(allowed_roots: list[str | Path] | None) -> list[Path]:
    """Normalize explicit roots or fall back to the environment setting."""

    if allowed_roots is None:
        return configured_roots()
    return [Path(root).expanduser().resolve() for root in allowed_roots if str(root).strip()]


def is_under_allowed_root(path: Path, allowed_roots: list[str | Path] | None = None) -> bool:
    """Return whether path is inside the optional local access boundary."""

    roots = normalize_allowed_roots(allowed_roots)
    if not roots:
        return True
    resolved = Path(path).expanduser().resolve()
    return any(resolved == root or root in resolved.parents for root in roots)


def scan_images(
    folder: str | Path,
    recursive: bool = False,
    *,
    allowed_roots: list[str | Path] | None = None,
) -> tuple[Path, list[Path]]:
    """Scan a local folder for supported image files."""

    root = Path(folder).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Path does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Not a folder: {root}")
    if not is_under_allowed_root(root, allowed_roots):
        raise PermissionError(f"Path is outside IMAGE_VIEWER_ALLOWED_ROOTS: {root}")

    iterator = root.rglob("*") if recursive else root.iterdir()
    files = [
        path
        for path in iterator
        if path.is_file() and path.suffix.casefold() in IMAGE_EXTENSIONS
    ]
    return root, sorted(files, key=natural_key)


def create_app(allowed_roots: list[str | Path] | None = None):
    """Create the Flask app. Flask is imported lazily because it is optional."""

    from flask import Flask, jsonify, render_template, request, send_file

    package_dir = Path(__file__).resolve().parent
    app = Flask(
        __name__,
        template_folder=str(package_dir / "templates"),
        static_folder=str(package_dir / "static"),
    )
    sessions: dict[str, list[dict[str, Any]]] = {}
    roots = normalize_allowed_roots(allowed_roots)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/api/load")
    def load_folders():
        payload = request.get_json(force=True, silent=True) or {}
        folders = payload.get("folders", [])
        recursive = bool(payload.get("recursive", False))
        if not isinstance(folders, list):
            return jsonify({"ok": False, "error": "folders must be a list"}), 400

        cleaned = [str(folder).strip() for folder in folders if str(folder).strip()]
        if not cleaned:
            return jsonify({"ok": False, "error": "Please enter at least one folder."}), 400

        groups: list[dict[str, Any]] = []
        errors: list[str] = []
        for folder in cleaned:
            try:
                root, files = scan_images(folder, recursive=recursive, allowed_roots=roots)
                groups.append(
                    {
                        "folder": str(root),
                        "name": root.name or str(root),
                        "files": files,
                    }
                )
            except Exception as exc:
                errors.append(str(exc))

        if errors:
            return jsonify({"ok": False, "error": "\n".join(errors)}), 400
        session_id = uuid.uuid4().hex
        sessions[session_id] = groups
        public_groups = [_public_group(group, index) for index, group in enumerate(groups)]
        return jsonify(
            {
                "ok": True,
                "session_id": session_id,
                "groups": public_groups,
                "max_frames": max((len(group["files"]) for group in groups), default=0),
            }
        )

    @app.get("/api/image/<session_id>/<int:group_index>/<int:frame_index>")
    def image(session_id: str, group_index: int, frame_index: int):
        groups = sessions.get(session_id)
        if groups is None:
            return "session not found or expired", 404
        if group_index < 0 or group_index >= len(groups):
            return "group_index out of range", 404

        group = groups[group_index]
        files: list[Path] = group["files"]
        if frame_index < 0 or frame_index >= len(files):
            return "frame not found in this folder", 404

        path = files[frame_index]
        folder = Path(group["folder"]).resolve()
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError:
            return "image file no longer exists", 404
        if not (resolved == folder or folder in resolved.parents):
            return "illegal path", 403
        return send_file(resolved, conditional=True, max_age=0)

    @app.post("/api/export-video")
    def export_video():
        payload = request.get_json(force=True, silent=True) or {}
        session_id = str(payload.get("session_id", ""))
        groups = sessions.get(session_id)
        if groups is None:
            return jsonify({"ok": False, "error": "session not found or expired"}), 404

        mode = str(payload.get("mode", "composite")).strip().lower()
        if mode not in {"composite", "separate", "both"}:
            return jsonify({"ok": False, "error": "mode must be composite, separate, or both"}), 400
        try:
            config = _export_config_from_payload(payload).normalized()
            result: dict[str, Any] = {"ok": True, "mode": mode}
            if mode in {"separate", "both"}:
                result["separate"] = export_mod.export_separate_videos(groups, config)
            if mode in {"composite", "both"}:
                result["composite"] = export_mod.export_composite_video(groups, config)
            return jsonify(result)
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True})

    return app


def _public_group(group: dict[str, Any], index: int) -> dict[str, Any]:
    files: list[Path] = group["files"]
    return {
        "index": index,
        "name": group["name"],
        "folder": group["folder"],
        "count": len(files),
        "first": files[0].name if files else None,
        "last": files[-1].name if files else None,
    }


def _export_config_from_payload(payload: dict[str, Any]) -> ExportConfig:
    output_dir = payload.get("output_dir") or "outputs/image_web_viewer"
    target_size = _optional_size(payload.get("target_width"), payload.get("target_height"))
    panel_size = _optional_size(payload.get("panel_width"), payload.get("panel_height"))
    return ExportConfig(
        output_dir=output_dir,
        file_prefix=str(payload.get("file_prefix") or "image_viewer"),
        fps=float(payload.get("fps") or 5.0),
        quality=str(payload.get("quality") or "low"),
        start_frame=int(payload.get("start_frame") or 0),
        end_frame=(
            None
            if payload.get("end_frame") in (None, "")
            else int(payload.get("end_frame"))
        ),
        target_size=target_size,
        composite_panel_size=panel_size or target_size,
        roi=payload.get("roi") if payload.get("use_roi", False) else None,
    )


def _optional_size(width, height) -> tuple[int, int] | None:
    if width in (None, "") or height in (None, ""):
        return None
    return int(width), int(height)
