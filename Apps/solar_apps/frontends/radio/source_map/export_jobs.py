"""In-memory asynchronous registry for cancellable source-map exports."""

from __future__ import annotations

import copy
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .exporting import (
    ExportCancelled,
    ExportConflictError,
    FrozenSourceArtifact,
    export_source_maps,
    freeze_artifact_records,
    scan_external_artifact_directory,
)


class ExportJobRegistry:
    """Run export functions on daemon threads and expose JSON-safe status."""

    def __init__(self, *, exporter=export_source_maps) -> None:
        self._exporter = exporter
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def start(
        self,
        artifacts,
        *,
        export_kind: str,
        content: str,
        destination: str | Path,
        roi_template=None,
        start_index: int = 1,
        end_index: int | None = None,
        fps: float = 10.0,
        quality: str = "high",
        overwrite: bool = False,
        **exporter_options,
    ) -> dict[str, Any]:
        """Validate sources synchronously, then start one background export."""

        frozen = freeze_artifact_records(artifacts)
        first = int(start_index)
        last = len(frozen) if end_index is None else int(end_index)
        if first < 1 or last < first or last > len(frozen):
            raise ValueError(
                f"Export range must be 1-based and inclusive within 1..{len(frozen)}"
            )
        if str(export_kind).strip().lower() == "image" and last != first:
            raise ValueError(
                "A single-image export range must contain exactly one frame"
            )

        job_id = uuid.uuid4().hex
        cancel_event = threading.Event()
        record = {
            "id": job_id,
            "status": "running",
            "kind": str(export_kind).strip().lower(),
            "content": str(content).strip().lower(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "total": last - first + 1,
            "completed": 0,
            "current_index": None,
            "result": None,
            "error": None,
            "error_code": None,
            "conflict_paths": [],
            "warnings": [],
            "cancel_event": cancel_event,
        }
        kwargs = {
            "export_kind": export_kind,
            "content": content,
            "destination": destination,
            "roi_template": roi_template,
            "start_index": first,
            "end_index": last,
            "fps": fps,
            "quality": quality,
            "overwrite": bool(overwrite),
            **exporter_options,
        }
        with self._lock:
            self._jobs[job_id] = record
        thread = threading.Thread(
            target=self._run,
            args=(job_id, frozen, kwargs),
            name=f"source-map-export-{job_id[:8]}",
            daemon=True,
        )
        record["thread"] = thread
        thread.start()
        return self.public(job_id)

    def start_from_directory(
        self, directory: str | Path, **kwargs: Any
    ) -> dict[str, Any]:
        """Fail-closed scan an external directory before starting an export."""

        return self.start(scan_external_artifact_directory(directory), **kwargs)

    def public(self, job_id: str) -> dict[str, Any]:
        """Return the stable, JSON-serializable status for one export."""

        with self._lock:
            record = self._jobs.get(str(job_id))
            if record is None:
                raise KeyError("Export job not found or expired")
            return self._public_record(record)

    def cancel(self, job_id: str) -> dict[str, Any]:
        """Request cancellation without blocking the request thread."""

        with self._lock:
            record = self._jobs.get(str(job_id))
            if record is None:
                raise KeyError("Export job not found or expired")
            if record["status"] == "running":
                record["status"] = "canceling"
                record["cancel_event"].set()
            return self._public_record(record)

    def wait(self, job_id: str, timeout: float | None = None) -> dict[str, Any]:
        """Wait for completion; intended for shutdown paths and focused tests."""

        with self._lock:
            record = self._jobs.get(str(job_id))
            if record is None:
                raise KeyError("Export job not found or expired")
            thread: threading.Thread = record["thread"]
        thread.join(timeout=timeout)
        return self.public(job_id)

    def stop_all(self, *, timeout: float = 5.0) -> None:
        """Cancel active jobs and briefly join them during application shutdown."""

        with self._lock:
            active = [
                (record["id"], record["thread"])
                for record in self._jobs.values()
                if record["status"] in {"running", "canceling"}
            ]
            for job_id, _thread in active:
                record = self._jobs[job_id]
                record["status"] = "canceling"
                record["cancel_event"].set()
        deadline = time.monotonic() + max(0.0, float(timeout))
        for _job_id, thread in active:
            thread.join(timeout=max(0.0, deadline - time.monotonic()))

    def _run(
        self,
        job_id: str,
        artifacts: tuple[FrozenSourceArtifact, ...],
        kwargs: dict[str, Any],
    ) -> None:
        def canceled() -> bool:
            with self._lock:
                return bool(self._jobs[job_id]["cancel_event"].is_set())

        def progress(
            completed: int,
            total: int,
            current_index: int,
            warnings,
        ) -> None:
            with self._lock:
                record = self._jobs[job_id]
                record["completed"] = min(max(0, int(completed)), int(total))
                record["total"] = int(total)
                record["current_index"] = int(current_index)
                record["warnings"] = list(
                    dict.fromkeys(
                        [*record["warnings"], *(str(item) for item in warnings)]
                    )
                )

        try:
            result = self._exporter(
                artifacts,
                **kwargs,
                cancel_check=canceled,
                progress_callback=progress,
            )
            with self._lock:
                record = self._jobs[job_id]
                record["result"] = copy.deepcopy(result)
                record["warnings"] = list(
                    dict.fromkeys(
                        [
                            *record["warnings"],
                            *(str(item) for item in result.get("warnings", [])),
                        ]
                    )
                )
                record["completed"] = record["total"]
                record["status"] = "completed"
        except ExportCancelled:
            with self._lock:
                self._jobs[job_id]["status"] = "canceled"
        except ExportConflictError as exc:
            with self._lock:
                record = self._jobs[job_id]
                record["status"] = "failed"
                record["error"] = str(exc)
                record["error_code"] = exc.code
                record["conflict_paths"] = list(exc.paths)
        except Exception as exc:
            with self._lock:
                record = self._jobs[job_id]
                if record["cancel_event"].is_set():
                    record["status"] = "canceled"
                else:
                    record["status"] = "failed"
                    record["error"] = str(exc) or exc.__class__.__name__

    @staticmethod
    def _public_record(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": record["id"],
            "status": record["status"],
            "kind": record["kind"],
            "content": record["content"],
            "created_at": record["created_at"],
            "total": record["total"],
            "completed": record["completed"],
            "current_index": record["current_index"],
            "result": copy.deepcopy(record["result"]),
            "error": record["error"],
            "error_code": record["error_code"],
            "conflict_paths": list(record["conflict_paths"]),
            "warnings": list(record["warnings"]),
        }


__all__ = ["ExportJobRegistry"]
