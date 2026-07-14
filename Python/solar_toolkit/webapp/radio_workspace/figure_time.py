"""UTC timeline matching and export preflight for Radio Figure Studio.

The functions in this module deliberately operate on JSON-shaped mappings instead
of workspace contract classes.  This keeps the scientific time policy reusable by
the HTTP API, tests, and future compatibility facades without introducing a
dependency on persistence or Flask.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

FIGURE_TIME_MODEL_VERSION = 1
MAX_SEQUENCE_SAMPLES = 10_000
SPECTROGRAM_MERGE_GAP_SECONDS = 1.0

_UTC = timezone.utc
_TRANSIENT_REVISION_KEYS = frozenset(
    {"preflight", "preflight_revision", "last_preflight"}
)
_FALLBACKS_BY_KIND = {
    "unknown": frozenset({"none"}),
    "timeless": frozenset({"none"}),
    "fixed": frozenset({"none", "hold_nearest", "hold_last"}),
    "series": frozenset({"none", "hold_nearest", "hold_last"}),
    "spectrogram": frozenset({"none", "out_of_range_note"}),
}


class FigureTimeValidationError(ValueError):
    """Raised when a Figure Studio time contract is structurally invalid."""


@dataclass(frozen=True)
class _TimeRange:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise FigureTimeValidationError("Time range start must not exceed end")

    @property
    def duration_s(self) -> float:
        return (self.end - self.start).total_seconds()


def _as_mapping(value: Any, *, label: str) -> dict[str, Any]:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        value = value.to_dict()
    if not isinstance(value, Mapping):
        raise FigureTimeValidationError(f"{label} must be a JSON object")
    return dict(value)


def _parse_utc(value: Any, *, label: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            raise FigureTimeValidationError(f"{label} is required")
        if text.endswith(("Z", "z")):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise FigureTimeValidationError(
                f"{label} must be an ISO-8601 UTC timestamp"
            ) from exc
    if parsed.tzinfo is None:
        # HTML datetime-local controls omit an offset.  Figure Studio labels these
        # controls UTC, so naive values are interpreted as UTC rather than local time.
        parsed = parsed.replace(tzinfo=_UTC)
    return parsed.astimezone(_UTC)


def _format_utc(value: datetime) -> str:
    normalized = value.astimezone(_UTC)
    return normalized.isoformat(timespec="auto").replace("+00:00", "Z")


def _finite_number(value: Any, *, label: str, minimum: float | None = None) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise FigureTimeValidationError(f"{label} must be a number") from exc
    if not math.isfinite(number):
        raise FigureTimeValidationError(f"{label} must be finite")
    if minimum is not None and number < minimum:
        raise FigureTimeValidationError(f"{label} must be at least {minimum}")
    return number


def normalize_figure_timeline(timeline: Mapping[str, Any] | Any) -> dict[str, Any]:
    """Validate and normalize a still or sequence timeline to UTC JSON values."""

    payload = _as_mapping(timeline, label="timeline")
    mode = str(payload.get("mode", "still")).strip().lower()
    if mode == "still":
        selected = payload.get(
            "selected_time_iso", payload.get("selected_time", payload.get("time_iso"))
        )
        return {
            "mode": "still",
            "selected_time_iso": _format_utc(
                _parse_utc(selected, label="timeline.selected_time_iso")
            ),
        }
    if mode != "sequence":
        raise FigureTimeValidationError("timeline.mode must be 'still' or 'sequence'")

    start = _parse_utc(
        payload.get("start_time_iso", payload.get("start_time")),
        label="timeline.start_time_iso",
    )
    end = _parse_utc(
        payload.get("end_time_iso", payload.get("end_time")),
        label="timeline.end_time_iso",
    )
    if start > end:
        raise FigureTimeValidationError(
            "timeline.start_time_iso must not exceed timeline.end_time_iso"
        )
    interval = _finite_number(
        payload.get("sample_interval_s", 1.0),
        label="timeline.sample_interval_s",
        minimum=0.000001,
    )
    playback_fps = _finite_number(
        payload.get("playback_fps", 10.0),
        label="timeline.playback_fps",
        minimum=0.000001,
    )
    normalized = {
        "mode": "sequence",
        "start_time_iso": _format_utc(start),
        "end_time_iso": _format_utc(end),
        "sample_interval_s": interval,
        "playback_fps": playback_fps,
    }
    # Validate the hard frame limit while the field names are still available for a
    # useful error.  Sampling never appends a short, off-cadence terminal frame.
    _timeline_sample_datetimes(normalized)
    return normalized


def _timeline_sample_datetimes(timeline: Mapping[str, Any]) -> list[datetime]:
    mode = str(timeline["mode"])
    if mode == "still":
        return [
            _parse_utc(
                timeline["selected_time_iso"], label="timeline.selected_time_iso"
            )
        ]
    start = _parse_utc(timeline["start_time_iso"], label="timeline.start_time_iso")
    end = _parse_utc(timeline["end_time_iso"], label="timeline.end_time_iso")
    interval = float(timeline["sample_interval_s"])
    total_s = (end - start).total_seconds()
    frame_count = math.floor(total_s / interval + 1e-12) + 1
    if frame_count > MAX_SEQUENCE_SAMPLES:
        raise FigureTimeValidationError(
            f"timeline produces {frame_count} frames; maximum is "
            f"{MAX_SEQUENCE_SAMPLES}"
        )
    samples = [
        start + timedelta(seconds=index * interval) for index in range(frame_count)
    ]
    if len(set(samples)) != len(samples):
        raise FigureTimeValidationError(
            "timeline.sample_interval_s is below datetime resolution"
        )
    return samples


def timeline_sample_times(timeline: Mapping[str, Any] | Any) -> list[str]:
    """Return the exact UTC sample times used by a normalized export timeline."""

    normalized = normalize_figure_timeline(timeline)
    return [_format_utc(value) for value in _timeline_sample_datetimes(normalized)]


def _segment_range(segment: Any, *, index: int) -> _TimeRange:
    if isinstance(segment, Mapping):
        start_value = segment.get(
            "start_time_iso", segment.get("start", segment.get("start_iso"))
        )
        end_value = segment.get(
            "end_time_iso", segment.get("end", segment.get("end_iso"))
        )
    elif isinstance(segment, Sequence) and not isinstance(segment, (str, bytes)):
        if len(segment) != 2:
            raise FigureTimeValidationError(
                f"coverage segment {index} must contain start and end"
            )
        start_value, end_value = segment
    else:
        raise FigureTimeValidationError(
            f"coverage segment {index} must be an object or two-item array"
        )
    return _TimeRange(
        _parse_utc(start_value, label=f"coverage_segments[{index}].start_time_iso"),
        _parse_utc(end_value, label=f"coverage_segments[{index}].end_time_iso"),
    )


def _merge_ranges(
    ranges: Sequence[_TimeRange], *, maximum_gap_s: float = 0.0
) -> list[_TimeRange]:
    if not ranges:
        return []
    ordered = sorted(ranges, key=lambda item: (item.start, item.end))
    merged = [ordered[0]]
    for item in ordered[1:]:
        previous = merged[-1]
        gap_s = (item.start - previous.end).total_seconds()
        if gap_s <= maximum_gap_s:
            merged[-1] = _TimeRange(previous.start, max(previous.end, item.end))
        else:
            merged.append(item)
    return merged


def _ranges_to_json(ranges: Sequence[_TimeRange]) -> list[dict[str, str]]:
    return [
        {
            "start_time_iso": _format_utc(item.start),
            "end_time_iso": _format_utc(item.end),
        }
        for item in ranges
    ]


def merge_coverage_segments(
    segments: Sequence[Any], *, maximum_gap_s: float = SPECTROGRAM_MERGE_GAP_SECONDS
) -> list[dict[str, str]]:
    """Merge overlapping/adjacent real coverage, including gaps up to one second."""

    if not isinstance(segments, Sequence) or isinstance(segments, (str, bytes)):
        raise FigureTimeValidationError("coverage_segments must be a JSON array")
    gap = _finite_number(maximum_gap_s, label="maximum_gap_s", minimum=0.0)
    ranges = [_segment_range(item, index=index) for index, item in enumerate(segments)]
    return _ranges_to_json(_merge_ranges(ranges, maximum_gap_s=gap))


def _coverage_gaps(ranges: Sequence[_TimeRange]) -> list[_TimeRange]:
    return [
        _TimeRange(left.end, right.start)
        for left, right in zip(ranges, ranges[1:], strict=False)
        if right.start > left.end
    ]


def _normalize_fallback(value: Any) -> str:
    fallback = str(value or "none").strip().lower().replace("-", "_")
    aliases = {"": "none", "off": "none", "disabled": "none"}
    return aliases.get(fallback, fallback)


def _sample_time(sample: Any, *, index: int) -> tuple[datetime, dict[str, Any]]:
    if isinstance(sample, Mapping):
        payload = dict(sample)
        value = payload.get(
            "time_iso",
            payload.get(
                "observation_time_iso",
                payload.get("frame_time", payload.get("time")),
            ),
        )
        source = {
            key: _make_jsonable(item)
            for key, item in payload.items()
            if key not in {"time_iso", "observation_time_iso", "frame_time", "time"}
        }
    else:
        value = sample
        source = {}
    return _parse_utc(value, label=f"samples[{index}].time_iso"), source


def _series_samples(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_samples = payload.get(
        "samples", payload.get("times_iso", payload.get("frame_times_iso"))
    )
    if not isinstance(raw_samples, Sequence) or isinstance(raw_samples, (str, bytes)):
        raise FigureTimeValidationError("series.samples must be a non-empty JSON array")
    parsed = [_sample_time(item, index=index) for index, item in enumerate(raw_samples)]
    if not parsed:
        raise FigureTimeValidationError("series.samples must not be empty")
    parsed.sort(key=lambda item: item[0])
    timestamps = [item[0] for item in parsed]
    if len(timestamps) != len(set(timestamps)):
        raise FigureTimeValidationError("series.samples must have unique timestamps")
    return [{"time_iso": _format_utc(time), **source} for time, source in parsed]


def _default_series_tolerance(samples: Sequence[Mapping[str, Any]]) -> float:
    if len(samples) < 2:
        return 0.0
    times = [
        _parse_utc(item["time_iso"], label="series.samples.time_iso")
        for item in samples
    ]
    cadences = [
        (right - left).total_seconds()
        for left, right in zip(times, times[1:], strict=False)
    ]
    return max(1.0, statistics.median(cadences) / 2.0)


def normalize_temporal_binding(
    binding: Mapping[str, Any] | Any | None,
) -> dict[str, Any]:
    """Validate one layer binding and return a JSON-serializable UTC form."""

    if binding is None:
        payload: dict[str, Any] = {}
    else:
        payload = _as_mapping(binding, label="temporal_binding")
    raw_kind = str(payload.get("kind", payload.get("type", "unknown"))).strip().lower()
    kind = {"static": "timeless", "single": "fixed"}.get(raw_kind, raw_kind)
    if kind not in _FALLBACKS_BY_KIND:
        raise FigureTimeValidationError(f"Unknown temporal binding kind: {raw_kind!r}")
    fallback = _normalize_fallback(
        payload.get("fallback_policy", payload.get("fallback"))
    )
    if fallback not in _FALLBACKS_BY_KIND[kind]:
        allowed = ", ".join(sorted(_FALLBACKS_BY_KIND[kind]))
        raise FigureTimeValidationError(
            f"fallback_policy {fallback!r} is invalid for {kind}; allowed: {allowed}"
        )

    normalized: dict[str, Any] = {"kind": kind, "fallback_policy": fallback}
    if kind in {"unknown", "timeless"}:
        return normalized
    if kind == "fixed":
        value = payload.get(
            "time_iso",
            payload.get("observation_time_iso", payload.get("frame_time")),
        )
        normalized["time_iso"] = _format_utc(
            _parse_utc(value, label="temporal_binding.time_iso")
        )
        normalized["tolerance_s"] = _finite_number(
            payload.get("tolerance_s", 0.0),
            label="temporal_binding.tolerance_s",
            minimum=0.0,
        )
        return normalized
    if kind == "series":
        samples = _series_samples(payload)
        tolerance_value = payload.get("tolerance_s")
        tolerance = (
            _default_series_tolerance(samples)
            if tolerance_value is None
            else _finite_number(
                tolerance_value,
                label="temporal_binding.tolerance_s",
                minimum=0.0,
            )
        )
        normalized.update({"samples": samples, "tolerance_s": tolerance})
        return normalized

    raw_segments = payload.get(
        "coverage_segments",
        payload.get("coverage_intervals", payload.get("segments")),
    )
    if raw_segments is None:
        start = payload.get("coverage_start_iso", payload.get("start_time_iso"))
        end = payload.get("coverage_end_iso", payload.get("end_time_iso"))
        raw_segments = [[start, end]] if start is not None or end is not None else []
    merge_gap_s = _finite_number(
        payload.get("merge_gap_s", SPECTROGRAM_MERGE_GAP_SECONDS),
        label="temporal_binding.merge_gap_s",
        minimum=0.0,
    )
    if merge_gap_s > SPECTROGRAM_MERGE_GAP_SECONDS:
        raise FigureTimeValidationError(
            "spectrogram merge_gap_s cannot exceed 1 second"
        )
    segments = merge_coverage_segments(raw_segments, maximum_gap_s=merge_gap_s)
    if not segments:
        raise FigureTimeValidationError(
            "spectrogram.coverage_segments must not be empty"
        )
    ranges = [_segment_range(item, index=index) for index, item in enumerate(segments)]
    normalized.update(
        {
            "coverage_segments": segments,
            "coverage_gaps": _ranges_to_json(_coverage_gaps(ranges)),
            "merge_gap_s": merge_gap_s,
        }
    )
    return normalized


def _binding_ranges(binding: Mapping[str, Any]) -> list[_TimeRange] | None:
    kind = binding["kind"]
    if kind == "timeless":
        return None
    if kind == "unknown":
        return []
    if kind == "fixed":
        point = _parse_utc(binding["time_iso"], label="fixed.time_iso")
        tolerance = timedelta(seconds=float(binding["tolerance_s"]))
        return [_TimeRange(point - tolerance, point + tolerance)]
    if kind == "series":
        tolerance = timedelta(seconds=float(binding["tolerance_s"]))
        ranges = [
            _TimeRange(
                _parse_utc(item["time_iso"], label="series.samples.time_iso")
                - tolerance,
                _parse_utc(item["time_iso"], label="series.samples.time_iso")
                + tolerance,
            )
            for item in binding["samples"]
        ]
        return _merge_ranges(ranges)
    return [
        _segment_range(item, index=index)
        for index, item in enumerate(binding["coverage_segments"])
    ]


def _intersect_two(
    left: Sequence[_TimeRange], right: Sequence[_TimeRange]
) -> list[_TimeRange]:
    intersections: list[_TimeRange] = []
    left_index = 0
    right_index = 0
    while left_index < len(left) and right_index < len(right):
        left_item = left[left_index]
        right_item = right[right_index]
        start = max(left_item.start, right_item.start)
        end = min(left_item.end, right_item.end)
        if start <= end:
            intersections.append(_TimeRange(start, end))
        if left_item.end < right_item.end:
            left_index += 1
        else:
            right_index += 1
    return _merge_ranges(intersections)


def _common_ranges(
    bindings: Sequence[Mapping[str, Any]], *, constraint: _TimeRange | None
) -> list[_TimeRange]:
    common = [constraint] if constraint is not None else None
    for binding in bindings:
        ranges = _binding_ranges(binding)
        if ranges is None:
            continue
        if common is None:
            common = list(ranges)
        else:
            common = _intersect_two(common, ranges)
        if not common:
            return []
    if common is None:
        if constraint is None:
            raise AssertionError(
                "A time constraint is required for all-timeless layers"
            )
        return [constraint]
    return common


def _nearest_sample(
    samples: Sequence[Mapping[str, Any]], requested: datetime
) -> tuple[datetime, Mapping[str, Any]]:
    candidates = [
        (
            _parse_utc(item["time_iso"], label="series.samples.time_iso"),
            item,
        )
        for item in samples
    ]
    return min(
        candidates,
        key=lambda item: (abs((item[0] - requested).total_seconds()), item[0]),
    )


def _last_sample(
    samples: Sequence[Mapping[str, Any]], requested: datetime
) -> tuple[datetime, Mapping[str, Any]] | None:
    candidates = [
        (
            _parse_utc(item["time_iso"], label="series.samples.time_iso"),
            item,
        )
        for item in samples
        if _parse_utc(item["time_iso"], label="series.samples.time_iso") <= requested
    ]
    return max(candidates, key=lambda item: item[0]) if candidates else None


def _source_fields(sample: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in sample.items() if key != "time_iso"}


def _evaluate_binding(
    binding: Mapping[str, Any], requested: datetime
) -> dict[str, Any]:
    requested_iso = _format_utc(requested)
    kind = binding["kind"]
    fallback = binding["fallback_policy"]
    base: dict[str, Any] = {
        "requested_time_iso": requested_iso,
        "strict_match": False,
        "resolved": False,
        "fallback_applied": None,
    }
    if kind == "unknown":
        return {**base, "reason": "time_classification_required"}
    if kind == "timeless":
        return {
            **base,
            "strict_match": True,
            "resolved": True,
            "reason": None,
        }
    if kind in {"fixed", "series"}:
        samples: list[dict[str, Any]]
        if kind == "fixed":
            samples = [{"time_iso": binding["time_iso"]}]
        else:
            samples = list(binding["samples"])
        source_time, source = _nearest_sample(samples, requested)
        delta_s = (source_time - requested).total_seconds()
        strict = abs(delta_s) <= float(binding["tolerance_s"]) + 1e-9
        selected_time = source_time
        selected_source: Mapping[str, Any] = source
        fallback_applied: str | None = None
        resolved = strict
        if not strict and fallback == "hold_nearest":
            resolved = True
            fallback_applied = fallback
        elif not strict and fallback == "hold_last":
            held = _last_sample(samples, requested)
            if held is not None:
                selected_time, selected_source = held
                delta_s = (selected_time - requested).total_seconds()
                resolved = True
                fallback_applied = fallback
        return {
            **base,
            "strict_match": strict,
            "resolved": resolved,
            "source_time_iso": _format_utc(selected_time),
            "delta_s": delta_s,
            "source": _source_fields(selected_source),
            "fallback_applied": fallback_applied,
            "annotation_required": fallback_applied is not None,
            "reason": None if resolved else "outside_frame_tolerance",
        }

    ranges = [
        _segment_range(item, index=index)
        for index, item in enumerate(binding["coverage_segments"])
    ]
    matching = next(
        (item for item in ranges if item.start <= requested <= item.end), None
    )
    if matching is not None:
        return {
            **base,
            "strict_match": True,
            "resolved": True,
            "coverage_segment": _ranges_to_json([matching])[0],
            "cursor_visible": True,
            "reason": None,
        }
    boundaries = [item.start for item in ranges] + [item.end for item in ranges]
    nearest = min(
        boundaries,
        key=lambda item: (abs((item - requested).total_seconds()), item),
    )
    fallback_applied = fallback if fallback == "out_of_range_note" else None
    return {
        **base,
        "resolved": fallback_applied is not None,
        "nearest_coverage_time_iso": _format_utc(nearest),
        "delta_s": (nearest - requested).total_seconds(),
        "fallback_applied": fallback_applied,
        "annotation_required": fallback_applied is not None,
        "cursor_visible": False,
        "reason": None if fallback_applied else "outside_spectrogram_coverage",
    }


def _missing_intervals(
    matches: Sequence[Mapping[str, Any]], *, key: str
) -> list[dict[str, Any]]:
    indices = [index for index, item in enumerate(matches) if not bool(item[key])]
    if not indices:
        return []
    groups: list[list[int]] = [[indices[0]]]
    for index in indices[1:]:
        if index == groups[-1][-1] + 1:
            groups[-1].append(index)
        else:
            groups.append([index])
    return [
        {
            "start_time_iso": matches[group[0]]["requested_time_iso"],
            "end_time_iso": matches[group[-1]]["requested_time_iso"],
            "sample_count": len(group),
        }
        for group in groups
    ]


def _nearest_point(ranges: Sequence[_TimeRange], requested: datetime) -> datetime:
    candidates: list[datetime] = []
    for item in ranges:
        if requested < item.start:
            candidates.append(item.start)
        elif requested > item.end:
            candidates.append(item.end)
        else:
            candidates.append(requested)
    return min(
        candidates,
        key=lambda item: (abs((item - requested).total_seconds()), item),
    )


def _longest_range(ranges: Sequence[_TimeRange]) -> _TimeRange:
    return min(ranges, key=lambda item: (-item.duration_s, item.start, item.end))


def _resolve_recommendation(
    *,
    timeline: Mapping[str, Any],
    ready: bool,
    common: Sequence[_TimeRange],
    blocked_layers: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    if ready:
        return None
    if timeline["mode"] == "still" and common:
        requested = _parse_utc(
            timeline["selected_time_iso"], label="timeline.selected_time_iso"
        )
        return {
            "action": "move_time",
            "selected_time_iso": _format_utc(_nearest_point(common, requested)),
            "requires_confirmation": True,
        }
    if timeline["mode"] == "sequence" and common:
        selected = _longest_range(common)
        trimmed = {
            "mode": "sequence",
            "start_time_iso": _format_utc(selected.start),
            "end_time_iso": _format_utc(selected.end),
            "sample_interval_s": timeline["sample_interval_s"],
            "playback_fps": timeline["playback_fps"],
        }
        return {
            "action": "trim_range",
            "start_time_iso": trimmed["start_time_iso"],
            "end_time_iso": trimmed["end_time_iso"],
            "estimated_frame_count": len(_timeline_sample_datetimes(trimmed)),
            "requires_confirmation": True,
        }
    options = ["supplement_or_replace_source", "remove_layer", "cancel_export"]
    if any(item["kind"] == "spectrogram" for item in blocked_layers):
        options.insert(0, "supplement_adjacent_spectrogram")
    return {
        "action": "resolve_layers",
        "layer_ids": [item["layer_id"] for item in blocked_layers],
        "options": options,
        "requires_confirmation": True,
    }


def _make_jsonable(value: Any, *, strip_transient: bool = False) -> Any:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        value = value.to_dict()
    if isinstance(value, Mapping):
        return {
            str(key): _make_jsonable(item, strip_transient=strip_transient)
            for key, item in value.items()
            if not strip_transient or str(key) not in _TRANSIENT_REVISION_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_make_jsonable(item, strip_transient=strip_transient) for item in value]
    if isinstance(value, datetime):
        return _format_utc(value)
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise FigureTimeValidationError(
                "Revision payload contains a non-finite number"
            )
        return value
    raise FigureTimeValidationError(
        f"Revision payload contains unsupported value type: {type(value).__name__}"
    )


def compute_preflight_revision(
    draft: Mapping[str, Any] | Any,
    source_fingerprints: Mapping[str, Any] | None = None,
) -> str:
    """Return a stable SHA-256 binding the full draft and current source state."""

    payload = {
        "figure_time_model_version": FIGURE_TIME_MODEL_VERSION,
        "draft": _make_jsonable(draft, strip_transient=True),
        "source_fingerprints": _make_jsonable(
            source_fingerprints or {}, strip_transient=True
        ),
    }
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def preflight_revision_matches(
    draft: Mapping[str, Any] | Any,
    revision: str,
    source_fingerprints: Mapping[str, Any] | None = None,
) -> bool:
    """Use a constant-time comparison to reject an export with stale preflight."""

    expected = compute_preflight_revision(draft, source_fingerprints)
    return hmac.compare_digest(expected, str(revision))


def preflight_figure(
    draft: Mapping[str, Any] | Any,
    *,
    source_fingerprints: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate every visible layer at the requested UTC export samples.

    Scientific availability is strict by default.  A frame is never interpolated
    or held unless the binding itself contains an explicit supported fallback.
    Recommendations are calculated only from strict (non-fallback) coverage.
    """

    payload = _as_mapping(draft, label="draft")
    timeline = normalize_figure_timeline(payload.get("timeline", {}))
    raw_layers = payload.get("layers", [])
    if not isinstance(raw_layers, Sequence) or isinstance(raw_layers, (str, bytes)):
        raise FigureTimeValidationError("draft.layers must be a JSON array")
    samples = _timeline_sample_datetimes(timeline)
    sample_times_iso = [_format_utc(item) for item in samples]

    layer_reports: list[dict[str, Any]] = []
    active_bindings: list[dict[str, Any]] = []
    layer_ids: set[str] = set()
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for index, raw_layer in enumerate(raw_layers):
        layer = _as_mapping(raw_layer, label=f"draft.layers[{index}]")
        layer_id = str(layer.get("id", layer.get("layer_id", ""))).strip()
        if not layer_id:
            raise FigureTimeValidationError(f"draft.layers[{index}].id is required")
        if layer_id in layer_ids:
            raise FigureTimeValidationError(f"Duplicate layer id: {layer_id!r}")
        layer_ids.add(layer_id)
        visible = bool(layer.get("visible", layer.get("enabled", True)))
        if not visible:
            layer_reports.append(
                {
                    "layer_id": layer_id,
                    "kind": None,
                    "status": "ignored",
                    "missing_count": 0,
                    "strict_missing_count": 0,
                    "missing_intervals": [],
                    "strict_missing_intervals": [],
                    "matches": [],
                }
            )
            continue
        binding = normalize_temporal_binding(layer.get("temporal_binding"))
        active_bindings.append(binding)
        matches = [_evaluate_binding(binding, requested) for requested in samples]
        missing = sum(not item["resolved"] for item in matches)
        strict_missing = sum(not item["strict_match"] for item in matches)
        fallback_count = sum(item["fallback_applied"] is not None for item in matches)
        status = "blocked" if missing else ("fallback" if fallback_count else "ready")
        report: dict[str, Any] = {
            "layer_id": layer_id,
            "kind": binding["kind"],
            "status": status,
            "fallback_policy": binding["fallback_policy"],
            "missing_count": missing,
            "strict_missing_count": strict_missing,
            "fallback_count": fallback_count,
            "missing_intervals": _missing_intervals(matches, key="resolved"),
            "strict_missing_intervals": _missing_intervals(matches, key="strict_match"),
            "matches": matches,
        }
        if "tolerance_s" in binding:
            report["tolerance_s"] = binding["tolerance_s"]
        if binding["kind"] == "spectrogram":
            report["coverage_segments"] = list(binding["coverage_segments"])
            report["coverage_gaps"] = list(binding["coverage_gaps"])
        layer_reports.append(report)
        if missing:
            code = (
                "time_classification_required"
                if binding["kind"] == "unknown"
                else "layer_time_coverage_insufficient"
            )
            issues.append(
                {
                    "code": code,
                    "layer_id": layer_id,
                    "missing_count": missing,
                    "message": (
                        "Classify this layer as Timeless or assign UTC time metadata."
                        if binding["kind"] == "unknown"
                        else "Layer does not cover every requested export time."
                    ),
                }
            )
        if fallback_count:
            warnings.append(
                {
                    "code": "explicit_time_fallback_applied",
                    "layer_id": layer_id,
                    "fallback_policy": binding["fallback_policy"],
                    "sample_count": fallback_count,
                    "message": "Export annotation and provenance are required.",
                }
            )

    active_reports = [item for item in layer_reports if item["status"] != "ignored"]
    if not active_reports:
        issues.append(
            {
                "code": "no_visible_layers",
                "layer_id": None,
                "missing_count": len(samples),
                "message": "At least one visible layer is required for export.",
            }
        )
    ready = bool(active_reports) and all(
        item["missing_count"] == 0 for item in active_reports
    )
    if timeline["mode"] == "still":
        point = _parse_utc(
            timeline["selected_time_iso"], label="timeline.selected_time_iso"
        )
        constraint = _TimeRange(point, point)
        # A nearest-time recommendation must search all strict source coverage, not
        # only the currently requested point.
        if active_bindings and all(
            _binding_ranges(binding) is None for binding in active_bindings
        ):
            common = [constraint]
        else:
            common = (
                _common_ranges(active_bindings, constraint=None)
                if active_bindings
                else []
            )
    else:
        constraint = _TimeRange(
            _parse_utc(timeline["start_time_iso"], label="timeline.start_time_iso"),
            _parse_utc(timeline["end_time_iso"], label="timeline.end_time_iso"),
        )
        common = (
            _common_ranges(active_bindings, constraint=constraint)
            if active_bindings
            else []
        )

    blocked_layers = [item for item in active_reports if item["missing_count"]]
    recommendation = _resolve_recommendation(
        timeline=timeline,
        ready=ready,
        common=common,
        blocked_layers=blocked_layers,
    )
    global_matches = (
        [
            {
                "requested_time_iso": sample_times_iso[index],
                "resolved": all(
                    report["matches"][index]["resolved"] for report in active_reports
                ),
                "strict_match": all(
                    report["matches"][index]["strict_match"]
                    for report in active_reports
                ),
            }
            for index in range(len(samples))
        ]
        if active_reports
        else [
            {
                "requested_time_iso": value,
                "resolved": False,
                "strict_match": False,
            }
            for value in sample_times_iso
        ]
    )
    result = {
        "figure_schema_version": int(payload.get("figure_schema_version", 1)),
        "workspace_id": str(payload.get("workspace_id", "")),
        "figure_time_model_version": FIGURE_TIME_MODEL_VERSION,
        "status": "ready" if ready else "blocked",
        "ready": ready,
        "timeline": timeline,
        "sample_times_iso": sample_times_iso,
        "sample_count": len(sample_times_iso),
        "layers": layer_reports,
        "global_missing_count": sum(not item["resolved"] for item in global_matches),
        "global_strict_missing_count": sum(
            not item["strict_match"] for item in global_matches
        ),
        "global_missing_intervals": _missing_intervals(global_matches, key="resolved"),
        "global_strict_missing_intervals": _missing_intervals(
            global_matches, key="strict_match"
        ),
        "common_valid_intervals": _ranges_to_json(common),
        "common_valid_time_iso": (
            _format_utc(
                _nearest_point(
                    common,
                    _parse_utc(
                        timeline["selected_time_iso"],
                        label="timeline.selected_time_iso",
                    ),
                )
            )
            if timeline["mode"] == "still" and common
            else None
        ),
        "longest_common_interval": (
            _ranges_to_json([_longest_range(common)])[0]
            if timeline["mode"] == "sequence" and common
            else None
        ),
        "recommendation": recommendation,
        "issues": issues,
        "warnings": warnings,
        "preflight_revision": compute_preflight_revision(payload, source_fingerprints),
        "source_fingerprints": _make_jsonable(source_fingerprints or {}),
    }
    # Contract-friendly aliases keep the HTTP/persistence layer thin while the
    # explicit ``global_*`` names remain useful to the browser compositor.
    result["missing_count"] = result["global_missing_count"]
    result["missing_intervals"] = list(result["global_missing_intervals"])
    result["common_valid_time"] = result["common_valid_time_iso"]
    # Enforce the public guarantee even if a future source field adds a non-JSON value.
    json.dumps(result, allow_nan=False, ensure_ascii=False)
    return result


__all__ = [
    "FIGURE_TIME_MODEL_VERSION",
    "MAX_SEQUENCE_SAMPLES",
    "SPECTROGRAM_MERGE_GAP_SECONDS",
    "FigureTimeValidationError",
    "compute_preflight_revision",
    "merge_coverage_segments",
    "normalize_figure_timeline",
    "normalize_temporal_binding",
    "preflight_figure",
    "preflight_revision_matches",
    "timeline_sample_times",
]
