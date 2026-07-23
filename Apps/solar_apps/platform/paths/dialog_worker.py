"""Isolated PySide6 worker for Windows/macOS native file and folder dialogs."""

from __future__ import annotations

import json
import sys
from typing import Any


def _name_filters(extensions: list[str]) -> list[str]:
    patterns = ["*" if item == "*" else f"*{item}" for item in extensions]
    if not patterns:
        return ["All files (*)"]
    return [f"Supported files ({' '.join(patterns)})", "All files (*)"]


def run_dialog(payload: dict[str, Any]) -> dict[str, Any]:
    """Run one QFileDialog and return its small JSON-compatible result."""

    from PySide6.QtWidgets import QApplication, QFileDialog

    app = QApplication.instance() or QApplication(["solar-native-path-dialog"])
    dialog = QFileDialog()
    dialog.setOption(QFileDialog.DontUseNativeDialog, False)
    dialog.setWindowTitle(str(payload["title"]))
    initial_path = str(payload.get("initial_path") or "")
    if initial_path:
        dialog.setDirectory(initial_path)
    extensions = [str(item) for item in payload.get("extensions") or []]
    dialog.setNameFilters(_name_filters(extensions))
    mode = str(payload["mode"])
    if mode == "open_file":
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        dialog.setFileMode(QFileDialog.ExistingFile)
    elif mode == "open_files":
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        dialog.setFileMode(QFileDialog.ExistingFiles)
    elif mode == "select_directory":
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.ShowDirsOnly, True)
    elif mode == "save_file":
        dialog.setAcceptMode(QFileDialog.AcceptSave)
        dialog.setFileMode(QFileDialog.AnyFile)
        suffix = str(payload.get("default_suffix") or "").lstrip(".")
        if suffix:
            dialog.setDefaultSuffix(suffix)
    else:
        raise ValueError(f"Unsupported dialog mode: {mode!r}")
    try:
        accepted = dialog.exec() == QFileDialog.Accepted
        return {
            "status": "selected" if accepted else "cancelled",
            "paths": [str(path) for path in dialog.selectedFiles()] if accepted else [],
        }
    finally:
        dialog.deleteLater()
        app.processEvents()


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict):
            raise TypeError("Worker payload must be a JSON object.")
        result = run_dialog(payload)
    except Exception as exc:  # The parent converts worker failures into HTTP 503.
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
