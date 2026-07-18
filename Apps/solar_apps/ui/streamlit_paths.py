"""Shared native path controls and root policy for local Streamlit apps."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from solar_apps.platform.paths.allowed_roots import configured_allowed_roots
from solar_apps.platform.paths.native_dialog import (
    NativeDialogError,
    NativePathDialogService,
    validate_allowed_path,
)
from solar_apps.platform.processes import selected_python_executable
from solar_apps.ui.state import frontend_path_memory

__all__ = [
    "PathAccessPolicy",
    "append_unique_paths",
    "render_native_path_input",
    "resolve_streamlit_allowed_roots",
]

_SERVICE_CACHE: dict[tuple[tuple[str, ...], str, str], NativePathDialogService] = {}
_SERVICE_CACHE_LOCK = threading.Lock()


def resolve_streamlit_allowed_roots(cli_value: str | None = None) -> tuple[Path, ...]:
    """Resolve configured roots with the standard CLI/env/YAML precedence."""

    return configured_allowed_roots(cli_value=cli_value)


def append_unique_paths(existing: str, additions: list[str] | tuple[str, ...]) -> str:
    """Append newline-delimited paths with case-insensitive Windows deduplication."""

    values = [line.strip() for line in str(existing or "").splitlines() if line.strip()]
    seen = {_path_key(value) for value in values}
    for raw in additions:
        value = str(raw).strip()
        key = _path_key(value)
        if value and key not in seen:
            seen.add(key)
            values.append(value)
    return "\n".join(values)


def _path_key(value: str) -> str:
    return os.path.normcase(os.path.normpath(str(value).strip()))


@dataclass(frozen=True)
class PathAccessPolicy:
    """Validate typed Streamlit paths against data and protected output roots."""

    input_roots: tuple[Path, ...]
    output_roots: tuple[Path, ...]
    base_directory: Path

    @classmethod
    def create(
        cls,
        input_roots: tuple[Path, ...] | list[Path],
        *,
        protected_output_roots: tuple[Path, ...] | list[Path] = (),
        base_directory: str | Path,
    ) -> PathAccessPolicy:
        inputs = tuple(
            Path(path).expanduser().resolve(strict=False) for path in input_roots
        )
        outputs = tuple(
            dict.fromkeys(
                [
                    *inputs,
                    *(
                        Path(path).expanduser().resolve(strict=False)
                        for path in protected_output_roots
                    ),
                ]
            )
        )
        return cls(
            input_roots=inputs,
            output_roots=outputs,
            base_directory=Path(base_directory).expanduser().resolve(strict=False),
        )

    def input_file(self, value: str | Path) -> Path:
        return validate_allowed_path(
            value,
            allowed_roots=self.input_roots,
            kind="file",
            base_directory=self.base_directory,
        )

    def input_directory(self, value: str | Path) -> Path:
        return validate_allowed_path(
            value,
            allowed_roots=self.input_roots,
            kind="directory",
            base_directory=self.base_directory,
        )

    def output_directory(self, value: str | Path) -> Path:
        return validate_allowed_path(
            value,
            allowed_roots=self.output_roots,
            kind="output_directory",
            base_directory=self.base_directory,
        )

    def save_file(self, value: str | Path, *, default_suffix: str = "") -> Path:
        return validate_allowed_path(
            value,
            allowed_roots=self.output_roots,
            kind="save_file",
            base_directory=self.base_directory,
            default_suffix=default_suffix,
        )


def _service_for(roots: tuple[Path, ...], frontend_id: str) -> NativePathDialogService:
    python_executable = selected_python_executable()
    key = (
        tuple(str(root) for root in roots),
        os.path.abspath(python_executable),
        frontend_id,
    )
    with _SERVICE_CACHE_LOCK:
        service = _SERVICE_CACHE.get(key)
        if service is None:
            service = NativePathDialogService(
                roots,
                python_executable=python_executable,
                memory=frontend_path_memory(roots),
            )
            _SERVICE_CACHE[key] = service
        return service


def render_native_path_input(
    st: Any,
    label: str,
    *,
    key: str,
    initial_value: str,
    roots: tuple[Path, ...],
    kind: str,
    extensions: tuple[str, ...] = (),
    default_suffix: str = "",
    allow_multiple: bool = False,
    placeholder: str | None = None,
    help_text: str | None = None,
    service: NativePathDialogService | Any | None = None,
    frontend_id: str = "streamlit",
    operation: str = "default",
    state_store: Any | None = None,
    stacked: bool = False,
) -> str:
    """Render an editable path plus a Windows-native Browse button."""

    pending_key = f"_{key}_native_path_pending"
    if pending_key in st.session_state:
        st.session_state[key] = st.session_state.pop(pending_key)
    saved_fields: dict[str, Any] = {}
    if state_store is not None:
        saved = state_store.load(default={})
        if isinstance(saved.get("fields"), dict):
            saved_fields = saved["fields"]
    if key not in st.session_state:
        st.session_state[key] = str(saved_fields.get(key, initial_value) or "")
    if stacked:
        value = st.text_input(
            label,
            key=key,
            placeholder=placeholder,
            help=help_text,
        )
        clicked = st.button(
            "Browse",
            key=f"{key}_browse",
            disabled=not roots,
            width="stretch",
        )
    else:
        input_column, button_column = st.columns([5, 1])
        with input_column:
            value = st.text_input(
                label,
                key=key,
                placeholder=placeholder,
                help=help_text,
            )
        with button_column:
            st.write("")
            clicked = st.button(
                "Browse",
                key=f"{key}_browse",
                disabled=not roots,
                width="stretch",
            )
    if clicked:
        mode = {
            "file": "open_files" if allow_multiple else "open_file",
            "directory": "select_directory",
            "save_file": "save_file",
        }.get(kind)
        if mode is None:
            raise ValueError(f"Unsupported Streamlit path kind: {kind!r}")
        try:
            selection = (service or _service_for(roots, frontend_id)).select(
                {
                    "mode": mode,
                    "title": label,
                    "initial_path": value,
                    "extensions": list(extensions),
                    "default_suffix": default_suffix,
                    "memory_context": {
                        "frontend": frontend_id,
                        "operation": operation,
                        "field": key,
                        "dialog_mode": mode,
                    },
                }
            )
        except NativeDialogError as exc:
            st.error(str(exc))
        else:
            if selection.status == "selected":
                selected = [str(path) for path in selection.paths]
                st.session_state[pending_key] = (
                    append_unique_paths(value, selected)
                    if allow_multiple
                    else selected[0]
                )
                st.rerun()
            else:
                st.info("Selection cancelled; the path was not changed.")
    result = str(st.session_state.get(key, value))
    if state_store is not None and saved_fields.get(key) != result:
        saved_fields[key] = result
        state_store.update({"fields": saved_fields})
    return result
