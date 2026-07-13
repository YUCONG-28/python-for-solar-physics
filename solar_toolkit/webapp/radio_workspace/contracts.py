"""Versioned data contracts for the modular radio workspace."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, ClassVar

from .figure_media import (
    MAX_FIGURE_DIMENSION,
    MAX_FIGURE_LAYERS,
    MAX_FIGURE_PIXELS,
)

SCHEMA_VERSION = 1
FIGURE_SCHEMA_VERSION = 1
UI_LAYOUT_VERSION = 2
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


def _json_list(value: Any, *, label: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"{label} must be a JSON array")
    return list(value)


def _finite_number(value: Any, *, label: str) -> float:
    number = float(value)
    if number != number or number in {float("inf"), float("-inf")}:
        raise ValueError(f"{label} must be finite")
    return number


def _figure_version(payload: dict[str, Any]) -> int:
    return int(payload.get("figure_schema_version", payload.get("schema_version", 0)))


def _require_figure_version(value: Any) -> int:
    version = int(value)
    if version != FIGURE_SCHEMA_VERSION:
        raise ValueError(f"Unsupported radio figure schema version: {version}")
    return version


def _validate_relative_path(value: str, *, label: str) -> str:
    normalized = str(value).strip()
    windows_path = PureWindowsPath(normalized)
    posix_path = PurePosixPath(normalized)
    if (
        not normalized
        or posix_path.is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive)
    ):
        raise ValueError(f"{label} must be relative")
    if ".." in normalized.replace("\\", "/").split("/"):
        raise ValueError(f"{label} may not contain '..'")
    return normalized.replace("\\", "/")


def _canonical_utc_time(value: Any, *, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} is required")
    if text.endswith(("Z", "z")):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO-8601 time") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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
    ui_layout_version: int = UI_LAYOUT_VERSION

    CURRENT_SCHEMA_VERSION: ClassVar[int] = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if int(self.schema_version) != SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported radio workspace schema version: {self.schema_version}"
            )
        self.id = _require_identifier(self.id, label="workspace id")
        self.name = str(self.name).strip() or "Radio Workspace"
        self.ui_layout_version = int(self.ui_layout_version)
        if not 1 <= self.ui_layout_version <= UI_LAYOUT_VERSION:
            raise ValueError(
                f"Unsupported radio UI layout version: {self.ui_layout_version}"
            )
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
            ui_layout_version=payload.get("ui_layout_version", 1),
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
            "ui_layout_version": self.ui_layout_version,
        }


@dataclass
class RadioFigureTimeline:
    """One UTC timeline shared by every time-aware layer in a figure."""

    mode: str = "still"
    selected_time_iso: str | None = None
    start_time_iso: str | None = None
    end_time_iso: str | None = None
    sample_interval_s: float = 1.0
    playback_fps: float = 12.0
    animation_format: str = "mp4"

    def __post_init__(self) -> None:
        self.mode = str(self.mode).strip().casefold()
        if self.mode not in {"still", "sequence"}:
            raise ValueError(f"Unknown radio figure timeline mode: {self.mode!r}")
        for attr in ("selected_time_iso", "start_time_iso", "end_time_iso"):
            value = getattr(self, attr)
            setattr(self, attr, str(value).strip() if value not in (None, "") else None)
        self.sample_interval_s = _finite_number(
            self.sample_interval_s, label="sample_interval_s"
        )
        self.playback_fps = _finite_number(self.playback_fps, label="playback_fps")
        if self.sample_interval_s <= 0:
            raise ValueError("sample_interval_s must be greater than zero")
        if self.playback_fps <= 0:
            raise ValueError("playback_fps must be greater than zero")
        self.animation_format = str(self.animation_format or "mp4").strip().casefold()
        if self.animation_format not in {"mp4", "webm"}:
            raise ValueError("animation_format must be 'mp4' or 'webm'")

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> RadioFigureTimeline:
        value = _json_mapping(payload, label="timeline")
        return cls(
            mode=value.get("mode", "still"),
            selected_time_iso=value.get("selected_time_iso"),
            start_time_iso=value.get("start_time_iso"),
            end_time_iso=value.get("end_time_iso"),
            sample_interval_s=value.get("sample_interval_s", 1.0),
            playback_fps=value.get("playback_fps", 12.0),
            animation_format=value.get("animation_format", value.get("format", "mp4")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "selected_time_iso": self.selected_time_iso,
            "start_time_iso": self.start_time_iso,
            "end_time_iso": self.end_time_iso,
            "sample_interval_s": self.sample_interval_s,
            "playback_fps": self.playback_fps,
            "animation_format": self.animation_format,
        }


@dataclass
class RadioFigureTemporalBinding:
    """Describe how one visual source maps onto the shared UTC timeline."""

    kind: str = "unknown"
    time_iso: str | None = None
    times_iso: list[str] = field(default_factory=list)
    samples: list[dict[str, Any]] = field(default_factory=list)
    coverage_segments: list[dict[str, Any]] = field(default_factory=list)
    tolerance_s: float | None = None
    fallback: str = "none"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.kind = str(self.kind).strip().casefold()
        if self.kind not in {
            "unknown",
            "timeless",
            "fixed",
            "series",
            "spectrogram",
        }:
            raise ValueError(f"Unknown temporal binding kind: {self.kind!r}")
        self.time_iso = (
            str(self.time_iso).strip() if self.time_iso not in (None, "") else None
        )
        self.times_iso = [
            str(item).strip() for item in self.times_iso if str(item).strip()
        ]
        normalized_samples: list[dict[str, Any]] = []
        for raw in self.samples:
            if not isinstance(raw, dict):
                raise TypeError("temporal samples must be JSON objects")
            sample = dict(raw)
            time_iso = sample.get("time_iso")
            if time_iso in (None, ""):
                raise ValueError("temporal samples require time_iso")
            sample["time_iso"] = str(time_iso).strip()
            normalized_samples.append(sample)
        if not normalized_samples:
            normalized_samples = [{"time_iso": item} for item in self.times_iso]
        self.samples = normalized_samples
        self.times_iso = [str(item["time_iso"]) for item in self.samples]
        normalized_segments: list[dict[str, Any]] = []
        for raw in self.coverage_segments:
            if not isinstance(raw, dict):
                raise TypeError("coverage_segments entries must be JSON objects")
            segment = dict(raw)
            start = segment.get(
                "start_time_iso", segment.get("start_iso", segment.get("start"))
            )
            end = segment.get(
                "end_time_iso", segment.get("end_iso", segment.get("end"))
            )
            if start in (None, "") or end in (None, ""):
                raise ValueError("coverage segments require start_iso and end_iso")
            segment["start_time_iso"] = str(start).strip()
            segment["end_time_iso"] = str(end).strip()
            segment.pop("start_iso", None)
            segment.pop("end_iso", None)
            segment.pop("start", None)
            segment.pop("end", None)
            normalized_segments.append(segment)
        self.coverage_segments = normalized_segments
        if self.tolerance_s is not None:
            self.tolerance_s = _finite_number(
                self.tolerance_s, label="temporal tolerance_s"
            )
            if self.tolerance_s < 0:
                raise ValueError("temporal tolerance_s must be zero or greater")
        self.fallback = str(self.fallback or "none").strip().casefold()
        if self.fallback not in {
            "none",
            "hold_nearest",
            "hold_last",
            "out_of_range_note",
        }:
            raise ValueError(f"Unknown temporal fallback: {self.fallback!r}")
        self.metadata = _json_mapping(self.metadata, label="temporal metadata")
        _reject_unsafe_figure_source_keys(self.samples)
        _reject_unsafe_figure_source_keys(self.coverage_segments)
        _reject_unsafe_figure_source_keys(self.metadata)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> RadioFigureTemporalBinding:
        value = _json_mapping(payload, label="temporal_binding")
        return cls(
            kind=value.get("kind", "unknown"),
            time_iso=value.get("time_iso"),
            times_iso=_string_list(value.get("times_iso"), label="times_iso"),
            samples=[
                dict(item) for item in _json_list(value.get("samples"), label="samples")
            ],
            coverage_segments=[
                dict(item)
                for item in _json_list(
                    value.get("coverage_segments"), label="coverage_segments"
                )
            ],
            tolerance_s=value.get("tolerance_s"),
            fallback=value.get("fallback_policy", value.get("fallback", "none")),
            metadata=_json_mapping(value.get("metadata"), label="temporal metadata"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "time_iso": self.time_iso,
            "samples": [dict(item) for item in self.samples],
            "coverage_segments": [dict(item) for item in self.coverage_segments],
            "tolerance_s": self.tolerance_s,
            "fallback_policy": self.fallback,
            "metadata": dict(self.metadata),
        }


_UNSAFE_FIGURE_SOURCE_KEYS = frozenset(
    {"path", "url", "uri", "src", "href", "data", "data_url", "file_path"}
)
_FIGURE_FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")


def _reject_unsafe_figure_source_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized_key = str(key).strip().casefold().replace("-", "_")
            if (
                normalized_key in _UNSAFE_FIGURE_SOURCE_KEYS
                or "path" in normalized_key
                or normalized_key.endswith(("_url", "_uri"))
            ):
                raise ValueError(f"Figure sources may not contain {key!r}")
            _reject_unsafe_figure_source_keys(item)
    elif isinstance(value, list):
        for item in value:
            _reject_unsafe_figure_source_keys(item)


def _canonical_figure_reference(
    source: dict[str, Any], *, allow_temporal_fields: bool
) -> dict[str, Any]:
    """Return only the controlled identifier fields persisted for one source."""

    _reject_unsafe_figure_source_keys(source)
    source_type = str(source.get("type", source.get("kind", ""))).strip().casefold()
    if source_type == "artifact":
        canonical = {
            "type": "artifact",
            "run_id": _require_identifier(
                str(source.get("run_id", "")), label="source run id"
            ),
            "artifact_id": _require_identifier(
                str(source.get("artifact_id", "")), label="source artifact id"
            ),
        }
    elif source_type == "preview":
        canonical = {
            "type": "preview",
            "preview_id": _require_identifier(
                str(source.get("preview_id", "")), label="source preview id"
            ),
        }
    else:
        raise ValueError(f"Unknown or nested radio figure source: {source_type!r}")

    fingerprint = str(source.get("fingerprint", "")).strip().casefold()
    if fingerprint:
        if not _FIGURE_FINGERPRINT_RE.fullmatch(fingerprint):
            raise ValueError("Figure source fingerprint must be a SHA-256 digest")
        canonical["fingerprint"] = fingerprint

    if allow_temporal_fields:
        time_iso = source.get("time_iso", source.get("observed_at"))
        if time_iso not in (None, ""):
            canonical["time_iso"] = _canonical_utc_time(
                time_iso, label="series source time_iso"
            )
        if source.get("frame_index") is not None:
            frame_index = int(source["frame_index"])
            if frame_index < 0:
                raise ValueError("Series source frame_index must be zero or greater")
            canonical["frame_index"] = frame_index
    return canonical


def _canonical_figure_source(source: dict[str, Any]) -> dict[str, Any]:
    """Accept compatible source payloads but persist only controlled references."""

    _reject_unsafe_figure_source_keys(source)
    source_type = str(source.get("type", source.get("kind", ""))).strip().casefold()
    if source_type == "series":
        frames = source.get("frames")
        if not isinstance(frames, list) or not frames:
            raise ValueError("A figure series source requires a non-empty frames array")
        canonical_frames: list[dict[str, Any]] = []
        for frame in frames:
            if not isinstance(frame, dict):
                raise TypeError("Figure series frames must be JSON objects")
            canonical_frames.append(
                _canonical_figure_reference(frame, allow_temporal_fields=True)
            )
        return {"type": "series", "frames": canonical_frames}
    return _canonical_figure_reference(source, allow_temporal_fields=False)


@dataclass
class RadioFigureLayer:
    """One independently positioned, cropped, and time-bound figure layer."""

    id: str
    source: dict[str, Any]
    temporal_binding: RadioFigureTemporalBinding
    title: str = ""
    frame: dict[str, Any] = field(default_factory=dict)
    transform: dict[str, Any] = field(default_factory=dict)
    crop: dict[str, Any] = field(default_factory=dict)
    z_index: int = 0
    visible: bool = True
    opacity: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.id = _require_identifier(self.id, label="figure layer id")
        self.source = _json_mapping(self.source, label="figure source")
        self.source = _canonical_figure_source(self.source)
        if not isinstance(self.temporal_binding, RadioFigureTemporalBinding):
            self.temporal_binding = RadioFigureTemporalBinding.from_dict(
                self.temporal_binding
            )
        source_type = str(
            self.source.get("type", self.source.get("kind", ""))
        ).casefold()
        if source_type == "series":
            if self.temporal_binding.kind != "series":
                raise ValueError(
                    "A series figure source requires a series temporal binding"
                )
            frames = [dict(item) for item in self.source.get("frames", [])]
            frame_times: list[str] = []
            for index, frame_item in enumerate(frames):
                supplied_index = frame_item.get("frame_index")
                if supplied_index is not None and int(supplied_index) != index:
                    raise ValueError(
                        "Series source frame_index values must be contiguous from zero"
                    )
                frame_time = frame_item.get("time_iso", frame_item.get("observed_at"))
                canonical_time = _canonical_utc_time(
                    frame_time, label=f"series frame {index} time_iso"
                )
                frame_item.pop("observed_at", None)
                frame_item["time_iso"] = canonical_time
                frame_item["frame_index"] = index
                frames[index] = frame_item
                frame_times.append(canonical_time)
            if len(frame_times) != len(set(frame_times)):
                raise ValueError("Series source frame times must be unique")

            samples = [dict(item) for item in self.temporal_binding.samples]
            if samples and len(samples) != len(frames):
                raise ValueError(
                    "Series source frames and temporal samples must have equal length"
                )
            if samples:
                for index, sample in enumerate(samples):
                    supplied_index = sample.get("frame_index")
                    if supplied_index is not None and int(supplied_index) != index:
                        raise ValueError(
                            "Temporal sample frame_index values must be contiguous from zero"
                        )
                    sample_time = _canonical_utc_time(
                        sample.get("time_iso"),
                        label=f"temporal sample {index} time_iso",
                    )
                    if sample_time != frame_times[index]:
                        raise ValueError(
                            "Series source frame times must match temporal samples"
                        )
            samples = [
                {"time_iso": value, "frame_index": index}
                for index, value in enumerate(frame_times)
            ]
            self.source["frames"] = frames
            self.temporal_binding.samples = samples
            self.temporal_binding.times_iso = list(frame_times)
        elif self.temporal_binding.kind == "series":
            raise ValueError(
                "A series temporal binding requires a controlled series source"
            )
        self.title = str(self.title)
        self.frame = _json_mapping(self.frame, label="figure frame")
        self.transform = _json_mapping(self.transform, label="figure transform")
        self.crop = _json_mapping(self.crop, label="figure crop")
        self.z_index = int(self.z_index)
        self.visible = bool(self.visible)
        self.opacity = _finite_number(self.opacity, label="figure layer opacity")
        if not 0 <= self.opacity <= 1:
            raise ValueError("figure layer opacity must be between zero and one")
        self.metadata = _json_mapping(self.metadata, label="figure layer metadata")
        _reject_unsafe_figure_source_keys(self.metadata)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RadioFigureLayer:
        value = _json_mapping(payload, label="figure layer")
        return cls(
            id=str(value.get("id", "")),
            source=_json_mapping(value.get("source"), label="figure source"),
            temporal_binding=RadioFigureTemporalBinding.from_dict(
                value.get("temporal_binding")
            ),
            title=str(value.get("title", "")),
            frame=_json_mapping(value.get("frame"), label="figure frame"),
            transform=_json_mapping(value.get("transform"), label="figure transform"),
            crop=_json_mapping(value.get("crop"), label="figure crop"),
            z_index=value.get("z_index", 0),
            visible=bool(value.get("visible", True)),
            opacity=value.get("opacity", 1.0),
            metadata=_json_mapping(value.get("metadata"), label="figure metadata"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "source": dict(self.source),
            "temporal_binding": self.temporal_binding.to_dict(),
            "frame": dict(self.frame),
            "transform": dict(self.transform),
            "crop": dict(self.crop),
            "z_index": self.z_index,
            "visible": self.visible,
            "opacity": self.opacity,
            "metadata": dict(self.metadata),
        }


@dataclass
class RadioFigureDraft:
    """The single mutable Figure Studio draft persisted by one workspace."""

    figure_schema_version: int
    workspace_id: str
    id: str
    mode: str
    canvas: dict[str, Any]
    timeline: RadioFigureTimeline
    layers: list[RadioFigureLayer] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    name: str = "Figure Draft"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.figure_schema_version = _require_figure_version(self.figure_schema_version)
        self.workspace_id = _require_identifier(self.workspace_id, label="workspace id")
        self.id = _require_identifier(self.id or "active", label="figure draft id")
        self.mode = str(self.mode).strip().casefold()
        if self.mode not in {"single", "mosaic"}:
            raise ValueError(f"Unknown radio figure mode: {self.mode!r}")
        self.canvas = _json_mapping(self.canvas, label="figure canvas")
        width = int(self.canvas.get("width", 1600))
        height = int(self.canvas.get("height", 1200))
        export_scale = _finite_number(
            self.canvas.get("export_scale", 1.0), label="canvas export_scale"
        )
        if width <= 0 or height <= 0 or export_scale <= 0:
            raise ValueError(
                "Figure canvas dimensions and export_scale must be positive"
            )
        if export_scale > 4:
            raise ValueError("Figure canvas export_scale may not exceed 4")
        export_width = round(width * export_scale)
        export_height = round(height * export_scale)
        if export_width > MAX_FIGURE_DIMENSION or export_height > MAX_FIGURE_DIMENSION:
            raise ValueError(
                f"Exported figure dimensions may not exceed {MAX_FIGURE_DIMENSION} pixels"
            )
        if export_width * export_height > MAX_FIGURE_PIXELS:
            raise ValueError(
                f"Exported figure area may not exceed {MAX_FIGURE_PIXELS} pixels"
            )
        self.canvas.update(
            {
                "width": width,
                "height": height,
                "background": str(self.canvas.get("background", "#ffffff")),
                "export_scale": export_scale,
            }
        )
        if not isinstance(self.timeline, RadioFigureTimeline):
            self.timeline = RadioFigureTimeline.from_dict(self.timeline)
        self.layers = [
            (
                item
                if isinstance(item, RadioFigureLayer)
                else RadioFigureLayer.from_dict(item)
            )
            for item in self.layers
        ]
        if len(self.layers) > MAX_FIGURE_LAYERS:
            raise ValueError(
                f"A radio figure may contain no more than {MAX_FIGURE_LAYERS} layers"
            )
        layer_ids = [item.id for item in self.layers]
        if len(layer_ids) != len(set(layer_ids)):
            raise ValueError("Radio figure layer ids must be unique")
        self.created_at = str(self.created_at)
        self.updated_at = str(self.updated_at)
        self.name = str(self.name).strip() or "Figure Draft"
        self.metadata = _json_mapping(self.metadata, label="figure draft metadata")
        _reject_unsafe_figure_source_keys(self.metadata)

    @classmethod
    def empty(cls, workspace_id: str) -> RadioFigureDraft:
        return cls(
            figure_schema_version=FIGURE_SCHEMA_VERSION,
            workspace_id=workspace_id,
            id="active",
            name="Figure Draft",
            mode="mosaic",
            canvas={
                "width": 1600,
                "height": 1200,
                "background": "#ffffff",
                "export_scale": 1.0,
            },
            timeline=RadioFigureTimeline(),
            layers=[],
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RadioFigureDraft:
        value = _json_mapping(payload, label="figure draft")
        return cls(
            figure_schema_version=_figure_version(value),
            workspace_id=str(value.get("workspace_id", "")),
            id=str(value.get("id", "active")),
            name=str(value.get("name", "Figure Draft")),
            mode=str(value.get("mode", "mosaic")),
            canvas=_json_mapping(value.get("canvas"), label="figure canvas"),
            timeline=RadioFigureTimeline.from_dict(value.get("timeline")),
            layers=[
                RadioFigureLayer.from_dict(item)
                for item in _json_list(value.get("layers"), label="figure layers")
            ],
            created_at=str(value.get("created_at", "")),
            updated_at=str(value.get("updated_at", "")),
            metadata=_json_mapping(value.get("metadata"), label="figure metadata"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "figure_schema_version": self.figure_schema_version,
            "workspace_id": self.workspace_id,
            "id": self.id,
            "name": self.name,
            "mode": self.mode,
            "canvas": dict(self.canvas),
            "timeline": self.timeline.to_dict(),
            "layers": [item.to_dict() for item in self.layers],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }


@dataclass
class RadioFigurePreflight:
    """Time-coverage decision returned immediately before figure export."""

    figure_schema_version: int
    workspace_id: str
    status: str
    preflight_revision: str
    timeline: dict[str, Any]
    ready: bool = False
    sample_times_iso: list[str] = field(default_factory=list)
    layers: list[dict[str, Any]] = field(default_factory=list)
    missing_count: int = 0
    missing_intervals: list[dict[str, Any]] = field(default_factory=list)
    global_strict_missing_count: int = 0
    global_strict_missing_intervals: list[dict[str, Any]] = field(default_factory=list)
    common_valid_intervals: list[dict[str, Any]] = field(default_factory=list)
    common_valid_time: str | None = None
    longest_common_interval: dict[str, Any] | None = None
    recommendation: dict[str, Any] | None = None
    source_fingerprints: dict[str, Any] = field(default_factory=dict)
    issues: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.figure_schema_version = _require_figure_version(self.figure_schema_version)
        self.workspace_id = _require_identifier(self.workspace_id, label="workspace id")
        self.status = str(self.status).strip().casefold()
        if self.status not in {"ready", "blocked"}:
            raise ValueError(f"Unknown figure preflight status: {self.status!r}")
        self.ready = bool(self.ready)
        if self.ready != (self.status == "ready"):
            raise ValueError("figure preflight ready flag does not match status")
        self.preflight_revision = str(self.preflight_revision).strip()
        if not self.preflight_revision:
            raise ValueError("preflight_revision is required")
        self.timeline = _json_mapping(self.timeline, label="preflight timeline")
        self.sample_times_iso = [str(item) for item in self.sample_times_iso]
        self.layers = [dict(item) for item in self.layers]
        self.missing_count = int(self.missing_count)
        if self.missing_count < 0:
            raise ValueError("missing_count must be zero or greater")
        self.missing_intervals = [dict(item) for item in self.missing_intervals]
        self.global_strict_missing_count = int(self.global_strict_missing_count)
        if self.global_strict_missing_count < 0:
            raise ValueError("global_strict_missing_count must be zero or greater")
        self.global_strict_missing_intervals = [
            dict(item) for item in self.global_strict_missing_intervals
        ]
        self.common_valid_intervals = [
            dict(item) for item in self.common_valid_intervals
        ]
        if self.longest_common_interval is not None:
            self.longest_common_interval = _json_mapping(
                self.longest_common_interval, label="longest_common_interval"
            )
        if self.recommendation is not None:
            self.recommendation = _json_mapping(
                self.recommendation, label="preflight recommendation"
            )
        self.source_fingerprints = _json_mapping(
            self.source_fingerprints, label="source_fingerprints"
        )
        self.issues = [dict(item) for item in self.issues]
        self.warnings = [dict(item) for item in self.warnings]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RadioFigurePreflight:
        value = _json_mapping(payload, label="figure preflight")
        return cls(
            figure_schema_version=_figure_version(value),
            workspace_id=str(value.get("workspace_id", "")),
            status=str(value.get("status", "")),
            preflight_revision=str(value.get("preflight_revision", "")),
            timeline=_json_mapping(value.get("timeline"), label="timeline"),
            ready=bool(value.get("ready", value.get("status") == "ready")),
            sample_times_iso=_string_list(
                value.get("sample_times_iso"), label="sample_times_iso"
            ),
            layers=[
                dict(item)
                for item in _json_list(value.get("layers"), label="preflight layers")
            ],
            missing_count=value.get(
                "missing_count", value.get("global_missing_count", 0)
            ),
            missing_intervals=[
                dict(item)
                for item in _json_list(
                    value.get(
                        "missing_intervals", value.get("global_missing_intervals")
                    ),
                    label="missing_intervals",
                )
            ],
            global_strict_missing_count=value.get("global_strict_missing_count", 0),
            global_strict_missing_intervals=[
                dict(item)
                for item in _json_list(
                    value.get("global_strict_missing_intervals"),
                    label="global_strict_missing_intervals",
                )
            ],
            common_valid_intervals=[
                dict(item)
                for item in _json_list(
                    value.get("common_valid_intervals"),
                    label="common_valid_intervals",
                )
            ],
            common_valid_time=value.get(
                "common_valid_time", value.get("common_valid_time_iso")
            ),
            longest_common_interval=value.get("longest_common_interval"),
            recommendation=value.get("recommendation"),
            source_fingerprints=_json_mapping(
                value.get("source_fingerprints"), label="source_fingerprints"
            ),
            issues=[
                dict(item)
                for item in _json_list(value.get("issues"), label="preflight issues")
            ],
            warnings=[
                dict(item)
                for item in _json_list(
                    value.get("warnings"), label="preflight warnings"
                )
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "figure_schema_version": self.figure_schema_version,
            "workspace_id": self.workspace_id,
            "status": self.status,
            "ready": self.ready,
            "preflight_revision": self.preflight_revision,
            "timeline": dict(self.timeline),
            "sample_times_iso": list(self.sample_times_iso),
            "layers": [dict(item) for item in self.layers],
            "missing_count": self.missing_count,
            "global_missing_count": self.missing_count,
            "missing_intervals": [dict(item) for item in self.missing_intervals],
            "global_missing_intervals": [dict(item) for item in self.missing_intervals],
            "global_strict_missing_count": self.global_strict_missing_count,
            "global_strict_missing_intervals": [
                dict(item) for item in self.global_strict_missing_intervals
            ],
            "common_valid_intervals": [
                dict(item) for item in self.common_valid_intervals
            ],
            "common_valid_time": self.common_valid_time,
            "common_valid_time_iso": self.common_valid_time,
            "longest_common_interval": (
                dict(self.longest_common_interval)
                if self.longest_common_interval is not None
                else None
            ),
            "recommendation": (
                dict(self.recommendation) if self.recommendation is not None else None
            ),
            "source_fingerprints": dict(self.source_fingerprints),
            "issues": [dict(item) for item in self.issues],
            "warnings": [dict(item) for item in self.warnings],
        }


@dataclass
class RadioFigureExport:
    """Immutable index record for one validated Figure Studio export."""

    figure_schema_version: int
    id: str
    workspace_id: str
    mime_type: str
    output_path: str
    thumbnail_path: str
    preflight_revision: str
    sha256: str
    size: int
    width: int
    height: int
    frame_count: int
    created_at: str
    duration_s: float | None = None
    mode: str = "still"

    def __post_init__(self) -> None:
        self.figure_schema_version = _require_figure_version(self.figure_schema_version)
        self.id = _require_identifier(self.id, label="figure export id")
        self.workspace_id = _require_identifier(self.workspace_id, label="workspace id")
        self.mime_type = str(self.mime_type).strip().casefold()
        if self.mime_type not in {"image/png", "video/mp4", "video/webm"}:
            raise ValueError(f"Unsupported figure export MIME type: {self.mime_type}")
        self.output_path = _validate_relative_path(
            self.output_path, label="figure output_path"
        )
        self.thumbnail_path = _validate_relative_path(
            self.thumbnail_path, label="figure thumbnail_path"
        )
        self.preflight_revision = str(self.preflight_revision).strip()
        if not self.preflight_revision:
            raise ValueError("preflight_revision is required")
        self.sha256 = str(self.sha256).strip().casefold()
        if not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            raise ValueError("figure export sha256 must be a hexadecimal digest")
        self.size = int(self.size)
        self.width = int(self.width)
        self.height = int(self.height)
        self.frame_count = int(self.frame_count)
        if min(self.size, self.width, self.height, self.frame_count) <= 0:
            raise ValueError(
                "Figure export dimensions, size, and frames must be positive"
            )
        if self.duration_s is not None:
            self.duration_s = _finite_number(self.duration_s, label="figure duration_s")
            if self.duration_s < 0:
                raise ValueError("figure duration_s must be zero or greater")
        self.mode = str(self.mode).strip().casefold()
        if self.mode not in {"still", "sequence"}:
            raise ValueError(f"Unknown figure export mode: {self.mode!r}")
        self.created_at = str(self.created_at)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RadioFigureExport:
        value = _json_mapping(payload, label="figure export")
        return cls(
            figure_schema_version=_figure_version(value),
            id=str(value.get("id", "")),
            workspace_id=str(value.get("workspace_id", "")),
            mime_type=str(value.get("mime_type", "")),
            output_path=str(value.get("output_path", "")),
            thumbnail_path=str(value.get("thumbnail_path", "")),
            preflight_revision=str(value.get("preflight_revision", "")),
            sha256=str(value.get("sha256", "")),
            size=value.get("size", 0),
            width=value.get("width", 0),
            height=value.get("height", 0),
            frame_count=value.get("frame_count", 0),
            created_at=str(value.get("created_at", "")),
            duration_s=value.get("duration_s"),
            mode=str(value.get("mode", "still")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "figure_schema_version": self.figure_schema_version,
            "id": self.id,
            "workspace_id": self.workspace_id,
            "mime_type": self.mime_type,
            "output_path": self.output_path,
            "thumbnail_path": self.thumbnail_path,
            "preflight_revision": self.preflight_revision,
            "sha256": self.sha256,
            "size": self.size,
            "width": self.width,
            "height": self.height,
            "frame_count": self.frame_count,
            "duration_s": self.duration_s,
            "mode": self.mode,
            "created_at": self.created_at,
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
    "FIGURE_SCHEMA_VERSION",
    "RUN_STATUSES",
    "SCHEMA_VERSION",
    "UI_LAYOUT_VERSION",
    "RadioActionSpec",
    "RadioArtifact",
    "RadioFigureDraft",
    "RadioFigureExport",
    "RadioFigureLayer",
    "RadioFigurePreflight",
    "RadioFigureTemporalBinding",
    "RadioFigureTimeline",
    "RadioModuleSpec",
    "RadioRunManifest",
    "RadioWorkspace",
]
