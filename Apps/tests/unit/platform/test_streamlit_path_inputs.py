from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from solar_apps.frontends.radio.roi_lightcurve.roi_lightcurve_app import (
    _roi_from_uploaded_or_path,
)
from solar_apps.platform.paths.native_dialog import (
    DialogSelection,
    NativeDialogForbiddenError,
)
from solar_apps.ui.streamlit_paths import (
    PathAccessPolicy,
    append_unique_paths,
    render_native_path_input,
    resolve_streamlit_allowed_roots,
)


class _Context:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _GuardedSessionState(dict[str, Any]):
    """Model Streamlit's ban on changing an instantiated widget key."""

    def __init__(self, values: dict[str, Any]) -> None:
        super().__init__(values)
        self.instantiated_widget_keys: set[str] = set()

    def __setitem__(self, key: str, value: Any) -> None:
        if key in self.instantiated_widget_keys:
            raise RuntimeError(f"widget key was modified after instantiation: {key}")
        super().__setitem__(key, value)


class _FakeStreamlit:
    def __init__(self, *, clicked: bool, value: str) -> None:
        self.session_state = _GuardedSessionState({"path": value})
        self.clicked = clicked
        self.errors: list[str] = []
        self.infos: list[str] = []
        self.reruns = 0
        self.column_specs: list[list[int]] = []

    def columns(self, spec: list[int]) -> list[_Context]:
        self.column_specs.append(spec)
        return [_Context() for _item in spec]

    def text_input(self, _label: str, *, key: str, **_kwargs: Any) -> str:
        self.session_state.instantiated_widget_keys.add(key)
        return str(self.session_state[key])

    def button(self, _label: str, *, key: str, **_kwargs: Any) -> bool:
        return self.clicked and key == "path_browse"

    def write(self, _value: str) -> None:
        return None

    def error(self, value: str) -> None:
        self.errors.append(value)

    def info(self, value: str) -> None:
        self.infos.append(value)

    def rerun(self) -> None:
        self.reruns += 1
        self.session_state.instantiated_widget_keys.clear()


class _FakeService:
    def __init__(self, selection: DialogSelection) -> None:
        self.selection = selection
        self.requests: list[dict[str, Any]] = []

    def select(self, payload: dict[str, Any]) -> DialogSelection:
        self.requests.append(payload)
        return self.selection


def test_append_unique_paths_is_case_insensitive_and_ordered() -> None:
    assert append_unique_paths(
        "D:\\Data\\one\nD:\\Data\\two",
        ("d:\\data\\ONE", "D:\\Data\\three"),
    ).splitlines() == ["D:\\Data\\one", "D:\\Data\\two", "D:\\Data\\three"]


def test_path_policy_separates_inputs_and_protected_outputs(tmp_path: Path) -> None:
    data = tmp_path / "data"
    output = tmp_path / "app-output"
    data.mkdir()
    output.mkdir()
    source = data / "source.csv"
    source.write_text("x", encoding="utf-8")
    policy = PathAccessPolicy.create(
        (data,), protected_output_roots=(output,), base_directory=tmp_path
    )
    assert policy.input_file(source) == source.resolve()
    assert policy.input_directory(data) == data.resolve()
    assert policy.output_directory(output / "new-run") == (output / "new-run").resolve()
    assert (
        policy.save_file(output / "movie", default_suffix=".mp4")
        == (output / "movie.mp4").resolve()
    )
    outside = tmp_path / "outside.csv"
    outside.write_text("outside", encoding="utf-8")
    with pytest.raises(NativeDialogForbiddenError):
        policy.input_file(outside)


def test_native_path_input_updates_session_state_after_selection(
    tmp_path: Path,
) -> None:
    selected = tmp_path / "selected.json"
    selected.write_text("{}", encoding="utf-8")
    st = _FakeStreamlit(clicked=True, value="old.json")
    service = _FakeService(DialogSelection("selected", (selected,)))

    value = render_native_path_input(
        st,
        "ROI JSON path",
        key="path",
        initial_value="",
        roots=(tmp_path,),
        kind="file",
        extensions=(".json",),
        service=service,
    )

    assert value == "old.json"
    assert st.session_state["path"] == "old.json"
    assert st.reruns == 1
    assert service.requests[0]["mode"] == "open_file"
    assert service.requests[0]["extensions"] == [".json"]
    assert service.requests[0]["memory_context"] == {
        "frontend": "streamlit",
        "operation": "default",
        "field": "path",
        "dialog_mode": "open_file",
    }

    st.clicked = False
    value = render_native_path_input(
        st,
        "ROI JSON path",
        key="path",
        initial_value="",
        roots=(tmp_path,),
        kind="file",
        extensions=(".json",),
        service=service,
    )
    assert value == str(selected)
    assert st.session_state["path"] == str(selected)


def test_native_path_input_cancel_keeps_typed_value(tmp_path: Path) -> None:
    st = _FakeStreamlit(clicked=True, value="typed.json")
    service = _FakeService(DialogSelection("cancelled"))

    value = render_native_path_input(
        st,
        "ROI JSON path",
        key="path",
        initial_value="",
        roots=(tmp_path,),
        kind="file",
        service=service,
    )

    assert value == "typed.json"
    assert st.session_state["path"] == "typed.json"
    assert st.reruns == 0
    assert st.infos == ["Selection cancelled; the path was not changed."]


def test_native_path_input_can_stack_in_a_narrow_sidebar(tmp_path: Path) -> None:
    st = _FakeStreamlit(clicked=False, value="typed.json")

    value = render_native_path_input(
        st,
        "ROI JSON path",
        key="path",
        initial_value="",
        roots=(tmp_path,),
        kind="file",
        stacked=True,
    )

    assert value == "typed.json"
    assert st.column_specs == []


def test_roi_json_path_import_and_upload_priority(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    path_payload = {
        "kind": "box",
        "label": "path",
        "bounds_arcsec": {"left": 1, "right": 2, "bottom": 3, "top": 4},
    }
    upload_payload = {
        "kind": "box",
        "label": "upload",
        "bounds_arcsec": {"left": 10, "right": 20, "bottom": 30, "top": 40},
    }
    roi_path = root / "roi.json"
    roi_path.write_text(json.dumps(path_payload), encoding="utf-8")
    policy = PathAccessPolicy.create((root,), base_directory=tmp_path)

    from_path = _roi_from_uploaded_or_path(
        uploaded_payload=None,
        path_text=str(roi_path),
        path_policy=policy,
    )
    from_upload = _roi_from_uploaded_or_path(
        uploaded_payload=json.dumps(upload_payload).encode("utf-8"),
        path_text=str(tmp_path / "outside.json"),
        path_policy=policy,
    )

    assert from_path.label == "path"
    assert from_upload.label == "upload"


def test_streamlit_root_precedence_is_cli_then_env_then_yaml(
    tmp_path: Path, monkeypatch
) -> None:
    cli_root = tmp_path / "cli"
    env_root = tmp_path / "env"
    config_root = tmp_path / "config"
    for root in (cli_root, env_root, config_root):
        root.mkdir()
    config_path = tmp_path / "paths.local.yaml"
    config_path.write_text(
        f"apps:\n  allowed_roots:\n    - '{config_root.as_posix()}'\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SOLAR_APPS_CONFIG", str(config_path))
    monkeypatch.setenv("SOLAR_APPS_ALLOWED_ROOTS", str(env_root))

    assert resolve_streamlit_allowed_roots(str(cli_root)) == (cli_root.resolve(),)
    assert resolve_streamlit_allowed_roots() == (env_root.resolve(),)

    monkeypatch.delenv("SOLAR_APPS_ALLOWED_ROOTS")
    assert resolve_streamlit_allowed_roots() == (config_root.resolve(),)
