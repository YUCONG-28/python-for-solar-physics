from __future__ import annotations

import importlib.util
import json
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest


def _flask_client(store, manager):
    flask = pytest.importorskip("flask")

    from solar_toolkit.webapp.radio_workspace import create_radio_blueprint

    app = flask.Flask(__name__)
    app.register_blueprint(
        create_radio_blueprint(store=store, run_manager=manager),
    )
    return app.test_client()


@dataclass
class _BatchRun:
    id: str
    batch_order: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": "queued",
            "provenance": {"batch_order": self.batch_order},
        }


class _RecordingBatchManager:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[dict[str, Any]]]] = []

    def start_batch(
        self, workspace_id: str, actions: list[dict[str, Any]]
    ) -> list[_BatchRun]:
        copied_actions = [dict(action) for action in actions]
        self.calls.append((workspace_id, copied_actions))
        return [
            _BatchRun(id=f"run-{index}", batch_order=index)
            for index, _action in enumerate(actions)
        ]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {
            "actions": [
                {
                    "module_id": "data-configuration",
                    "action_id": "raw-quality",
                }
            ]
        },
        {
            "confirmed": False,
            "actions": [
                {
                    "module_id": "data-configuration",
                    "action_id": "raw-quality",
                }
            ],
        },
        {"confirmed": True},
        {"confirmed": True, "actions": []},
    ],
)
def test_batch_api_requires_explicit_confirmation_and_nonempty_actions(
    tmp_path: Path,
    payload: dict[str, Any],
):
    from solar_toolkit.webapp.radio_workspace import RadioWorkspaceStore

    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[tmp_path])
    manager = _RecordingBatchManager()
    client = _flask_client(store, manager)

    response = client.post(
        "/api/radio/workspaces/workspace-1/runs/batch",
        json=payload,
    )

    assert response.status_code == 400
    assert response.get_json()["ok"] is False
    assert manager.calls == []


def test_confirmed_batch_api_preserves_the_reviewed_action_order(tmp_path: Path):
    from solar_toolkit.webapp.radio_workspace import RadioWorkspaceStore

    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[tmp_path])
    manager = _RecordingBatchManager()
    client = _flask_client(store, manager)
    actions = [
        {
            "module_id": "data-configuration",
            "action_id": "raw-quality",
            "form": {"freqs": "149"},
        },
        {
            "module_id": "imaging-localization",
            "action_id": "extract-centers",
            "form": {"polarization": "L"},
        },
        {
            "module_id": "physical-diagnostics",
            "action_id": "analyze-existing-tables",
            "form": {"drift_csv": "selected-drift.csv"},
        },
    ]

    response = client.post(
        "/api/radio/workspaces/workspace-1/runs/batch",
        json={"confirmed": True, "actions": actions},
    )

    assert response.status_code == 202
    assert manager.calls == [("workspace-1", actions)]
    body = response.get_json()
    assert [item["id"] for item in body["runs"]] == ["run-0", "run-1", "run-2"]
    assert [item["provenance"]["batch_order"] for item in body["runs"]] == [
        0,
        1,
        2,
    ]


def _manifest_with_artifact(store, workspace_id: str, run_id: str):
    from solar_toolkit.webapp.radio_workspace import (
        SCHEMA_VERSION,
        RadioArtifact,
        RadioRunManifest,
    )

    artifact = RadioArtifact(
        schema_version=SCHEMA_VERSION,
        id="report",
        relative_path="report.txt",
        kind="text",
        mime_type="text/plain",
        artifact_type="physics-report",
        source_run_id=run_id,
        size=0,
        previewable=True,
    )
    manifest = RadioRunManifest(
        schema_version=SCHEMA_VERSION,
        id=run_id,
        workspace_id=workspace_id,
        module_id="physical-diagnostics",
        action_id="analyze-existing-tables",
        status="succeeded",
        command=[sys.executable, "-c", "pass"],
        cwd=str(store.output_root),
        request={},
        resolved_config={},
        input_sources=[],
        provenance={},
        artifacts=[artifact],
        created_at="2026-07-13T00:00:00+00:00",
        finished_at="2026-07-13T00:00:01+00:00",
        returncode=0,
    )
    store.create_run(manifest)
    artifact_path = store.run_dir(workspace_id, run_id) / "artifacts" / "report.txt"
    artifact_path.write_text("safe report", encoding="utf-8")
    return manifest, artifact_path


def test_tampered_artifact_manifest_is_rejected_without_content_disclosure(
    tmp_path: Path,
):
    from solar_toolkit.webapp.radio_workspace import RadioWorkspaceStore

    output = tmp_path / "output"
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.txt"
    secret.write_text("TOP-SECRET-CONTENT", encoding="utf-8")
    store = RadioWorkspaceStore(output, allowed_roots=[tmp_path])
    workspace = store.create_workspace(workspace_id="artifact-manifest")
    manifest, _artifact_path = _manifest_with_artifact(
        store, workspace.id, "manifest-run"
    )

    run_json = store.run_dir(workspace.id, manifest.id) / "run.json"
    payload = json.loads(run_json.read_text(encoding="utf-8"))
    payload["artifacts"][0]["relative_path"] = str(secret)
    run_json.write_text(json.dumps(payload), encoding="utf-8")

    client = _flask_client(store, object())
    response = client.get(
        f"/api/radio/workspaces/{workspace.id}/runs/{manifest.id}/"
        f"artifacts/{manifest.artifacts[0].id}?download=1"
    )

    assert response.status_code == 400
    assert b"TOP-SECRET-CONTENT" not in response.data
    assert str(secret).encode() not in response.data


def test_artifact_symlink_swap_is_rejected_without_content_disclosure(tmp_path: Path):
    from solar_toolkit.webapp.radio_workspace import RadioWorkspaceStore

    output = tmp_path / "output"
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.txt"
    secret.write_text("TOP-SECRET-CONTENT", encoding="utf-8")
    store = RadioWorkspaceStore(output, allowed_roots=[tmp_path])
    workspace = store.create_workspace(workspace_id="artifact-symlink")
    manifest, artifact_path = _manifest_with_artifact(
        store, workspace.id, "symlink-run"
    )
    artifact_path.unlink()
    try:
        artifact_path.symlink_to(secret)
    except OSError:
        pytest.skip("File symlinks are unavailable in this environment")

    client = _flask_client(store, object())
    response = client.get(
        f"/api/radio/workspaces/{workspace.id}/runs/{manifest.id}/"
        f"artifacts/{manifest.artifacts[0].id}?download=1"
    )

    assert response.status_code == 403
    assert b"TOP-SECRET-CONTENT" not in response.data
    assert str(secret).encode() not in response.data


def test_physical_required_any_is_rejected_before_a_run_is_created(tmp_path: Path):
    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
    )

    launches = 0

    def unexpected_popen(*_args, **_kwargs):
        nonlocal launches
        launches += 1
        raise AssertionError("a worker must not launch for an invalid request")

    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[tmp_path])
    workspace = store.create_workspace(workspace_id="physical-required-any")
    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
        popen_factory=unexpected_popen,
    )
    client = _flask_client(store, manager)
    try:
        response = client.post(
            f"/api/radio/workspaces/{workspace.id}/runs",
            json={
                "module_id": "physical-diagnostics",
                "action_id": "analyze-existing-tables",
                "form": {},
            },
        )

        assert response.status_code == 400
        assert response.get_json()["error"] == (
            "Run requires at least one of: gaussian_csv, drift_csv"
        )
        assert store.list_runs(workspace.id) == []
        assert list((store.workspace_dir(workspace.id) / "runs").iterdir()) == []
        assert launches == 0
    finally:
        manager.close(cancel_running=True)


def test_workspace_all_fields_and_interrupted_recovery_survive_restarts(
    tmp_path: Path,
):
    from solar_toolkit.webapp.radio_workspace import (
        MODULES,
        SCHEMA_VERSION,
        RadioRunManager,
        RadioRunManifest,
        RadioWorkspaceStore,
    )

    output = tmp_path / "output"
    shared = tmp_path / "shared"
    shared.mkdir()
    store = RadioWorkspaceStore(output, allowed_roots=[tmp_path])
    workspace = store.create_workspace(
        workspace_id="restart-workspace",
        name="Recovered Event",
        event_preset={"id": "radio-20250503", "observer": "MUSER"},
        shared_paths={"radio_dir": str(shared)},
        advanced_config={
            "physical-diagnostics": {"density_model": "newkirk"},
            "quality": {"strict": True},
        },
        concurrency=4,
    )
    module_ids = [module.id for module in MODULES]
    workspace = store.update_workspace(
        workspace.id,
        {
            "enabled_modules": [
                "data-configuration",
                "physical-diagnostics",
                "trajectory-media",
                "runs-results",
            ],
            "module_order": list(reversed(module_ids)),
            "collapsed_modules": [
                "data-configuration",
                "trajectory-media",
            ],
            "pinned_modules": ["physical-diagnostics"],
        },
    )
    expected_workspace = workspace.to_dict()

    for run_id, status in (("queued-run", "queued"), ("running-run", "running")):
        store.create_run(
            RadioRunManifest(
                schema_version=SCHEMA_VERSION,
                id=run_id,
                workspace_id=workspace.id,
                module_id="data-configuration",
                action_id="raw-quality",
                status=status,
                command=[sys.executable, "-c", "pass"],
                cwd=str(tmp_path),
                request={"form": {"root": str(shared)}},
                resolved_config={"root": str(shared)},
                input_sources=[],
                provenance={"dependencies_auto_run": False},
                created_at="2026-07-13T00:00:00+00:00",
                started_at=(
                    "2026-07-13T00:00:01+00:00" if status == "running" else None
                ),
            )
        )

    reopened = RadioWorkspaceStore(output, allowed_roots=[tmp_path])
    assert reopened.load_workspace(workspace.id).to_dict() == expected_workspace
    first_manager = RadioRunManager(
        reopened,
        repo_root=tmp_path,
        python_executable=sys.executable,
    )
    try:
        first_recovery = {
            run_id: reopened.load_run(workspace.id, run_id).to_dict()
            for run_id in ("queued-run", "running-run")
        }
        for manifest in first_recovery.values():
            assert manifest["status"] == "interrupted"
            assert manifest["finished_at"]
            assert "service stopped" in manifest["error"]
    finally:
        first_manager.close(cancel_running=True)

    run_files = {
        run_id: (reopened.run_dir(workspace.id, run_id) / "run.json")
        for run_id in ("queued-run", "running-run")
    }
    before_second_restart = {
        run_id: path.read_bytes() for run_id, path in run_files.items()
    }
    second_store = RadioWorkspaceStore(output, allowed_roots=[tmp_path])
    second_manager = RadioRunManager(
        second_store,
        repo_root=tmp_path,
        python_executable=sys.executable,
    )
    try:
        assert second_store.load_workspace(workspace.id).to_dict() == expected_workspace
        assert {
            run_id: second_store.load_run(workspace.id, run_id).to_dict()
            for run_id in ("queued-run", "running-run")
        } == first_recovery
        assert {
            run_id: path.read_bytes() for run_id, path in run_files.items()
        } == before_second_restart

        client = _flask_client(second_store, second_manager)
        response = client.get(f"/api/radio/workspaces/{workspace.id}")
        assert response.status_code == 200
        assert response.get_json()["workspace"] == expected_workspace
    finally:
        second_manager.close(cancel_running=True)


def test_runtime_user_roots_are_atomic_and_preserve_workspace_outputs(
    tmp_path: Path,
):
    from solar_toolkit.webapp.radio_workspace import RadioWorkspaceStore

    startup = tmp_path / "startup"
    selected = tmp_path / "selected"
    custom_output = startup / "custom-output"
    startup.mkdir()
    selected.mkdir()
    custom_output.mkdir()
    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[startup])
    workspace = store.create_workspace(
        workspace_id="protected-output",
        output_root=custom_output,
    )

    store.replace_user_roots([selected, selected / "."])

    payload = store.allowed_roots_payload()
    assert payload["user_roots"] == [str(selected.resolve())]
    assert payload["startup_roots"] == [str(startup.resolve())]
    assert payload["output_root"] == str((tmp_path / "output").resolve())
    assert payload["protected_roots"] == [
        str((tmp_path / "output").resolve()),
        str(custom_output.resolve()),
    ]
    assert payload["effective_roots"] == [
        str(selected.resolve()),
        str((tmp_path / "output").resolve()),
        str(custom_output.resolve()),
    ]
    assert store.browser.resolve(selected, directory_only=True) == selected.resolve()
    assert store.browser.resolve(custom_output, directory_only=True) == (
        custom_output.resolve()
    )
    with pytest.raises(PermissionError, match="outside allowed roots"):
        store.browser.resolve(startup, directory_only=True)

    reopened = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[selected])
    assert reopened.load_workspace(workspace.id).output_root == str(
        custom_output.resolve()
    )
    assert custom_output.resolve() in reopened.protected_roots
    assert reopened.browser.resolve(custom_output, directory_only=True) == (
        custom_output.resolve()
    )

    store.delete_workspace(workspace.id)
    assert store.protected_roots == ((tmp_path / "output").resolve(),)
    with pytest.raises(PermissionError, match="outside allowed roots"):
        store.browser.resolve(custom_output, directory_only=True)


def test_runtime_user_roots_reject_invalid_replacements_without_mutation(
    tmp_path: Path,
):
    from solar_toolkit.webapp.radio_workspace import RadioWorkspaceStore

    startup = tmp_path / "startup"
    startup.mkdir()
    not_a_directory = tmp_path / "file.txt"
    not_a_directory.write_text("file", encoding="utf-8")
    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[startup])
    original_roots = store.browser.allowed_roots

    invalid_cases = [
        ([], ValueError),
        ([""], ValueError),
        (["relative/path"], ValueError),
        ([tmp_path / "missing"], FileNotFoundError),
        ([not_a_directory], NotADirectoryError),
        ([1], TypeError),
    ]
    for roots, error_type in invalid_cases:
        with pytest.raises(error_type):
            store.replace_user_roots(roots)
        assert store.browser.allowed_roots == original_roots

    too_many = []
    for index in range(33):
        root = tmp_path / f"root-{index}"
        root.mkdir()
        too_many.append(root)
    with pytest.raises(ValueError, match="No more than 32"):
        store.set_user_roots(too_many)
    assert store.browser.allowed_roots == original_roots


def test_run_manager_uses_replaced_store_browser_for_future_requests(tmp_path: Path):
    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
    )

    startup = tmp_path / "startup"
    selected = tmp_path / "selected"
    startup.mkdir()
    selected.mkdir()
    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[startup])
    workspace = store.create_workspace(workspace_id="dynamic-roots")
    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
    )
    try:
        manager.resolve_request(
            workspace.id,
            "data-configuration",
            "raw-quality",
            {"form": {"root": str(startup)}},
        )
        with pytest.raises(PermissionError, match="outside allowed roots"):
            manager.resolve_request(
                workspace.id,
                "data-configuration",
                "raw-quality",
                {"form": {"root": str(selected)}},
            )

        store.replace_user_roots([selected])
        manager.resolve_request(
            workspace.id,
            "data-configuration",
            "raw-quality",
            {"form": {"root": str(selected)}},
        )
        with pytest.raises(PermissionError, match="outside allowed roots"):
            manager.resolve_request(
                workspace.id,
                "data-configuration",
                "raw-quality",
                {"form": {"root": str(startup)}},
            )
    finally:
        manager.close(cancel_running=True)


def test_concurrent_root_replacement_blocks_new_workspaces_in_the_old_root(
    tmp_path: Path,
):
    from solar_toolkit.webapp.radio_workspace import RadioWorkspaceStore

    old_root = tmp_path / "old-root"
    new_root = tmp_path / "new-root"
    old_root.mkdir()
    new_root.mkdir()
    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[old_root])
    start = threading.Barrier(2)
    replacement_done = threading.Event()
    failures: list[BaseException] = []

    def replace_roots() -> None:
        start.wait()
        store.replace_user_roots([new_root])
        replacement_done.set()

    def create_after_replacement() -> None:
        start.wait()
        if not replacement_done.wait(timeout=5):
            failures.append(TimeoutError("root replacement did not complete"))
            return
        try:
            store.create_workspace(
                workspace_id="old-root-after-replacement",
                output_root=old_root,
                shared_paths={"radio_root": str(old_root)},
            )
        except BaseException as exc:
            failures.append(exc)

    replacement_thread = threading.Thread(target=replace_roots)
    creation_thread = threading.Thread(target=create_after_replacement)
    replacement_thread.start()
    creation_thread.start()
    replacement_thread.join(timeout=5)
    creation_thread.join(timeout=5)

    assert not replacement_thread.is_alive()
    assert not creation_thread.is_alive()
    assert len(failures) == 1
    assert isinstance(failures[0], PermissionError)
    assert "outside allowed roots" in str(failures[0])
    assert not (
        old_root / "radio_workbench" / "old-root-after-replacement" / "workspace.json"
    ).exists()
    assert [item.id for item in store.list_workspaces()] == []


def test_workspace_creation_holds_root_lock_from_validation_through_persistence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from solar_toolkit.webapp.radio_workspace import RadioWorkspaceStore

    old_root = tmp_path / "old-root"
    new_root = tmp_path / "new-root"
    old_root.mkdir()
    new_root.mkdir()
    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[old_root])
    validation_reached = threading.Event()
    release_validation = threading.Event()
    replacement_started = threading.Event()
    replacement_lock_attempted = threading.Event()
    replacement_finished = threading.Event()
    creation_errors: list[BaseException] = []
    replacement_errors: list[BaseException] = []
    original_validate = store._validate_shared_paths
    original_lock = store._lock

    class ObservedRLock:
        def __enter__(self):
            if threading.current_thread().name == "root-replacer":
                replacement_lock_attempted.set()
            original_lock.acquire()
            return self

        def __exit__(self, _exc_type, _exc, _traceback):
            original_lock.release()
            return False

    monkeypatch.setattr(store, "_lock", ObservedRLock())

    def pause_after_shared_path_validation(shared_paths: dict[str, str]) -> None:
        original_validate(shared_paths)
        validation_reached.set()
        if not release_validation.wait(timeout=5):
            raise TimeoutError("workspace validation pause was not released")

    monkeypatch.setattr(
        store,
        "_validate_shared_paths",
        pause_after_shared_path_validation,
    )

    def create_workspace() -> None:
        try:
            store.create_workspace(
                workspace_id="create-during-root-replacement",
                output_root=old_root,
                shared_paths={"radio_root": str(old_root)},
            )
        except BaseException as exc:
            creation_errors.append(exc)

    def replace_roots() -> None:
        replacement_started.set()
        try:
            store.replace_user_roots([new_root])
        except BaseException as exc:
            replacement_errors.append(exc)
        finally:
            replacement_finished.set()

    creation_thread = threading.Thread(target=create_workspace)
    replacement_thread = threading.Thread(target=replace_roots, name="root-replacer")
    creation_thread.start()
    assert validation_reached.wait(timeout=5)
    replacement_thread.start()
    assert replacement_started.wait(timeout=5)
    assert replacement_lock_attempted.wait(timeout=5)
    replacement_completed_during_validation = replacement_finished.wait(timeout=1)
    release_validation.set()
    creation_thread.join(timeout=5)
    replacement_thread.join(timeout=5)

    assert replacement_completed_during_validation is False
    assert not creation_thread.is_alive()
    assert not replacement_thread.is_alive()
    assert creation_errors == []
    assert replacement_errors == []
    workspace = store.load_workspace("create-during-root-replacement")
    assert workspace.output_root == str(old_root.resolve())
    assert store.user_roots == (new_root.resolve(),)
    assert old_root.resolve() in store.protected_roots
    assert (old_root / "radio_workbench" / workspace.id / "workspace.json").is_file()


@pytest.mark.skipif(
    importlib.util.find_spec("flask") is None,
    reason="Flask is optional; install the app extra to test HTTP routes.",
)
def test_allowed_roots_api_requires_local_host_and_per_start_token(tmp_path: Path):
    from solar_toolkit.webapp.server import create_app

    startup = tmp_path / "startup"
    selected = tmp_path / "selected"
    startup.mkdir()
    selected.mkdir()
    app = create_app(
        allowed_roots=[startup],
        python_executable=sys.executable,
        repo_root=tmp_path,
        radio_output_root=tmp_path / "output-one",
    )
    second_app = create_app(
        allowed_roots=[startup],
        python_executable=sys.executable,
        repo_root=tmp_path,
        radio_output_root=tmp_path / "output-two",
    )
    client = app.test_client()
    second_client = second_app.test_client()
    try:
        config_response = client.get("/api/client-config")
        config = config_response.get_json()
        token = config["radio_root_token"]
        assert config_response.headers["Cache-Control"] == "no-store"
        assert (
            token
            != second_client.get("/api/client-config").get_json()["radio_root_token"]
        )

        roots = client.get("/api/radio/allowed-roots").get_json()
        assert roots["user_roots"] == [str(startup.resolve())]
        assert roots["startup_roots"] == [str(startup.resolve())]

        assert (
            client.put(
                "/api/radio/allowed-roots", json={"roots": [str(selected)]}
            ).status_code
            == 403
        )
        assert (
            client.put(
                "/api/radio/allowed-roots",
                json={"roots": [str(selected)]},
                headers={"X-Radio-Root-Token": "wrong"},
            ).status_code
            == 403
        )
        assert (
            client.put(
                "/api/radio/allowed-roots",
                json={"roots": [str(selected)]},
                headers={
                    "Host": "attacker.example:5000",
                    "X-Radio-Root-Token": token,
                },
            ).status_code
            == 403
        )
        assert (
            client.put(
                "/api/radio/allowed-roots",
                json={"roots": [str(selected)]},
                headers={"X-Radio-Root-Token": token},
                environ_base={"REMOTE_ADDR": "203.0.113.10"},
            ).status_code
            == 403
        )

        updated = client.put(
            "/api/radio/allowed-roots",
            json={"roots": [str(selected)]},
            headers={"X-Radio-Root-Token": token},
        )
        assert updated.status_code == 200
        assert updated.get_json()["user_roots"] == [str(selected.resolve())]
        assert (
            client.get(
                "/api/radio/files", query_string={"path": str(selected)}
            ).status_code
            == 200
        )
        assert (
            client.get(
                "/api/radio/files", query_string={"path": str(startup)}
            ).status_code
            == 403
        )

        remote_config = client.get(
            "/api/client-config",
            environ_base={"REMOTE_ADDR": "203.0.113.10"},
        )
        hostile_host_config = client.get(
            "/api/client-config", headers={"Host": "attacker.example:5000"}
        )
        assert "radio_root_token" not in remote_config.get_json()
        assert "radio_root_token" not in hostile_host_config.get_json()
        assert remote_config.headers["Cache-Control"] == "no-store"
    finally:
        app.extensions["radio_workspace"]["close"]()
        second_app.extensions["radio_workspace"]["close"]()
