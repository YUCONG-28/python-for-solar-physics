"""UI asset binding for the platform-owned native path-dialog adapter."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from solar_apps.platform.paths.flask_dialog import (
    register_native_path_dialog as register_platform_native_path_dialog,
)
from solar_apps.platform.paths.native_dialog import NativePathDialogService
from solar_apps.platform.processes import selected_python_executable

from . import media

__all__ = ["register_native_path_dialog"]


def register_native_path_dialog(
    app: Any,
    *,
    allowed_roots: Iterable[str | Path],
    service: NativePathDialogService | Any | None = None,
    memory: Any | None = None,
    route: str = "/api/native-path-dialog",
) -> NativePathDialogService | Any:
    """Register the shared service with the packaged browser client."""

    return register_platform_native_path_dialog(
        app,
        allowed_roots=allowed_roots,
        python_executable=selected_python_executable(),
        service=service,
        memory=memory,
        client_script_source=media.read_asset_bytes("native_path_dialog.js"),
        route=route,
    )
