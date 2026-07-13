"""Versioned data contracts for the modular radio workspace."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, ClassVar

SCHEMA_VERSION = 1
RUN_STATUSES = frozenset(
    {"queued", "running", "succeeded", "failed", "canceled", "interrupted"}
)
_IDENTIFIER_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")


def _require_identifier(value: str, *, label: str) -> str:
    normalized = str(value).strip()
    if not _IDENTIFIER_RE.fullmatch(normalized):
        raise ValueError(f"Invalid {label}: {value!r}")
    return normalized


def _json_mapping(value: Any, *, label: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be a JSON object")
    return dict(value)


def _string_list(value: Any, *, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"{label} must be a JSON array")
    return [str(item) for item in value]


@dataclass(frozen=True)
class RadioActionSpec:
    """One independently runnable or previewable action inside a radio module."""

    id: str
    title: str
    description: str
    input_schema: tuple[dict[str, Any], ...] = ()
    run_required_fields: tuple[str, ...] = ()
    run_required_any_fields: tuple[str, ...] = ()
    accepts_artifacts: tuple[str, ...] = ()
    produces_artifacts: tuple[str, ...] = ()
    command_module: str | None = None
    fixed_arguments: tuple[str, ...] = ()
    blocked_arguments: tuple[str, ...] = ()
    output_flag: str | None = None
    output_filename: str | None = None
    config_json_flag: str | None = None
    preview_adapter: str | None = None
    section: str = "main"
    risk_level: str = "standard"
    default_config: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_identifier(self.id, label="action id"))
        if self.section not in {"main", "advanced", "adjacent"}:
            raise ValueError(f"Unknown action section: {self.section!r}")
        if self.risk_level not in {"standard", "advanced"}:
            raise ValueError(f"Unknown action risk level: {self.risk_level!r}")
        if self.output_filename and not self.output_flag:
            raise ValueError("output_filename requires output_flag")

    @property
    def runnable(self) -> bool:
        return bool(self.command_module)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "input_schema": [dict(item) for item in self.input_schema],
            "run_required_fields": list(self.run_required_fields),
            "run_required_any_fields": list(self.run_required_any_fields),
            "accepts_artifacts": list(self.accepts_artifacts),
            "produces_artifacts": list(self.produces_artifacts),
            "command_module": self.command_module,
            "fixed_arguments": list(self.fixed_arguments),
            "blocked_arguments": list(self.blocked_arguments),
            "output_flag": self.output_flag,
            "output_filename": self.output_filename,
            "config_json_flag": self.config_json_flag,
            "preview_adapter": self.preview_adapter,
            "section": self.section,
            "risk_level": self.risk_level,
            "default_config": dict(self.default_config),
            "runnable": self.runnable,
            "preview_supported": self.preview_adapter is not None,
        }


@dataclass(frozen=True)
class RadioModuleSpec:
    """A fused research-purpose module shown in the radio workspace sidebar."""

    id: str
    title: str
    group: str
    description: str
    actions: tuple[RadioActionSpec, ...]
    accepts_artifacts: tuple[str, ...] = ()
    produces_artifacts: tuple[str, ...] = ()
    default_enabled: bool = False
    default_collapsed: bool = True
    always_available: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_identifier(self.id, label="module id"))
        if self.group not in {"Core", "Analysis", "Context", "Advanced"}:
            raise ValueError(f"Unknown module group: {self.group!r}")
        action_ids = [item.id for item in self.actions]
        if len(action_ids) != len(set(action_ids)):
            raise ValueError(f"Duplicate action id in module {self.id!r}")

    def get_action(self, action_id: str) -> RadioActionSpec:
        for action in self.actions:
            if action.id == action_id:
                return action
        raise KeyError(f"Unknown radio action {self.id}/{action_id}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "id": self.id,
            "title": self.title,
            "group": self.group,
            "description": self.description,
            "actions": [item.to_dict() for item in self.actions],
            "accepts_artifacts": list(self.accepts_artifacts),
            "produces_artifacts": list(self.produces_artifacts),
            "default_enabled": self.default_enabled,
            "default_collapsed": self.default_collapsed,
            "always_available": self.always_available,
        }


@dataclass
class RadioWorkspace:
    """Persisted user choices and configuration for one local radio workspace."""

    schema_version: int
    id: str
    name: str
    output_root: str
    created_at: str
    updated_at: str
    event_preset: dict[str, Any] = field(default_factory=dict)
    shared_paths: dict[str, str] = field(default_factory=dict)
    advanced_config: dict[str, Any] = field(default_factory=dict)
    enabled_modules: list[str] = field(default_factory=list)
    module_order: list[str] = field(default_factory=list)
    collapsed_modules: list[str] = field(default_factory=list)
    pinned_modules: list[str] = field(default_factory=list)
    concurrency: int = 1

    CURRENT_SCHEMA_VERSION: ClassVar[int] = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if int(self.schema_version) != SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported radio workspace schema version: {self.schema_version}"
            )
        self.id = _require_identifier(self.id, label="workspace id")
        self.name = str(self.name).strip() or "Radio Workspace"
        self.concurrency = int(self.concurrency)
        if not 1 <= self.concurrency <= 4:
            raise ValueError("concurrency must be between 1 and 4")
        self.event_preset = _json_mapping(self.event_preset, label="event_preset")
        self.shared_paths = {
            str(key): str(value) for key, value in self.shared_paths.items()
        }
        self.advanced_config = _json_mapping(
            self.advanced_config, label="advanced_config"
        )
        for attr in (
            "enabled_modules",
            "module_order",
            "collapsed_modules",
            "pinned_modules",
        ):
            setattr(self, attr, _string_list(getattr(self, attr), label=attr))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RadioWorkspace:
        return cls(
            schema_version=payload.get("schema_version", 0),
            id=payload.get("id", ""),
            name=payload.get("name", "Radio Workspace"),
            output_root=payload.get("output_root", ""),
            created_at=payload.get("created_at", ""),
            updated_at=payload.get("updated_at", ""),
            event_preset=_json_mapping(
                payload.get("event_preset"), label="event_preset"
            ),
            shared_paths=_json_mapping(
                payload.get("shared_paths"), label="shared_paths"
            ),
            advanced_config=_json_mapping(
                payload.get("advanced_config"), label="advanced_config"
            ),
            enabled_modules=_string_list(
                payload.get("enabled_modules"), label="enabled_modules"
            ),
            module_order=_string_list(
                payload.get("module_order"), label="module_order"
            ),
            collapsed_modules=_string_list(
                payload.get("collapsed_modules"), label="collapsed_modules"
            ),
            pinned_modules=_string_list(
                payload.get("pinned_modules"), label="pinned_modules"
            ),
            concurrency=payload.get("concurrency", 1),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "name": self.name,
            "output_root": self.output_root,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "event_preset": dict(self.event_preset),
            "shared_paths": dict(self.shared_paths),
            "advanced_config": dict(self.advanced_config),
            "enabled_modules": list(self.enabled_modules),
            "module_order": list(self.module_order),
            "collapsed_modules": list(self.collapsed_modules),
            "pinned_modules": list(self.pinned_modules),
            "concurrency": self.concurrency,
        }


@dataclass(frozen=True)
class RadioArtifact:
    """One indexed output produced by a radio action."""

    id: str
    relative_path: str
    kind: str
    mime_type: str
    artifact_type: str = "file"
    role: str = "output"
    source_run_id: str | None = None
    size: int = 0
    previewable: bool = False
    downloadable: bool = True
    created_at: str = ""
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_identifier(self.id, label="artifact id")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported radio artifact schema version: {self.schema_version}"
            )
        windows_path = PureWindowsPath(self.relative_path)
        posix_path = PurePosixPath(self.relative_path)
        if (
            not self.relative_path
            or posix_path.is_absolute()
            or windows_path.is_absolute()
            or bool(windows_path.drive)
        ):
            raise ValueError("Artifact paths must be relative")
        if ".." in self.relative_path.replace("\\", "/").split("/"):
            raise ValueError("Artifact paths may not contain '..'")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RadioArtifact:
        return cls(
            schema_version=int(payload.get("schema_version", 0)),
            id=str(payload.get("id", "")),
            relative_path=str(payload.get("relative_path", "")),
            kind=str(payload.get("kind", "file")),
            mime_type=str(payload.get("mime_type", "application/octet-stream")),
            artifact_type=str(payload.get("artifact_type", "file")),
            role=str(payload.get("role", "output")),
            source_run_id=payload.get("source_run_id"),
            size=int(payload.get("size", 0)),
            previewable=bool(payload.get("previewable", False)),
            downloadable=bool(payload.get("downloadable", True)),
            created_at=str(payload.get("created_at", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "relative_path": self.relative_path,
            "kind": self.kind,
            "mime_type": self.mime_type,
            "artifact_type": self.artifact_type,
            "role": self.role,
            "source_run_id": self.source_run_id,
            "size": self.size,
            "previewable": self.previewable,
            "downloadable": self.downloadable,
            "created_at": self.created_at,
        }


@dataclass
class RadioRunManifest:
    """Durable state, provenance, and output index for one action run."""

    schema_version: int
    id: str
    workspace_id: str
    module_id: str
    action_id: str
    status: str
    command: list[str]
    cwd: str
    request: dict[str, Any]
    resolved_config: dict[str, Any]
    input_sources: list[dict[str, Any]]
    provenance: dict[str, Any]
    artifacts: list[RadioArtifact] = field(default_factory=list)
    progress: float = 0.0
    log_path: str = "run.log"
    created_at: str = ""
    started_at: str | None = None
    finished_at: str | None = None
    returncode: int | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported radio run schema version: {self.schema_version}"
            )
        self.id = _require_identifier(self.id, label="run id")
        self.workspace_id = _require_identifier(self.workspace_id, label="workspace id")
        self.module_id = _require_identifier(self.module_id, label="module id")
        self.action_id = _require_identifier(self.action_id, label="action id")
        if self.status not in RUN_STATUSES:
            raise ValueError(f"Unknown radio run status: {self.status!r}")
        self.progress = float(self.progress)
        if not 0.0 <= self.progress <= 1.0:
            raise ValueError("run progress must be between 0 and 1")
        if self.log_path != "run.log":
            raise ValueError("run log_path must be 'run.log'")
        if not isinstance(self.command, list) or not all(
            isinstance(item, str) for item in self.command
        ):
            raise TypeError("command must be an argument-token list")
        self.request = _json_mapping(self.request, label="request")
        self.resolved_config = _json_mapping(
            self.resolved_config, label="resolved_config"
        )
        self.provenance = _json_mapping(self.provenance, label="provenance")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RadioRunManifest:
        return cls(
            schema_version=int(payload.get("schema_version", 0)),
            id=str(payload.get("id", "")),
            workspace_id=str(payload.get("workspace_id", "")),
            module_id=str(payload.get("module_id", "")),
            action_id=str(payload.get("action_id", "")),
            status=str(payload.get("status", "")),
            command=_string_list(payload.get("command"), label="command"),
            cwd=str(payload.get("cwd", "")),
            request=_json_mapping(payload.get("request"), label="request"),
            resolved_config=_json_mapping(
                payload.get("resolved_config"), label="resolved_config"
            ),
            input_sources=list(payload.get("input_sources") or []),
            provenance=_json_mapping(payload.get("provenance"), label="provenance"),
            artifacts=[
                RadioArtifact.from_dict(item) for item in payload.get("artifacts", [])
            ],
            progress=float(payload.get("progress", 0.0)),
            log_path=str(payload.get("log_path", "run.log")),
            created_at=str(payload.get("created_at", "")),
            started_at=payload.get("started_at"),
            finished_at=payload.get("finished_at"),
            returncode=payload.get("returncode"),
            error=payload.get("error"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "workspace_id": self.workspace_id,
            "module_id": self.module_id,
            "action_id": self.action_id,
            "status": self.status,
            "command": list(self.command),
            "cwd": self.cwd,
            "request": dict(self.request),
            "resolved_config": dict(self.resolved_config),
            "input_sources": list(self.input_sources),
            "provenance": dict(self.provenance),
            "artifacts": [item.to_dict() for item in self.artifacts],
            "progress": self.progress,
            "log_path": self.log_path,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "returncode": self.returncode,
            "error": self.error,
        }


__all__ = [
    "RUN_STATUSES",
    "SCHEMA_VERSION",
    "RadioActionSpec",
    "RadioArtifact",
    "RadioModuleSpec",
    "RadioRunManifest",
    "RadioWorkspace",
]
