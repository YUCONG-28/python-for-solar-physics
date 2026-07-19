"""Allowed-root validation, native dialogs, and recent-path memory."""

from __future__ import annotations

from .allowed_roots import (
    AllowedRootPolicyError,
    configured_allowed_roots,
    normalize_allowed_roots,
    prepare_allowed_root_args,
)
from .memory import PathMemoryContext, RecentPathMemory
from .native_dialog import (
    DialogRequest,
    DialogSelection,
    NativePathDialogService,
    validate_allowed_path,
)

__all__ = [
    "AllowedRootPolicyError",
    "DialogRequest",
    "DialogSelection",
    "NativePathDialogService",
    "PathMemoryContext",
    "RecentPathMemory",
    "configured_allowed_roots",
    "normalize_allowed_roots",
    "prepare_allowed_root_args",
    "validate_allowed_path",
]
