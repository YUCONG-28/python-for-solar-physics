from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
RADIO_JS = REPO_ROOT / "solar_toolkit/webapp/static/radio.js"
RADIO_HTML = REPO_ROOT / "solar_toolkit/webapp/templates/radio.html"


def _javascript_section(source: str, start: str, end: str) -> str:
    return source[source.index(start) : source.index(end, source.index(start))]


def test_radio_workspace_assets_are_english_local_and_explicit():
    paths = [
        REPO_ROOT / "solar_toolkit/webapp/templates/radio.html",
        REPO_ROOT / "solar_toolkit/webapp/static/radio.js",
        REPO_ROOT / "solar_toolkit/webapp/static/radio.css",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    for marker in (
        "Radio Workspace",
        "Data &amp; Configuration",
        "Run Selected Actions",
        "Runs &amp; Results",
        "Presets only change the layout. They never start a run.",
        "Enabling a module does not read data or start a task.",
        "/api/radio",
        "mediabunny-1.50.8.cjs",
        "plotly_selected",
        "/api/client-close",
    ):
        assert marker in combined
    assert not re.search(r"[\u4e00-\u9fff]", combined)
    assert "<iframe" not in combined.casefold()
    assert "https://cdn" not in combined.casefold()


def test_radio_frontend_workspace_layout_and_preset_contracts():
    javascript = RADIO_JS.read_text(encoding="utf-8")
    template = RADIO_HTML.read_text(encoding="utf-8")

    assert 'const groups = ["Core", "Analysis", "Context", "Advanced"]' in javascript
    assert (
        'byId("newWorkspaceButton").addEventListener("click", openNewWorkspaceDialog)'
        in javascript
    )
    assert 'byId("workspaceSelect").addEventListener("change"' in javascript
    assert "async function switchWorkspace(workspaceId)" in javascript
    assert 'localStorage.setItem("solar-radio-workspace-id", workspaceId)' in javascript
    assert 'id="workspaceSelect"' in template
    assert 'id="newWorkspaceButton"' in template
    save_workspace = _javascript_section(
        javascript, "  async function saveWorkspace", "  async function openFileBrowser"
    )
    assert (
        "const creatingWorkspace = !state.workspace || state.workspaceDraftNew"
        in save_workspace
    )
    assert "state.selectedActions.clear()" in save_workspace
    assert "state.activeRuns.clear()" in save_workspace
    assert "state.workspaceDraftNew = false" in save_workspace

    preset = _javascript_section(
        javascript, "  function applyPreset()", "  function resetLayout()"
    )
    assert "state.layout.enabled_modules" in preset
    assert "scheduleLayoutSave();" in preset
    assert "renderAll();" in preset
    assert "requestJson" not in preset
    assert "runAction" not in preset
    assert "confirmSelected" not in preset

    render_all = _javascript_section(
        javascript, "  function renderAll()", "  function populatePresets()"
    )
    assert "state.selectedActions = new Set" in render_all
    assert 'enabled.has(key.split("/")[0])' in render_all

    sidebar_module = _javascript_section(
        javascript,
        "  function renderSidebarModule(module)",
        "  function iconButton(text, label, handler)",
    )
    assert "toggleCollapsed(module.id)" in sidebar_module
    assert "collapseButton.disabled = !enabled" in sidebar_module
    collapse = _javascript_section(
        javascript, "  function toggleCollapsed(moduleId)", "  function moveModule"
    )
    assert "state.layout.collapsed_modules" in collapse
    assert "scheduleLayoutSave()" in collapse
    assert "renderAll()" in collapse


def test_radio_frontend_runtime_allowed_root_management_contract():
    javascript = RADIO_JS.read_text(encoding="utf-8")
    template = RADIO_HTML.read_text(encoding="utf-8")

    for element_id in (
        "manageAllowedRootsButton",
        "allowedRootsSummary",
        "allowedRootsDialog",
        "allowedRootsForm",
        "allowedRootsInput",
        "applyAllowedRootsButton",
        "browserAccessHelp",
        "browserManageRootsButton",
    ):
        assert f'id="{element_id}"' in template
    assert "Enter one editable data directory per line." in template
    assert "Changes apply only to future requests in this server session" in template
    assert "queued or running actions continue unchanged" in template
    assert "Protected output and saved-workspace roots" in template
    assert "--allowed-roots" in template

    root_management = _javascript_section(
        javascript,
        "  async function loadAllowedRoots()",
        "  async function openFileBrowser",
    )
    assert "requestJson(`${API}/allowed-roots`)" in root_management
    assert "payload.user_roots" in root_management
    assert "payload.startup_roots" in root_management
    assert "payload.protected_roots" in root_management
    assert "payload.effective_roots" in root_management
    assert "payload.roots" not in root_management
    assert 'method: "PUT"' in root_management
    assert 'headers: {"X-Radio-Root-Token": state.radioRootToken}' in root_management
    assert "body: {roots}" in root_management
    assert "parseAllowedRoots" in root_management
    assert "isAbsoluteLocalPath" in root_management
    assert "const roots = [...state.userRoots]" in root_management
    assert "roots.push(suggestedPath)" in root_management
    assert "await loadAllowedRoots()" in root_management
    assert "if (resumePath) await browsePath(resumePath)" in root_management
    assert "runAction" not in root_management
    assert "/runs" not in root_management

    browser = _javascript_section(
        javascript,
        "  async function browsePath(path)",
        "  function renderBrowserEntry(entry)",
    )
    assert "state.browser.rejectedPath" in browser
    assert "browserAccessHelp" in browser
    assert "outside (?:the )?allowed roots" in browser

    assert 'state.radioRootToken = String(config.radio_root_token || "")' in javascript
    assert "openAllowedRootsDialog(requested, requested)" in javascript
    assert (
        "File access roots updated for this server session. No action was started."
        in javascript
    )
    assert "state.effectiveRoots" in javascript
    assert "Protected output and workspace roots remain available." in javascript


def test_radio_frontend_field_and_multi_artifact_binding_contracts():
    javascript = RADIO_JS.read_text(encoding="utf-8")

    assert 'if (input.type === "number") input.step = "any"' in javascript
    assert "form[input.name] = input.checked" in javascript
    assert 'input.multiple = field.type === "multiselect"' in javascript
    assert "[...input.selectedOptions].map((option) => option.value)" in javascript
    assert "label.hidden = Boolean(field.hidden)" in javascript
    assert "reportValidity(" not in javascript
    assert "function addArtifactBinding(wrapper, action)" in javascript
    assert 'data-role="add-artifact-binding"' in javascript
    assert 'remove.dataset.role = "remove-artifact-binding"' in javascript
    assert (
        "for (const binding of $$(\"[data-role='artifact-binding']\", formElement))"
        in javascript
    )
    assert "const boundFields = new Set()" in javascript
    assert "if (field && boundFields.has(field))" in javascript
    assert "inputSources.push({" in javascript

    choices = _javascript_section(
        javascript,
        "  async function loadArtifactChoices(wrapper, action)",
        "  function artifactMatchesTypes(artifact, accepted)",
    )
    assert (
        "allArtifacts.filter((artifact) => artifactMatchesField(artifact, action, fieldName))"
        in choices
    )
    assert "wrapper._allArtifacts = allArtifacts" in choices
    assert "select.disabled = true" in choices
    assert "select.disabled = false" in choices
    assert "matched.length ? matched : allArtifacts" not in choices

    field_filter = _javascript_section(
        javascript,
        "  function artifactMatchesField(artifact, action, fieldName)",
        "  function renderField(field)",
    )
    assert "const accepted = field?.artifact_types || []" in field_filter
    assert "accepted.includes(artifact.artifact_type)" in field_filter
    assert "accepted.includes(artifact.semantic_type)" in field_filter
    assert "accepted.includes(artifact.kind)" in field_filter
    assert "artifactMatchesAction(artifact, action)" in field_filter

    binding = _javascript_section(
        javascript,
        "  function addArtifactBinding(wrapper, action)",
        "  function updateArtifactBindingControls(wrapper, action)",
    )
    assert 'fieldSelect.addEventListener("change"' in binding
    assert "artifactMatchesField(artifact, action, fieldSelect.value)" in binding
    assert "populateArtifactBindingArtifacts(row, compatible)" in binding


def test_radio_frontend_roi_candidate_selector_is_native_and_preview_only():
    javascript = RADIO_JS.read_text(encoding="utf-8")

    preview = _javascript_section(
        javascript,
        "  async function renderPreview(panel, preview)",
        "  function attachDriftLineSelector(panel, plot, contract)",
    )
    assert 'preview.adapter === "roi-selection"' in preview
    assert "attachRoiFileSelector(panel, preview)" in preview
    assert "function attachRoiFileSelector(panel, preview)" in preview
    assert "$(\"[name='selected_files_json']\", card)" in preview
    assert "Reference files (up to 9)" in preview
    assert "click Preview again" in preview
    assert "does not change extraction inputs" in preview
    assert "JSON.stringify(paths)" in preview
    assert "requestJson" not in _javascript_section(
        javascript,
        "  function attachRoiFileSelector(panel, preview)",
        "  function attachDriftLineSelector(panel, plot, contract)",
    )


def test_radio_frontend_plans_only_unique_explicit_selected_artifact_transfers():
    javascript = RADIO_JS.read_text(encoding="utf-8")

    planner = _javascript_section(
        javascript,
        "  function configuredValueIsPresent(value)",
        "  function selectedPayloads()",
    )
    assert "for (let producerIndex = 0; producerIndex < consumerIndex" in planner
    assert "field?.artifact_types || []" in planner
    assert "items[producerIndex].action.produces_artifacts" in planner
    assert 'actionAccepted.has("*")' in planner
    assert "if (candidates.length === 1)" in planner
    assert 'type: "batch_artifact"' in planner
    assert "workspace.shared_paths" in planner
    assert "workspace.event_preset" in planner
    assert "workspace.advanced_config" in planner
    assert "body.advanced_config" in planner
    assert "scopedActionConfigurations" in planner
    assert "field.config_path" in planner
    assert "state.selectedActions" not in planner
    assert "runAction" not in planner
    assert "requestJson" not in planner

    selected = _javascript_section(
        javascript,
        "  function selectedPayloads()",
        "  function describeSelectedSource(input)",
    )
    assert "state.layout.module_order" in selected
    assert "a.module.actions.indexOf(a.action)" in selected
    assert "b.module.actions.indexOf(b.action)" in selected
    assert "return planSelectedArtifactTransfers(payloads)" in selected

    review = _javascript_section(
        javascript,
        "  function describeSelectedSource(input)",
        "  async function confirmSelected(event)",
    )
    assert 'input.type === "batch_artifact"' in review
    assert "selected action ${input.producer_index + 1}" in review
    assert "(${input.artifact_type})" in review


def test_radio_frontend_preview_cleanup_and_safe_artifact_render_contracts():
    javascript = RADIO_JS.read_text(encoding="utf-8")
    combined = javascript + "\n" + RADIO_HTML.read_text(encoding="utf-8")

    assert "cleanupActionPreview(card);" in javascript
    assert (
        "for (const card of state.actionElements.values()) cleanupActionPreview(card)"
        in javascript
    )
    assert "window.clearInterval(timer)" in javascript
    assert "URL.revokeObjectURL(downloadUrl)" in javascript
    assert 'selectionInput.value = ""' in javascript
    assert 'panel.dataset.selection = ""' in javascript
    assert "download.href = `${url}?download=1`" in javascript
    assert 'document.createElement("img")' in javascript
    assert 'document.createElement("video")' in javascript
    assert 'window.open(url, "_blank", "noopener,noreferrer")' in javascript
    assert "script.src = `${API}/assets/plotly.js`" in javascript
    assert "loadScript(`${API}/assets/mediabunny-1.50.8.cjs`)" in javascript
    assert "<iframe" not in combined.casefold()
    assert "https://cdn" not in combined.casefold()


def test_radio_frontend_blocks_duplicate_action_queue_requests():
    javascript = RADIO_JS.read_text(encoding="utf-8")
    run_action = _javascript_section(
        javascript, "  async function runAction", "  function isActionRunActive"
    )

    assert (
        'card.dataset.startPending === "true" || isActionRunActive(key)' in run_action
    )
    assert 'card.dataset.startPending = "true"' in run_action
    assert "runButton.disabled = true" in run_action
    assert 'card.dataset.startPending = "false"' in run_action
    assert (
        "if (!isActionRunActive(key)) runButton.disabled = !action.runnable"
        in run_action
    )
    assert "requestJson" in run_action
    assert run_action.index('card.dataset.startPending = "true"') < run_action.index(
        "requestJson"
    )


def test_radio_catalog_fuses_overlapping_capabilities_into_eight_modules():
    from solar_toolkit.webapp.radio_workspace.catalog import MODULES, PRESETS

    assert [module.title for module in MODULES] == [
        "Data & Configuration",
        "Imaging & Source Localization",
        "ROI & Light Curves",
        "Spectrogram & Drift",
        "Physical Diagnostics",
        "Context & Overlays",
        "Trajectory & Media",
        "Runs & Results",
    ]
    assert set(PRESETS) == {
        "source-localization",
        "roi-study",
        "burst-physics",
        "multi-instrument-context",
        "full-analysis",
    }
    assert MODULES[0].default_enabled is True
    assert MODULES[0].default_collapsed is False
    assert all(module.default_collapsed for module in MODULES[1:])

    advanced = {
        (module.id, action.id)
        for module in MODULES
        for action in module.actions
        if action.section != "main"
    }
    assert advanced == {
        ("imaging-localization", "rrll-percentile-comparison"),
        ("spectrogram-drift", "cso-legacy-mode"),
        ("physical-diagnostics", "legacy-full-pipeline"),
        ("context-overlays", "dem-radio-overlay"),
    }


@pytest.mark.skipif(
    importlib.util.find_spec("flask") is None,
    reason="Flask is optional; install the app extra to test HTTP routes.",
)
def test_existing_webapp_serves_integrated_radio_workspace(tmp_path):
    from solar_toolkit.webapp.server import create_app

    output_root = tmp_path / "output"
    app = create_app(
        allowed_roots=[tmp_path],
        python_executable=sys.executable,
        repo_root=REPO_ROOT,
        radio_output_root=output_root,
        stop_on_client_close=False,
    )
    client = app.test_client()
    try:
        page = client.get("/radio")
        legacy_modules = client.get("/api/modules").get_json()
        modules = client.get("/api/radio/modules").get_json()
        presets = client.get("/api/radio/presets").get_json()
        files = client.get("/api/radio/files").get_json()
        media = client.get("/api/radio/assets/browser_media.js")

        assert page.status_code == 200
        assert "Select only the modules you need" in page.get_data(as_text=True)
        assert modules["ok"] is True
        assert len(modules["modules"]) == 8
        assert not any(
            item["category"] == "Radio Analysis" for item in legacy_modules["modules"]
        )
        assert client.get("/api/modules/radio-source-map").status_code == 200
        assert len(presets["presets"]) == 5
        assert output_root.resolve().as_posix().casefold() in {
            Path(root).as_posix().casefold() for root in files["roots"]
        }
        assert media.status_code == 200
        assert media.headers["X-Content-Type-Options"] == "nosniff"

        created_ids = []
        for name in ("Source Study", "Burst Study"):
            response = client.post(
                "/api/radio/workspaces",
                json={
                    "name": name,
                    "output_root": str(output_root),
                    "shared_paths": {},
                    "advanced_config": {},
                    "concurrency": 1,
                },
            )
            assert response.status_code == 201
            created_ids.append(response.get_json()["workspace"]["id"])
        saved = client.get("/api/radio/workspaces").get_json()["workspaces"]
        assert {item["id"] for item in saved} == set(created_ids)
        opened = client.get(f"/api/radio/workspaces/{created_ids[1]}")
        assert opened.status_code == 200
        assert opened.get_json()["workspace"]["name"] == "Burst Study"

        manager = app.extensions["radio_workspace"]["run_manager"]
        assert list(manager._pending) == []
        assert manager._active_total == 0
    finally:
        app.extensions["radio_workspace"]["run_manager"].close(cancel_running=True)
