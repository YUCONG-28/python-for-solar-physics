from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path

import pytest

from solar_apps.platform.paths.native_dialog import (
    DialogRequest,
    NativeDialogBusyError,
    NativeDialogForbiddenError,
    NativeDialogRequestError,
    NativeDialogUnavailableError,
    NativeDialogUnsupportedError,
    NativePathDialogService,
    validate_allowed_path,
)
from solar_apps.platform.paths.flask_dialog import register_native_path_dialog
from solar_apps.platform.paths.memory import PathMemoryContext, RecentPathMemory
from solar_apps.platform.state import StateStore


def _completed(payload: dict, *, returncode: int = 0, stderr: str = ""):
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=json.dumps(payload), stderr=stderr
    )


def test_request_normalizes_extensions_and_rejects_invalid_fields() -> None:
    request = DialogRequest.from_payload(
        {
            "mode": "save_file",
            "extensions": ["PNG", "*.png", ".fits"],
            "default_suffix": "png",
        }
    )
    assert request.extensions == (".png", ".fits")
    assert request.default_suffix == ".png"
    with pytest.raises(NativeDialogRequestError):
        DialogRequest.from_payload({"mode": "unknown"})
    with pytest.raises(NativeDialogRequestError):
        DialogRequest.from_payload({"mode": "open_file", "extensions": "fits"})


def test_service_selects_file_folder_many_and_save_path(tmp_path: Path) -> None:
    folder = tmp_path / "data"
    folder.mkdir()
    first = folder / "first.fits"
    second = folder / "second.fits"
    first.write_text("one", encoding="utf-8")
    second.write_text("two", encoding="utf-8")
    responses = iter(
        [
            _completed({"status": "selected", "paths": [str(first)]}),
            _completed({"status": "selected", "paths": [str(first), str(second)]}),
            _completed({"status": "selected", "paths": [str(folder)]}),
            _completed({"status": "selected", "paths": [str(folder / "figure")]}),
        ]
    )
    service = NativePathDialogService(
        [tmp_path], runner=lambda *args, **kwargs: next(responses), platform_name="nt"
    )
    assert service.select({"mode": "open_file"}).paths == (first.resolve(),)
    assert service.select({"mode": "open_files"}).paths == (
        first.resolve(),
        second.resolve(),
    )
    assert service.select({"mode": "select_directory"}).paths == (folder.resolve(),)
    assert service.select({"mode": "save_file", "default_suffix": ".png"}).paths == (
        (folder / "figure.png").resolve(),
    )


def test_cancel_keeps_empty_selection(tmp_path: Path) -> None:
    service = NativePathDialogService(
        [tmp_path],
        runner=lambda *args, **kwargs: _completed({"status": "cancelled", "paths": []}),
        platform_name="nt",
    )
    assert service.select({"mode": "select_directory"}).to_dict() == {
        "ok": True,
        "status": "cancelled",
        "paths": [],
    }


def test_service_uses_recent_memory_and_new_worker_module(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    remembered = root / "remembered"
    selected_dir = root / "selected"
    remembered.mkdir(parents=True)
    selected_dir.mkdir()
    store = StateStore(
        tmp_path / "recent.json",
        "recent_paths",
        allowed_keys=("field", "operation", "frontend", "global"),
    )
    memory = RecentPathMemory(store, (root,))
    context = PathMemoryContext("source-map", "load", "input")
    memory.remember(
        context=context,
        dialog_mode="open_file",
        paths=(remembered / "previous.fits",),
    )
    selected = selected_dir / "next.fits"
    selected.write_text("data", encoding="utf-8")
    calls: list[tuple[list[str], dict]] = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return _completed({"status": "selected", "paths": [str(selected)]})

    service = NativePathDialogService(
        (root,),
        runner=runner,
        platform_name="nt",
        memory=memory,
    )
    selection = service.select(
        {
            "mode": "open_file",
            "memory_context": {
                "frontend": "source-map",
                "operation": "load",
                "field": "input",
            },
        }
    )

    assert selection.paths == (selected.resolve(),)
    assert calls[0][0][-2:] == [
        "-m",
        "solar_apps.platform.paths.dialog_worker",
    ]
    worker_payload = json.loads(calls[0][1]["input"])
    assert worker_payload["initial_path"] == str(remembered.resolve())
    worker_environment = calls[0][1]["env"]
    assert "PYTHONPATH" not in worker_environment
    assert worker_environment["SOLAR_APPS_PYTHON_EXECUTABLE"] == (
        service.python_executable
    )
    assert worker_environment["PATH"].split(os.pathsep)[0] == str(
        Path(service.python_executable).parent
    )
    assert memory.resolve_initial(
        context=context,
        dialog_mode="open_file",
    ) == str(selected_dir.resolve())


def test_save_file_requires_immediate_existing_parent(tmp_path: Path) -> None:
    missing_parent = tmp_path / "missing" / "nested"
    with pytest.raises(NativeDialogRequestError, match="parent directory"):
        validate_allowed_path(
            missing_parent / "movie",
            allowed_roots=[tmp_path],
            kind="save_file",
            default_suffix=".mp4",
        )


def test_outside_root_missing_kind_and_symlink_escape_are_rejected(
    tmp_path: Path,
) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    outside_file = outside / "secret.txt"
    outside_file.write_text("secret", encoding="utf-8")
    service = NativePathDialogService(
        [allowed],
        runner=lambda *args, **kwargs: _completed(
            {"status": "selected", "paths": [str(outside_file)]}
        ),
        platform_name="nt",
    )
    with pytest.raises(NativeDialogForbiddenError):
        service.select({"mode": "open_file"})
    with pytest.raises(NativeDialogRequestError):
        validate_allowed_path(
            allowed / "missing.txt", allowed_roots=[allowed], kind="file"
        )
    link = allowed / "escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks are unavailable on this Windows account")
    with pytest.raises(NativeDialogForbiddenError):
        validate_allowed_path(link / "secret.txt", allowed_roots=[allowed], kind="file")


def test_worker_failures_and_platform_are_explicit(tmp_path: Path) -> None:
    unsupported = NativePathDialogService([tmp_path], platform_name="posix")
    with pytest.raises(NativeDialogUnsupportedError):
        unsupported.select({"mode": "select_directory"})
    malformed = NativePathDialogService(
        [tmp_path],
        runner=lambda *args, **kwargs: subprocess.CompletedProcess(
            args=[], returncode=0, stdout="not-json", stderr=""
        ),
        platform_name="nt",
    )
    with pytest.raises(NativeDialogUnavailableError):
        malformed.select({"mode": "select_directory"})


def test_service_rejects_concurrent_dialogs(tmp_path: Path) -> None:
    started = threading.Event()
    release = threading.Event()

    def runner(*args, **kwargs):
        started.set()
        release.wait(timeout=5)
        return _completed({"status": "cancelled", "paths": []})

    service = NativePathDialogService([tmp_path], runner=runner, platform_name="nt")
    thread = threading.Thread(
        target=lambda: service.select({"mode": "select_directory"}), daemon=True
    )
    thread.start()
    assert started.wait(timeout=2)
    with pytest.raises(NativeDialogBusyError):
        service.select({"mode": "select_directory"})
    release.set()
    thread.join(timeout=2)


class _FakeSelection:
    def __init__(self, status: str, paths: tuple[Path, ...] = ()) -> None:
        self.status = status
        self.paths = paths

    def to_dict(self):
        return {
            "ok": True,
            "status": self.status,
            "paths": [str(path) for path in self.paths],
        }


class _FakeDialogService:
    supported = True

    def __init__(self, selection: _FakeSelection) -> None:
        self.selection = selection
        self.calls: list[dict] = []

    def select(self, payload):
        self.calls.append(payload)
        return self.selection


class _FailingDialogService:
    supported = True

    def __init__(self, error: Exception) -> None:
        self.error = error

    def select(self, _payload):
        raise self.error


def test_flask_route_requires_local_token_and_returns_selection(tmp_path: Path) -> None:
    flask = pytest.importorskip("flask")
    app = flask.Flask(__name__)
    selected = tmp_path / "chosen.txt"
    service = _FakeDialogService(_FakeSelection("selected", (selected,)))
    register_native_path_dialog(
        app,
        allowed_roots=[tmp_path],
        service=service,
        client_script_source="window.solarPathDialog = {};",
    )
    client = app.test_client()
    config = client.get("/api/native-path-dialog")
    assert config.status_code == 200
    token = config.get_json()["token"]
    assert (
        client.post("/api/native-path-dialog", json={"mode": "open_file"}).status_code
        == 403
    )
    response = client.post(
        "/api/native-path-dialog",
        json={"mode": "open_file"},
        headers={"X-Native-Dialog-Token": token},
    )
    assert response.status_code == 200
    assert response.get_json()["paths"] == [str(selected)]
    assert client.get("/api/native-path-dialog/client.js").status_code == 200
    remote = client.get(
        "/api/native-path-dialog", environ_overrides={"REMOTE_ADDR": "192.0.2.1"}
    )
    assert remote.status_code == 403


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (NativeDialogRequestError("bad request"), 400),
        (NativeDialogForbiddenError("outside root"), 403),
        (NativeDialogBusyError("busy"), 409),
        (NativeDialogUnsupportedError("unsupported"), 501),
        (NativeDialogUnavailableError("worker failed"), 503),
    ],
)
def test_flask_route_maps_dialog_failures(error: Exception, status_code: int) -> None:
    flask = pytest.importorskip("flask")
    app = flask.Flask(f"failure_{status_code}")
    register_native_path_dialog(
        app,
        allowed_roots=[Path.cwd()],
        service=_FailingDialogService(error),
    )
    client = app.test_client()
    token = client.get("/api/native-path-dialog").get_json()["token"]

    response = client.post(
        "/api/native-path-dialog",
        json={"mode": "open_file"},
        headers={"X-Native-Dialog-Token": token},
    )

    assert response.status_code == status_code
    assert response.get_json()["ok"] is False


def test_flask_route_rejects_non_object_json(tmp_path: Path) -> None:
    flask = pytest.importorskip("flask")
    app = flask.Flask("invalid_json")
    register_native_path_dialog(
        app,
        allowed_roots=[tmp_path],
        service=_FakeDialogService(_FakeSelection("cancelled")),
    )
    client = app.test_client()
    token = client.get("/api/native-path-dialog").get_json()["token"]

    response = client.post(
        "/api/native-path-dialog",
        json=["not", "an", "object"],
        headers={"X-Native-Dialog-Token": token},
    )

    assert response.status_code == 400
