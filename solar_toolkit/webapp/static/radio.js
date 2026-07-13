(function radioWorkspaceApp() {
  "use strict";

  const API = "/api/radio";
  const TERMINAL = new Set(["succeeded", "failed", "canceled", "interrupted"]);
  const state = {
    modules: [],
    presets: [],
    workspaces: [],
    workspace: null,
    workspaceDraftNew: false,
    layout: null,
    selectedActions: new Set(),
    actionElements: new Map(),
    activeRuns: new Map(),
    runs: [],
    browser: {target: null, kind: "file", current: "", selected: "", rejectedPath: ""},
    userRoots: [],
    startupRoots: [],
    protectedRoots: [],
    effectiveRoots: [],
    radioRootToken: "",
    rootsResumePath: "",
    clientId: `radio-workspace-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    stopOnClose: true,
    heartbeatTimer: null,
    saveTimer: null,
    pollTimer: null,
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const byId = (id) => document.getElementById(id);
  const keyFor = (moduleId, actionId) => `${moduleId}/${actionId}`;

  async function requestJson(path, options = {}) {
    const init = {...options, headers: {...(options.headers || {})}};
    if (init.body && typeof init.body !== "string") {
      init.headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(init.body);
    }
    const response = await fetch(path, init);
    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("json") ? await response.json() : {ok: response.ok};
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.error || `${response.status} ${response.statusText}`);
    }
    return payload;
  }

  function showNotice(message, tone = "warning") {
    const notice = byId("workspaceNotice");
    notice.textContent = message;
    notice.dataset.tone = tone;
    notice.hidden = false;
    window.clearTimeout(showNotice.timer);
    showNotice.timer = window.setTimeout(() => { notice.hidden = true; }, 7000);
  }

  function setHealth(ok, label) {
    const pill = byId("radioHealth");
    pill.dataset.state = ok ? "ready" : "error";
    pill.textContent = label;
  }

  function defaultLayout() {
    return {
      enabled_modules: state.modules.filter((item) => item.default_enabled).map((item) => item.id),
      module_order: state.modules.map((item) => item.id),
      collapsed_modules: state.modules.filter((item) => item.default_collapsed).map((item) => item.id),
      pinned_modules: [],
    };
  }

  function normalizeLayout(source) {
    const defaults = defaultLayout();
    const ids = new Set(state.modules.map((item) => item.id));
    const unique = (values) => Array.from(new Set((values || []).filter((id) => ids.has(id))));
    const order = unique(source?.module_order);
    for (const id of defaults.module_order) if (!order.includes(id)) order.push(id);
    const required = state.modules.filter((item) => item.always_available).map((item) => item.id);
    const enabled = unique(source?.enabled_modules ?? defaults.enabled_modules);
    for (const id of required) if (!enabled.includes(id)) enabled.push(id);
    return {
      enabled_modules: enabled,
      module_order: order,
      collapsed_modules: unique(source?.collapsed_modules ?? defaults.collapsed_modules),
      pinned_modules: unique(source?.pinned_modules),
    };
  }

  function moduleById(id) {
    return state.modules.find((item) => item.id === id);
  }

  function orderedModules() {
    const position = new Map(state.layout.module_order.map((id, index) => [id, index]));
    return [...state.modules].sort((left, right) => {
      const pinDelta = Number(state.layout.pinned_modules.includes(right.id)) - Number(state.layout.pinned_modules.includes(left.id));
      return pinDelta || (position.get(left.id) ?? 999) - (position.get(right.id) ?? 999);
    });
  }

  function scheduleLayoutSave() {
    window.clearTimeout(state.saveTimer);
    if (!state.workspace) {
      localStorage.setItem("solar-radio-layout", JSON.stringify(state.layout));
      return;
    }
    state.saveTimer = window.setTimeout(async () => {
      try {
        const payload = await requestJson(`${API}/workspaces/${state.workspace.id}/layout`, {
          method: "PATCH",
          body: state.layout,
        });
        state.workspace = payload.workspace;
      } catch (error) {
        showNotice(`Layout could not be saved: ${error.message}`);
      }
    }, 180);
  }

  function updateWorkspaceSummary() {
    const workspace = state.workspace;
    byId("workspaceName").textContent = workspace?.name || "Not configured";
    byId("workspaceEvent").textContent = workspace?.event_preset?.title || workspace?.event_preset?.id || "—";
    byId("workspaceOutput").textContent = workspace?.output_root || "—";
    byId("workspaceConcurrency").textContent = String(workspace?.concurrency || 1);
    const enabled = state.layout.enabled_modules.filter((id) => id !== "runs-results").map(moduleById).filter(Boolean);
    byId("workspaceTitle").textContent = enabled.length === 1 ? enabled[0].title : `${enabled.length} analysis modules enabled`;
    byId("workspaceHint").textContent = workspace
      ? "Configure and run actions independently. Missing inputs never trigger upstream work."
      : "Configure a workspace before running. Layout changes remain local until then.";
  }

  function renderAllowedRootsSummary() {
    const root = byId("allowedRootsSummary");
    root.replaceChildren();
    if (!state.effectiveRoots.length) {
      root.textContent = "No file access roots are configured.";
      return;
    }
    for (const path of state.effectiveRoots) {
      const item = document.createElement("div");
      item.className = "allowed-root-path";
      item.title = path;
      item.textContent = path;
      if (state.protectedRoots.some((protectedPath) => protectedPath.toLocaleLowerCase() === path.toLocaleLowerCase())) {
        item.dataset.protected = "true";
        item.title = `${path} (protected output root)`;
      }
      root.append(item);
    }
    if (state.protectedRoots.length) {
      const note = document.createElement("small");
      note.textContent = "Protected output and workspace roots remain available.";
      root.append(note);
    }
  }

  function renderSidebar() {
    const root = byId("moduleGroups");
    root.replaceChildren();
    const groups = ["Core", "Analysis", "Context", "Advanced"];
    for (const groupName of groups) {
      const modules = orderedModules().filter((item) => item.group === groupName);
      const group = document.createElement("details");
      group.className = "module-group";
      group.open = groupName !== "Advanced";
      const summary = document.createElement("summary");
      summary.innerHTML = `<span>${escapeHtml(groupName)}</span><span>${modules.length}</span>`;
      group.append(summary);
      const list = document.createElement("div");
      list.className = "module-nav-list";
      if (modules.length) {
        for (const module of modules) list.append(renderSidebarModule(module));
      } else {
        const note = document.createElement("p");
        note.className = "module-nav-note";
        note.textContent = "Legacy and adjacent actions stay inside their owning modules.";
        list.append(note);
      }
      group.append(list);
      root.append(group);
    }
  }

  function renderSidebarModule(module) {
    const enabled = state.layout.enabled_modules.includes(module.id);
    const collapsed = state.layout.collapsed_modules.includes(module.id);
    const row = document.createElement("div");
    row.className = "module-nav-item";
    row.dataset.enabled = String(enabled);

    const toggle = document.createElement("input");
    toggle.type = "checkbox";
    toggle.className = "module-toggle";
    toggle.checked = enabled;
    toggle.disabled = module.always_available;
    toggle.ariaLabel = `Enable ${module.title}`;
    toggle.addEventListener("change", () => {
      const list = state.layout.enabled_modules;
      if (toggle.checked && !list.includes(module.id)) list.push(module.id);
      if (!toggle.checked) state.layout.enabled_modules = list.filter((id) => id !== module.id);
      if (!toggle.checked && !state.layout.collapsed_modules.includes(module.id)) state.layout.collapsed_modules.push(module.id);
      scheduleLayoutSave();
      renderAll();
    });

    const text = document.createElement("div");
    text.innerHTML = `<strong>${escapeHtml(module.title)}</strong><small>${escapeHtml(module.description)}</small>`;

    const controls = document.createElement("div");
    controls.className = "module-nav-controls";
    const collapseButton = iconButton(collapsed ? "▸" : "▾", `${collapsed ? "Expand" : "Collapse"} ${module.title}`, () => toggleCollapsed(module.id));
    collapseButton.disabled = !enabled;
    controls.append(
      iconButton(state.layout.pinned_modules.includes(module.id) ? "★" : "☆", `Pin ${module.title}`, () => togglePinned(module.id)),
      collapseButton,
      iconButton("↑", `Move ${module.title} up`, () => moveModule(module.id, -1)),
      iconButton("↓", `Move ${module.title} down`, () => moveModule(module.id, 1)),
    );
    row.append(toggle, text, controls);
    return row;
  }

  function iconButton(text, label, handler) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "icon-button";
    button.textContent = text;
    button.ariaLabel = label;
    button.addEventListener("click", handler);
    return button;
  }

  function togglePinned(moduleId) {
    const pins = state.layout.pinned_modules;
    state.layout.pinned_modules = pins.includes(moduleId) ? pins.filter((id) => id !== moduleId) : [...pins, moduleId];
    scheduleLayoutSave();
    renderAll();
  }

  function toggleCollapsed(moduleId) {
    const collapsed = state.layout.collapsed_modules;
    state.layout.collapsed_modules = collapsed.includes(moduleId) ? collapsed.filter((id) => id !== moduleId) : [...collapsed, moduleId];
    scheduleLayoutSave();
    renderAll();
  }

  function moveModule(moduleId, delta) {
    const order = [...state.layout.module_order];
    const index = order.indexOf(moduleId);
    const next = index + delta;
    if (index < 0 || next < 0 || next >= order.length) return;
    [order[index], order[next]] = [order[next], order[index]];
    state.layout.module_order = order;
    scheduleLayoutSave();
    renderAll();
  }

  function renderWorkspace() {
    const root = byId("enabledModules");
    for (const card of state.actionElements.values()) cleanupActionPreview(card);
    root.replaceChildren();
    state.actionElements.clear();
    const enabled = orderedModules().filter((item) => state.layout.enabled_modules.includes(item.id) && item.id !== "runs-results");
    byId("emptyWorkspace").hidden = enabled.length > 0;
    for (const module of enabled) root.append(renderModule(module));
  }

  function renderModule(module) {
    const collapsed = state.layout.collapsed_modules.includes(module.id);
    const panel = document.createElement("section");
    panel.className = "module-panel";
    panel.dataset.moduleId = module.id;
    panel.dataset.collapsed = String(collapsed);

    const header = document.createElement("header");
    header.className = "module-panel-header";
    const copy = document.createElement("div");
    copy.innerHTML = `<h3>${escapeHtml(module.title)}</h3><p>${escapeHtml(module.description)}</p><span class="module-tier">${escapeHtml(module.group)}</span>`;
    const controls = document.createElement("div");
    controls.className = "module-panel-controls";
    controls.append(iconButton(collapsed ? "Expand" : "Collapse", `${collapsed ? "Expand" : "Collapse"} ${module.title}`, () => toggleCollapsed(module.id)));
    header.append(copy, controls);
    panel.append(header);

    const body = document.createElement("div");
    body.className = "module-body";
    const mainActions = module.actions.filter((item) => item.section === "main");
    const advancedActions = module.actions.filter((item) => item.section !== "main");
    if (mainActions.length) body.append(renderActionGrid(module, mainActions));
    if (advancedActions.length) {
      const advanced = document.createElement("details");
      advanced.className = "advanced-actions";
      advanced.innerHTML = "<summary>Advanced and adjacent capabilities</summary>";
      advanced.append(renderActionGrid(module, advancedActions));
      body.append(advanced);
    }
    panel.append(body);
    return panel;
  }

  function renderActionGrid(module, actions) {
    const grid = document.createElement("div");
    grid.className = "action-grid";
    for (const action of actions) grid.append(renderAction(module, action));
    return grid;
  }

  function renderAction(module, action) {
    const fragment = byId("actionTemplate").content.cloneNode(true);
    const card = $(".action-card", fragment);
    const key = keyFor(module.id, action.id);
    card.dataset.actionKey = key;
    $("[data-role='action-title']", card).textContent = action.title;
    $("[data-role='action-description']", card).textContent = action.description;
    const select = $("[data-role='select-action']", card);
    select.checked = state.selectedActions.has(key);
    select.disabled = !action.runnable;
    select.addEventListener("change", () => {
      if (select.checked) state.selectedActions.add(key); else state.selectedActions.delete(key);
      updateSelectedCount();
    });

    const form = $("[data-role='action-form']", card);
    form.addEventListener("submit", (event) => event.preventDefault());
    if (artifactBindableFields(action).length) form.append(renderArtifactSource(action));
    for (const field of action.input_schema || []) form.append(renderField(field));
    const advanced = $("[data-role='advanced-json']", card);
    advanced.value = JSON.stringify(action.default_config || {}, null, 2);

    const previewButton = $("[data-role='preview']", card);
    previewButton.disabled = !(action.preview_supported || action.runnable);
    previewButton.title = action.preview_supported ? "Build an explicit same-page preview" : "Validate inputs and inspect the resolved command without running it";
    previewButton.addEventListener("click", () => previewAction(module, action, card));

    const runButton = $("[data-role='run']", card);
    runButton.disabled = !action.runnable;
    runButton.title = action.runnable ? "Run only this action" : "Use Preview for this interactive capability";
    runButton.addEventListener("click", () => runAction(module, action, card));
    $("[data-role='cancel']", card).addEventListener("click", () => cancelActionRun(key));
    state.actionElements.set(key, card);
    const active = state.activeRuns.get(key);
    if (active) updateActionRunState(key, active);
    return card;
  }

  function renderArtifactSource(action) {
    const wrapper = document.createElement("div");
    wrapper.className = "artifact-source wide";
    wrapper.innerHTML = `<label>Input source<select data-role="source-mode"><option value="manual">Files or paths below</option><option value="artifact">Workspace artifacts</option></select></label><div data-role="artifact-picker" hidden><div data-role="artifact-bindings"></div><div class="path-control"><button type="button" class="secondary" data-role="add-artifact-binding">Add binding</button><button type="button" class="secondary" data-role="refresh-artifacts">Refresh artifacts</button></div></div><small>Accepted: ${escapeHtml((action.accepts_artifacts || []).join(", "))}. Each binding records its source run without copying the file.</small>`;
    const mode = $("[data-role='source-mode']", wrapper);
    const picker = $("[data-role='artifact-picker']", wrapper);
    mode.addEventListener("change", () => { picker.hidden = mode.value !== "artifact"; });
    $("[data-role='add-artifact-binding']", wrapper).addEventListener("click", () => addArtifactBinding(wrapper, action));
    $("[data-role='refresh-artifacts']", wrapper).addEventListener("click", () => loadArtifactChoices(wrapper, action));
    addArtifactBinding(wrapper, action);
    return wrapper;
  }

  function artifactBindableFields(action) {
    return (action.input_schema || []).filter((field) => field.path && (field.artifact_types || []).length);
  }

  function addArtifactBinding(wrapper, action) {
    const pathFields = artifactBindableFields(action);
    const rows = $$('[data-role="artifact-binding"]', wrapper);
    if (rows.length >= Math.max(1, pathFields.length)) return;
    const usedFields = new Set(rows.map((row) => $("[data-role='artifact-field']", row)?.value));
    const preferredField = pathFields.find((field) => !usedFields.has(field.name))?.name || pathFields[0]?.name || "";
    const row = document.createElement("div");
    row.className = "artifact-picker";
    row.dataset.role = "artifact-binding";
    const fieldLabel = document.createElement("label");
    fieldLabel.append(document.createTextNode("Bind to field"));
    const fieldSelect = document.createElement("select");
    fieldSelect.dataset.role = "artifact-field";
    if (pathFields.length) {
      for (const field of pathFields) fieldSelect.add(new Option(field.label || titleCase(field.name), field.name));
      fieldSelect.value = preferredField;
    } else {
      fieldSelect.add(new Option("Adapter input", ""));
    }
    fieldLabel.append(fieldSelect);
    const artifactLabel = document.createElement("label");
    artifactLabel.append(document.createTextNode("Artifact"));
    const controls = document.createElement("div");
    controls.className = "path-control";
    const artifactSelect = document.createElement("select");
    artifactSelect.dataset.role = "artifact-id";
    artifactSelect.add(new Option("Choose an artifact", ""));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "secondary";
    remove.dataset.role = "remove-artifact-binding";
    remove.textContent = "Remove";
    remove.addEventListener("click", () => {
      row.remove();
      updateArtifactBindingControls(wrapper, action);
    });
    controls.append(artifactSelect, remove);
    artifactLabel.append(controls);
    row.append(fieldLabel, artifactLabel);
    $("[data-role='artifact-bindings']", wrapper).append(row);
    fieldSelect.addEventListener("change", () => {
      const compatible = (wrapper._allArtifacts || []).filter((artifact) => artifactMatchesField(artifact, action, fieldSelect.value));
      populateArtifactBindingArtifacts(row, compatible);
      updateArtifactBindingControls(wrapper, action);
    });
    const compatible = (wrapper._allArtifacts || []).filter((artifact) => artifactMatchesField(artifact, action, preferredField));
    populateArtifactBindingArtifacts(row, compatible);
    updateArtifactBindingControls(wrapper, action);
  }

  function updateArtifactBindingControls(wrapper, action) {
    const pathFields = artifactBindableFields(action);
    const rows = $$('[data-role="artifact-binding"]', wrapper);
    $("[data-role='add-artifact-binding']", wrapper).disabled = rows.length >= Math.max(1, pathFields.length);
    for (const row of rows) $("[data-role='remove-artifact-binding']", row).disabled = rows.length <= 1;
  }

  function populateArtifactBindingArtifacts(row, artifacts) {
    const select = $("[data-role='artifact-id']", row);
    const selected = select.value;
    select.replaceChildren(new Option(artifacts.length ? "Choose an artifact" : "No compatible artifacts", ""));
    for (const artifact of artifacts) {
      const option = new Option(`${artifact.kind}: ${artifact.relative_path}`, artifact.id);
      option.dataset.runId = artifact.run_id || artifact.source_run_id;
      option.dataset.kind = artifact.kind;
      select.add(option);
    }
    if ([...select.options].some((option) => option.value === selected)) select.value = selected;
  }

  async function loadArtifactChoices(wrapper, action) {
    if (!state.workspace) return showNotice("Configure a workspace before choosing a saved artifact.");
    for (const select of $$("[data-role='artifact-id']", wrapper)) select.disabled = true;
    try {
      const payload = await requestJson(`${API}/workspaces/${state.workspace.id}/artifacts`);
      const allArtifacts = payload.artifacts || [];
      wrapper._allArtifacts = allArtifacts;
      for (const row of $$("[data-role='artifact-binding']", wrapper)) {
        const fieldName = $("[data-role='artifact-field']", row)?.value || "";
        const matched = allArtifacts.filter((artifact) => artifactMatchesField(artifact, action, fieldName));
        populateArtifactBindingArtifacts(row, matched);
      }
    } catch (error) {
      wrapper._allArtifacts = [];
      for (const select of $$("[data-role='artifact-id']", wrapper)) select.replaceChildren(new Option("Artifacts unavailable", ""));
      showNotice(`Artifacts could not be loaded: ${error.message}`);
    } finally {
      for (const select of $$("[data-role='artifact-id']", wrapper)) select.disabled = false;
    }
  }

  function artifactMatchesTypes(artifact, accepted) {
    if (accepted.includes("*") || accepted.includes(artifact.kind) || accepted.includes(artifact.artifact_type) || accepted.includes(artifact.semantic_type)) return true;
    const generic = String(artifact.kind || "");
    return accepted.some((item) =>
      (item.endsWith("-table") && generic === "table") ||
      ((item.endsWith("-image") || item.endsWith("-map")) && generic === "image") ||
      ((item.endsWith("-json") || item.endsWith("-selection")) && generic === "json") ||
      (item === "radio-fits" && /fits|file/.test(generic)) ||
      (item.endsWith("-video") && generic === "video") ||
      (item.endsWith("-html") && generic === "html")
    );
  }

  function artifactMatchesAction(artifact, action) {
    const accepted = action.accepts_artifacts || [];
    return artifactMatchesTypes(artifact, accepted);
  }

  function artifactMatchesField(artifact, action, fieldName) {
    const field = (action.input_schema || []).find((item) => item.name === fieldName);
    const accepted = field?.artifact_types || [];
    const fieldMatches = accepted.includes("*") || accepted.includes(artifact.artifact_type) || accepted.includes(artifact.semantic_type) || accepted.includes(artifact.kind);
    return accepted.length > 0 && artifactMatchesAction(artifact, action) && fieldMatches;
  }

  function renderField(field) {
    const label = document.createElement("label");
    label.dataset.fieldName = field.name;
    label.hidden = Boolean(field.hidden);
    if (["argv", "textarea", "json"].includes(field.type)) label.classList.add("wide");
    label.append(document.createTextNode(field.label + (field.required ? " *" : "")));
    let input;
    if (["select", "multiselect"].includes(field.type)) {
      input = document.createElement("select");
      input.multiple = field.type === "multiselect";
      for (const choice of field.choices || []) input.add(new Option(choice, choice));
    } else if (["argv", "textarea", "json"].includes(field.type)) {
      input = document.createElement("textarea");
      input.rows = field.type === "argv" ? 3 : 5;
      if (field.type === "argv") input.placeholder = '["--flag", "value"]';
    } else {
      input = document.createElement("input");
      input.type = field.type === "checkbox" ? "checkbox" : field.type === "number" ? "number" : "text";
      if (input.type === "number") input.step = "any";
    }
    input.name = field.name;
    input.dataset.fieldType = field.type || "text";
    input.required = Boolean(field.required);
    if (field.default !== undefined) {
      if (input.type === "checkbox") {
        input.checked = Boolean(field.default);
      } else if (field.type === "multiselect" && Array.isArray(field.default)) {
        const defaults = new Set(field.default.map(String));
        for (const option of input.options) option.selected = defaults.has(option.value);
      } else {
        input.value = field.type === "argv" && Array.isArray(field.default) ? JSON.stringify(field.default) : field.default;
      }
    }
    if (field.path) {
      const control = document.createElement("div");
      control.className = "path-control";
      const browse = document.createElement("button");
      browse.type = "button";
      browse.className = "secondary";
      browse.textContent = "Browse";
      browse.addEventListener("click", () => openFileBrowser(input, field.type === "directory" || /dir|folder|root/i.test(field.name) ? "directory" : "file"));
      control.append(input, browse);
      label.append(control);
    } else {
      label.append(input);
    }
    if (field.help) {
      const help = document.createElement("small");
      help.textContent = field.help;
      label.append(help);
    }
    return label;
  }

  function collectActionPayload(module, action, card, validate = true) {
    const formElement = $("[data-role='action-form']", card);
    const form = {};
    let argumentsList = [];
    for (const input of $$('[name]', formElement)) {
      const type = input.dataset.fieldType || input.type;
      if (type === "checkbox") {
        form[input.name] = input.checked;
      } else if (type === "number") {
        if (input.value !== "") form[input.name] = Number(input.value);
      } else if (type === "multiselect") {
        const values = [...input.selectedOptions].map((option) => option.value);
        if (input.required && !values.length) throw new Error(`${titleCase(input.name)} requires at least one selection.`);
        form[input.name] = values;
      } else if (type === "argv") {
        if (input.value.trim()) {
          const parsed = JSON.parse(input.value);
          if (!Array.isArray(parsed) || parsed.some((item) => typeof item !== "string")) throw new Error("Additional arguments must be a JSON array of strings.");
          argumentsList = parsed;
        }
      } else if (input.value !== "") {
        form[input.name] = input.value;
      }
    }
    const advancedText = $("[data-role='advanced-json']", card).value.trim() || "{}";
    const advancedConfig = JSON.parse(advancedText);
    if (!advancedConfig || Array.isArray(advancedConfig) || typeof advancedConfig !== "object") throw new Error("Advanced configuration must be a JSON object.");
    const inputSources = [];
    const sourceMode = $("[data-role='source-mode']", formElement);
    if (sourceMode?.value === "artifact") {
      const boundFields = new Set();
      for (const binding of $$("[data-role='artifact-binding']", formElement)) {
        const option = $("[data-role='artifact-id']", binding)?.selectedOptions?.[0];
        if (!option?.value) throw new Error("Choose an artifact for every binding or remove the unused binding.");
        const field = $("[data-role='artifact-field']", binding)?.value || "";
        if (field && boundFields.has(field)) throw new Error(`Bind only one artifact to ${titleCase(field)}.`);
        if (field) boundFields.add(field);
        inputSources.push({
          type: "artifact",
          run_id: option.dataset.runId,
          artifact_id: option.value,
          field,
        });
      }
      if (!inputSources.length) throw new Error("Add at least one workspace artifact binding or switch the input source to files.");
    }
    // Required values may come from an artifact binding or a lower-precedence
    // workspace layer, so the server validates the fully resolved request.
    void validate;
    return {module_id: module.id, action_id: action.id, form, arguments: argumentsList, advanced_config: advancedConfig, input_sources: inputSources};
  }

  async function previewAction(module, action, card) {
    const panel = $("[data-role='preview-panel']", card);
    try {
      if (action.preview_adapter === "file-browser") {
        const input = $("[name='path']", card);
        return openFileBrowser(input, "directory");
      }
      if (action.preview_adapter === "run-index" || action.preview_adapter === "artifact-index") {
        return openResultsDrawer();
      }
      requireWorkspace();
      if (["roi-selection", "drift-selection"].includes(action.preview_adapter)) {
        for (const name of ["roi_json_payload", "drift_lines_json"]) {
          const selectionInput = $(`[name='${name}']`, card);
          if (selectionInput) selectionInput.value = "";
        }
      }
      setActionStatus(card, "running", "Previewing");
      panel.hidden = false;
      panel.textContent = "Preparing explicit preview…";
      const body = collectActionPayload(module, action, card);
      const payload = await requestJson(`${API}/workspaces/${state.workspace.id}/modules/${module.id}/actions/${action.id}/preview`, {method: "POST", body});
      await renderPreview(panel, payload.preview || {});
      setActionStatus(card, "succeeded", "Preview ready");
    } catch (error) {
      panel.hidden = false;
      panel.textContent = error.message;
      setActionStatus(card, "failed", "Preview failed");
    }
  }

  async function renderPreview(panel, preview) {
    const card = panel.closest(".action-card");
    cleanupActionPreview(card);
    panel.replaceChildren();
    if (preview.adapter === "roi-selection" && Array.isArray(preview.candidates)) {
      attachRoiFileSelector(panel, preview);
    }
    if (preview.figure) {
      await ensurePlotly();
      const plot = document.createElement("div");
      plot.className = "plotly-preview";
      panel.append(plot);
      const figure = typeof preview.figure === "string" ? JSON.parse(preview.figure) : preview.figure;
      await window.Plotly.newPlot(plot, figure.data || [], figure.layout || {}, {responsive: true, displaylogo: false});
      card._previewCleanup = () => window.Plotly?.purge?.(plot);
      if (preview.playback?.frames?.length) {
        attachTrajectoryPlayer(panel, plot, preview.playback);
      }
      if (preview.selection_target || preview.selection) {
        const selectionContract = preview.selection_target || preview.selection;
        if (selectionContract.mode === "two-point-lines") {
          attachDriftLineSelector(panel, plot, selectionContract);
          return;
        }
        const output = document.createElement("pre");
        output.textContent = "Drag on the plot to create a selection.";
        panel.append(output);
        plot.on("plotly_selected", (event) => {
          const points = (event?.points || []).map((item) => ({x: item.x, y: item.y, pointIndex: item.pointIndex}));
          const selectionInput = $("[name='roi_json_payload']", panel.closest(".action-card"));
          if (!event?.range && !event?.lassoPoints && !points.length) {
            output.textContent = "No ROI selected. Drag a box or lasso on the plot.";
            panel.dataset.selection = "";
            if (selectionInput) selectionInput.value = "";
            return;
          }
          const selection = {range: event?.range || null, lassoPoints: event?.lassoPoints || null, points};
          output.textContent = JSON.stringify(selection, null, 2);
          panel.dataset.selection = JSON.stringify(selection);
          if (selectionInput) selectionInput.value = JSON.stringify(selection);
        });
      }
      return;
    }
    if (preview.image_url) {
      const image = document.createElement("img");
      image.src = preview.image_url;
      image.alt = preview.title || "Action preview";
      panel.append(image);
    }
    if (preview.message) {
      const message = document.createElement("p");
      message.textContent = preview.message;
      panel.append(message);
    }
    if (preview.command) {
      const command = document.createElement("pre");
      command.textContent = preview.command.join(" ");
      panel.append(command);
    }
    if (preview.resolved_config) {
      const details = document.createElement("details");
      details.innerHTML = "<summary>Resolved configuration</summary>";
      const pre = document.createElement("pre");
      pre.textContent = JSON.stringify(preview.resolved_config, null, 2);
      details.append(pre);
      panel.append(details);
    }
    if (!panel.childElementCount) panel.textContent = preview.available === false ? "No native preview is available. You can still run this action explicitly." : "Preview completed.";
  }

  function attachRoiFileSelector(panel, preview) {
    const card = panel.closest(".action-card");
    const managedInput = $("[name='selected_files_json']", card);
    const selected = new Set(preview.selected_files || preview.candidates.filter((item) => item.selected).map((item) => item.path));
    const fieldset = document.createElement("fieldset");
    fieldset.className = "roi-file-selector";
    const legend = document.createElement("legend");
    legend.textContent = "Reference files (up to 9)";
    const hint = document.createElement("small");
    hint.textContent = "Choose files, then click Preview again to rebuild the multi-frequency reference grid. This does not change extraction inputs.";
    const status = document.createElement("span");
    status.className = "roi-file-status";
    const list = document.createElement("div");
    list.className = "roi-file-list";

    const writeSelection = () => {
      const paths = $$('input[type="checkbox"]:checked', list).map((input) => input.value);
      if (managedInput) managedInput.value = JSON.stringify(paths);
      status.textContent = `${paths.length} selected`;
    };
    for (const candidate of preview.candidates) {
      const label = document.createElement("label");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = candidate.path;
      checkbox.checked = selected.has(candidate.path);
      const frequency = candidate.frequency_mhz == null ? "unknown frequency" : `${Number(candidate.frequency_mhz).toLocaleString()} MHz`;
      const time = candidate.observation_time || "unknown time";
      label.append(checkbox, document.createTextNode(`${candidate.relative_path || candidate.name} | ${frequency} | ${candidate.polarization || "UNKNOWN"} | ${time}`));
      checkbox.addEventListener("change", () => {
        if (checkbox.checked && $$('input[type="checkbox"]:checked', list).length > 9) {
          checkbox.checked = false;
          status.textContent = "Select at most 9 reference files.";
          return;
        }
        writeSelection();
      });
      list.append(label);
    }
    fieldset.append(legend, hint, list, status);
    panel.append(fieldset);
    writeSelection();
  }

  function attachDriftLineSelector(panel, plot, contract) {
    const toolbar = document.createElement("div");
    toolbar.className = "selection-controls";
    toolbar.innerHTML = '<button type="button" class="secondary" data-role="undo-drift">Undo line</button><button type="button" class="secondary" data-role="clear-drift">Clear lines</button><span>Click two endpoints for each drift line.</span>';
    panel.insertBefore(toolbar, plot);
    const output = document.createElement("pre");
    output.textContent = "No drift lines selected.";
    panel.append(output);
    const pending = [];
    const lines = [];
    const colors = ["#ffffff", "#52d6ff", "#8bf18b", "#ffd166", "#ff75d8", "#ff9f5a"];

    const write = async () => {
      const shapes = lines.map((line) => ({type: "line", x0: line.t_start, x1: line.t_end, y0: line.f_start_mhz, y1: line.f_end_mhz, line: {color: line.color, width: 3}}));
      if (pending.length === 1) shapes.push({type: "circle", x0: pending[0].x, x1: pending[0].x, y0: pending[0].y, y1: pending[0].y, line: {color: colors[lines.length % colors.length], width: 7}});
      await window.Plotly.relayout(plot, {shapes});
      output.textContent = lines.length ? JSON.stringify(lines, null, 2) : pending.length ? "Start endpoint selected. Click the end endpoint." : "No drift lines selected.";
      const card = panel.closest(".action-card");
      const input = $(`[name='${contract.output_field || "drift_lines_json"}']`, card);
      if (input) input.value = lines.length ? JSON.stringify(lines) : "";
    };
    plot.addEventListener("click", (event) => {
      const full = plot._fullLayout;
      const size = full?._size;
      const xaxis = full?.xaxis;
      const yaxis = full?.yaxis;
      if (!size || !xaxis?.p2d || !yaxis?.p2d) return;
      const bounds = plot.getBoundingClientRect();
      const px = event.clientX - bounds.left - size.l;
      const py = event.clientY - bounds.top - size.t;
      if (px < 0 || py < 0 || px > size.w || py > size.h) return;
      const xValue = xaxis.p2d(px);
      const yValue = Number(yaxis.p2d(py));
      const timestamp = new Date(xValue);
      if (!Number.isFinite(timestamp.getTime()) || !Number.isFinite(yValue)) return;
      pending.push({x: timestamp.toISOString(), y: yValue});
      if (pending.length === 2) {
        const start = pending.shift();
        const end = pending.shift();
        const duration = (new Date(end.x) - new Date(start.x)) / 1000;
        const index = lines.length + 1;
        lines.push({
          label: `drift_${String(index).padStart(3, "0")}`,
          t_start: start.x,
          f_start_mhz: start.y,
          t_end: end.x,
          f_end_mhz: end.y,
          drift_rate_mhz_s: duration ? (end.y - start.y) / duration : null,
          color: colors[(index - 1) % colors.length],
          note: "",
        });
      }
      write();
    });
    $("[data-role='undo-drift']", toolbar).addEventListener("click", () => {
      if (pending.length) pending.pop(); else lines.pop();
      write();
    });
    $("[data-role='clear-drift']", toolbar).addEventListener("click", () => {
      pending.splice(0);
      lines.splice(0);
      write();
    });
  }

  function attachTrajectoryPlayer(panel, plot, payload) {
    const controls = document.createElement("div");
    controls.className = "trajectory-controls";
    controls.innerHTML = `<button type="button" class="secondary" data-role="previous-frame">Previous</button><button type="button" data-role="play-frames">Play</button><button type="button" class="secondary" data-role="next-frame">Next</button><input type="range" min="0" max="${payload.frames.length - 1}" value="0" data-role="frame-range" aria-label="Trajectory frame"/><select data-role="record-format" aria-label="Recording format"><option value="mp4">MP4</option><option value="webm">WebM</option></select><button type="button" class="secondary" data-role="record-frames">Record</button><a data-role="record-download" class="artifact-link" hidden>Download</a><span data-role="playback-status"></span>`;
    panel.insertBefore(controls, plot);
    const previous = $("[data-role='previous-frame']", controls);
    const play = $("[data-role='play-frames']", controls);
    const next = $("[data-role='next-frame']", controls);
    const range = $("[data-role='frame-range']", controls);
    const status = $("[data-role='playback-status']", controls);
    const record = $("[data-role='record-frames']", controls);
    const format = $("[data-role='record-format']", controls);
    const download = $("[data-role='record-download']", controls);
    let frameIndex = 0;
    let timer = null;
    let recording = false;
    let cancelRecording = false;
    let downloadUrl = null;
    const card = panel.closest(".action-card");
    const baseCleanup = card._previewCleanup;
    card._previewCleanup = () => {
      stop();
      cancelRecording = true;
      if (downloadUrl) URL.revokeObjectURL(downloadUrl);
      downloadUrl = null;
      if (typeof baseCleanup === "function") baseCleanup();
    };

    const renderFrame = async (index) => {
      frameIndex = Math.max(0, Math.min(Number(index), payload.frames.length - 1));
      const frame = payload.frames[frameIndex];
      range.value = String(frameIndex);
      status.textContent = `${frameIndex + 1} / ${payload.frames.length} · ${frame.time}`;
      await window.Plotly.react(
        plot,
        trajectoryFrameData(payload, frame),
        trajectoryFrameLayout(payload, frame, plot.clientWidth || 960),
        {responsive: true, displaylogo: false},
      );
    };
    const stop = () => {
      if (timer !== null) window.clearInterval(timer);
      timer = null;
      play.textContent = "Play";
    };
    previous.addEventListener("click", () => { stop(); renderFrame(frameIndex - 1); });
    next.addEventListener("click", () => { stop(); renderFrame(frameIndex + 1); });
    range.addEventListener("input", () => { stop(); renderFrame(range.value); });
    play.addEventListener("click", () => {
      if (timer !== null) return stop();
      play.textContent = "Pause";
      const fps = Math.max(0.2, Number(payload.config?.fps || 2));
      timer = window.setInterval(() => renderFrame((frameIndex + 1) % payload.frames.length), Math.max(25, 1000 / fps));
    });
    record.addEventListener("click", async () => {
      if (recording) {
        cancelRecording = true;
        return;
      }
      stop();
      recording = true;
      cancelRecording = false;
      record.textContent = "Cancel recording";
      download.hidden = true;
      if (downloadUrl) URL.revokeObjectURL(downloadUrl);
      downloadUrl = null;
      const original = frameIndex;
      let session = null;
      try {
        await ensureMediaAssets();
        const canvas = document.createElement("canvas");
        canvas.width = 1280;
        canvas.height = 720;
        const context = canvas.getContext("2d", {alpha: false});
        const fps = Math.max(0.2, Number(payload.config?.fps || 2));
        session = await window.SolarToolkitMedia.createCanvasRecorder({canvas, format: format.value, quality: "high", fps, targetMode: "buffer", contentHint: "detail"});
        for (let index = 0; index < payload.frames.length; index += 1) {
          if (cancelRecording) throw new DOMException("Recording canceled", "AbortError");
          await renderFrame(index);
          const dataUrl = await window.Plotly.toImage(plot, {format: "png", width: 1280, height: 720, scale: 1});
          const image = await dataUrlImage(dataUrl);
          context.fillStyle = "#081019";
          context.fillRect(0, 0, canvas.width, canvas.height);
          context.drawImage(image, 0, 0, canvas.width, canvas.height);
          await session.addFrame(index / fps, 1 / fps, {keyFrame: index === 0});
          status.textContent = `Encoding ${index + 1} / ${payload.frames.length}`;
        }
        const result = await session.finalize();
        const mime = format.value === "mp4" ? "video/mp4" : "video/webm";
        const blob = new Blob([result.buffer], {type: mime});
        downloadUrl = URL.createObjectURL(blob);
        download.href = downloadUrl;
        download.download = `radio-source-trajectory.${format.value}`;
        download.textContent = `Download ${format.value.toUpperCase()}`;
        download.hidden = false;
        status.textContent = `${format.value.toUpperCase()} ready · ${payload.frames.length} frames · ${(blob.size / 1024 / 1024).toFixed(2)} MB`;
      } catch (error) {
        if (session && !["canceled", "finalized"].includes(session.state)) await session.cancel().catch(() => {});
        status.textContent = error.name === "AbortError" ? "Recording canceled." : `Recording failed: ${error.message}`;
      } finally {
        recording = false;
        cancelRecording = false;
        record.textContent = "Record";
        await renderFrame(original);
      }
    });
    renderFrame(0);
  }

  function cleanupActionPreview(card) {
    if (!card || typeof card._previewCleanup !== "function") return;
    try {
      card._previewCleanup();
    } finally {
      card._previewCleanup = null;
    }
  }

  function trajectoryFrameData(payload, frame) {
    return (frame.groups || []).map((group) => {
      const trace = payload.traces[group.trace];
      const start = Math.max(0, Number(group.start));
      const end = Math.max(start, Number(group.end));
      const count = end - start;
      const minimum = Math.min(1, Math.max(0, Number(payload.config?.trail_min_opacity || 0.25)));
      const opacity = count <= 1 ? [1] : Array.from({length: count}, (_, index) => minimum + ((1 - minimum) * index) / (count - 1));
      return {
        type: "scattergl",
        mode: payload.config?.draw_lines ? "lines+markers" : "markers",
        name: trace.name,
        x: trace.x.slice(start, end),
        y: trace.y.slice(start, end),
        marker: {size: Math.max(1, Number(payload.config?.marker_size || 8)), symbol: trace.marker_symbol || "circle", opacity},
        line: {width: 2},
        xaxis: trajectoryAxisName("x", Number(trace.facet || 0), payload),
        yaxis: trajectoryAxisName("y", Number(trace.facet || 0), payload),
        hovertemplate: `${trace.name}<br>x=%{x:.2f}<br>y=%{y:.2f}<extra></extra>`,
      };
    });
  }

  function trajectoryAxisName(prefix, index, payload) {
    if (payload.layout?.plot_layout !== "facets") return prefix;
    return index <= 0 ? prefix : `${prefix}${index + 1}`;
  }

  function trajectoryFrameLayout(payload, frame, width) {
    const themes = payload.layout?.themes || {};
    const dark = window.matchMedia?.("(prefers-color-scheme: dark)")?.matches;
    const mode = payload.layout?.theme_mode || "auto";
    const theme = mode === "dark" || (mode === "auto" && dark) ? themes.dark || payload.layout.theme : themes.light || payload.layout.theme;
    const axis = payload.layout?.axis || {x0: -1, x1: 1, y0: -1, y1: 1};
    const facets = payload.layout?.plot_layout === "facets" ? payload.layout.facets || [] : [];
    const count = Math.max(1, facets.length);
    const columns = facets.length ? Math.min(3, count) : 1;
    const rows = Math.ceil(count / columns);
    const layout = {
      title: `${payload.layout?.title || "Radio source trajectory"} | ${frame.time}`,
      height: Math.max(420, Number(payload.layout?.height || Math.min(760, width * 0.75))),
      margin: {l: 50, r: 20, t: 70, b: 48},
      paper_bgcolor: theme?.paper_bgcolor || "#081019",
      plot_bgcolor: theme?.plot_bgcolor || "#101b27",
      font: {color: theme?.font_color || "#edf5fb"},
      legend: {orientation: "h", y: 1.05},
      annotations: [],
      images: [],
      uirevision: "radio-workspace-playback",
    };
    const background = frame.background ? payload.backgrounds?.[frame.background] : null;
    for (let index = 0; index < count; index += 1) {
      const row = Math.floor(index / columns);
      const column = index % columns;
      const gapX = 0.06;
      const gapY = 0.12;
      const cellWidth = (1 - gapX * (columns - 1)) / columns;
      const cellHeight = (1 - gapY * (rows - 1)) / rows;
      const domainX = [column * (cellWidth + gapX), column * (cellWidth + gapX) + cellWidth];
      const domainY = [1 - (row + 1) * cellHeight - row * gapY, 1 - row * (cellHeight + gapY)];
      const suffix = index === 0 ? "" : String(index + 1);
      layout[`xaxis${suffix}`] = {title: "HPLN / arcsec", range: [axis.x0, axis.x1], domain: domainX, gridcolor: theme?.grid_color};
      layout[`yaxis${suffix}`] = {title: "HPLT / arcsec", range: [axis.y0, axis.y1], domain: domainY, gridcolor: theme?.grid_color, scaleanchor: `x${suffix}`, scaleratio: 1};
      if (background) {
        layout.images.push({source: background.source, xref: `x${suffix}`, yref: `y${suffix}`, x: background.x0, y: background.y1, sizex: background.x1 - background.x0, sizey: background.y1 - background.y0, sizing: "stretch", opacity: 1, layer: "below"});
      }
      if (facets[index]) layout.annotations.push({text: facets[index].label, showarrow: false, xref: "paper", yref: "paper", x: (domainX[0] + domainX[1]) / 2, y: Math.min(1.06, domainY[1] + 0.04)});
    }
    return layout;
  }

  function dataUrlImage(url) {
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error("Could not rasterize the current trajectory frame."));
      image.src = url;
    });
  }

  async function ensureMediaAssets() {
    if (window.Mediabunny && window.SolarToolkitMedia) return;
    if (!ensureMediaAssets.promise) {
      ensureMediaAssets.promise = loadScript(`${API}/assets/mediabunny-1.50.8.cjs`).then(() => loadScript(`${API}/assets/browser_media.js`));
    }
    await ensureMediaAssets.promise;
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = src;
      script.onload = resolve;
      script.onerror = () => reject(new Error(`Bundled browser asset could not be loaded: ${src}`));
      document.head.append(script);
    });
  }

  async function ensurePlotly() {
    if (window.Plotly) return;
    if (!ensurePlotly.promise) {
      ensurePlotly.promise = new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = `${API}/assets/plotly.js`;
        script.onload = resolve;
        script.onerror = () => reject(new Error("The bundled Plotly runtime could not be loaded."));
        document.head.append(script);
      });
    }
    await ensurePlotly.promise;
  }

  function requireWorkspace() {
    if (!state.workspace) throw new Error("Configure and save a workspace before running or previewing this action.");
  }

  async function runAction(module, action, card) {
    const key = keyFor(module.id, action.id);
    const runButton = $("[data-role='run']", card);
    if (card.dataset.startPending === "true" || isActionRunActive(key)) {
      showNotice(`${action.title} is already queued or running.`);
      return;
    }
    card.dataset.startPending = "true";
    runButton.disabled = true;
    try {
      requireWorkspace();
      const body = collectActionPayload(module, action, card);
      setActionStatus(card, "queued", "Queueing");
      const payload = await requestJson(`${API}/workspaces/${state.workspace.id}/runs`, {method: "POST", body});
      registerRuns([payload.run]);
      showNotice(`${action.title} was queued. No other action was started.`, "success");
    } catch (error) {
      setActionStatus(card, "failed", "Not started");
      showNotice(error.message);
    } finally {
      card.dataset.startPending = "false";
      if (!isActionRunActive(key)) runButton.disabled = !action.runnable;
    }
  }

  function isActionRunActive(key) {
    const run = state.activeRuns.get(key);
    return Boolean(run && !TERMINAL.has(run.status));
  }

  function registerRuns(runs) {
    for (const run of runs || []) {
      const key = keyFor(run.module_id, run.action_id);
      state.activeRuns.set(key, run);
      const card = state.actionElements.get(key);
      if (card) {
        card.dataset.artifactsLoaded = "false";
        const result = $("[data-role='action-result']", card);
        result.hidden = true;
        result.replaceChildren();
      }
      updateActionRunState(key, run);
    }
    startPolling();
  }

  function updateActionRunState(key, run) {
    const card = state.actionElements.get(key);
    if (!card) return;
    const progress = Number.isFinite(Number(run.progress)) ? ` · ${Math.round(Number(run.progress) * 100)}%` : "";
    setActionStatus(card, run.status, `${titleCase(run.status)}${progress}`);
    const cancel = $("[data-role='cancel']", card);
    const active = ["queued", "running"].includes(run.status);
    cancel.disabled = !active;
    $("[data-role='run']", card).disabled = active;
    const log = $("[data-role='action-log']", card);
    if (run.logs?.length) {
      log.hidden = false;
      log.textContent = run.logs.join("\n");
    }
    if (TERMINAL.has(run.status) && card.dataset.artifactsLoaded !== "true") {
      loadActionArtifacts(card, run).catch((error) => {
        const result = $("[data-role='action-result']", card);
        result.hidden = false;
        result.textContent = `Artifacts could not be loaded: ${error.message}`;
      });
    }
  }

  async function loadActionArtifacts(card, run) {
    card.dataset.artifactsLoaded = "true";
    const result = $("[data-role='action-result']", card);
    const payload = await requestJson(`${API}/workspaces/${state.workspace.id}/runs/${run.id}/artifacts`);
    result.replaceChildren();
    for (const artifact of payload.artifacts || []) result.append(renderArtifact(run, artifact));
    if (!result.childElementCount) result.textContent = "This action produced no indexed artifacts.";
    result.hidden = false;
  }

  function setActionStatus(card, stateName, label) {
    const status = $("[data-role='action-status']", card);
    status.dataset.state = stateName;
    status.textContent = label;
  }

  async function cancelActionRun(key) {
    const run = state.activeRuns.get(key);
    if (!run || !state.workspace) return;
    try {
      const payload = await requestJson(`${API}/workspaces/${state.workspace.id}/runs/${run.id}/cancel`, {method: "POST"});
      state.activeRuns.set(key, payload.run);
      updateActionRunState(key, payload.run);
    } catch (error) {
      showNotice(`Cancel failed: ${error.message}`);
    }
  }

  function startPolling() {
    if (state.pollTimer) return;
    const tick = async () => {
      const pending = [...state.activeRuns.entries()].filter(([, run]) => !TERMINAL.has(run.status));
      if (!pending.length) {
        window.clearInterval(state.pollTimer);
        state.pollTimer = null;
        return;
      }
      for (const [key, run] of pending) {
        try {
          const payload = await requestJson(`${API}/workspaces/${state.workspace.id}/runs/${run.id}/status`);
          const logPayload = await requestJson(`${API}/workspaces/${state.workspace.id}/runs/${run.id}/log?offset=0`);
          payload.run.logs = logPayload.lines || [];
          state.activeRuns.set(key, payload.run);
          updateActionRunState(key, payload.run);
        } catch (error) {
          console.warn(error);
        }
      }
    };
    state.pollTimer = window.setInterval(tick, 1000);
    tick();
  }

  function updateSelectedCount() {
    const count = state.selectedActions.size;
    byId("selectedActionCount").textContent = `${count} action${count === 1 ? "" : "s"} selected`;
    byId("runSelectedButton").disabled = count === 0;
  }

  function configuredValueIsPresent(value) {
    if (value === null || value === undefined) return false;
    if (typeof value === "string") return value.trim() !== "";
    if (Array.isArray(value)) return value.length > 0;
    if (typeof value === "object") return Object.keys(value).length > 0;
    return true;
  }

  function nestedConfigurationValue(source, path) {
    let value = source;
    for (const part of String(path || "").split(".").filter(Boolean)) {
      if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
      value = value[part];
    }
    return value;
  }

  function fieldIsConfigured(source, field) {
    if (!source || typeof source !== "object" || Array.isArray(source)) return false;
    return [field.name, field.config_path]
      .filter(Boolean)
      .some((path) => configuredValueIsPresent(nestedConfigurationValue(source, path)));
  }

  function scopedActionConfigurations(source, moduleId, actionId) {
    if (!source || typeof source !== "object" || Array.isArray(source)) return [];
    const directModule = source[moduleId];
    const modulesModule = source.modules?.[moduleId];
    return [
      source,
      directModule,
      modulesModule,
      directModule?.actions?.[actionId],
      directModule?.[actionId],
      modulesModule?.actions?.[actionId],
      modulesModule?.[actionId],
      source.actions?.[actionId],
      source[actionId],
    ].filter((item) => item && typeof item === "object" && !Array.isArray(item));
  }

  function actionInputIsPresent(item, fieldName) {
    const body = item.body;
    if ((body.input_sources || []).some((source) => source.field === fieldName)) return true;
    if (configuredValueIsPresent(body.form?.[fieldName])) return true;
    const field = (item.action.input_schema || []).find((candidate) => candidate.name === fieldName);
    if (!field) return false;
    const workspace = state.workspace || {};
    const configurations = [
      workspace.shared_paths,
      ...scopedActionConfigurations(workspace.event_preset, item.module.id, item.action.id),
      ...scopedActionConfigurations(workspace.advanced_config, item.module.id, item.action.id),
      ...scopedActionConfigurations(body.advanced_config, item.module.id, item.action.id),
    ];
    return configurations.some((source) => fieldIsConfigured(source, field));
  }

  function batchArtifactCandidates(items, consumerIndex, fieldNames) {
    const consumer = items[consumerIndex];
    const actionAccepted = new Set(consumer.action.accepts_artifacts || []);
    const candidates = [];
    for (const fieldName of fieldNames) {
      const field = (consumer.action.input_schema || []).find((item) => item.name === fieldName);
      const fieldAccepted = new Set(field?.artifact_types || []);
      if (!field?.path || fieldAccepted.size === 0) continue;
      for (let producerIndex = 0; producerIndex < consumerIndex; producerIndex += 1) {
        for (const artifactType of new Set(items[producerIndex].action.produces_artifacts || [])) {
          if (!fieldAccepted.has(artifactType)) continue;
          if (!actionAccepted.has("*") && !actionAccepted.has(artifactType)) continue;
          candidates.push({producer_index: producerIndex, artifact_type: artifactType, field: fieldName});
        }
      }
    }
    return candidates;
  }

  function planSelectedArtifactTransfers(items) {
    for (let consumerIndex = 0; consumerIndex < items.length; consumerIndex += 1) {
      const item = items[consumerIndex];
      const requiredFields = new Set([
        ...(item.action.input_schema || []).filter((field) => field.required).map((field) => field.name),
        ...(item.action.run_required_fields || []),
      ]);
      for (const fieldName of requiredFields) {
        if (actionInputIsPresent(item, fieldName)) continue;
        const candidates = batchArtifactCandidates(items, consumerIndex, [fieldName]);
        if (candidates.length === 1) item.body.input_sources.push({type: "batch_artifact", ...candidates[0]});
      }

      const anyFields = item.action.run_required_any_fields || [];
      if (anyFields.length && !anyFields.some((fieldName) => actionInputIsPresent(item, fieldName))) {
        const candidates = batchArtifactCandidates(items, consumerIndex, anyFields);
        if (candidates.length === 1) item.body.input_sources.push({type: "batch_artifact", ...candidates[0]});
      }
    }
    return items;
  }

  function selectedPayloads() {
    const payloads = [];
    for (const key of state.selectedActions) {
      const [moduleId, actionId] = key.split("/");
      const module = moduleById(moduleId);
      const action = module?.actions.find((item) => item.id === actionId);
      const card = state.actionElements.get(key);
      if (module && action && card) {
        if (card.dataset.startPending === "true" || isActionRunActive(key)) throw new Error(`${action.title} is already queued or running.`);
        payloads.push({module, action, body: collectActionPayload(module, action, card)});
      }
    }
    const order = new Map(state.layout.module_order.map((id, index) => [id, index]));
    payloads.sort((a, b) => {
      const moduleDelta = (order.get(a.module.id) ?? 999) - (order.get(b.module.id) ?? 999);
      if (moduleDelta) return moduleDelta;
      const actionDelta = a.module.actions.indexOf(a.action) - b.module.actions.indexOf(b.action);
      return actionDelta || keyFor(a.module.id, a.action.id).localeCompare(keyFor(b.module.id, b.action.id));
    });
    return planSelectedArtifactTransfers(payloads);
  }

  function describeSelectedSource(input) {
    if (input.type === "batch_artifact") {
      return `${input.field} ← selected action ${input.producer_index + 1} (${input.artifact_type})`;
    }
    return `${input.field} ← run ${input.run_id}`;
  }

  function reviewSelected() {
    try {
      requireWorkspace();
      const items = selectedPayloads();
      const summary = byId("runSelectedSummary");
      summary.replaceChildren();
      for (const [index, item] of items.entries()) {
        const row = document.createElement("div");
        row.className = "run-summary-item";
        const source = item.body.input_sources.length
          ? item.body.input_sources.map(describeSelectedSource).join("; ")
          : "Form paths / workspace configuration (no selected-action transfer)";
        const dependency = index === 0 ? "First confirmed action" : `After confirmed action ${index}`;
        row.innerHTML = `<strong>${index + 1}. ${escapeHtml(item.module.title)} / ${escapeHtml(item.action.title)}</strong><code>Input: ${escapeHtml(source)}\nOrder: ${escapeHtml(dependency)}\nOutput: ${escapeHtml(state.workspace.output_root)}/radio_workbench/${escapeHtml(state.workspace.id)}/runs/&lt;run-id&gt;/artifacts</code>`;
        summary.append(row);
      }
      byId("runSelectedDialog").showModal();
    } catch (error) {
      showNotice(error.message);
    }
  }

  async function confirmSelected(event) {
    event.preventDefault();
    try {
      const items = selectedPayloads();
      const payload = await requestJson(`${API}/workspaces/${state.workspace.id}/runs/batch`, {
        method: "POST",
        body: {confirmed: true, actions: items.map((item) => item.body)},
      });
      byId("runSelectedDialog").close();
      registerRuns(payload.runs || []);
      showNotice(`${(payload.runs || []).length} explicitly selected actions were queued in the confirmed order.`, "success");
    } catch (error) {
      showNotice(`Batch was not started: ${error.message}`);
    }
  }

  function applyPreset() {
    const id = byId("presetSelect").value;
    const preset = state.presets.find((item) => item.id === id);
    if (!preset) return showNotice("Choose a preset first.");
    const required = state.modules.filter((item) => item.always_available).map((item) => item.id);
    state.layout.enabled_modules = Array.from(new Set([...preset.module_ids, ...required]));
    state.layout.module_order = [...preset.module_ids, ...state.layout.module_order.filter((item) => !preset.module_ids.includes(item))];
    state.layout.collapsed_modules = state.modules.filter((item) => !state.layout.enabled_modules.includes(item.id)).map((item) => item.id);
    scheduleLayoutSave();
    renderAll();
    showNotice(`${preset.title} changed the module layout only. No action was started.`, "success");
  }

  function resetLayout() {
    state.layout = normalizeLayout(defaultLayout());
    state.selectedActions.clear();
    scheduleLayoutSave();
    renderAll();
    showNotice("The default layout was restored. No action was started.", "success");
  }

  function openWorkspaceDialog() {
    const workspace = state.workspace;
    state.workspaceDraftNew = false;
    byId("workspaceNameInput").value = workspace?.name || "Radio Analysis";
    byId("workspaceOutputInput").value = workspace?.output_root || "";
    byId("workspaceOutputInput").disabled = Boolean(workspace);
    byId("workspaceEventInput").value = workspace?.event_preset?.id || "";
    byId("workspaceConcurrencyInput").value = String(workspace?.concurrency || 1);
    byId("workspacePathsInput").value = JSON.stringify(workspace?.shared_paths || {}, null, 2);
    byId("workspaceAdvancedInput").value = JSON.stringify(workspace?.advanced_config || {}, null, 2);
    byId("workspaceDialog").showModal();
  }

  function openNewWorkspaceDialog() {
    state.workspaceDraftNew = true;
    byId("workspaceNameInput").value = "Radio Analysis";
    byId("workspaceOutputInput").value = "";
    byId("workspaceOutputInput").disabled = false;
    byId("workspaceEventInput").value = "";
    byId("workspaceConcurrencyInput").value = "1";
    byId("workspacePathsInput").value = "{}";
    byId("workspaceAdvancedInput").value = "{}";
    byId("workspaceDialog").showModal();
  }

  async function saveWorkspace(event) {
    event.preventDefault();
    try {
      const advanced = JSON.parse(byId("workspaceAdvancedInput").value || "{}");
      if (!advanced || Array.isArray(advanced) || typeof advanced !== "object") throw new Error("Advanced workspace configuration must be a JSON object.");
      const sharedPaths = JSON.parse(byId("workspacePathsInput").value || "{}");
      if (!sharedPaths || Array.isArray(sharedPaths) || typeof sharedPaths !== "object") throw new Error("Shared paths must be a JSON object.");
      const body = {
        name: byId("workspaceNameInput").value,
        output_root: byId("workspaceOutputInput").value,
        event_preset: byId("workspaceEventInput").value ? {id: byId("workspaceEventInput").value, title: byId("workspaceEventInput").selectedOptions[0]?.textContent} : {},
        shared_paths: sharedPaths,
        advanced_config: advanced,
        concurrency: Number(byId("workspaceConcurrencyInput").value),
      };
      const creatingWorkspace = !state.workspace || state.workspaceDraftNew;
      let payload;
      if (!creatingWorkspace) {
        delete body.output_root;
        payload = await requestJson(`${API}/workspaces/${state.workspace.id}`, {method: "PATCH", body});
      } else {
        payload = await requestJson(`${API}/workspaces`, {method: "POST", body});
        const initialLayout = normalizeLayout(defaultLayout());
        payload = await requestJson(`${API}/workspaces/${payload.workspace.id}/layout`, {
          method: "PATCH",
          body: initialLayout,
        });
      }
      state.workspace = payload.workspace;
      state.layout = normalizeLayout(state.workspace);
      if (creatingWorkspace) {
        state.selectedActions.clear();
        state.activeRuns.clear();
        if (state.pollTimer) window.clearInterval(state.pollTimer);
        state.pollTimer = null;
      }
      state.workspaceDraftNew = false;
      const workspaceIndex = state.workspaces.findIndex((item) => item.id === state.workspace.id);
      if (workspaceIndex >= 0) state.workspaces[workspaceIndex] = state.workspace;
      else state.workspaces.push(state.workspace);
      populateWorkspaceChoices();
      localStorage.setItem("solar-radio-workspace-id", state.workspace.id);
      byId("workspaceDialog").close();
      renderAll();
      showNotice("Workspace saved. No action was started.", "success");
    } catch (error) {
      showNotice(`Workspace was not saved: ${error.message}`);
    }
  }

  async function loadAllowedRoots() {
    const payload = await requestJson(`${API}/allowed-roots`);
    state.userRoots = Array.isArray(payload.user_roots) ? payload.user_roots.map(String) : [];
    state.startupRoots = Array.isArray(payload.startup_roots) ? payload.startup_roots.map(String) : [];
    state.protectedRoots = Array.isArray(payload.protected_roots) ? payload.protected_roots.map(String) : [];
    state.effectiveRoots = Array.isArray(payload.effective_roots) ? payload.effective_roots.map(String) : [];
    renderAllowedRootsSummary();
    return state.userRoots;
  }

  function parseAllowedRoots(value) {
    const seen = new Set();
    const roots = [];
    for (const line of String(value || "").split(/\r?\n/)) {
      const path = line.trim();
      const key = path.toLocaleLowerCase();
      if (path && !seen.has(key)) {
        seen.add(key);
        roots.push(path);
      }
    }
    return roots;
  }

  function isAbsoluteLocalPath(path) {
    return /^(?:[A-Za-z]:[\\/]|\\\\[^\\/]+[\\/][^\\/]+|\/)/.test(path);
  }

  function openAllowedRootsDialog(suggestedPath = "", resumePath = "") {
    const roots = [...state.userRoots];
    if (suggestedPath && !roots.some((path) => path.toLocaleLowerCase() === suggestedPath.toLocaleLowerCase())) {
      roots.push(suggestedPath);
    }
    state.rootsResumePath = resumePath;
    byId("allowedRootsInput").value = roots.join("\n");
    byId("allowedRootsError").hidden = true;
    byId("allowedRootsError").textContent = "";
    byId("allowedRootsDialog").showModal();
  }

  async function applyAllowedRoots(event) {
    event.preventDefault();
    const errorRoot = byId("allowedRootsError");
    const applyButton = byId("applyAllowedRootsButton");
    const roots = parseAllowedRoots(byId("allowedRootsInput").value);
    errorRoot.hidden = true;
    if (!roots.length) {
      errorRoot.textContent = "Add at least one editable absolute directory.";
      errorRoot.hidden = false;
      return;
    }
    const invalid = roots.filter((path) => !isAbsoluteLocalPath(path));
    if (invalid.length) {
      errorRoot.textContent = `Every root must be an absolute directory: ${invalid.join(", ")}`;
      errorRoot.hidden = false;
      return;
    }
    if (!state.radioRootToken) {
      errorRoot.textContent = "This server did not provide permission to change file access roots.";
      errorRoot.hidden = false;
      return;
    }
    applyButton.disabled = true;
    try {
      await requestJson(`${API}/allowed-roots`, {
        method: "PUT",
        headers: {"X-Radio-Root-Token": state.radioRootToken},
        body: {roots},
      });
      await loadAllowedRoots();
      const resumePath = state.rootsResumePath;
      byId("allowedRootsDialog").close();
      showNotice("File access roots updated for this server session. No action was started.", "success");
      if (resumePath) await browsePath(resumePath);
    } catch (error) {
      errorRoot.textContent = `File access roots were not updated: ${error.message}`;
      errorRoot.hidden = false;
    } finally {
      applyButton.disabled = false;
    }
  }

  async function openFileBrowser(target, kind = "file") {
    state.browser.target = target || null;
    state.browser.kind = kind;
    state.browser.selected = target?.value || "";
    const dialog = byId("fileBrowserDialog");
    dialog.showModal();
    await browsePath(target?.value || "");
  }

  async function browsePath(path) {
    const entriesRoot = byId("browserEntries");
    const accessHelp = byId("browserAccessHelp");
    accessHelp.hidden = true;
    entriesRoot.textContent = "Loading allowed paths…";
    try {
      const query = path ? `?path=${encodeURIComponent(path)}` : "";
      const payload = await requestJson(`${API}/files${query}`);
      state.browser.current = payload.path || "";
      state.browser.rejectedPath = "";
      byId("browserPathInput").value = state.browser.current;
      const roots = byId("browserRoots");
      roots.replaceChildren();
      for (const rootPath of payload.roots || []) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "secondary";
        button.textContent = rootPath;
        button.addEventListener("click", () => browsePath(rootPath));
        roots.append(button);
      }
      entriesRoot.replaceChildren();
      for (const entry of payload.entries || []) entriesRoot.append(renderBrowserEntry(entry));
      if (!entriesRoot.childElementCount) entriesRoot.textContent = "This folder has no visible entries.";
    } catch (error) {
      entriesRoot.textContent = error.message;
      if (/outside (?:the )?allowed roots|not (?:inside|within) allowed roots/i.test(error.message)) {
        state.browser.rejectedPath = String(path || byId("browserPathInput").value || "").trim();
        byId("browserAccessMessage").textContent = "This location is not in the current file access roots.";
        accessHelp.hidden = false;
      }
    }
  }

  function renderBrowserEntry(entry) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "browser-entry";
    button.innerHTML = `<span>${entry.is_dir ? "Folder" : "File"}</span><span>${escapeHtml(entry.name)}</span><small>${entry.is_file ? formatBytes(entry.size) : ""}</small>`;
    button.addEventListener("click", () => {
      if (entry.is_dir && state.browser.kind === "directory") selectBrowserPath(entry.path, button);
      else if (entry.is_file && state.browser.kind === "file") selectBrowserPath(entry.path, button);
    });
    button.addEventListener("dblclick", () => { if (entry.is_dir) browsePath(entry.path); });
    return button;
  }

  function selectBrowserPath(path, button) {
    state.browser.selected = path;
    $$(".browser-entry", byId("browserEntries")).forEach((item) => { item.dataset.selected = String(item === button); });
    byId("browserSelection").textContent = path;
    byId("chooseBrowserPathButton").disabled = false;
  }

  function chooseBrowserPath(event) {
    event.preventDefault();
    if (state.browser.target && state.browser.selected) {
      state.browser.target.value = state.browser.selected;
      state.browser.target.dispatchEvent(new Event("change", {bubbles: true}));
    }
    byId("fileBrowserDialog").close();
  }

  async function openResultsDrawer() {
    byId("resultsDrawer").dataset.open = "true";
    byId("resultsDrawer").ariaHidden = "false";
    byId("drawerScrim").hidden = false;
    if (!state.workspace) {
      byId("runList").textContent = "Configure a workspace to view persisted runs.";
      return;
    }
    await loadRuns();
  }

  function closeResultsDrawer() {
    byId("resultsDrawer").dataset.open = "false";
    byId("resultsDrawer").ariaHidden = "true";
    byId("drawerScrim").hidden = true;
  }

  async function loadRuns() {
    const root = byId("runList");
    root.textContent = "Loading runs…";
    try {
      const payload = await requestJson(`${API}/workspaces/${state.workspace.id}/runs`);
      state.runs = payload.runs || [];
      renderRuns();
    } catch (error) {
      root.textContent = error.message;
    }
  }

  function renderRuns() {
    const root = byId("runList");
    root.replaceChildren();
    const filter = byId("resultStatusFilter").value;
    const runs = state.runs.filter((item) => !filter || item.status === filter);
    for (const run of runs) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "run-list-item";
      button.innerHTML = `<span><strong>${escapeHtml(run.module_id)} / ${escapeHtml(run.action_id)}</strong><small>${escapeHtml(run.id)}</small></span><span class="action-status" data-state="${escapeHtml(run.status)}">${escapeHtml(titleCase(run.status))}</span>`;
      button.addEventListener("click", () => showRunDetail(run.id));
      root.append(button);
    }
    if (!runs.length) root.textContent = "No runs match this filter.";
  }

  async function showRunDetail(runId) {
    const root = byId("runDetail");
    root.classList.remove("empty-state");
    root.textContent = "Loading run details…";
    try {
      const [runPayload, logPayload, artifactsPayload] = await Promise.all([
        requestJson(`${API}/workspaces/${state.workspace.id}/runs/${runId}`),
        requestJson(`${API}/workspaces/${state.workspace.id}/runs/${runId}/log?offset=0`),
        requestJson(`${API}/workspaces/${state.workspace.id}/runs/${runId}/artifacts`),
      ]);
      const run = runPayload.run;
      root.replaceChildren();
      const heading = document.createElement("h3");
      heading.textContent = `${run.module_id} / ${run.action_id}`;
      const meta = document.createElement("p");
      const progress = Number.isFinite(Number(run.progress)) ? ` · Progress: ${Math.round(Number(run.progress) * 100)}%` : "";
      meta.textContent = `Status: ${run.status}${progress} · Run ID: ${run.id}`;
      const provenance = document.createElement("details");
      provenance.innerHTML = "<summary>Provenance and resolved configuration</summary>";
      const provenanceText = document.createElement("pre");
      provenanceText.textContent = JSON.stringify({input_sources: run.input_sources, provenance: run.provenance, resolved_config: run.resolved_config}, null, 2);
      provenance.append(provenanceText);
      const log = document.createElement("pre");
      log.className = "action-log";
      log.hidden = false;
      log.textContent = (logPayload.lines || []).join("\n") || "No log output.";
      const artifacts = document.createElement("div");
      artifacts.className = "artifact-list";
      for (const artifact of artifactsPayload.artifacts || []) artifacts.append(renderArtifact(run, artifact));
      if (!artifacts.childElementCount) artifacts.textContent = "No artifacts indexed yet.";
      root.append(heading, meta, provenance, log, artifacts);
    } catch (error) {
      root.textContent = error.message;
    }
  }

  function renderArtifact(run, artifact) {
    const row = document.createElement("div");
    row.className = "artifact-item";
    const text = document.createElement("span");
    text.innerHTML = `<strong>${escapeHtml(artifact.relative_path)}</strong><small>${escapeHtml(artifact.kind)} · ${formatBytes(artifact.size)}</small>`;
    const url = `${API}/workspaces/${state.workspace.id}/runs/${run.id}/artifacts/${artifact.id}`;
    const actions = document.createElement("span");
    actions.className = "artifact-actions";
    if (artifact.previewable) {
      const preview = document.createElement("button");
      preview.type = "button";
      preview.className = "artifact-link secondary";
      preview.textContent = "Preview";
      preview.addEventListener("click", () => toggleArtifactPreview(row, artifact, url));
      actions.append(preview);
    }
    const download = document.createElement("a");
    download.href = `${url}?download=1`;
    download.textContent = "Download";
    download.className = "artifact-link";
    download.setAttribute("download", artifact.relative_path.split("/").pop() || "artifact");
    actions.append(download);
    row.append(text, actions);
    return row;
  }

  async function toggleArtifactPreview(row, artifact, url) {
    const existing = $("[data-role='artifact-preview']", row);
    if (existing) {
      existing.remove();
      return;
    }
    if (artifact.kind === "html") {
      window.open(url, "_blank", "noopener,noreferrer");
      return;
    }
    const panel = document.createElement("div");
    panel.className = "artifact-preview";
    panel.dataset.role = "artifact-preview";
    panel.textContent = "Loading preview...";
    row.append(panel);
    try {
      if (artifact.kind === "image") {
        const image = document.createElement("img");
        image.src = url;
        image.alt = artifact.relative_path;
        panel.replaceChildren(image);
      } else if (artifact.kind === "video") {
        const video = document.createElement("video");
        video.src = url;
        video.controls = true;
        video.preload = "metadata";
        panel.replaceChildren(video);
      } else if (["json", "table"].includes(artifact.kind) && !/\.(xlsx?|xls)$/i.test(artifact.relative_path)) {
        const response = await fetch(url, {headers: {Accept: "text/plain,application/json"}});
        if (!response.ok) throw new Error(`Preview request failed (${response.status}).`);
        const body = await response.text();
        const pre = document.createElement("pre");
        pre.textContent = body.length > 200000 ? `${body.slice(0, 200000)}\n\nPreview truncated at 200 KB.` : body;
        panel.replaceChildren(pre);
      } else {
        panel.textContent = "This format opens in a separate preview tab.";
        window.open(url, "_blank", "noopener,noreferrer");
      }
    } catch (error) {
      panel.textContent = error.message;
    }
  }

  function renderAll() {
    const enabled = new Set(state.layout.enabled_modules);
    state.selectedActions = new Set(
      [...state.selectedActions].filter((key) => enabled.has(key.split("/")[0]))
    );
    updateWorkspaceSummary();
    renderSidebar();
    renderWorkspace();
    updateSelectedCount();
  }

  function populatePresets() {
    const select = byId("presetSelect");
    for (const preset of state.presets) select.add(new Option(preset.title, preset.id));
  }

  function populateEventPresets(payload) {
    const select = byId("workspaceEventInput");
    select.replaceChildren(new Option("Package defaults", ""));
    for (const preset of payload.event_presets || []) select.add(new Option(preset.title || preset.id, preset.id));
  }

  function populateWorkspaceChoices() {
    const select = byId("workspaceSelect");
    const label = state.workspaces.length ? "Choose a workspace" : "No saved workspace";
    select.replaceChildren(new Option(label, ""));
    for (const workspace of state.workspaces) {
      select.add(new Option(workspace.name || workspace.id, workspace.id));
    }
    select.value = state.workspace?.id || "";
  }

  async function switchWorkspace(workspaceId) {
    if (!workspaceId || workspaceId === state.workspace?.id) return;
    const detail = await requestJson(`${API}/workspaces/${workspaceId}`);
    state.workspace = detail.workspace;
    state.layout = normalizeLayout(state.workspace);
    state.selectedActions.clear();
    state.activeRuns.clear();
    if (state.pollTimer) window.clearInterval(state.pollTimer);
    state.pollTimer = null;
    localStorage.setItem("solar-radio-workspace-id", workspaceId);
    populateWorkspaceChoices();
    renderAll();
    showNotice(`Opened workspace: ${state.workspace.name}. No action was started.`, "success");
  }

  async function loadExistingWorkspace() {
    const payload = await requestJson(`${API}/workspaces`);
    const workspaces = payload.workspaces || [];
    state.workspaces = workspaces;
    const remembered = localStorage.getItem("solar-radio-workspace-id");
    state.workspace = workspaces.find((item) => item.id === remembered) || workspaces[0] || null;
    if (state.workspace && !state.workspace.module_order) {
      const detail = await requestJson(`${API}/workspaces/${state.workspace.id}`);
      state.workspace = detail.workspace;
    }
    populateWorkspaceChoices();
  }

  function wireEvents() {
    byId("applyPresetButton").addEventListener("click", applyPreset);
    byId("resetLayoutButton").addEventListener("click", resetLayout);
    byId("workspaceButton").addEventListener("click", openWorkspaceDialog);
    byId("newWorkspaceButton").addEventListener("click", openNewWorkspaceDialog);
    byId("workspaceSelect").addEventListener("change", (event) => {
      switchWorkspace(event.target.value).catch((error) => showNotice(error.message));
    });
    byId("workspaceForm").addEventListener("submit", (event) => {
      if (event.submitter?.id === "saveWorkspaceButton") saveWorkspace(event);
    });
    byId("runSelectedButton").addEventListener("click", reviewSelected);
    byId("confirmRunSelectedButton").addEventListener("click", confirmSelected);
    byId("openResultsButton").addEventListener("click", openResultsDrawer);
    byId("closeResultsButton").addEventListener("click", closeResultsDrawer);
    byId("drawerScrim").addEventListener("click", closeResultsDrawer);
    byId("refreshRunsButton").addEventListener("click", loadRuns);
    byId("resultStatusFilter").addEventListener("change", renderRuns);
    byId("manageAllowedRootsButton").addEventListener("click", () => openAllowedRootsDialog());
    byId("browserManageRootsButton").addEventListener("click", () => {
      const requested = state.browser.rejectedPath || byId("browserPathInput").value.trim();
      openAllowedRootsDialog(requested, requested);
    });
    byId("allowedRootsForm").addEventListener("submit", (event) => {
      if (event.submitter?.id === "applyAllowedRootsButton") applyAllowedRoots(event);
    });
    byId("allowedRootsDialog").addEventListener("close", () => { state.rootsResumePath = ""; });
    $$(".browse-button").forEach((button) => button.addEventListener("click", () => openFileBrowser(byId(button.dataset.target), button.dataset.kind)));
    byId("browserGoButton").addEventListener("click", () => browsePath(byId("browserPathInput").value));
    byId("browserParentButton").addEventListener("click", () => {
      const path = state.browser.current.replace(/[\\/]+$/, "");
      const parent = path.replace(/[\\/][^\\/]+$/, "");
      browsePath(parent || path);
    });
    byId("chooseBrowserPathButton").addEventListener("click", chooseBrowserPath);
    window.addEventListener("pagehide", notifyClientClose);
    window.addEventListener("beforeunload", notifyClientClose);
  }

  async function initClientLifecycle() {
    try {
      const config = await requestJson("/api/client-config");
      state.stopOnClose = Boolean(config.stop_on_close);
      state.radioRootToken = String(config.radio_root_token || "");
      const interval = Math.max(Number(config.heartbeat_interval_ms || 5000), 1000);
      state.heartbeatTimer = window.setInterval(sendHeartbeat, interval);
      await sendHeartbeat();
    } catch {
      state.heartbeatTimer = null;
    }
  }

  async function sendHeartbeat() {
    try {
      await requestJson("/api/client-heartbeat", {
        method: "POST",
        body: {client_id: state.clientId},
      });
    } catch {
      return;
    }
  }

  function notifyClientClose() {
    const payload = JSON.stringify({client_id: state.clientId, stop_on_close: state.stopOnClose});
    if (navigator.sendBeacon) {
      navigator.sendBeacon("/api/client-close", new Blob([payload], {type: "application/json"}));
      return;
    }
    fetch("/api/client-close", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: payload,
      keepalive: true,
    });
  }

  async function boot() {
    wireEvents();
    const lifecycleReady = initClientLifecycle();
    try {
      const [health, catalog, presets] = await Promise.all([
        requestJson("/api/health"),
        requestJson(`${API}/modules`),
        requestJson(`${API}/presets`),
      ]);
      setHealth(Boolean(health.ok), "Ready");
      state.modules = catalog.modules || [];
      state.presets = presets.presets || [];
      await lifecycleReady;
      try {
        await loadAllowedRoots();
      } catch (error) {
        byId("allowedRootsSummary").textContent = "File access roots are unavailable.";
        showNotice(`File access roots could not be loaded: ${error.message}`);
      }
      populatePresets();
      populateEventPresets(presets);
      try {
        await loadExistingWorkspace();
      } catch (error) {
        showNotice(`Saved workspaces could not be opened: ${error.message}`);
      }
      let localLayout = null;
      try { localLayout = JSON.parse(localStorage.getItem("solar-radio-layout") || "null"); } catch { localLayout = null; }
      state.layout = normalizeLayout(state.workspace || localLayout || defaultLayout());
      renderAll();
    } catch (error) {
      setHealth(false, "Unavailable");
      byId("enabledModules").innerHTML = `<section class="empty-workspace"><h2>Radio Workspace unavailable</h2><p>${escapeHtml(error.message)}</p></section>`;
    }
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>'"]/g, (char) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"}[char]));
  }

  function titleCase(value) {
    return String(value || "").replace(/[-_]/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
  }

  function formatBytes(value) {
    const size = Number(value) || 0;
    if (size < 1024) return `${size} B`;
    if (size < 1024 ** 2) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / 1024 ** 2).toFixed(1)} MB`;
  }

  boot();
})();
