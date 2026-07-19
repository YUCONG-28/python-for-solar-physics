"""Validated image-sequence and ROI exports for source-map artifacts.

This module intentionally has no Flask dependency.  Web adapters pass frozen
artifact records into :func:`export_source_maps` after applying their own
allowed-root policy.
"""

from __future__ import annotations

import copy
import json
import math
import os
import re
import shutil
import tempfile
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageColor, ImageDraw, ImageFont

from solar_toolkit.visualization.media import (
    normalize_even_size,
    probe_video,
    write_media_from_paths,
)

from .artifacts import (
    COORDINATE_SYSTEM,
    ROI_SCHEMA_VERSION,
    data_to_image_pixel,
    sha256_file,
    sidecar_path_for,
    validate_roi_set,
    validate_source_map_artifact,
)

EXPORT_SCHEMA_VERSION = 1
EXPORT_KINDS = frozenset({"image", "image_sequence", "video"})
EXPORT_CONTENTS = frozenset({"original", "roi"})

ProgressCallback = Callable[[int, int, int, Sequence[str]], None]
CancelCheck = Callable[[], bool]
MediaWriter = Callable[..., bool]
MediaProbe = Callable[..., dict[str, Any]]


class ExportError(RuntimeError):
    """Base error for a source-map export."""


class ExportConflictError(ExportError):
    """Raised when a single-file target already exists."""

    code = "target_exists"

    def __init__(self, paths: Sequence[str | Path]) -> None:
        self.paths = tuple(str(Path(path)) for path in paths)
        super().__init__("Export target already exists: " + ", ".join(self.paths))


class ExportCancelled(ExportError):
    """Raised when an export observes its cancellation flag."""


@dataclass(frozen=True)
class FrozenSourceArtifact:
    """Validated immutable pointers and metadata for one source-map PNG."""

    id: str
    image_path: Path
    sidecar_path: Path
    metadata: dict[str, Any]
    roi_set: dict[str, Any] | None = None
    source_index: int | None = None

    @property
    def image_sha256(self) -> str:
        return str(self.metadata["image"]["sha256"])


def freeze_artifact_record(
    record: Mapping[str, Any] | FrozenSourceArtifact,
) -> FrozenSourceArtifact:
    """Revalidate and freeze one server artifact record before an export."""

    if isinstance(record, FrozenSourceArtifact):
        image_path = record.image_path
        sidecar_path = record.sidecar_path
        supplied_metadata: Mapping[str, Any] | None = record.metadata
        record_id = record.id
        roi_set = record.roi_set
        source_index = record.source_index
    elif isinstance(record, Mapping):
        image_path = Path(record.get("image_path") or "")
        sidecar_path = Path(record.get("sidecar_path") or sidecar_path_for(image_path))
        supplied_metadata = (
            record.get("metadata")
            if isinstance(record.get("metadata"), Mapping)
            else None
        )
        record_id = str(record.get("id") or "")
        roi_set = (
            copy.deepcopy(record.get("roi_set"))
            if isinstance(record.get("roi_set"), Mapping)
            else None
        )
        raw_index = record.get("source_index", record.get("sequence_index"))
        source_index = int(raw_index) if raw_index is not None else None
    else:
        raise TypeError("Artifact record must be a mapping")

    metadata = validate_source_map_artifact(image_path, sidecar_path)
    if supplied_metadata is not None:
        supplied_sha = str((supplied_metadata.get("image") or {}).get("sha256") or "")
        if supplied_sha and supplied_sha != metadata["image"]["sha256"]:
            raise ValueError(
                "Frozen artifact metadata no longer matches its source PNG"
            )
    resolved_image = Path(metadata["_image_path"])
    resolved_sidecar = Path(metadata["_sidecar_path"])
    return FrozenSourceArtifact(
        id=record_id or f"artifact-{sha256_file(resolved_image)[:16]}",
        image_path=resolved_image,
        sidecar_path=resolved_sidecar,
        metadata=copy.deepcopy(metadata),
        roi_set=roi_set,
        source_index=source_index,
    )


def freeze_artifact_records(
    records: Sequence[Mapping[str, Any] | FrozenSourceArtifact],
) -> tuple[FrozenSourceArtifact, ...]:
    """Freeze a nonempty ordered collection and reject duplicate PNGs."""

    frozen = tuple(freeze_artifact_record(record) for record in records)
    if not frozen:
        raise ValueError("At least one source-map artifact is required")
    paths = [os.path.normcase(str(item.image_path)) for item in frozen]
    if len(paths) != len(set(paths)):
        raise ValueError("Source-map artifact list contains duplicate PNG paths")
    return frozen


def scan_external_artifact_directory(
    directory: str | Path,
) -> tuple[FrozenSourceArtifact, ...]:
    """Validate every PNG and matching sidecar in an external directory.

    The directory is fail-closed: a PNG without its matching
    ``.source-map.json`` file, a mismatched hash, or a symlink escape rejects
    the entire scan before any export output is written.
    """

    root = Path(directory).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(f"External source-map path is not a directory: {root}")
    candidates = [
        entry
        for entry in root.iterdir()
        if entry.is_file() and entry.suffix.casefold() == ".png"
    ]
    if not candidates:
        raise ValueError("External source-map directory contains no PNG files")

    records: list[FrozenSourceArtifact] = []
    for image in candidates:
        resolved_image = image.resolve(strict=True)
        _require_within(resolved_image, root)
        sidecar = sidecar_path_for(image)
        if not sidecar.is_file():
            raise FileNotFoundError(
                f"Source-map sidecar is missing for {image.name}: {sidecar.name}"
            )
        resolved_sidecar = sidecar.resolve(strict=True)
        _require_within(resolved_sidecar, root)
        metadata = validate_source_map_artifact(resolved_image, resolved_sidecar)
        records.append(
            FrozenSourceArtifact(
                id=f"external-{sha256_file(resolved_image)[:16]}",
                image_path=resolved_image,
                sidecar_path=resolved_sidecar,
                metadata=metadata,
            )
        )
    records.sort(key=lambda item: scientific_image_sort_key(item.image_path.name))
    return tuple(records)


_SCIENTIFIC_UTC_PATTERNS = (
    re.compile(r"(?<!\d)(\d{8})T(\d{6})(?:\.(\d{1,6}))?Z(?!\d)", re.I),
    re.compile(r"(?<!\d)(\d{8})[_-](\d{6})(?:[._-](\d{1,6}))?(?!\d)"),
    re.compile(
        r"(?<!\d)(\d{4})-(\d{2})-(\d{2})[T_ -]"
        r"(\d{2})[:-](\d{2})[:-](\d{2})(?:[._-](\d{1,6}))?Z?(?!\d)",
        re.I,
    ),
)
_NATURAL_PART = re.compile(r"(\d+)")


def scientific_utc_from_filename(filename: str) -> datetime | None:
    """Extract the first supported scientific UTC timestamp from a filename."""

    name = Path(filename).name
    for index, pattern in enumerate(_SCIENTIFIC_UTC_PATTERNS):
        match = pattern.search(name)
        if match is None:
            continue
        try:
            if index < 2:
                day, clock, fraction = match.groups()
                parsed = datetime.strptime(day + clock, "%Y%m%d%H%M%S")
            else:
                year, month, day, hour, minute, second, fraction = match.groups()
                parsed = datetime(
                    int(year), int(month), int(day), int(hour), int(minute), int(second)
                )
            microsecond = int((fraction or "").ljust(6, "0")[:6] or "0")
            return parsed.replace(microsecond=microsecond, tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def natural_sort_key(value: str) -> tuple[tuple[int, Any], ...]:
    """Return a case-insensitive numeric-aware filename key."""

    return tuple(
        (1, int(part)) if part.isdigit() else (0, part.casefold())
        for part in _NATURAL_PART.split(str(value))
        if part
    )


def scientific_image_sort_key(value: str) -> tuple[Any, ...]:
    """Sort parseable scientific times first, then natural filenames."""

    observed_at = scientific_utc_from_filename(value)
    natural = natural_sort_key(Path(value).name)
    return (0, observed_at, natural) if observed_at is not None else (1, natural)


def validate_roi_template(
    payload: Any,
    *,
    expected_image_sha256: str | None = None,
    template_mode: bool = False,
) -> dict[str, Any]:
    """Validate a ROI set, optionally allowing explicit cross-image reuse.

    Strict mode retains the existing image SHA-256 contract.  Template mode is
    deliberately explicit and records the originating image hash as
    provenance while normalizing the bundle for the requested target image.
    """

    if not isinstance(payload, Mapping):
        raise ValueError("ROI template must be a JSON object")
    source_sha = str(payload.get("image_sha256") or "").strip()
    if not source_sha:
        raise ValueError("ROI template image_sha256 is required")
    target_sha = str(expected_image_sha256 or source_sha)
    if not template_mode:
        normalized = validate_roi_set(payload, expected_image_sha256=target_sha)
    else:
        candidate = copy.deepcopy(dict(payload))
        candidate["image_sha256"] = target_sha
        normalized = validate_roi_set(candidate, expected_image_sha256=target_sha)

    for roi in normalized["rois"]:
        color = str(roi["style"]["color"])
        try:
            ImageColor.getrgb(color)
        except ValueError as exc:
            raise ValueError(
                f"ROI {roi['name']} has an invalid color: {color}"
            ) from exc

    if template_mode:
        supplied_provenance = payload.get("provenance")
        provenance = (
            copy.deepcopy(dict(supplied_provenance))
            if isinstance(supplied_provenance, Mapping)
            else {}
        )
        provenance.update(
            {
                "template_mode": True,
                "template_source_image_sha256": source_sha,
            }
        )
        normalized["provenance"] = provenance
    return normalized


def rasterize_roi_overlay(
    artifact: Mapping[str, Any] | FrozenSourceArtifact,
    roi_template: Mapping[str, Any],
    *,
    output_path: str | Path | None = None,
) -> tuple[Image.Image, list[str]]:
    """Draw one HPLN/HPLT ROI template across every mapped radio panel."""

    frozen = freeze_artifact_record(artifact)
    normalized = validate_roi_template(
        roi_template,
        expected_image_sha256=frozen.image_sha256,
        template_mode=True,
    )
    with Image.open(frozen.image_path) as opened:
        image = opened.convert("RGBA")
    warnings: list[str] = []
    for panel in frozen.metadata["panels"]:
        _draw_panel_rois(image, frozen.metadata, panel, normalized["rois"], warnings)
    rendered = image.convert("RGB")
    if output_path is not None:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        rendered.save(target, format="PNG")
    return rendered, list(dict.fromkeys(warnings))


def export_source_maps(
    artifacts: Sequence[Mapping[str, Any] | FrozenSourceArtifact],
    *,
    export_kind: str,
    content: str,
    destination: str | Path,
    roi_template: Mapping[str, Any] | None = None,
    start_index: int = 1,
    end_index: int | None = None,
    fps: float = 10.0,
    quality: str = "high",
    overwrite: bool = False,
    cancel_check: CancelCheck | None = None,
    progress_callback: ProgressCallback | None = None,
    media_writer: MediaWriter = write_media_from_paths,
    media_probe: MediaProbe = probe_video,
) -> dict[str, Any]:
    """Export a single PNG, a unique PNG-sequence directory, or MP4.

    All sources are revalidated before writing.  Single-file products are
    staged beside the destination and published as a group; image sequences
    are fully staged and then exposed with one directory rename.
    """

    kind = str(export_kind).strip().lower()
    selected_content = str(content).strip().lower()
    if kind not in EXPORT_KINDS:
        raise ValueError(f"Unsupported export kind: {export_kind}")
    if selected_content not in EXPORT_CONTENTS:
        raise ValueError(f"Unsupported export content: {content}")
    frozen = freeze_artifact_records(artifacts)
    selection, first, last = _select_range(frozen, start_index, end_index)
    if kind == "image" and len(selection) != 1:
        raise ValueError("A single-image export range must contain exactly one frame")
    normalized_roi = _resolve_roi_template(selection, selected_content, roi_template)
    _raise_if_cancelled(cancel_check)

    progress = progress_callback or (lambda *_args: None)
    if kind == "image_sequence":
        return _export_sequence(
            selection,
            destination=Path(destination),
            content=selected_content,
            roi_template=normalized_roi,
            first=first,
            last=last,
            cancel_check=cancel_check,
            progress=progress,
        )
    if kind == "image":
        return _export_single_image(
            selection[0],
            destination=Path(destination),
            content=selected_content,
            roi_template=normalized_roi,
            first=first,
            last=last,
            overwrite=bool(overwrite),
            cancel_check=cancel_check,
            progress=progress,
        )
    return _export_video(
        selection,
        destination=Path(destination),
        content=selected_content,
        roi_template=normalized_roi,
        first=first,
        last=last,
        fps=_positive_fps(fps),
        quality="high" if quality == "high" else "low",
        overwrite=bool(overwrite),
        cancel_check=cancel_check,
        progress=progress,
        media_writer=media_writer,
        media_probe=media_probe,
    )


def preflight_export_destination(
    *,
    export_kind: str,
    content: str,
    destination: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Validate an export destination before an asynchronous job is started.

    Flask adapters use this to turn :class:`ExportConflictError` into an
    immediate HTTP 409 response.  The target expansion exactly matches
    :func:`export_source_maps`, including sidecar, ROI, and manifest companions.
    """

    kind = str(export_kind).strip().lower()
    selected_content = str(content).strip().lower()
    if kind not in EXPORT_KINDS:
        raise ValueError(f"Unsupported export kind: {export_kind}")
    if selected_content not in EXPORT_CONTENTS:
        raise ValueError(f"Unsupported export content: {content}")
    requested = Path(destination)
    if kind == "image_sequence":
        root = requested.expanduser().resolve(strict=True)
        if not root.is_dir():
            raise NotADirectoryError(
                f"Sequence export destination is not a directory: {root}"
            )
        return {"destination": str(root), "targets": []}

    suffix = ".png" if kind == "image" else ".mp4"
    target = _ensure_suffix(requested, suffix)
    _require_existing_parent(target)
    targets = [target]
    if kind == "image":
        targets.append(sidecar_path_for(target))
    targets.append(_manifest_path_for(target))
    if selected_content == "roi":
        targets.append(target.with_suffix(".roi-set.json"))
    _preflight_targets(targets, overwrite=bool(overwrite))
    return {
        "destination": str(target),
        "targets": [str(path) for path in targets],
    }


def _export_single_image(
    artifact: FrozenSourceArtifact,
    *,
    destination: Path,
    content: str,
    roi_template: dict[str, Any] | None,
    first: int,
    last: int,
    overwrite: bool,
    cancel_check: CancelCheck | None,
    progress: ProgressCallback,
) -> dict[str, Any]:
    target = _ensure_suffix(destination, ".png")
    _require_existing_parent(target)
    sidecar_target = sidecar_path_for(target)
    manifest_target = _manifest_path_for(target)
    roi_target = target.with_suffix(".roi-set.json") if content == "roi" else None
    targets = [target, sidecar_target, manifest_target]
    if roi_target is not None:
        targets.append(roi_target)
    _preflight_targets(targets, overwrite=overwrite)

    warnings: list[str] = []
    with tempfile.TemporaryDirectory(
        prefix=f".{target.stem}-", dir=target.parent
    ) as raw:
        stage = Path(raw)
        staged_image = stage / target.name
        if content == "original":
            shutil.copyfile(artifact.image_path, staged_image)
        else:
            assert roi_template is not None
            rendered, warnings = rasterize_roi_overlay(artifact, roi_template)
            rendered.save(staged_image, format="PNG")
        output_sha = sha256_file(staged_image)
        staged_sidecar = stage / sidecar_target.name
        _write_json(
            staged_sidecar,
            _exported_sidecar(
                artifact,
                output_name=target.name,
                output_sha=output_sha,
                content=content,
                warnings=warnings,
                roi_template=roi_template,
            ),
        )
        staged_roi: Path | None = None
        if roi_target is not None:
            assert roi_template is not None
            staged_roi = stage / roi_target.name
            _write_json(
                staged_roi,
                _roi_for_output(roi_template, artifact, output_sha),
            )
        frame = _frame_manifest_record(
            artifact,
            selection_index=first,
            output_name=target.name,
            output_sha=output_sha,
            warnings=warnings,
        )
        manifest = _export_manifest(
            export_kind="image",
            content=content,
            first=first,
            last=last,
            frames=[frame],
            warnings=warnings,
            roi_template=roi_template,
        )
        staged_manifest = stage / manifest_target.name
        _write_json(staged_manifest, manifest)
        _raise_if_cancelled(cancel_check)
        staged = [staged_image, staged_sidecar, staged_manifest]
        if staged_roi is not None:
            staged.append(staged_roi)
        _publish_file_group(staged, targets, overwrite=overwrite)
    progress(1, 1, first, warnings)
    return {
        "kind": "image",
        "content": content,
        "path": str(target.resolve()),
        "sidecar_path": str(sidecar_target.resolve()),
        "roi_set_path": str(roi_target.resolve()) if roi_target is not None else None,
        "manifest_path": str(manifest_target.resolve()),
        "warnings": warnings,
    }


def _export_sequence(
    selection: Sequence[FrozenSourceArtifact],
    *,
    destination: Path,
    content: str,
    roi_template: dict[str, Any] | None,
    first: int,
    last: int,
    cancel_check: CancelCheck | None,
    progress: ProgressCallback,
) -> dict[str, Any]:
    root = destination.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(
            f"Sequence export destination is not a directory: {root}"
        )
    output_dir = _unique_sequence_directory(root)
    temporary = root / f".{output_dir.name}.partial-{uuid.uuid4().hex}"
    temporary.mkdir()
    warnings: list[str] = []
    frames: list[dict[str, Any]] = []
    output_names: list[str] = []
    try:
        for offset, artifact in enumerate(selection):
            _raise_if_cancelled(cancel_check)
            selection_index = first + offset
            base = _safe_frame_stem(artifact.image_path.stem)
            suffix = "_annotated" if content == "roi" else ""
            output_name = f"{offset + 1:04d}_{base}{suffix}.png"
            output = temporary / output_name
            frame_warnings: list[str] = []
            if content == "original":
                shutil.copyfile(artifact.image_path, output)
            else:
                assert roi_template is not None
                rendered, frame_warnings = rasterize_roi_overlay(artifact, roi_template)
                rendered.save(output, format="PNG")
            output_sha = sha256_file(output)
            sidecar_output = sidecar_path_for(output)
            _write_json(
                sidecar_output,
                _exported_sidecar(
                    artifact,
                    output_name=output_name,
                    output_sha=output_sha,
                    content=content,
                    warnings=frame_warnings,
                    roi_template=roi_template,
                ),
            )
            if content == "roi":
                assert roi_template is not None
                _write_json(
                    output.with_suffix(".roi-set.json"),
                    _roi_for_output(roi_template, artifact, output_sha),
                )
            frame_record = _frame_manifest_record(
                artifact,
                selection_index=selection_index,
                output_name=output_name,
                output_sha=output_sha,
                warnings=frame_warnings,
            )
            frames.append(frame_record)
            output_names.append(output_name)
            warnings.extend(frame_warnings)
            progress(offset + 1, len(selection), selection_index, frame_warnings)
        warnings = list(dict.fromkeys(warnings))
        manifest = _export_manifest(
            export_kind="image_sequence",
            content=content,
            first=first,
            last=last,
            frames=frames,
            warnings=warnings,
            roi_template=roi_template,
        )
        _write_json(temporary / "source-map-export.json", manifest)
        _raise_if_cancelled(cancel_check)
        os.replace(temporary, output_dir)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)
    return {
        "kind": "image_sequence",
        "content": content,
        "output_dir": str(output_dir.resolve()),
        "manifest_path": str((output_dir / "source-map-export.json").resolve()),
        "files": [str((output_dir / name).resolve()) for name in output_names],
        "warnings": warnings,
    }


def _export_video(
    selection: Sequence[FrozenSourceArtifact],
    *,
    destination: Path,
    content: str,
    roi_template: dict[str, Any] | None,
    first: int,
    last: int,
    fps: float,
    quality: str,
    overwrite: bool,
    cancel_check: CancelCheck | None,
    progress: ProgressCallback,
    media_writer: MediaWriter,
    media_probe: MediaProbe,
) -> dict[str, Any]:
    target = _ensure_suffix(destination, ".mp4")
    _require_existing_parent(target)
    manifest_target = _manifest_path_for(target)
    roi_target = target.with_suffix(".roi-set.json") if content == "roi" else None
    targets = [target, manifest_target]
    if roi_target is not None:
        targets.append(roi_target)
    _preflight_targets(targets, overwrite=overwrite)

    warnings: list[str] = []
    frames: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(
        prefix=f".{target.stem}-", dir=target.parent
    ) as raw:
        stage = Path(raw)
        frame_dir = stage / "frames"
        frame_dir.mkdir()
        with Image.open(selection[0].image_path) as first_image:
            frame_size = normalize_even_size(first_image.size)
        frame_paths: list[str] = []
        for offset, artifact in enumerate(selection):
            _raise_if_cancelled(cancel_check)
            selection_index = first + offset
            frame_warnings: list[str] = []
            frame_path = frame_dir / f"{offset + 1:06d}.png"
            if content == "original":
                with Image.open(artifact.image_path) as opened:
                    frame_image = opened.convert("RGB")
            else:
                assert roi_template is not None
                frame_image, frame_warnings = rasterize_roi_overlay(
                    artifact, roi_template
                )
            _save_padded_video_frame(frame_image, frame_path, frame_size)
            frame_paths.append(str(frame_path))
            frames.append(
                _frame_manifest_record(
                    artifact,
                    selection_index=selection_index,
                    output_name=None,
                    output_sha=None,
                    warnings=frame_warnings,
                )
            )
            warnings.extend(frame_warnings)
            progress(offset + 1, len(selection), selection_index, frame_warnings)
        staged_video = stage / target.name
        _raise_if_cancelled(cancel_check)
        ok = media_writer(
            frame_paths,
            staged_video,
            fps,
            quality=quality,
            target_size_tuple=frame_size,
            output_format="mp4",
        )
        if not ok:
            raise ExportError("MP4 encoder did not produce a valid video")
        _raise_if_cancelled(cancel_check)
        media = media_probe(
            staged_video,
            expected_size=frame_size,
            expected_frame_count=len(selection),
        )
        reported_fps = media.get("frame_rate")
        if reported_fps is None or not math.isclose(
            float(reported_fps), fps, rel_tol=0.02, abs_tol=0.05
        ):
            raise ExportError(
                f"Encoded video frame rate mismatch: expected {fps:g}, got {reported_fps}"
            )
        expected_duration = len(selection) / fps
        reported_duration = media.get("duration")
        if reported_duration is None or not math.isclose(
            float(reported_duration), expected_duration, rel_tol=0.05, abs_tol=0.15
        ):
            raise ExportError(
                "Encoded video duration does not match the selected frame range"
            )
        warnings = list(dict.fromkeys(warnings))
        manifest = _export_manifest(
            export_kind="video",
            content=content,
            first=first,
            last=last,
            frames=frames,
            warnings=warnings,
            roi_template=roi_template,
            video={
                "filename": target.name,
                "sha256": sha256_file(staged_video),
                "fps": fps,
                "quality": quality,
                **media,
            },
        )
        staged_manifest = stage / manifest_target.name
        _write_json(staged_manifest, manifest)
        staged = [staged_video, staged_manifest]
        if roi_target is not None:
            assert roi_template is not None
            staged_roi = stage / roi_target.name
            _write_json(staged_roi, roi_template)
            staged.append(staged_roi)
        _raise_if_cancelled(cancel_check)
        _publish_file_group(staged, targets, overwrite=overwrite)
    return {
        "kind": "video",
        "content": content,
        "path": str(target.resolve()),
        "manifest_path": str(manifest_target.resolve()),
        "roi_set_path": str(roi_target.resolve()) if roi_target is not None else None,
        "media": media,
        "warnings": warnings,
    }


def _draw_panel_rois(
    canvas: Image.Image,
    metadata: Mapping[str, Any],
    panel: Mapping[str, Any],
    rois: Sequence[Mapping[str, Any]],
    warnings: list[str],
) -> None:
    panel_id = str(panel["id"])
    x0, x1 = (float(value) for value in panel["xlim_arcsec"])
    y0, y1 = (float(value) for value in panel["ylim_arcsec"])
    bounds = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
    width = int(metadata["image"]["width"])
    height = int(metadata["image"]["height"])
    left, top, right, bottom = (float(value) for value in panel["bbox_normalized"])
    crop_box = (
        max(0, int(math.floor(left * width))),
        max(0, int(math.floor(top * height))),
        min(width, int(math.ceil(right * width))),
        min(height, int(math.ceil(bottom * height))),
    )
    for roi in rois:
        if not roi.get("visible", True):
            continue
        intersects = _roi_intersects_bounds(roi, bounds)
        if not intersects:
            warnings.append(
                f"ROI {roi['name']} does not intersect panel {panel_id}; frame retained."
            )
            continue
        color = _rgba_color(str(roi["style"]["color"]))
        line_width = max(1, int(round(float(roi["style"]["line_width"]))))
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        segments, label_point = _roi_segments_and_label(roi, bounds)
        for start, end in segments:
            first = data_to_image_pixel(metadata, panel_id, *start)
            second = data_to_image_pixel(metadata, panel_id, *end)
            draw.line([first, second], fill=color, width=line_width)
        if roi["style"].get("show_label", True):
            pixel = data_to_image_pixel(metadata, panel_id, *label_point)
            _draw_roi_label(draw, str(roi["name"]), pixel, color, crop_box)
        clipped = layer.crop(crop_box)
        canvas.alpha_composite(clipped, dest=crop_box[:2])


def _roi_segments_and_label(
    roi: Mapping[str, Any], bounds: tuple[float, float, float, float]
) -> tuple[list[tuple[tuple[float, float], tuple[float, float]]], tuple[float, float]]:
    geometry = roi["geometry"]
    if roi["type"] == "rectangle":
        left = float(geometry["left"])
        right = float(geometry["right"])
        bottom = float(geometry["bottom"])
        top = float(geometry["top"])
        points = [(left, top), (right, top), (right, bottom), (left, bottom)]
        label_point = points[0]
    else:
        points = [
            tuple(float(value) for value in point) for point in geometry["points"]
        ]
        label_point = points[0]
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        clipped = _clip_segment(start, end, bounds)
        if clipped is not None:
            segments.append(clipped)
    return segments, label_point


def _draw_roi_label(
    draw: ImageDraw.ImageDraw,
    text: str,
    point: tuple[float, float],
    color: tuple[int, int, int, int],
    crop_box: tuple[int, int, int, int],
) -> None:
    font = _label_font()
    text_box = draw.textbbox((0, 0), text, font=font)
    text_width = max(1, text_box[2] - text_box[0])
    text_height = max(1, text_box[3] - text_box[1])
    box_width = text_width + 12
    box_height = text_height + 8
    left, top, right, bottom = crop_box
    x = min(max(float(point[0]), left), max(left, right - box_width))
    y = min(max(float(point[1]) - box_height - 2, top), max(top, bottom - box_height))
    draw.rectangle([x, y, x + box_width, y + box_height], fill=(18, 25, 29, 199))
    draw.text((x + 6, y + 4), text, fill=color, font=font)


def _label_font() -> ImageFont.ImageFont:
    for path in (
        Path(os.environ.get("WINDIR") or os.environ.get("SystemRoot") or "")
        / "Fonts"
        / "segoeuib.ttf",
        Path(os.environ.get("WINDIR") or os.environ.get("SystemRoot") or "")
        / "Fonts"
        / "arial.ttf",
    ):
        try:
            return ImageFont.truetype(str(path), 16)
        except OSError:
            continue
    return ImageFont.load_default()


def _rgba_color(value: str) -> tuple[int, int, int, int]:
    parsed = ImageColor.getrgb(value)
    if len(parsed) == 4:
        return parsed
    return parsed + (255,)


def _roi_intersects_bounds(
    roi: Mapping[str, Any], bounds: tuple[float, float, float, float]
) -> bool:
    left, bottom, right, top = bounds
    geometry = roi["geometry"]
    if roi["type"] == "rectangle":
        return not (
            float(geometry["right"]) < left
            or float(geometry["left"]) > right
            or float(geometry["top"]) < bottom
            or float(geometry["bottom"]) > top
        )
    points = [tuple(float(value) for value in point) for point in geometry["points"]]
    if any(left <= x <= right and bottom <= y <= top for x, y in points):
        return True
    corners = [(left, bottom), (left, top), (right, top), (right, bottom)]
    if any(_point_in_polygon(corner, points) for corner in corners):
        return True
    return any(
        _clip_segment(points[index], points[(index + 1) % len(points)], bounds)
        is not None
        for index in range(len(points))
    )


def _point_in_polygon(
    point: tuple[float, float], polygon: Sequence[tuple[float, float]]
) -> bool:
    x, y = point
    inside = False
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y):
            crossing = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing:
                inside = not inside
        previous = current
    return inside


def _clip_segment(
    start: tuple[float, float],
    end: tuple[float, float],
    bounds: tuple[float, float, float, float],
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Clip a line segment to an axis-aligned data-coordinate rectangle."""

    left, bottom, right, top = bounds
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    entering = 0.0
    leaving = 1.0
    for p, q in (
        (-dx, x1 - left),
        (dx, right - x1),
        (-dy, y1 - bottom),
        (dy, top - y1),
    ):
        if p == 0:
            if q < 0:
                return None
            continue
        ratio = q / p
        if p < 0:
            entering = max(entering, ratio)
        else:
            leaving = min(leaving, ratio)
        if entering > leaving:
            return None
    return (
        (x1 + entering * dx, y1 + entering * dy),
        (x1 + leaving * dx, y1 + leaving * dy),
    )


def _resolve_roi_template(
    selection: Sequence[FrozenSourceArtifact],
    content: str,
    supplied: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if content == "original":
        return None
    payload = supplied or selection[0].roi_set
    if payload is None:
        raise ValueError("ROI content requires a ROI template")
    return validate_roi_template(
        payload,
        expected_image_sha256=selection[0].image_sha256,
        template_mode=True,
    )


def _select_range(
    artifacts: Sequence[FrozenSourceArtifact], start_index: int, end_index: int | None
) -> tuple[tuple[FrozenSourceArtifact, ...], int, int]:
    first = int(start_index)
    last = len(artifacts) if end_index is None else int(end_index)
    if first < 1 or last < first or last > len(artifacts):
        raise ValueError(
            f"Export range must be 1-based and inclusive within 1..{len(artifacts)}"
        )
    return tuple(artifacts[first - 1 : last]), first, last


def _exported_sidecar(
    artifact: FrozenSourceArtifact,
    *,
    output_name: str,
    output_sha: str,
    content: str,
    warnings: Sequence[str],
    roi_template: Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload = {
        key: copy.deepcopy(value)
        for key, value in artifact.metadata.items()
        if not str(key).startswith("_")
    }
    payload["image"]["filename"] = output_name
    payload["image"]["sha256"] = output_sha
    payload["warnings"] = list(
        dict.fromkeys([*(payload.get("warnings") or []), *warnings])
    )
    payload["export"] = {
        "content": content,
        "source_image_sha256": artifact.image_sha256,
    }
    if roi_template is not None:
        payload["export"]["roi_template_source_image_sha256"] = _template_source_sha(
            roi_template
        )
    return payload


def _roi_for_output(
    roi_template: Mapping[str, Any],
    artifact: FrozenSourceArtifact,
    output_sha: str,
) -> dict[str, Any]:
    payload = copy.deepcopy(dict(roi_template))
    payload["schema_version"] = ROI_SCHEMA_VERSION
    payload["coordinate_system"] = COORDINATE_SYSTEM
    payload["image_sha256"] = output_sha
    provenance = (
        dict(payload.get("provenance"))
        if isinstance(payload.get("provenance"), Mapping)
        else {}
    )
    provenance.update(
        {
            "template_mode": True,
            "template_source_image_sha256": _template_source_sha(roi_template),
            "frame_source_image_sha256": artifact.image_sha256,
        }
    )
    payload["provenance"] = provenance
    return payload


def _template_source_sha(template: Mapping[str, Any]) -> str:
    provenance = template.get("provenance")
    if isinstance(provenance, Mapping):
        source = str(provenance.get("template_source_image_sha256") or "")
        if source:
            return source
    return str(template.get("image_sha256") or "")


def _frame_manifest_record(
    artifact: FrozenSourceArtifact,
    *,
    selection_index: int,
    output_name: str | None,
    output_sha: str | None,
    warnings: Sequence[str],
) -> dict[str, Any]:
    return {
        "selection_index": int(selection_index),
        "source_index": artifact.source_index,
        "artifact_id": artifact.id,
        "source_image_path": str(artifact.image_path),
        "source_sidecar_path": str(artifact.sidecar_path),
        "source_image_sha256": artifact.image_sha256,
        "output_filename": output_name,
        "output_image_sha256": output_sha,
        "warnings": list(warnings),
    }


def _export_manifest(
    *,
    export_kind: str,
    content: str,
    first: int,
    last: int,
    frames: Sequence[Mapping[str, Any]],
    warnings: Sequence[str],
    roi_template: Mapping[str, Any] | None,
    video: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "coordinate_system": COORDINATE_SYSTEM,
        "export_kind": export_kind,
        "content": content,
        "range": {"start_index": first, "end_index": last, "inclusive": True},
        "frame_count": len(frames),
        "warnings": list(dict.fromkeys(warnings)),
        "frames": [dict(frame) for frame in frames],
        "roi_source": None,
    }
    if roi_template is not None:
        payload["roi_source"] = {
            "schema_version": roi_template.get("schema_version"),
            "template_source_image_sha256": _template_source_sha(roi_template),
        }
    if video is not None:
        payload["video"] = dict(video)
    return payload


def _publish_file_group(
    staged_paths: Sequence[Path], targets: Sequence[Path], *, overwrite: bool
) -> None:
    if len(staged_paths) != len(targets):
        raise ValueError("Staged file and destination counts differ")
    _preflight_targets(targets, overwrite=overwrite)
    backups: dict[Path, Path] = {}
    published: list[Path] = []
    try:
        if overwrite:
            for target in targets:
                if target.exists():
                    backup = target.with_name(
                        f".{target.name}.backup-{uuid.uuid4().hex}"
                    )
                    os.replace(target, backup)
                    backups[target] = backup
        for staged, target in zip(staged_paths, targets):
            os.replace(staged, target)
            published.append(target)
    except Exception:
        for target in reversed(published):
            target.unlink(missing_ok=True)
        for target, backup in backups.items():
            if backup.exists():
                os.replace(backup, target)
        raise
    else:
        for backup in backups.values():
            backup.unlink(missing_ok=True)


def _preflight_targets(targets: Sequence[Path], *, overwrite: bool) -> None:
    existing = [path for path in targets if path.exists()]
    if existing and not overwrite:
        raise ExportConflictError(existing)
    for target in targets:
        if target.exists() and not target.is_file():
            raise ExportConflictError([target])


def _manifest_path_for(target: Path) -> Path:
    return target.with_name(f"{target.stem}.source-map-export.json")


def _unique_sequence_directory(root: Path) -> Path:
    stem = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_source-map-export")
    for index in range(1, 10000):
        suffix = "" if index == 1 else f"_{index}"
        candidate = root / f"{stem}{suffix}"
        if not candidate.exists():
            return candidate
    raise ExportError("Could not allocate a unique image-sequence export directory")


def _safe_frame_stem(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value)).strip("._")
    return safe or "source_map"


def _save_padded_video_frame(
    image: Image.Image, target: Path, frame_size: tuple[int, int]
) -> None:
    """Fit without distortion and center-pad to the first frame's even size."""

    width, height = frame_size
    fitted = image.convert("RGB").copy()
    resampling = getattr(Image, "Resampling", Image)
    fitted.thumbnail((width, height), resample=resampling.LANCZOS)
    canvas = Image.new("RGB", (width, height), (0, 0, 0))
    offset = ((width - fitted.width) // 2, (height - fitted.height) // 2)
    canvas.paste(fitted, offset)
    canvas.save(target, format="PNG")


def _ensure_suffix(path: Path, suffix: str) -> Path:
    expanded = path.expanduser()
    if not expanded.suffix:
        expanded = expanded.with_suffix(suffix)
    if expanded.suffix.casefold() != suffix:
        raise ValueError(f"Export path must use the {suffix} extension")
    return expanded.resolve(strict=False)


def _require_existing_parent(path: Path) -> None:
    parent = path.parent.resolve(strict=True)
    if not parent.is_dir():
        raise NotADirectoryError(f"Export parent is not a directory: {parent}")


def _require_within(path: Path, root: Path) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise PermissionError(
            f"Path escapes the selected source-map directory: {path}"
        ) from exc


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )


def _positive_fps(value: Any) -> float:
    fps = float(value)
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError("Video FPS must be a positive finite number")
    return fps


def _raise_if_cancelled(cancel_check: CancelCheck | None) -> None:
    if cancel_check is not None and cancel_check():
        raise ExportCancelled("Export canceled")


__all__ = [
    "EXPORT_CONTENTS",
    "EXPORT_KINDS",
    "EXPORT_SCHEMA_VERSION",
    "ExportCancelled",
    "ExportConflictError",
    "ExportError",
    "FrozenSourceArtifact",
    "export_source_maps",
    "freeze_artifact_record",
    "freeze_artifact_records",
    "natural_sort_key",
    "preflight_export_destination",
    "rasterize_roi_overlay",
    "scan_external_artifact_directory",
    "scientific_image_sort_key",
    "scientific_utc_from_filename",
    "validate_roi_template",
]
