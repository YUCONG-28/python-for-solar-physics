from __future__ import annotations

import importlib.util
import io
import re
import sys
import threading
import time
from pathlib import Path

import pytest


class _FakeStdout:
    def __init__(self, lines: list[str] | None = None) -> None:
        self._lines = list(lines or ["radio worker completed\n"])

    def readline(self) -> str:
        return self._lines.pop(0) if self._lines else ""

    def close(self) -> None:
        return None


class _CompletingProcess:
    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode
        self.stdout = _FakeStdout()
        self.pid = None

    def poll(self) -> int:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        return self.returncode

    def terminate(self) -> None:
        self.returncode = -15

    def kill(self) -> None:
        self.returncode = -9


def _artifact_popen(command: list[str], **_kwargs) -> _CompletingProcess:
    for flag in ("--out", "--out-dir", "--output-dir"):
        if flag not in command:
            continue
        output = Path(command[command.index(flag) + 1])
        if output.suffix:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("x,y\n1,2\n", encoding="utf-8")
        else:
            output.mkdir(parents=True, exist_ok=True)
            (output / "result.json").write_text('{"ok": true}\n', encoding="utf-8")
        break
    return _CompletingProcess()


def test_radio_catalog_fuses_eight_optional_modules_and_layout_presets():
    from solar_toolkit.webapp.radio_workspace import EVENT_PRESETS, MODULES, PRESETS

    assert [module.id for module in MODULES] == [
        "data-configuration",
        "imaging-localization",
        "roi-light-curves",
        "spectrogram-drift",
        "physical-diagnostics",
        "context-overlays",
        "trajectory-media",
        "runs-results",
    ]
    assert all(module.default_enabled is module.always_available for module in MODULES)
    assert all(module.default_collapsed for module in MODULES)
    assert MODULES[-1].always_available is True
    assert set(PRESETS) == {
        "source-localization",
        "roi-study",
        "burst-physics",
        "multi-instrument-context",
        "full-analysis",
    }
    assert set(EVENT_PRESETS) == {"radio-20250124", "radio-20250503"}
    assert PRESETS["roi-study"]["module_ids"] == [
        "data-configuration",
        "roi-light-curves",
        "runs-results",
    ]
    visible_items: list[str] = []
    for module in MODULES:
        visible_items.extend(
            [
                module.title,
                module.description,
                *[action.title for action in module.actions],
                *[action.description for action in module.actions],
            ]
        )
    visible_text = "\n".join(visible_items)
    assert not re.search(r"[\u4e00-\u9fff]", visible_text)
    imaging = next(item for item in MODULES if item.id == "imaging-localization")
    inspect = imaging.get_action("inspect-source-map")
    fit = imaging.get_action("fit-gaussian")
    assert inspect.config_json_flag == "--workspace-config-json"
    assert inspect.default_config["features"]["gaussian_overlay"] is False
    assert fit.default_config["features"]["gaussian_overlay"] is True
    assert fit.accepts_artifacts == ("radio-fits",)
    rrll = imaging.get_action("rrll-percentile-comparison")
    assert rrll.accepts_artifacts == ("cso-data",)
    rrll_fields = {field["name"]: field for field in rrll.input_schema}
    assert rrll_fields["radio_root"]["required"] is True
    assert rrll_fields["spectrogram_file"]["artifact_types"] == ["cso-data"]
    physical = next(item for item in MODULES if item.id == "physical-diagnostics")
    table_action = physical.get_action("analyze-existing-tables")
    assert set(table_action.accepts_artifacts) == {"gaussian-table", "drift-table"}
    spectrogram = next(item for item in MODULES if item.id == "spectrogram-drift")
    assert "spectrogram-metadata" in spectrogram.produces_artifacts
    select_drift = spectrogram.get_action("select-drift-lines")
    drift_fields = {field["name"]: field for field in select_drift.input_schema}
    assert drift_fields["spectrogram_metadata"]["artifact_types"] == [
        "spectrogram-metadata"
    ]
    blocked = {"--select-drift", "--drift-port", "--drift-launch-policy"}
    for action_id in ("dynamic-spectrum-drift", "cso-legacy-mode"):
        action = spectrogram.get_action(action_id)
        assert set(action.blocked_arguments) == blocked
        assert set(action.to_dict()["blocked_arguments"]) == blocked
    roi_module = next(item for item in MODULES if item.id == "roi-light-curves")
    select_roi = roi_module.get_action("select-roi")
    select_fields = {field["name"]: field for field in select_roi.input_schema}
    assert select_fields["selected_files_json"]["type"] == "json"
    assert select_fields["selected_files_json"]["hidden"] is True
    extract = roi_module.get_action("extract-light-curves")
    fields = {field["name"]: field for field in extract.input_schema}
    assert extract.run_required_any_fields == ("roi_bounds", "roi_json")
    assert fields["pattern"]["default"] == "*.fits"
    assert fields["no_recursive"]["cli_flag"] == "--no-recursive"
    assert fields["time_start"]["cli_flag"] == "--time-start"
    assert fields["time_end"]["cli_flag"] == "--time-end"
    assert fields["pair_time_tolerance_sec"]["default"] == 0.5
    assert fields["selected_products"]["type"] == "multiselect"
    assert set(fields["selected_products"]["default"]) == {
        "csv",
        "json",
        "reference_png",
        "lightcurve_png",
        "lightcurve_detail_png",
        "lightcurve_normalized_png",
    }
    assert fields["detail_frequency_mhz"]["cli_flag"] == ("--detail-frequency-mhz")


def test_workspace_store_persists_layout_concurrency_and_custom_output_root(
    tmp_path: Path,
):
    from solar_toolkit.webapp.radio_workspace import RadioWorkspaceStore

    default_root = tmp_path / "default"
    custom_root = tmp_path / "custom"
    custom_root.mkdir()
    store = RadioWorkspaceStore(default_root, allowed_roots=[tmp_path])
    workspace = store.create_workspace(
        workspace_id="workspace-one",
        name="Event workspace",
        output_root=custom_root,
        concurrency=3,
    )

    assert workspace.output_root == str(custom_root.resolve())
    assert workspace.enabled_modules == ["runs-results"]
    assert workspace.concurrency == 3
    assert (custom_root / "radio_workbench" / workspace.id / "workspace.json").is_file()

    updated = store.update_layout(
        workspace.id,
        {
            "preset_id": "source-localization",
            "pinned_modules": ["imaging-localization"],
        },
    )
    assert updated.enabled_modules == [
        "data-configuration",
        "imaging-localization",
        "trajectory-media",
        "runs-results",
    ]
    assert updated.pinned_modules == ["imaging-localization"]

    reopened = RadioWorkspaceStore(default_root, allowed_roots=[tmp_path])
    assert reopened.load_workspace(workspace.id).module_order == updated.module_order
    assert [item.id for item in reopened.list_workspaces()] == [workspace.id]
    with pytest.raises(ValueError, match="output_root cannot be changed"):
        reopened.update_workspace(workspace.id, {"output_root": str(default_root)})
    with pytest.raises(ValueError, match="between 1 and 4"):
        reopened.update_workspace(workspace.id, {"concurrency": 5})


def test_safe_file_browser_blocks_traversal_and_outside_symlinks(tmp_path: Path):
    from solar_toolkit.webapp.radio_workspace import SafePathBrowser

    allowed = tmp_path / "allowed"
    blocked = tmp_path / "blocked"
    allowed.mkdir()
    blocked.mkdir()
    (allowed / "inside.fits").write_bytes(b"fits")
    browser = SafePathBrowser([allowed])

    listing = browser.list_directory(allowed)
    assert [item["name"] for item in listing["entries"]] == ["inside.fits"]
    with pytest.raises(PermissionError, match="outside allowed roots"):
        browser.resolve(blocked / "outside.fits", must_exist=False)
    with pytest.raises(PermissionError, match="outside allowed roots"):
        browser.resolve(allowed / ".." / "blocked", must_exist=True)

    link = allowed / "outside-link"
    try:
        link.symlink_to(blocked, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks are not available in this environment")
    assert "outside-link" not in {
        item["name"] for item in browser.list_directory(allowed)["entries"]
    }


def test_request_resolution_uses_fixed_precedence_and_never_runs_dependencies(
    tmp_path: Path,
):
    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
    )

    roots = []
    for name in ("event", "shared", "advanced", "form"):
        path = tmp_path / name
        path.mkdir()
        roots.append(path)
    event, shared, advanced, form = roots
    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[tmp_path])
    workspace = store.create_workspace(
        workspace_id="precedence",
        event_preset={
            "imaging-localization": {
                "extract-centers": {"radio_dir": str(event), "threshold": 0.7}
            }
        },
        shared_paths={"radio_dir": str(shared)},
        advanced_config={
            "imaging-localization": {
                "extract-centers": {"radio_dir": str(advanced), "threshold": 0.8}
            }
        },
    )
    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
        popen_factory=_artifact_popen,
    )
    try:
        resolved = manager.resolve_request(
            workspace.id,
            "imaging-localization",
            "extract-centers",
            {
                "advanced_config": {"threshold": 0.9},
                "form": {"radio_dir": str(form), "threshold": 0.99},
                "arguments": ["--future-compatible-option"],
            },
        )
        assert resolved["config"]["radio_dir"] == str(form)
        assert resolved["config"]["threshold"] == 0.99
        assert resolved["provenance"]["dependencies_auto_run"] is False
        assert resolved["provenance"]["configuration_precedence"] == [
            "package_defaults",
            "event_preset",
            "workspace_shared_paths",
            "advanced_config",
            "action_form",
        ]
        assert resolved["command"][:3] == [
            sys.executable,
            "-m",
            "solar_toolkit.radio.centers",
        ]
        assert "--future-compatible-option" in resolved["command"]
        for arguments in (
            ["--threshold", "0.2"],
            ["--threshold=0.2"],
            ["--out", str(tmp_path / "override.csv")],
            [f"--out={tmp_path / 'override.csv'}"],
        ):
            with pytest.raises(ValueError, match="managed by the Radio Workspace"):
                manager.resolve_request(
                    workspace.id,
                    "imaging-localization",
                    "extract-centers",
                    {
                        "form": {"radio_dir": str(form)},
                        "arguments": arguments,
                    },
                )
        for argument in (
            "--config=radio_20250124_config",
            '--workspace-config-json={"mode":"single_band"}',
        ):
            with pytest.raises(ValueError, match="managed by the Radio Workspace"):
                manager.resolve_request(
                    workspace.id,
                    "imaging-localization",
                    "fit-gaussian",
                    {
                        "form": {"radio_dir": str(form)},
                        "arguments": [argument],
                    },
                )
        with pytest.raises(TypeError, match="JSON array"):
            manager.resolve_request(
                workspace.id,
                "imaging-localization",
                "extract-centers",
                {"form": {"radio_dir": str(form)}, "arguments": "--help"},
            )
    finally:
        manager.close(cancel_running=True)


def test_workspace_cso_actions_force_cli_only_and_block_server_arguments(
    tmp_path: Path,
):
    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
    )

    cso_file = tmp_path / "cso.fits"
    cso_file.write_bytes(b"SIMPLE  =                    T")
    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[tmp_path])
    workspace = store.create_workspace(workspace_id="cso-cli-only")
    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
        popen_factory=_artifact_popen,
    )
    action_payloads = {
        "dynamic-spectrum-drift": {"form": {"file_path": str(cso_file)}},
        "cso-legacy-mode": {"form": {"file_path": str(cso_file)}},
    }
    dangerous_arguments = (
        ["--select-drift"],
        ["--select-drift=true"],
        ["--drift-port", "9123"],
        ["--drift-port=9123"],
        ["--drift-launch-policy", "always"],
        ["--drift-launch-policy=always"],
    )
    try:
        for action_id, payload in action_payloads.items():
            resolved = manager.resolve_request(
                workspace.id,
                "spectrogram-drift",
                action_id,
                payload,
            )
            command = resolved["command"]
            assert command.count("--drift-launch-policy") == 1
            policy_index = command.index("--drift-launch-policy")
            assert command[policy_index + 1] == "cli_only"
            assert "--no-drift-browser" in command
            assert "--export-drift-preview" in command
            assert "--output-dir" in command

            for arguments in dangerous_arguments:
                with pytest.raises(ValueError, match="blocked by the Radio Workspace"):
                    manager.resolve_request(
                        workspace.id,
                        "spectrogram-drift",
                        action_id,
                        {**payload, "arguments": arguments},
                    )

            compatible = manager.resolve_request(
                workspace.id,
                "spectrogram-drift",
                action_id,
                {**payload, "arguments": ["--future-cso-option"]},
            )
            assert "--future-cso-option" in compatible["command"]
    finally:
        manager.close(cancel_running=True)


def test_advanced_event_actions_require_explicit_allowed_root_paths(tmp_path: Path):
    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
    )

    allowed = tmp_path / "allowed"
    allowed.mkdir()
    radio_root = allowed / "radio"
    radio_root.mkdir()
    cso_file = allowed / "spectrum.fits"
    cso_file.write_bytes(b"SIMPLE  =                    T")
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_file = outside / "outside.fits"
    outside_file.write_bytes(b"SIMPLE  =                    T")
    store = RadioWorkspaceStore(allowed / "output", allowed_roots=[allowed])
    workspace = store.create_workspace(workspace_id="advanced-explicit-paths")
    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
        popen_factory=_artifact_popen,
    )
    try:
        with pytest.raises(ValueError, match="Missing required fields"):
            manager.resolve_request(
                workspace.id,
                "spectrogram-drift",
                "cso-legacy-mode",
                {},
            )
        with pytest.raises(PermissionError, match="outside allowed roots"):
            manager.resolve_request(
                workspace.id,
                "spectrogram-drift",
                "cso-legacy-mode",
                {"form": {"file_path": str(outside_file)}},
            )
        legacy = manager.resolve_request(
            workspace.id,
            "spectrogram-drift",
            "cso-legacy-mode",
            {"form": {"file_path": str(cso_file)}},
        )
        assert legacy["command"][legacy["command"].index("--file-path") + 1] == str(
            cso_file.resolve()
        )

        with pytest.raises(ValueError, match="Missing required fields"):
            manager.resolve_request(
                workspace.id,
                "imaging-localization",
                "rrll-percentile-comparison",
                {},
            )
        with pytest.raises(PermissionError, match="outside allowed roots"):
            manager.resolve_request(
                workspace.id,
                "imaging-localization",
                "rrll-percentile-comparison",
                {
                    "form": {
                        "radio_root": str(outside),
                        "spectrogram_file": str(cso_file),
                    }
                },
            )
        rrll = manager.resolve_request(
            workspace.id,
            "imaging-localization",
            "rrll-percentile-comparison",
            {
                "form": {
                    "radio_root": str(radio_root),
                    "spectrogram_file": str(cso_file),
                }
            },
        )
        assert rrll["command"][rrll["command"].index("--radio-root") + 1] == str(
            radio_root.resolve()
        )
        assert rrll["command"][rrll["command"].index("--spectrogram-file") + 1] == str(
            cso_file.resolve()
        )
    finally:
        manager.close(cancel_running=True)


def test_semantic_artifact_type_prefers_specific_declared_name():
    from solar_toolkit.webapp.radio_workspace import RadioRunManager

    artifact_type = RadioRunManager._semantic_artifact_type(
        Path("drift_rate_selection_metadata.json"),
        kind="json",
        declared_types=("spectrogram", "spectrogram-metadata", "drift-table"),
    )

    assert artifact_type == "spectrogram-metadata"


def test_explicit_artifact_binding_overrides_stale_manual_value(tmp_path: Path):
    from solar_toolkit.webapp.radio_workspace import (
        SCHEMA_VERSION,
        RadioArtifact,
        RadioRunManager,
        RadioRunManifest,
        RadioWorkspaceStore,
    )

    manual = tmp_path / "manual.csv"
    manual.write_text("x,y\n1,2\n", encoding="utf-8")
    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[tmp_path])
    workspace = store.create_workspace(workspace_id="artifact-precedence")
    source = RadioRunManifest(
        schema_version=SCHEMA_VERSION,
        id="source-run",
        workspace_id=workspace.id,
        module_id="imaging-localization",
        action_id="extract-centers",
        status="succeeded",
        command=[sys.executable, "-c", "pass"],
        cwd=str(tmp_path),
        request={},
        resolved_config={},
        input_sources=[],
        provenance={},
        artifacts=[
            RadioArtifact(
                schema_version=SCHEMA_VERSION,
                id="centers-artifact",
                relative_path="centers.csv",
                kind="table",
                mime_type="text/csv",
                artifact_type="center-table",
                source_run_id="source-run",
            )
        ],
        created_at="2026-07-13T00:00:00+00:00",
    )
    store.create_run(source)
    artifact_path = store.run_dir(workspace.id, source.id) / "artifacts" / "centers.csv"
    artifact_path.write_text("x,y\n3,4\n", encoding="utf-8")
    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
        popen_factory=_artifact_popen,
    )
    try:
        resolved = manager.resolve_request(
            workspace.id,
            "trajectory-media",
            "trajectory-export",
            {
                "form": {"centers": str(manual)},
                "input_sources": [
                    {
                        "type": "artifact",
                        "run_id": source.id,
                        "artifact_id": source.artifacts[0].id,
                        "field": "centers",
                    }
                ],
            },
        )

        assert resolved["config"]["centers"] == str(artifact_path.resolve())
        assert resolved["provenance"]["layers"]["action_form"]["centers"] == str(manual)
        assert resolved["provenance"]["layers"]["artifact_bindings"]["centers"] == str(
            artifact_path.resolve()
        )
        centers_index = resolved["command"].index("--centers") + 1
        assert resolved["command"][centers_index] == str(artifact_path.resolve())
    finally:
        manager.close(cancel_running=True)


def test_workspace_artifact_must_match_field_level_artifact_types(tmp_path: Path):
    from solar_toolkit.webapp.radio_workspace import (
        SCHEMA_VERSION,
        RadioArtifact,
        RadioRunManager,
        RadioRunManifest,
        RadioWorkspaceStore,
    )

    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[tmp_path])
    workspace = store.create_workspace(workspace_id="field-artifact-types")
    source = RadioRunManifest(
        schema_version=SCHEMA_VERSION,
        id="gaussian-source",
        workspace_id=workspace.id,
        module_id="imaging-localization",
        action_id="fit-gaussian",
        status="succeeded",
        command=[sys.executable, "-c", "pass"],
        cwd=str(tmp_path),
        request={},
        resolved_config={},
        input_sources=[],
        provenance={},
        artifacts=[
            RadioArtifact(
                schema_version=SCHEMA_VERSION,
                id="gaussian-table",
                relative_path="gaussian.csv",
                kind="table",
                mime_type="text/csv",
                artifact_type="gaussian-table",
                source_run_id="gaussian-source",
            )
        ],
        created_at="2026-07-13T00:00:00+00:00",
    )
    store.create_run(source)
    artifact_path = (
        store.run_dir(workspace.id, source.id) / "artifacts" / "gaussian.csv"
    )
    artifact_path.write_text("frequency_mhz,x,y\n149,1,2\n", encoding="utf-8")
    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
        popen_factory=_artifact_popen,
    )
    try:
        with pytest.raises(
            ValueError,
            match="gaussian-table.*not accepted by input field 'drift_csv'",
        ):
            manager.resolve_request(
                workspace.id,
                "physical-diagnostics",
                "analyze-existing-tables",
                {
                    "input_sources": [
                        {
                            "type": "artifact",
                            "run_id": source.id,
                            "artifact_id": source.artifacts[0].id,
                            "field": "drift_csv",
                        }
                    ]
                },
            )
    finally:
        manager.close(cancel_running=True)


def test_input_sources_require_one_unique_declared_path_field(tmp_path: Path):
    from solar_toolkit.webapp.radio_workspace import (
        SCHEMA_VERSION,
        RadioArtifact,
        RadioRunManager,
        RadioRunManifest,
        RadioWorkspaceStore,
    )

    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[tmp_path])
    workspace = store.create_workspace(workspace_id="artifact-fields")
    source = RadioRunManifest(
        schema_version=SCHEMA_VERSION,
        id="source-run",
        workspace_id=workspace.id,
        module_id="imaging-localization",
        action_id="extract-centers",
        status="succeeded",
        command=[sys.executable, "-c", "pass"],
        cwd=str(tmp_path),
        request={},
        resolved_config={},
        input_sources=[],
        provenance={},
        artifacts=[
            RadioArtifact(
                schema_version=SCHEMA_VERSION,
                id="centers-artifact",
                relative_path="centers.csv",
                kind="table",
                mime_type="text/csv",
                artifact_type="center-table",
                source_run_id="source-run",
            )
        ],
        created_at="2026-07-13T00:00:00+00:00",
    )
    store.create_run(source)
    artifact_path = store.run_dir(workspace.id, source.id) / "artifacts" / "centers.csv"
    artifact_path.write_text("x,y\n3,4\n", encoding="utf-8")
    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
        popen_factory=_artifact_popen,
    )
    try:
        base_source = {
            "type": "artifact",
            "run_id": source.id,
            "artifact_id": source.artifacts[0].id,
        }
        with pytest.raises(ValueError, match="must bind to a path field"):
            manager.resolve_request(
                workspace.id,
                "trajectory-media",
                "trajectory-export",
                {"input_sources": [base_source]},
            )
        with pytest.raises(ValueError, match="is not available"):
            manager.resolve_request(
                workspace.id,
                "trajectory-media",
                "trajectory-export",
                {"input_sources": [{**base_source, "field": "not_a_field"}]},
            )
        with pytest.raises(ValueError, match="bound more than once"):
            manager.resolve_request(
                workspace.id,
                "trajectory-media",
                "trajectory-export",
                {
                    "input_sources": [
                        {**base_source, "field": "centers"},
                        {**base_source, "field": "centers"},
                    ]
                },
            )
        with pytest.raises(
            ValueError,
            match="center-table.*not accepted by data-configuration/raw-quality",
        ):
            manager.resolve_request(
                workspace.id,
                "data-configuration",
                "raw-quality",
                {"input_sources": [{**base_source, "field": "root"}]},
            )
    finally:
        manager.close(cancel_running=True)


def test_action_path_fields_validate_file_and_directory_kinds(tmp_path: Path):
    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
    )

    folder = tmp_path / "radio"
    folder.mkdir()
    centers = tmp_path / "centers.csv"
    centers.write_text("x,y\n1,2\n", encoding="utf-8")
    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[tmp_path])
    workspace = store.create_workspace(workspace_id="path-kinds")
    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
        popen_factory=_artifact_popen,
    )
    try:
        with pytest.raises(NotADirectoryError, match="Directory does not exist"):
            manager.resolve_request(
                workspace.id,
                "imaging-localization",
                "extract-centers",
                {"form": {"radio_dir": str(centers)}},
            )
        with pytest.raises(FileNotFoundError, match="File does not exist"):
            manager.resolve_request(
                workspace.id,
                "trajectory-media",
                "trajectory-export",
                {"form": {"centers": str(folder)}},
            )
    finally:
        manager.close(cancel_running=True)


@pytest.mark.parametrize(
    ("form", "advanced"),
    [
        ({"pattern": "../outside/*.fits"}, {}),
        ({"pattern": "/outside/*.fits"}, {}),
        ({"pattern": "C:\\outside\\*.fits"}, {}),
        ({"pattern": ""}, {}),
        ({}, {"nested": {"radio_glob": "..\\outside\\*.fits"}}),
    ],
)
def test_action_patterns_and_structured_json_cannot_escape_the_selected_root(
    tmp_path: Path,
    form: dict[str, object],
    advanced: dict[str, object],
):
    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
    )

    radio_dir = tmp_path / "radio"
    radio_dir.mkdir()
    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[tmp_path])
    workspace = store.create_workspace(workspace_id="pattern-boundary")
    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
        popen_factory=_artifact_popen,
    )
    try:
        with pytest.raises(ValueError, match="Pattern .* from .* action configuration"):
            manager.resolve_request(
                workspace.id,
                "imaging-localization",
                "extract-centers",
                {
                    "form": {"radio_dir": str(radio_dir), **form},
                    "advanced_config": advanced,
                },
            )
        resolved = manager.resolve_request(
            workspace.id,
            "imaging-localization",
            "extract-centers",
            {"form": {"radio_dir": str(radio_dir), "pattern": "**/*.fits"}},
        )
        assert resolved["config"]["pattern"] == "**/*.fits"
    finally:
        manager.close(cancel_running=True)


def test_structured_workspace_config_reaches_source_map_worker(tmp_path: Path):
    import json

    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
    )

    radio_dir = tmp_path / "radio"
    radio_dir.mkdir()
    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[tmp_path])
    workspace = store.create_workspace(workspace_id="source-map-config")
    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
        popen_factory=_artifact_popen,
    )
    try:
        resolved = manager.resolve_request(
            workspace.id,
            "imaging-localization",
            "inspect-source-map",
            {
                "form": {"mode": "multi_band", "radio_dir": str(radio_dir)},
                "advanced_config": {"gaussian": {"fit_snr_threshold": 8.0}},
            },
        )
        command = resolved["command"]
        flag_index = command.index("--workspace-config-json")
        forwarded = json.loads(command[flag_index + 1])
        assert forwarded["features"]["gaussian_overlay"] is False
        assert forwarded["gaussian"]["fit_snr_threshold"] == 8.0
        assert forwarded["data"]["multi_band_root"] == str(radio_dir)
    finally:
        manager.close(cancel_running=True)


def test_web_actions_reject_non_package_event_config_modules(tmp_path: Path):
    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
    )

    radio_dir = tmp_path / "radio"
    radio_dir.mkdir()
    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[tmp_path])
    workspace = store.create_workspace(workspace_id="config-boundary")
    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
        popen_factory=_artifact_popen,
    )
    try:
        with pytest.raises(ValueError, match="package-owned radio .*config"):
            manager.resolve_request(
                workspace.id,
                "imaging-localization",
                "inspect-source-map",
                {
                    "form": {
                        "config": "arbitrary_local_module",
                        "mode": "multi_band",
                        "radio_dir": str(radio_dir),
                    }
                },
            )
        resolved = manager.resolve_request(
            workspace.id,
            "imaging-localization",
            "inspect-source-map",
            {
                "form": {
                    "config": "example_radio_pipeline_config",
                    "mode": "multi_band",
                    "radio_dir": str(radio_dir),
                }
            },
        )
        assert "example_radio_pipeline_config" in resolved["command"]
    finally:
        manager.close(cancel_running=True)


def test_run_manager_persists_state_logs_artifacts_and_artifact_reuse(tmp_path: Path):
    import json

    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
    )

    radio_dir = tmp_path / "radio"
    radio_dir.mkdir()
    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[tmp_path])
    workspace = store.create_workspace(workspace_id="run-workspace")
    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
        popen_factory=_artifact_popen,
    )
    try:
        first = manager.start(
            workspace.id,
            "imaging-localization",
            "extract-centers",
            {"form": {"radio_dir": str(radio_dir)}},
        )
        completed = manager.wait(workspace.id, first.id, timeout=3.0)

        assert completed.status == "succeeded"
        assert completed.progress == 1.0
        assert completed.log_path == "run.log"
        assert completed.returncode == 0
        assert len(completed.artifacts) == 1
        assert completed.artifacts[0].kind == "table"
        assert completed.artifacts[0].artifact_type == "center-table"
        assert completed.artifacts[0].source_run_id == completed.id
        run_dir = store.run_dir(workspace.id, completed.id)
        assert (run_dir / "request.json").is_file()
        assert (run_dir / "resolved_config.json").is_file()
        assert (run_dir / "run.json").is_file()
        request_document = json.loads(
            (run_dir / "request.json").read_text(encoding="utf-8")
        )
        config_document = json.loads(
            (run_dir / "resolved_config.json").read_text(encoding="utf-8")
        )
        run_document = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        assert request_document == completed.request
        assert config_document == completed.resolved_config
        assert run_document["resolved_config"] == config_document
        lines, next_offset = store.read_log(workspace.id, completed.id)
        assert lines == ["radio worker completed"]
        assert next_offset == 1

        second = manager.start(
            workspace.id,
            "trajectory-media",
            "trajectory-export",
            {
                "input_sources": [
                    {
                        "type": "artifact",
                        "run_id": completed.id,
                        "artifact_id": completed.artifacts[0].id,
                        "field": "centers",
                    }
                ]
            },
        )
        trajectory = manager.wait(workspace.id, second.id, timeout=3.0)
        assert trajectory.status == "succeeded"
        assert trajectory.input_sources[0]["run_id"] == completed.id
        assert "--centers" in trajectory.command
        assert trajectory.provenance["dependencies_auto_run"] is False
        assert {run.id for run in store.list_runs(workspace.id)} == {
            completed.id,
            trajectory.id,
        }
    finally:
        manager.close(cancel_running=True)


def test_startup_marks_unfinished_persisted_runs_interrupted(tmp_path: Path):
    from solar_toolkit.webapp.radio_workspace import (
        SCHEMA_VERSION,
        RadioRunManager,
        RadioRunManifest,
        RadioWorkspaceStore,
    )

    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[tmp_path])
    workspace = store.create_workspace(workspace_id="recovery")
    queued = RadioRunManifest(
        schema_version=SCHEMA_VERSION,
        id="unfinished",
        workspace_id=workspace.id,
        module_id="data-configuration",
        action_id="raw-quality",
        status="queued",
        command=[sys.executable, "-m", "solar_toolkit.radio.raw_quality_cli"],
        cwd=str(tmp_path),
        request={},
        resolved_config={},
        input_sources=[],
        provenance={},
        created_at="2026-07-13T00:00:00+00:00",
    )
    store.create_run(queued)

    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
        popen_factory=_artifact_popen,
    )
    try:
        recovered = store.load_run(workspace.id, queued.id)
        assert recovered.status == "interrupted"
        assert "service stopped" in recovered.error
    finally:
        manager.close(cancel_running=True)


def test_workspace_concurrency_keeps_unselected_run_queued_and_cancelable(
    tmp_path: Path,
):
    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
    )

    class BlockingProcess:
        def __init__(self, released: threading.Event) -> None:
            self.released = released
            self.stdout = _FakeStdout([])
            self.returncode = None
            self.pid = None

        def poll(self):
            return 0 if self.released.is_set() else None

        def wait(self, timeout=None):
            assert self.released.wait(timeout or 3.0)
            self.returncode = 0
            return 0

        def terminate(self):
            self.returncode = -15
            self.released.set()

        def kill(self):
            self.returncode = -9
            self.released.set()

    radio_dir = tmp_path / "radio"
    radio_dir.mkdir()
    released = threading.Event()
    started = threading.Event()
    launch_count = 0

    def popen_factory(*_args, **_kwargs):
        nonlocal launch_count
        launch_count += 1
        started.set()
        return BlockingProcess(released)

    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[tmp_path])
    workspace = store.create_workspace(workspace_id="queue", concurrency=1)
    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
        popen_factory=popen_factory,
    )
    try:
        first = manager.start(
            workspace.id,
            "data-configuration",
            "raw-quality",
            {"form": {"root": str(radio_dir)}},
        )
        assert started.wait(2.0)
        second = manager.start(
            workspace.id,
            "data-configuration",
            "raw-quality",
            {"form": {"root": str(radio_dir)}},
        )
        deadline = time.monotonic() + 2.0
        while manager.status(workspace.id, second.id).status != "queued":
            assert time.monotonic() < deadline
            time.sleep(0.01)
        canceled = manager.cancel(workspace.id, second.id)
        assert canceled.status == "canceled"
        assert launch_count == 1
        released.set()
        assert manager.wait(workspace.id, first.id, timeout=3.0).status == "succeeded"
    finally:
        released.set()
        manager.close(cancel_running=True)


def test_global_concurrency_and_per_workspace_limits_are_enforced(tmp_path: Path):
    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
    )

    released = threading.Event()
    lock = threading.Lock()
    launched = threading.Event()
    active = 0
    maximum_active = 0
    launch_count = 0

    class BlockingProcess:
        def __init__(self) -> None:
            self.stdout = _FakeStdout([])
            self.returncode = None
            self.pid = None

        def poll(self):
            return 0 if released.is_set() else None

        def wait(self, timeout=None):
            nonlocal active
            assert released.wait(timeout or 5.0)
            with lock:
                active -= 1
            self.returncode = 0
            return 0

        def terminate(self):
            released.set()

        def kill(self):
            released.set()

    def popen_factory(*_args, **_kwargs):
        nonlocal active, maximum_active, launch_count
        with lock:
            active += 1
            launch_count += 1
            maximum_active = max(maximum_active, active)
            if launch_count >= 4:
                launched.set()
        return BlockingProcess()

    radio_dir = tmp_path / "radio"
    radio_dir.mkdir()
    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[tmp_path])
    first_workspace = store.create_workspace(
        workspace_id="concurrency-one", concurrency=1
    )
    second_workspace = store.create_workspace(
        workspace_id="concurrency-three", concurrency=3
    )
    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
        popen_factory=popen_factory,
        global_concurrency=4,
    )
    runs = []
    try:
        for workspace in (first_workspace, second_workspace):
            for _index in range(3):
                runs.append(
                    manager.start(
                        workspace.id,
                        "data-configuration",
                        "raw-quality",
                        {"form": {"root": str(radio_dir)}},
                    )
                )
        assert launched.wait(3.0)
        deadline = time.monotonic() + 3.0
        while True:
            first_running = sum(
                manager.status(first_workspace.id, run.id).status == "running"
                for run in runs[:3]
            )
            second_running = sum(
                manager.status(second_workspace.id, run.id).status == "running"
                for run in runs[3:]
            )
            if first_running == 1 and second_running == 3:
                break
            assert time.monotonic() < deadline
            time.sleep(0.01)
        with lock:
            assert active == 4
            assert launch_count == 4
            assert maximum_active == 4
        released.set()
        for run in runs:
            assert manager.wait(run.workspace_id, run.id, timeout=5.0).status == (
                "succeeded"
            )
        with lock:
            assert maximum_active == 4
    finally:
        released.set()
        manager.close(cancel_running=True)


def test_batch_validation_is_atomic_before_any_run_is_created(tmp_path: Path):
    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
    )

    radio_dir = tmp_path / "radio"
    radio_dir.mkdir()
    launches = 0

    def popen_factory(*args, **kwargs):
        nonlocal launches
        launches += 1
        return _artifact_popen(*args, **kwargs)

    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[tmp_path])
    workspace = store.create_workspace(workspace_id="atomic-batch")
    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
        popen_factory=popen_factory,
    )
    try:
        with pytest.raises(KeyError, match="Unknown radio action"):
            manager.start_batch(
                workspace.id,
                [
                    {
                        "module_id": "data-configuration",
                        "action_id": "raw-quality",
                        "form": {"root": str(radio_dir)},
                    },
                    {
                        "module_id": "data-configuration",
                        "action_id": "not-a-real-action",
                    },
                ],
            )
        assert store.list_runs(workspace.id) == []
        assert launches == 0
    finally:
        manager.close(cancel_running=True)


def test_batch_creation_failure_rolls_back_every_run_before_queueing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
    )

    radio_dir = tmp_path / "radio"
    radio_dir.mkdir()
    launches = 0

    def popen_factory(*args, **kwargs):
        nonlocal launches
        launches += 1
        return _artifact_popen(*args, **kwargs)

    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[tmp_path])
    workspace = store.create_workspace(workspace_id="creation-rollback")
    original_atomic_json = store._atomic_json
    request_writes = 0

    def fail_during_second_run(path: Path, payload: dict):
        nonlocal request_writes
        if path.name == "request.json":
            request_writes += 1
            if request_writes == 2:
                raise OSError("injected batch creation failure")
        original_atomic_json(path, payload)

    monkeypatch.setattr(store, "_atomic_json", fail_during_second_run)
    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
        popen_factory=popen_factory,
    )
    try:
        with pytest.raises(OSError, match="injected batch creation failure"):
            manager.start_batch(
                workspace.id,
                [
                    {
                        "module_id": "data-configuration",
                        "action_id": "raw-quality",
                        "form": {"root": str(radio_dir), "freqs": "149"},
                    },
                    {
                        "module_id": "data-configuration",
                        "action_id": "raw-quality",
                        "form": {"root": str(radio_dir), "freqs": "164"},
                    },
                ],
            )
        assert request_writes == 2
        assert store.list_runs(workspace.id) == []
        assert list((store.workspace_dir(workspace.id) / "runs").iterdir()) == []
        assert launches == 0
    finally:
        manager.close(cancel_running=True)


def test_confirmed_batch_runs_only_selected_actions_in_exact_sequence(tmp_path: Path):
    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
    )

    class GateProcess:
        def __init__(self, gate: threading.Event) -> None:
            self.gate = gate
            self.stdout = _FakeStdout([])
            self.returncode = None
            self.pid = None

        def poll(self):
            return 0 if self.gate.is_set() else None

        def wait(self, timeout=None):
            assert self.gate.wait(timeout or 3.0)
            self.returncode = 0
            return 0

        def terminate(self):
            self.returncode = -15
            self.gate.set()

        kill = terminate

    radio_dir = tmp_path / "radio"
    radio_dir.mkdir()
    gates = [threading.Event(), threading.Event()]
    launched: list[list[str]] = []

    def popen_factory(command, **_kwargs):
        launched.append(command)
        return GateProcess(gates[len(launched) - 1])

    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[tmp_path])
    workspace = store.create_workspace(workspace_id="ordered-batch", concurrency=4)
    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
        popen_factory=popen_factory,
    )
    try:
        runs = manager.start_batch(
            workspace.id,
            [
                {
                    "module_id": "data-configuration",
                    "action_id": "raw-quality",
                    "form": {"root": str(radio_dir), "freqs": "149"},
                },
                {
                    "module_id": "data-configuration",
                    "action_id": "raw-quality",
                    "form": {"root": str(radio_dir), "freqs": "164"},
                },
            ],
        )
        deadline = time.monotonic() + 2.0
        while len(launched) < 1 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert len(launched) == 1
        assert manager.status(workspace.id, runs[1].id).status == "queued"
        assert runs[0].provenance["dependencies_auto_run"] is False
        assert runs[1].provenance["depends_on_run_ids"] == [runs[0].id]
        gates[0].set()
        deadline = time.monotonic() + 2.0
        while len(launched) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert len(launched) == 2
        gates[1].set()
        assert manager.wait(workspace.id, runs[0].id).status == "succeeded"
        assert manager.wait(workspace.id, runs[1].id).status == "succeeded"
        persisted = manager.list_runs(workspace.id)
        assert {item.id for item in persisted} == {runs[0].id, runs[1].id}
        assert [
            runs[0].provenance["batch_order"],
            runs[1].provenance["batch_order"],
        ] == [0, 1]
        assert launched[0][launched[0].index("--freqs") + 1] == "149"
        assert launched[1][launched[1].index("--freqs") + 1] == "164"
    finally:
        for gate in gates:
            gate.set()
        manager.close(cancel_running=True)


def test_batch_artifact_is_resolved_after_the_selected_producer_succeeds(
    tmp_path: Path,
):
    import json

    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
    )

    radio_dir = tmp_path / "radio"
    radio_dir.mkdir()
    launched: list[list[str]] = []

    def popen_factory(command: list[str], **kwargs):
        launched.append(command)
        if "solar_toolkit.radio.source_map_cli" in command:
            output = Path(command[command.index("--output-dir") + 1])
            output.mkdir(parents=True, exist_ok=True)
            (output / "gaussian_table.csv").write_text(
                "frequency_mhz,x_arcsec,y_arcsec\n149,1,2\n",
                encoding="utf-8",
            )
            return _CompletingProcess()
        return _artifact_popen(command, **kwargs)

    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[tmp_path])
    workspace = store.create_workspace(workspace_id="batch-artifact-success")
    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
        popen_factory=popen_factory,
    )
    try:
        runs = manager.start_batch(
            workspace.id,
            [
                {
                    "module_id": "imaging-localization",
                    "action_id": "fit-gaussian",
                    "form": {"radio_dir": str(radio_dir)},
                },
                {
                    "module_id": "physical-diagnostics",
                    "action_id": "analyze-existing-tables",
                    "input_sources": [
                        {
                            "type": "batch_artifact",
                            "producer_index": 0,
                            "artifact_type": "gaussian-table",
                            "field": "gaussian_csv",
                        }
                    ],
                },
            ],
        )
        assert "--gaussian-csv" not in runs[1].command
        assert runs[1].input_sources == [
            {
                "type": "batch_artifact",
                "run_id": runs[0].id,
                "artifact_type": "gaussian-table",
                "field": "gaussian_csv",
            }
        ]

        producer = manager.wait(workspace.id, runs[0].id, timeout=3.0)
        consumer = manager.wait(workspace.id, runs[1].id, timeout=3.0)
        assert producer.status == "succeeded"
        assert consumer.status == "succeeded"
        assert len(launched) == 2
        assert "--gaussian-csv" in consumer.command
        bound_path = Path(
            consumer.command[consumer.command.index("--gaussian-csv") + 1]
        )
        assert bound_path.name == "gaussian_table.csv"
        assert consumer.input_sources[0]["type"] == "artifact"
        assert consumer.input_sources[0]["run_id"] == producer.id
        assert consumer.input_sources[0]["artifact_type"] == "gaussian-table"
        assert consumer.provenance["planned_input_sources"][0]["run_id"] == (
            producer.id
        )
        assert consumer.provenance["actual_input_sources"] == (consumer.input_sources)
        assert consumer.provenance["dependencies_auto_run"] is False
        consumer_dir = store.run_dir(workspace.id, consumer.id)
        request_document = json.loads(
            (consumer_dir / "request.json").read_text(encoding="utf-8")
        )
        config_document = json.loads(
            (consumer_dir / "resolved_config.json").read_text(encoding="utf-8")
        )
        run_document = json.loads(
            (consumer_dir / "run.json").read_text(encoding="utf-8")
        )
        assert request_document["input_sources"][0] == {
            "type": "batch_artifact",
            "producer_index": 0,
            "artifact_type": "gaussian-table",
            "field": "gaussian_csv",
        }
        assert config_document == run_document["resolved_config"]
        assert config_document == consumer.resolved_config
        assert config_document["gaussian_csv"] == str(bound_path.resolve())
    finally:
        manager.close(cancel_running=True)


@pytest.mark.parametrize(
    ("source", "consumer", "error"),
    [
        (
            {
                "type": "batch_artifact",
                "producer_index": 1,
                "artifact_type": "center-table",
                "field": "centers",
            },
            ("trajectory-media", "trajectory-export"),
            "earlier selected action",
        ),
        (
            {
                "type": "batch_artifact",
                "producer_index": 0,
                "artifact_type": "gaussian-table",
                "field": "centers",
            },
            ("trajectory-media", "trajectory-export"),
            "does not declare artifact type",
        ),
        (
            {
                "type": "batch_artifact",
                "producer_index": 0,
                "artifact_type": "center-table",
                "field": "gaussian_csv",
            },
            ("physical-diagnostics", "analyze-existing-tables"),
            "not accepted by the selected consumer",
        ),
        (
            {
                "type": "batch_artifact",
                "producer_index": 0,
                "artifact_type": "center-table",
                "field": "freqs",
            },
            ("trajectory-media", "trajectory-export"),
            "must name a consumer path field",
        ),
    ],
)
def test_invalid_batch_artifact_reference_creates_no_runs(
    tmp_path: Path,
    source: dict[str, object],
    consumer: tuple[str, str],
    error: str,
):
    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
    )

    radio_dir = tmp_path / "radio"
    radio_dir.mkdir()
    launches = 0

    def popen_factory(*args, **kwargs):
        nonlocal launches
        launches += 1
        return _artifact_popen(*args, **kwargs)

    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[tmp_path])
    workspace = store.create_workspace(workspace_id="bad-batch-artifact")
    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
        popen_factory=popen_factory,
    )
    try:
        with pytest.raises((TypeError, ValueError), match=error):
            manager.start_batch(
                workspace.id,
                [
                    {
                        "module_id": "imaging-localization",
                        "action_id": "extract-centers",
                        "form": {"radio_dir": str(radio_dir)},
                    },
                    {
                        "module_id": consumer[0],
                        "action_id": consumer[1],
                        "input_sources": [source],
                    },
                ],
            )
        assert store.list_runs(workspace.id) == []
        assert launches == 0
    finally:
        manager.close(cancel_running=True)


def test_batch_artifact_must_match_field_level_type_before_any_run_is_created(
    tmp_path: Path,
):
    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
    )

    radio_dir = tmp_path / "radio"
    radio_dir.mkdir()
    launches = 0

    def popen_factory(*args, **kwargs):
        nonlocal launches
        launches += 1
        return _artifact_popen(*args, **kwargs)

    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[tmp_path])
    workspace = store.create_workspace(workspace_id="batch-field-artifact-types")
    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
        popen_factory=popen_factory,
    )
    try:
        with pytest.raises(
            ValueError,
            match="gaussian-table.*not accepted by input field 'drift_csv'",
        ):
            manager.start_batch(
                workspace.id,
                [
                    {
                        "module_id": "imaging-localization",
                        "action_id": "fit-gaussian",
                        "form": {"radio_dir": str(radio_dir)},
                    },
                    {
                        "module_id": "physical-diagnostics",
                        "action_id": "analyze-existing-tables",
                        "input_sources": [
                            {
                                "type": "batch_artifact",
                                "producer_index": 0,
                                "artifact_type": "gaussian-table",
                                "field": "drift_csv",
                            }
                        ],
                    },
                ],
            )
        assert store.list_runs(workspace.id) == []
        assert launches == 0
    finally:
        manager.close(cancel_running=True)


def test_batch_rejects_ordinary_and_deferred_sources_for_the_same_field_atomically(
    tmp_path: Path,
):
    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
    )

    radio_dir = tmp_path / "radio"
    radio_dir.mkdir()
    centers = tmp_path / "centers.csv"
    centers.write_text("x,y\n1,2\n", encoding="utf-8")
    launches = 0

    def popen_factory(*args, **kwargs):
        nonlocal launches
        launches += 1
        return _artifact_popen(*args, **kwargs)

    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[tmp_path])
    workspace = store.create_workspace(workspace_id="duplicate-batch-field")
    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
        popen_factory=popen_factory,
    )
    try:
        with pytest.raises(ValueError, match="'centers' was bound more than once"):
            manager.start_batch(
                workspace.id,
                [
                    {
                        "module_id": "imaging-localization",
                        "action_id": "extract-centers",
                        "form": {"radio_dir": str(radio_dir)},
                    },
                    {
                        "module_id": "trajectory-media",
                        "action_id": "trajectory-export",
                        "input_sources": [
                            {
                                "type": "path",
                                "path": str(centers),
                                "field": "centers",
                            },
                            {
                                "type": "batch_artifact",
                                "producer_index": 0,
                                "artifact_type": "center-table",
                                "field": "centers",
                            },
                        ],
                    },
                ],
            )
        assert store.list_runs(workspace.id) == []
        assert launches == 0
    finally:
        manager.close(cancel_running=True)


@pytest.mark.parametrize("artifact_count", [0, 2])
def test_batch_artifact_requires_exactly_one_match_before_worker_launch(
    tmp_path: Path, artifact_count: int
):
    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
    )

    radio_dir = tmp_path / "radio"
    radio_dir.mkdir()
    launches = 0

    def popen_factory(command: list[str], **_kwargs):
        nonlocal launches
        launches += 1
        if launches == 1:
            output = Path(command[command.index("--out") + 1])
            output.parent.mkdir(parents=True, exist_ok=True)
            if artifact_count:
                output.write_text("x,y\n1,2\n", encoding="utf-8")
            if artifact_count == 2:
                (output.parent / "second_centers.csv").write_text(
                    "x,y\n3,4\n", encoding="utf-8"
                )
        return _CompletingProcess()

    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[tmp_path])
    workspace = store.create_workspace(workspace_id=f"artifact-count-{artifact_count}")
    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
        popen_factory=popen_factory,
    )
    try:
        runs = manager.start_batch(
            workspace.id,
            [
                {
                    "module_id": "imaging-localization",
                    "action_id": "extract-centers",
                    "form": {"radio_dir": str(radio_dir)},
                },
                {
                    "module_id": "trajectory-media",
                    "action_id": "trajectory-export",
                    "input_sources": [
                        {
                            "type": "batch_artifact",
                            "producer_index": 0,
                            "artifact_type": "center-table",
                            "field": "centers",
                        }
                    ],
                },
            ],
        )
        assert manager.wait(workspace.id, runs[0].id, timeout=3.0).status == (
            "succeeded"
        )
        consumer = manager.wait(workspace.id, runs[1].id, timeout=3.0)
        assert consumer.status == "failed"
        assert consumer.returncode == -1
        assert f"resolved to {artifact_count} artifacts" in consumer.error
        assert "exactly one is required" in consumer.error
        assert launches == 1
    finally:
        manager.close(cancel_running=True)


def test_single_action_rejects_batch_artifact_sources(tmp_path: Path):
    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
    )

    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[tmp_path])
    workspace = store.create_workspace(workspace_id="single-batch-artifact")
    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
        popen_factory=_artifact_popen,
    )
    payload = {
        "input_sources": [
            {
                "type": "batch_artifact",
                "producer_index": 0,
                "artifact_type": "center-table",
                "field": "centers",
            }
        ]
    }
    try:
        with pytest.raises(ValueError, match="only allowed in a confirmed batch"):
            manager.preview(
                workspace.id,
                "trajectory-media",
                "trajectory-export",
                payload,
            )
        with pytest.raises(ValueError, match="only allowed in a confirmed batch"):
            manager.start(
                workspace.id,
                "trajectory-media",
                "trajectory-export",
                payload,
            )
        assert store.list_runs(workspace.id) == []
    finally:
        manager.close(cancel_running=True)


def test_running_cancel_is_idempotent_and_releases_the_queue_slot(tmp_path: Path):
    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
    )

    class BlockingProcess:
        def __init__(self) -> None:
            self.released = threading.Event()
            self.stdout = _FakeStdout([])
            self.returncode = None
            self.pid = None
            self.terminated = False

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            assert self.released.wait(timeout or 3.0)
            return int(self.returncode)

        def terminate(self):
            self.terminated = True
            self.returncode = -15
            self.released.set()

        kill = terminate

    radio_dir = tmp_path / "radio"
    radio_dir.mkdir()
    processes: list[BlockingProcess | _CompletingProcess] = []

    def popen_factory(*_args, **_kwargs):
        process = BlockingProcess() if not processes else _CompletingProcess()
        processes.append(process)
        return process

    store = RadioWorkspaceStore(tmp_path / "output", allowed_roots=[tmp_path])
    workspace = store.create_workspace(workspace_id="running-cancel", concurrency=1)
    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
        popen_factory=popen_factory,
    )
    try:
        first = manager.start(
            workspace.id,
            "data-configuration",
            "raw-quality",
            {"form": {"root": str(radio_dir)}},
        )
        deadline = time.monotonic() + 2.0
        while not processes and time.monotonic() < deadline:
            time.sleep(0.01)
        assert processes
        canceled = manager.cancel(workspace.id, first.id)
        assert canceled.status == "canceled"
        assert manager.cancel(workspace.id, first.id).status == "canceled"
        assert processes[0].terminated is True
        second = manager.start(
            workspace.id,
            "data-configuration",
            "raw-quality",
            {"form": {"root": str(radio_dir)}},
        )
        assert manager.wait(workspace.id, second.id, timeout=3.0).status == "succeeded"
        assert manager.status(workspace.id, first.id).status == "canceled"
    finally:
        manager.close(cancel_running=True)


def test_structured_and_manifest_paths_cannot_escape_allowed_roots(tmp_path: Path):
    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
    )

    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    secret = outside / "secret.txt"
    secret.write_text("do not disclose", encoding="utf-8")
    store = RadioWorkspaceStore(allowed / "output", allowed_roots=[allowed])
    workspace = store.create_workspace(workspace_id="path-boundary")
    manager = RadioRunManager(
        store,
        repo_root=allowed,
        python_executable=sys.executable,
        popen_factory=_artifact_popen,
    )
    try:
        radio_file = allowed / "single-source.fits"
        radio_file.write_bytes(b"fixture")
        resolved = manager.resolve_request(
            workspace.id,
            "imaging-localization",
            "inspect-source-map",
            {
                "form": {
                    "mode": "single_band",
                    "single_file_path": str(radio_file),
                }
            },
        )
        assert resolved["config"]["single_file_path"] == str(radio_file)

        with pytest.raises(PermissionError, match="outside allowed roots"):
            manager.resolve_request(
                workspace.id,
                "imaging-localization",
                "inspect-source-map",
                {
                    "advanced_config": {
                        "mode": "multi_band",
                        "data": {"multi_band_root": str(outside)},
                        "features": {"spectrogram_panel": False},
                    }
                },
            )

        radio_dir = allowed / "radio"
        radio_dir.mkdir()
        run = manager.start(
            workspace.id,
            "data-configuration",
            "raw-quality",
            {"form": {"root": str(radio_dir)}},
        )
        completed = manager.wait(workspace.id, run.id, timeout=3.0)
        from dataclasses import replace

        with pytest.raises(ValueError, match="must be relative"):
            replace(
                completed.artifacts[0],
                relative_path=str(secret),
            )
    finally:
        manager.close(cancel_running=True)


@pytest.mark.skipif(
    importlib.util.find_spec("flask") is None,
    reason="Flask is optional; install the app extra to test HTTP routes.",
)
def test_radio_blueprint_exposes_workspace_preview_run_and_artifact_routes(
    tmp_path: Path,
):
    from flask import Flask

    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
        create_radio_blueprint,
    )

    default_output = tmp_path / "default-output"
    custom_output = tmp_path / "custom-output"
    custom_output.mkdir()
    radio_dir = tmp_path / "radio"
    radio_dir.mkdir()
    store = RadioWorkspaceStore(default_output, allowed_roots=[tmp_path])
    manager = RadioRunManager(
        store,
        repo_root=tmp_path,
        python_executable=sys.executable,
        popen_factory=_artifact_popen,
    )
    app = Flask(__name__)
    app.register_blueprint(create_radio_blueprint(store=store, run_manager=manager))
    client = app.test_client()
    try:
        assert client.get("/api/radio/health").get_json()["ok"] is True
        assert len(client.get("/api/radio/modules").get_json()["modules"]) == 8
        preset_payload = client.get("/api/radio/presets").get_json()
        assert len(preset_payload["presets"]) == 5
        assert len(preset_payload["event_presets"]) == 2
        plotly_asset = client.get("/api/radio/assets/plotly.js")
        media_asset = client.get("/api/radio/assets/browser_media.js")
        assert plotly_asset.status_code == 200
        assert b"Plotly" in plotly_asset.data[:1000]
        assert media_asset.status_code == 200
        assert media_asset.headers["X-Content-Type-Options"] == "nosniff"
        assert client.get("/api/radio/assets/not-allowed.js").status_code == 404

        created_response = client.post(
            "/api/radio/workspaces",
            json={
                "name": "API workspace",
                "output_root": str(custom_output),
                "concurrency": 2,
            },
        )
        assert created_response.status_code == 201
        workspace = created_response.get_json()["workspace"]
        workspace_id = workspace["id"]
        assert workspace["output_root"] == str(custom_output.resolve())
        assert len(client.get("/api/radio/workspaces").get_json()["workspaces"]) == 1

        layout = client.patch(
            f"/api/radio/workspaces/{workspace_id}/layout",
            json={"preset_id": "roi-study"},
        ).get_json()["workspace"]
        assert layout["enabled_modules"] == [
            "data-configuration",
            "roi-light-curves",
            "runs-results",
        ]
        assert client.get(f"/api/radio/files?path={radio_dir}").status_code == 200

        preview = client.post(
            f"/api/radio/workspaces/{workspace_id}/modules/"
            "data-configuration/actions/raw-quality/preview",
            json={
                "form": {"root": str(radio_dir)},
                "advanced_config": {"freqs": "149,164"},
                "arguments": [],
            },
        )
        assert preview.status_code == 200
        assert preview.get_json()["preview"]["validation_only"] is True

        bad_run = client.post(
            f"/api/radio/workspaces/{workspace_id}/runs",
            json={
                "module_id": "data-configuration",
                "action_id": "raw-quality",
                "arguments": "--help",
            },
        )
        assert bad_run.status_code == 400

        started = client.post(
            f"/api/radio/workspaces/{workspace_id}/runs",
            json={
                "module_id": "data-configuration",
                "action_id": "raw-quality",
                "form": {"root": str(radio_dir)},
                "arguments": [],
            },
        )
        assert started.status_code == 202
        run_id = started.get_json()["run"]["id"]
        completed = manager.wait(workspace_id, run_id, timeout=3.0)
        artifact = completed.artifacts[0]
        artifact_response = client.get(
            f"/api/radio/workspaces/{workspace_id}/runs/{run_id}/"
            f"artifacts/{artifact.id}"
        )
        assert artifact_response.status_code == 200
        assert io.BytesIO(artifact_response.data).read().startswith(b'{"ok"')
        assert client.get(
            f"/api/radio/workspaces/{workspace_id}/runs/{run_id}/log"
        ).get_json()["lines"] == ["radio worker completed"]
    finally:
        manager.close(cancel_running=True)
