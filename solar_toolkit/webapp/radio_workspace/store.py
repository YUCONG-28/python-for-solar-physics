"""Atomic file-backed storage and safe local-file access for Radio Workspace."""

from __future__ import annotations

import json
import os
import shutil
import threading
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .catalog import MODULES, PRESETS
from .contracts import SCHEMA_VERSION, RadioArtifact, RadioRunManifest, RadioWorkspace

_MAX_USER_ROOTS = 32


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _inside(path: Path, roots: Iterable[Path]) -> bool:
    return any(path == root or root in path.parents for root in roots)


def _deduplicate(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        item = str(value)
        if item not in result:
            result.append(item)
    return result


class SafePathBrowser:
    """Resolve and list paths without escaping explicitly allowed local roots."""

    def __init__(self, allowed_roots: Iterable[str | Path]) -> None:
        roots: list[Path] = []
        for value in allowed_roots:
            root = Path(value).expanduser().resolve(strict=False)
            if root not in roots:
                roots.append(root)
        if not roots:
            raise ValueError("At least one allowed root is required")
        self.allowed_roots = tuple(roots)

    def resolve(
        self,
        value: str | Path,
        *,
        must_exist: bool = True,
        file_only: bool = False,
        directory_only: bool = False,
    ) -> Path:
        raw = str(value).strip()
        if not raw:
            raise ValueError("path is required")
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            raise ValueError("Browser paths must be absolute")
        resolved = candidate.resolve(strict=must_exist)
        if not _inside(resolved, self.allowed_roots):
            raise PermissionError(f"Path is outside allowed roots: {resolved}")
        if file_only and not resolved.is_file():
            raise FileNotFoundError(f"File does not exist: {resolved}")
        if directory_only and not resolved.is_dir():
            raise NotADirectoryError(f"Directory does not exist: {resolved}")
        return resolved

    def roots_payload(self) -> dict[str, Any]:
        return {
            "path": None,
            "roots": [str(root) for root in self.allowed_roots],
            "entries": [
                self._entry(root, root.name or str(root)) for root in self.allowed_roots
            ],
        }

    def list_directory(self, value: str | Path | None = None) -> dict[str, Any]:
        if value in (None, ""):
            return self.roots_payload()
        folder = self.resolve(value, directory_only=True)
        entries: list[dict[str, Any]] = []
        for child in folder.iterdir():
            try:
                resolved = child.resolve(strict=True)
            except (FileNotFoundError, OSError):
                continue
            if not _inside(resolved, self.allowed_roots):
                continue
            try:
                entries.append(self._entry(child, child.name))
            except OSError:
                continue
        entries.sort(key=lambda item: (not item["is_dir"], item["name"].casefold()))
        return {
            "path": str(folder),
            "roots": [str(root) for root in self.allowed_roots],
            "entries": entries,
        }

    @staticmethod
    def _entry(path: Path, name: str) -> dict[str, Any]:
        stat = path.stat()
        return {
            "name": name,
            "path": str(path.resolve(strict=True)),
            "is_dir": path.is_dir(),
            "is_file": path.is_file(),
            "size": stat.st_size if path.is_file() else None,
            "modified_at": datetime.fromtimestamp(
                stat.st_mtime, timezone.utc
            ).isoformat(),
            "symlink": path.is_symlink(),
        }


class RadioWorkspaceStore:
    """Persist workspaces and runs below ``<output-root>/radio_workbench``."""

    def __init__(
        self,
        output_root: str | Path,
        *,
        allowed_roots: Iterable[str | Path] = (),
    ) -> None:
        self.output_root = Path(output_root).expanduser().resolve(strict=False)
        self.root = self.output_root / "radio_workbench"
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        startup_roots: list[Path] = []
        for value in allowed_roots:
            root = Path(value).expanduser().resolve(strict=False)
            if root not in startup_roots:
                startup_roots.append(root)
        self._startup_roots = tuple(startup_roots)
        self._user_roots = self._startup_roots
        self._protected_roots = (self.output_root,)
        self._browser = SafePathBrowser([*self._user_roots, *self._protected_roots])
        self._index_path = self.root / "workspace_index.json"
        self._module_ids = [module.id for module in MODULES]
        with self._lock:
            self._refresh_protected_roots_locked()

    @property
    def browser(self) -> SafePathBrowser:
        """Return the current immutable browser snapshot."""

        with self._lock:
            return self._browser

    @property
    def startup_roots(self) -> tuple[Path, ...]:
        """Return the immutable roots declared when the service started."""

        return self._startup_roots

    @property
    def user_roots(self) -> tuple[Path, ...]:
        """Return the roots currently selected by the local user."""

        with self._lock:
            return self._user_roots

    @property
    def protected_roots(self) -> tuple[Path, ...]:
        """Return output roots retained for persisted workspaces and results."""

        with self._lock:
            return self._protected_roots

    def replace_user_roots(self, roots: Iterable[str | Path]) -> tuple[Path, ...]:
        """Atomically replace user-selected roots after strict validation."""

        if isinstance(roots, (str, bytes, Path)):
            raise TypeError("roots must be an array of absolute directory paths")
        values = list(roots)
        if not values:
            raise ValueError("At least one user root is required")
        if len(values) > _MAX_USER_ROOTS:
            raise ValueError(f"No more than {_MAX_USER_ROOTS} user roots are allowed")

        normalized: list[Path] = []
        for value in values:
            if not isinstance(value, (str, Path)):
                raise TypeError("Every user root must be a path string")
            raw = str(value).strip()
            if not raw:
                raise ValueError("User root paths may not be empty")
            candidate = Path(raw)
            if not candidate.is_absolute():
                raise ValueError(f"User roots must be absolute paths: {raw}")
            resolved = candidate.expanduser().resolve(strict=True)
            if not resolved.is_dir():
                raise NotADirectoryError(f"User root is not a directory: {resolved}")
            if resolved not in normalized:
                normalized.append(resolved)

        if not normalized:
            raise ValueError("At least one user root is required")
        with self._lock:
            self._refresh_protected_roots_locked()
            browser = SafePathBrowser([*normalized, *self._protected_roots])
            self._user_roots = tuple(normalized)
            self._browser = browser
            return self._user_roots

    def set_user_roots(self, roots: Iterable[str | Path]) -> tuple[Path, ...]:
        """Compatibility alias for replacing user-selected roots."""

        return self.replace_user_roots(roots)

    def allowed_roots_payload(self) -> dict[str, Any]:
        """Describe startup, user-selected, and always-retained output roots."""

        with self._lock:
            return {
                "user_roots": [str(root) for root in self._user_roots],
                "startup_roots": [str(root) for root in self._startup_roots],
                "output_root": str(self.output_root),
                "protected_roots": [str(root) for root in self._protected_roots],
                "effective_roots": [str(root) for root in self._browser.allowed_roots],
                "update_effect": (
                    "Changes apply to future browsing, previews, and runs; active "
                    "and queued runs keep their resolved inputs. Workspace output "
                    "roots remain protected until their workspaces are deleted."
                ),
            }

    def create_workspace(
        self,
        *,
        name: str = "Radio Workspace",
        event_preset: dict[str, Any] | None = None,
        shared_paths: dict[str, str] | None = None,
        advanced_config: dict[str, Any] | None = None,
        concurrency: int = 1,
        workspace_id: str | None = None,
        output_root: str | Path | None = None,
    ) -> RadioWorkspace:
        workspace_id = workspace_id or uuid.uuid4().hex
        with self._lock:
            selected_output_root = (
                self.output_root
                if output_root in (None, "")
                else self._browser.resolve(output_root, must_exist=False)
            )
            now = utc_now()
            enabled = [module.id for module in MODULES if module.default_enabled]
            collapsed = [module.id for module in MODULES if module.default_collapsed]
            workspace = RadioWorkspace(
                schema_version=SCHEMA_VERSION,
                id=workspace_id,
                name=name,
                output_root=str(selected_output_root),
                created_at=now,
                updated_at=now,
                event_preset=event_preset or {},
                shared_paths=shared_paths or {},
                advanced_config=advanced_config or {},
                enabled_modules=enabled,
                module_order=list(self._module_ids),
                collapsed_modules=collapsed,
                pinned_modules=[],
                concurrency=concurrency,
            )
            self._validate_workspace_modules(workspace)
            self._validate_shared_paths(workspace.shared_paths)
            path = self._workspace_path(selected_output_root, workspace.id)
            if path.exists():
                raise FileExistsError(f"Radio workspace already exists: {workspace.id}")
            (path / "runs").mkdir(parents=True)
            self._atomic_json(path / "workspace.json", workspace.to_dict())
            index = self._read_index()
            index[workspace.id] = str(selected_output_root)
            self._write_index(index)
            self._refresh_protected_roots_locked()
        return workspace

    def list_workspaces(self) -> list[RadioWorkspace]:
        workspaces: list[RadioWorkspace] = []
        with self._lock:
            paths: dict[str, Path] = {
                workspace_id: self._workspace_path(output_root, workspace_id)
                for workspace_id, output_root in self._read_index().items()
            }
            for item in self.root.iterdir():
                if item.is_symlink() or not item.is_dir():
                    continue
                paths.setdefault(item.name, item)
            for item in paths.values():
                config = item / "workspace.json"
                if not config.is_file():
                    continue
                try:
                    workspaces.append(self._read_workspace(config))
                except (OSError, TypeError, ValueError, json.JSONDecodeError):
                    continue
        return sorted(workspaces, key=lambda item: item.updated_at, reverse=True)

    def load_workspace(self, workspace_id: str) -> RadioWorkspace:
        path = self.workspace_dir(workspace_id) / "workspace.json"
        with self._lock:
            if not path.is_file():
                raise KeyError(f"Unknown radio workspace: {workspace_id}")
            return self._read_workspace(path)

    def update_workspace(
        self, workspace_id: str, updates: dict[str, Any]
    ) -> RadioWorkspace:
        allowed = {
            "name",
            "event_preset",
            "shared_paths",
            "advanced_config",
            "enabled_modules",
            "module_order",
            "collapsed_modules",
            "pinned_modules",
            "concurrency",
        }
        if "output_root" in updates:
            raise ValueError(
                "output_root cannot be changed after workspace creation; "
                "create a new workspace instead"
            )
        unknown = set(updates) - allowed
        if unknown:
            raise ValueError(f"Unknown workspace fields: {', '.join(sorted(unknown))}")
        with self._lock:
            workspace = self.load_workspace(workspace_id)
            payload = workspace.to_dict()
            payload.update(updates)
            payload["updated_at"] = utc_now()
            updated = RadioWorkspace.from_dict(payload)
            self._validate_workspace_modules(updated)
            self._validate_shared_paths(updated.shared_paths)
            self._atomic_json(
                self.workspace_dir(workspace_id) / "workspace.json",
                updated.to_dict(),
            )
        return updated

    def update_layout(
        self, workspace_id: str, payload: dict[str, Any]
    ) -> RadioWorkspace:
        updates = dict(payload)
        preset_id = updates.pop("preset_id", None)
        allowed = {
            "enabled_modules",
            "module_order",
            "collapsed_modules",
            "pinned_modules",
        }
        unknown = set(updates) - allowed
        if unknown:
            raise ValueError(f"Unknown layout fields: {', '.join(sorted(unknown))}")
        if preset_id:
            try:
                preset_modules = list(PRESETS[str(preset_id)]["module_ids"])
            except KeyError as exc:
                raise KeyError(f"Unknown radio preset: {preset_id}") from exc
            updates.setdefault("enabled_modules", preset_modules)
            updates.setdefault(
                "module_order",
                [
                    *preset_modules,
                    *[item for item in self._module_ids if item not in preset_modules],
                ],
            )
            updates.setdefault(
                "collapsed_modules",
                [item for item in self._module_ids if item not in preset_modules],
            )
        return self.update_workspace(workspace_id, updates)

    def delete_workspace(self, workspace_id: str) -> None:
        path = self.workspace_dir(workspace_id)
        with self._lock:
            if not path.is_dir():
                raise KeyError(f"Unknown radio workspace: {workspace_id}")
            resolved = path.resolve(strict=True)
            if resolved.parent != self.root.resolve(strict=True) or path.is_symlink():
                expected_parent = (
                    Path(self.load_workspace(workspace_id).output_root)
                    / "radio_workbench"
                ).resolve(strict=True)
                if resolved.parent != expected_parent or path.is_symlink():
                    raise PermissionError("Refusing to delete an unsafe workspace path")
            shutil.rmtree(resolved)
            index = self._read_index()
            index.pop(workspace_id, None)
            self._write_index(index)
            self._refresh_protected_roots_locked()

    def workspace_dir(self, workspace_id: str) -> Path:
        if not workspace_id or any(
            char not in "abcdefghijklmnopqrstuvwxyz0123456789_-"
            for char in workspace_id
        ):
            raise ValueError(f"Invalid workspace id: {workspace_id!r}")
        with self._lock:
            output_root = self._read_index().get(workspace_id, str(self.output_root))
        return self._workspace_path(output_root, workspace_id)

    def run_dir(self, workspace_id: str, run_id: str) -> Path:
        if not run_id or any(
            char not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for char in run_id
        ):
            raise ValueError(f"Invalid run id: {run_id!r}")
        base = self.workspace_dir(workspace_id) / "runs"
        path = (base / run_id).resolve(strict=False)
        if path.parent != base.resolve(strict=False):
            raise PermissionError("Run path escaped the workspace root")
        return path

    def create_run(self, manifest: RadioRunManifest) -> RadioRunManifest:
        self.load_workspace(manifest.workspace_id)
        path = self.run_dir(manifest.workspace_id, manifest.id)
        with self._lock:
            if path.exists():
                raise FileExistsError(f"Radio run already exists: {manifest.id}")
            (path / "artifacts").mkdir(parents=True)
            self._atomic_json(path / "request.json", manifest.request)
            self._atomic_json(path / "resolved_config.json", manifest.resolved_config)
            self._atomic_json(path / "run.json", manifest.to_dict())
            (path / "run.log").write_text("", encoding="utf-8")
        return manifest

    def create_runs_atomic(
        self, manifests: Iterable[RadioRunManifest]
    ) -> list[RadioRunManifest]:
        """Create a prepared batch without leaving partial run directories."""

        runs = list(manifests)
        if not runs:
            return []
        paths: list[Path] = []
        with self._lock:
            for manifest in runs:
                self.load_workspace(manifest.workspace_id)
                path = self.run_dir(manifest.workspace_id, manifest.id)
                if path in paths:
                    raise ValueError(f"Duplicate radio run id: {manifest.id}")
                if path.exists():
                    raise FileExistsError(f"Radio run already exists: {manifest.id}")
                paths.append(path)
            try:
                for manifest in runs:
                    self.create_run(manifest)
            except BaseException as exc:
                rollback_errors: list[OSError] = []
                for path in reversed(paths):
                    try:
                        if path.is_symlink() or path.is_file():
                            path.unlink(missing_ok=True)
                        elif path.is_dir():
                            shutil.rmtree(path)
                    except OSError as rollback_error:
                        rollback_errors.append(rollback_error)
                if rollback_errors:
                    raise RuntimeError(
                        "Radio batch creation failed and rollback was incomplete"
                    ) from exc
                raise
        return runs

    def load_run(self, workspace_id: str, run_id: str) -> RadioRunManifest:
        path = self.run_dir(workspace_id, run_id) / "run.json"
        with self._lock:
            if not path.is_file():
                raise KeyError(f"Unknown radio run: {run_id}")
            return RadioRunManifest.from_dict(self._read_json(path))

    def list_runs(self, workspace_id: str) -> list[RadioRunManifest]:
        workspace = self.load_workspace(workspace_id)
        del workspace
        runs_dir = self.workspace_dir(workspace_id) / "runs"
        runs: list[RadioRunManifest] = []
        with self._lock:
            if not runs_dir.is_dir():
                return []
            for child in runs_dir.iterdir():
                if child.is_symlink() or not child.is_dir():
                    continue
                path = child / "run.json"
                if not path.is_file():
                    continue
                try:
                    runs.append(RadioRunManifest.from_dict(self._read_json(path)))
                except (OSError, TypeError, ValueError, json.JSONDecodeError):
                    continue
        return sorted(runs, key=lambda item: item.created_at, reverse=True)

    def save_run(self, manifest: RadioRunManifest) -> RadioRunManifest:
        run_dir = self.run_dir(manifest.workspace_id, manifest.id)
        path = run_dir / "run.json"
        with self._lock:
            if not path.is_file():
                raise KeyError(f"Unknown radio run: {manifest.id}")
            self._atomic_json(
                run_dir / "resolved_config.json", manifest.resolved_config
            )
            self._atomic_json(path, manifest.to_dict())
        return manifest

    def append_log(self, workspace_id: str, run_id: str, line: str) -> None:
        path = self.run_dir(workspace_id, run_id) / "run.log"
        with self._lock, path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(str(line).rstrip("\r\n") + "\n")

    def read_log(
        self, workspace_id: str, run_id: str, *, offset: int = 0
    ) -> tuple[list[str], int]:
        if offset < 0:
            raise ValueError("offset must be zero or greater")
        path = self.run_dir(workspace_id, run_id) / "run.log"
        if not path.is_file():
            raise KeyError(f"Unknown radio run: {run_id}")
        with self._lock:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[offset:], len(lines)

    def artifact_path(
        self, workspace_id: str, run_id: str, artifact_id: str
    ) -> tuple[RadioArtifact, Path]:
        manifest = self.load_run(workspace_id, run_id)
        try:
            artifact = next(
                item for item in manifest.artifacts if item.id == artifact_id
            )
        except StopIteration as exc:
            raise KeyError(f"Unknown radio artifact: {artifact_id}") from exc
        root = (self.run_dir(workspace_id, run_id) / "artifacts").resolve(strict=True)
        path = (root / artifact.relative_path).resolve(strict=True)
        if not _inside(path, (root,)) or not path.is_file():
            raise PermissionError("Artifact path escaped its run directory")
        return artifact, path

    def recover_interrupted_runs(self) -> list[RadioRunManifest]:
        recovered: list[RadioRunManifest] = []
        for workspace in self.list_workspaces():
            for manifest in self.list_runs(workspace.id):
                if manifest.status not in {"queued", "running"}:
                    continue
                manifest.status = "interrupted"
                manifest.progress = 1.0
                manifest.finished_at = utc_now()
                manifest.error = "The local service stopped before this run completed."
                self.save_run(manifest)
                recovered.append(manifest)
        return recovered

    def _read_workspace(self, path: Path) -> RadioWorkspace:
        workspace = RadioWorkspace.from_dict(self._read_json(path))
        self._validate_workspace_modules(workspace)
        return workspace

    def _validate_workspace_modules(self, workspace: RadioWorkspace) -> None:
        allowed = set(self._module_ids)
        for module in MODULES:
            if module.always_available and module.id not in workspace.enabled_modules:
                workspace.enabled_modules.append(module.id)
        for field_name in (
            "enabled_modules",
            "module_order",
            "collapsed_modules",
            "pinned_modules",
        ):
            values = getattr(workspace, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} contains duplicate module ids")
            unknown = set(values) - allowed
            if unknown:
                raise ValueError(
                    f"{field_name} contains unknown modules: {', '.join(sorted(unknown))}"
                )
        workspace.module_order = _deduplicate(
            [*workspace.module_order, *self._module_ids]
        )

    def _validate_shared_paths(self, shared_paths: dict[str, str]) -> None:
        for value in shared_paths.values():
            if value:
                self.browser.resolve(value, must_exist=False)

    def _workspace_path(self, output_root: str | Path, workspace_id: str) -> Path:
        base = Path(output_root).expanduser().resolve(strict=False) / "radio_workbench"
        path = (base / workspace_id).resolve(strict=False)
        if path.parent != base.resolve(strict=False):
            raise PermissionError("Workspace path escaped the selected output root")
        return path

    def _read_index(self) -> dict[str, str]:
        if not self._index_path.is_file():
            return {}
        payload = self._read_json(self._index_path)
        if int(payload.get("schema_version", 0)) != SCHEMA_VERSION:
            raise ValueError("Unsupported radio workspace index schema version")
        raw = payload.get("workspaces", {})
        if not isinstance(raw, dict):
            raise TypeError("Radio workspace index must contain a workspaces object")
        result: dict[str, str] = {}
        for workspace_id, output_root in raw.items():
            if not isinstance(output_root, str):
                continue
            try:
                resolved = self._validated_index_output_root(
                    str(workspace_id), output_root
                )
            except (
                OSError,
                TypeError,
                ValueError,
                PermissionError,
                json.JSONDecodeError,
            ):
                continue
            result[str(workspace_id)] = str(resolved)
        return result

    def _write_index(self, index: dict[str, str]) -> None:
        self._atomic_json(
            self._index_path,
            {"schema_version": SCHEMA_VERSION, "workspaces": dict(index)},
        )

    def _refresh_protected_roots_locked(self) -> None:
        protected = [self.output_root]
        for output_root in self._read_index().values():
            resolved = Path(output_root).expanduser().resolve(strict=False)
            if resolved not in protected:
                protected.append(resolved)
        self._protected_roots = tuple(protected)
        self._browser = SafePathBrowser([*self._user_roots, *protected])

    def _validated_index_output_root(self, workspace_id: str, output_root: str) -> Path:
        if not workspace_id or any(
            char not in "abcdefghijklmnopqrstuvwxyz0123456789_-"
            for char in workspace_id
        ):
            raise ValueError(f"Invalid workspace id: {workspace_id!r}")
        candidate = Path(output_root).expanduser()
        if not candidate.is_absolute():
            raise ValueError("Indexed workspace output roots must be absolute")
        resolved = candidate.resolve(strict=True)
        if not resolved.is_dir():
            raise NotADirectoryError(
                f"Indexed workspace output root is not a directory: {resolved}"
            )

        workbench = resolved / "radio_workbench"
        workspace_dir = workbench / workspace_id
        config = workspace_dir / "workspace.json"
        if workbench.is_symlink() or workspace_dir.is_symlink() or config.is_symlink():
            raise PermissionError("Indexed workspace paths may not be symlinks")
        resolved_workbench = workbench.resolve(strict=True)
        resolved_workspace = workspace_dir.resolve(strict=True)
        if (
            not resolved_workbench.is_dir()
            or not resolved_workspace.is_dir()
            or resolved_workspace.parent != resolved_workbench
            or not config.is_file()
        ):
            raise PermissionError("Indexed workspace path is invalid")

        workspace = RadioWorkspace.from_dict(self._read_json(config))
        if workspace.id != workspace_id:
            raise ValueError("Indexed workspace id does not match workspace.json")
        declared_output = Path(workspace.output_root).expanduser()
        if not declared_output.is_absolute():
            raise ValueError("Workspace output_root must be absolute")
        if declared_output.resolve(strict=True) != resolved:
            raise ValueError("Indexed output root does not match workspace.json")
        return resolved

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError(f"Expected a JSON object in {path}")
        return payload

    @staticmethod
    def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temp.write_text(
                json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            os.replace(temp, path)
        finally:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass


__all__ = ["RadioWorkspaceStore", "SafePathBrowser", "utc_now"]
