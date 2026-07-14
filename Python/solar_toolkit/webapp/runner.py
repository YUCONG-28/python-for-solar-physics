"""Safe local job execution helpers for the web workbench."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

__all__ = [
    "JobContext",
    "JobRecord",
    "JobRunner",
    "PopenLike",
    "default_python_executable",
    "ensure_allowed_path",
    "normalize_arguments",
    "prepend_conda_dll_paths_to_env",
    "validate_payload_paths",
]

DEFAULT_CONDA_PYTHON = Path("D:/miniforge3/envs/solarphysics_env/python.exe")
SHELL_OPERATOR_TOKENS = {"&&", "||", "|", ";", ">", ">>", "<", "`"}
PATH_KEY_PARTS = (
    "path",
    "paths",
    "dir",
    "dirs",
    "folder",
    "folders",
    "root",
    "file",
    "files",
)
PATH_FLAG_PARTS = (
    "path",
    "dir",
    "folder",
    "root",
    "file",
    "out",
    "output",
    "centers",
    "aia",
)


class PopenLike(Protocol):
    stdout: Any
    returncode: int | None

    def poll(self) -> int | None: ...

    def wait(self, timeout: float | None = None) -> int: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...


@dataclass(frozen=True)
class JobContext:
    """Execution context shared by workflow modules."""

    repo_root: Path
    allowed_roots: list[Path] = field(default_factory=list)
    python_executable: str | Path = field(
        default_factory=lambda: default_python_executable()
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "repo_root", Path(self.repo_root).resolve())
        object.__setattr__(
            self,
            "allowed_roots",
            [Path(root).expanduser().resolve() for root in self.allowed_roots],
        )
        object.__setattr__(self, "python_executable", str(self.python_executable))


@dataclass
class JobRecord:
    """In-memory state for one launched workflow."""

    id: str
    module_id: str
    title: str
    command: list[str]
    cwd: Path
    status: str = "queued"
    returncode: int | None = None
    logs: list[str] = field(default_factory=list)
    started_at: float | None = None
    finished_at: float | None = None
    process: PopenLike | None = field(default=None, repr=False)
    error: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "module_id": self.module_id,
            "title": self.title,
            "command": self.command,
            "cwd": str(self.cwd),
            "status": self.status,
            "returncode": self.returncode,
            "logs": list(self.logs),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
        }


def default_python_executable() -> str:
    """Return the project-preferred Python executable when it exists."""

    if DEFAULT_CONDA_PYTHON.exists():
        return str(DEFAULT_CONDA_PYTHON)
    return sys.executable


def normalize_arguments(raw: object) -> list[str]:
    """Return a safe argument-token list from text or JSON list input."""

    if raw in (None, ""):
        return []
    if isinstance(raw, str):
        tokens = shlex.split(raw, posix=False)
    elif isinstance(raw, (list, tuple)):
        tokens = [str(item) for item in raw if str(item).strip()]
    else:
        raise TypeError("arguments must be a string or list")
    for token in tokens:
        if "\n" in token or "\r" in token:
            raise ValueError("arguments may not contain newlines")
        if token.strip() in SHELL_OPERATOR_TOKENS:
            raise ValueError(f"shell operator token is not allowed: {token}")
    return tokens


def validate_payload_paths(payload: dict[str, Any], *, context: JobContext) -> None:
    """Validate explicit path fields and likely path arguments."""

    for key, value in payload.items():
        if key == "arguments":
            _validate_argument_paths(normalize_arguments(value), context=context)
        elif _is_path_key(key):
            _validate_value_paths(value, context=context)


def _is_path_key(key: str) -> bool:
    normalized = key.casefold()
    if normalized in {"file_prefix", "prefix"}:
        return False
    return any(part in normalized for part in PATH_KEY_PARTS)


def _validate_value_paths(value: Any, *, context: JobContext) -> None:
    if value in (None, ""):
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _validate_value_paths(item, context=context)
        return
    if isinstance(value, dict):
        for item in value.values():
            _validate_value_paths(item, context=context)
        return
    if isinstance(value, str):
        for line in value.splitlines():
            stripped = line.strip()
            if stripped:
                ensure_allowed_path(stripped, context=context)


def _validate_argument_paths(args: list[str], *, context: JobContext) -> None:
    previous_flag = ""
    for token in args:
        if token.startswith("-"):
            previous_flag = token.casefold()
            continue
        if _looks_like_path(token) or any(
            part in previous_flag for part in PATH_FLAG_PARTS
        ):
            ensure_allowed_path(token, context=context)
        previous_flag = ""


def ensure_allowed_path(value: str | Path, *, context: JobContext) -> Path:
    """Resolve and validate a user-supplied local path."""

    raw = str(value).strip().strip('"').strip("'")
    if not raw:
        raise PermissionError("empty paths are not allowed")
    path = Path(raw).expanduser()
    resolved = (
        path.resolve(strict=False)
        if path.is_absolute()
        else (context.repo_root / path).resolve(strict=False)
    )
    roots = [context.repo_root, *context.allowed_roots]
    if not roots:
        return resolved
    if any(resolved == root or root in resolved.parents for root in roots):
        return resolved
    raise PermissionError(f"Path is outside allowed roots: {resolved}")


def _looks_like_path(token: str) -> bool:
    if token.startswith(("http://", "https://")):
        return False
    path = Path(token.strip('"').strip("'"))
    return (
        path.is_absolute()
        or token.startswith(("~", ".", ".."))
        or "/" in token
        or "\\" in token
        or (len(token) > 2 and token[1:3] == ":\\")
    )


class JobRunner:
    """Launch and track local workflow subprocesses."""

    def __init__(
        self,
        registry,
        context: JobContext,
        *,
        popen_factory=None,
    ) -> None:
        self.registry = registry
        self.context = context
        self.popen_factory = popen_factory or subprocess.Popen
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.Lock()

    def start(self, module_id: str, payload: dict[str, Any] | None = None) -> JobRecord:
        module = self.registry.get(module_id)
        command = module.build_command(payload or {}, context=self.context)
        job = JobRecord(
            id=uuid.uuid4().hex,
            module_id=module.id,
            title=module.title,
            command=command,
            cwd=self.context.repo_root,
        )
        with self._lock:
            self._jobs[job.id] = job
        thread = threading.Thread(target=self._run_job, args=(job,), daemon=True)
        thread.start()
        return job

    def status(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(f"Unknown job: {job_id}")
            return job.to_public_dict()

    def wait(self, job_id: str, timeout: float = 30.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status = self.status(job_id)
            if status["status"] not in {"queued", "running"}:
                return status
            time.sleep(0.01)
        raise TimeoutError(f"Job did not finish within {timeout} seconds: {job_id}")

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(f"Unknown job: {job_id}")
            if job.status not in {"queued", "running"}:
                return job.to_public_dict()
            process = job.process
            job.status = "canceled"
            job.finished_at = time.time()
        if process is not None:
            try:
                process.terminate()
            except Exception:
                process.kill()
        return self.status(job_id)

    def _run_job(self, job: JobRecord) -> None:
        self._set_job_fields(job.id, status="running", started_at=time.time())
        try:
            process = self.popen_factory(
                job.command,
                cwd=str(job.cwd),
                env=prepend_conda_dll_paths_to_env(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self._set_job_fields(job.id, process=process)
            self._read_process_output(job.id, process)
            returncode = process.wait()
            final_status = "succeeded" if returncode == 0 else "failed"
            current = self.status(job.id)
            if current["status"] == "canceled":
                final_status = "canceled"
            self._set_job_fields(
                job.id,
                status=final_status,
                returncode=returncode,
                finished_at=time.time(),
            )
        except Exception as exc:
            self._append_log(job.id, f"Job failed to start: {exc}")
            self._set_job_fields(
                job.id,
                status="failed",
                error=str(exc),
                returncode=-1,
                finished_at=time.time(),
            )

    def _read_process_output(self, job_id: str, process: PopenLike) -> None:
        stdout = getattr(process, "stdout", None)
        if stdout is None:
            return
        while True:
            line = stdout.readline()
            if line:
                self._append_log(job_id, line.rstrip("\n"))
                continue
            if process.poll() is not None:
                break
            time.sleep(0.02)
        close = getattr(stdout, "close", None)
        if callable(close):
            close()

    def _append_log(self, job_id: str, line: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.logs.append(line)

    def _set_job_fields(self, job_id: str, **fields: Any) -> None:
        with self._lock:
            job = self._jobs[job_id]
            for key, value in fields.items():
                setattr(job, key, value)


def prepend_conda_dll_paths_to_env(env: dict[str, str] | None = None) -> dict[str, str]:
    """Return an environment with the project conda DLL paths prepended."""

    env = dict(env or os.environ)
    roots = [
        "D:/miniforge3/envs/solarphysics_env",
        "D:/miniforge3/envs/solarphysics_env/Library/mingw-w64/bin",
        "D:/miniforge3/envs/solarphysics_env/Library/usr/bin",
        "D:/miniforge3/envs/solarphysics_env/Library/bin",
        "D:/miniforge3/envs/solarphysics_env/Scripts",
    ]
    env["PATH"] = os.pathsep.join([*roots, env.get("PATH", "")])
    return env
