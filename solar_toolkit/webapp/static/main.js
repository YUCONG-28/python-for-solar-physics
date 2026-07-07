const state = {
  modules: [],
  archived: [],
  selectedModule: null,
  activeJobId: null,
  pollTimer: null,
  clientId: `webapp-${Date.now()}-${Math.random().toString(16).slice(2)}`,
  stopOnClose: true,
};

const els = {
  healthStatus: document.getElementById("healthStatus"),
  moduleSearch: document.getElementById("moduleSearch"),
  categoryNav: document.getElementById("categoryNav"),
  categoryTitle: document.getElementById("categoryTitle"),
  categorySummary: document.getElementById("categorySummary"),
  refreshModulesBtn: document.getElementById("refreshModulesBtn"),
  moduleGrid: document.getElementById("moduleGrid"),
  legacyList: document.getElementById("legacyList"),
  moduleDetail: document.getElementById("moduleDetail"),
  jobForm: document.getElementById("jobForm"),
  argumentsInput: document.getElementById("argumentsInput"),
  pathsInput: document.getElementById("pathsInput"),
  runJobBtn: document.getElementById("runJobBtn"),
  cancelJobBtn: document.getElementById("cancelJobBtn"),
  jobStatus: document.getElementById("jobStatus"),
  jobLog: document.getElementById("jobLog"),
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error || `Request failed: ${response.status}`);
  }
  return payload;
}

async function loadHealth() {
  try {
    await fetchJson("/api/health");
    els.healthStatus.textContent = "Ready";
    els.healthStatus.dataset.state = "ready";
  } catch (error) {
    els.healthStatus.textContent = "Offline";
    els.healthStatus.dataset.state = "error";
  }
}

async function loadModules() {
  const payload = await fetchJson("/api/modules");
  state.modules = payload.modules || [];
  state.archived = payload.archived_references || [];
  renderCategories();
  renderModules();
  renderLegacyReferences();
}

function visibleModules() {
  const query = els.moduleSearch.value.trim().toLowerCase();
  if (!query) return state.modules;
  return state.modules.filter((item) =>
    [item.title, item.category, item.description, item.script_path]
      .join(" ")
      .toLowerCase()
      .includes(query)
  );
}

function renderCategories() {
  const categories = [...new Set(state.modules.map((item) => item.category))];
  els.categoryNav.innerHTML = categories
    .map((category) => {
      const count = state.modules.filter((item) => item.category === category).length;
      return `<button type="button" data-category="${escapeHtml(category)}">
        <span>${escapeHtml(category)}</span><strong>${count}</strong>
      </button>`;
    })
    .join("");
  els.categoryNav.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      els.moduleSearch.value = button.dataset.category || "";
      renderModules();
    });
  });
}

function renderModules() {
  const modules = visibleModules();
  els.categoryTitle.textContent = els.moduleSearch.value.trim() || "Workflow Library";
  els.categorySummary.textContent = `${modules.length} workflow modules available`;
  els.moduleGrid.innerHTML = modules
    .map((item) => {
      const active = state.selectedModule && state.selectedModule.id === item.id;
      return `<button type="button" class="module-card ${active ? "active" : ""}" data-id="${escapeHtml(item.id)}">
        <span class="module-meta">${escapeHtml(item.category)} / ${escapeHtml(item.status)}</span>
        <strong>${escapeHtml(item.title)}</strong>
        <span>${escapeHtml(item.description)}</span>
        <span class="risk ${escapeHtml(item.risk_level)}">${escapeHtml(item.risk_level)}</span>
      </button>`;
    })
    .join("");
  els.moduleGrid.querySelectorAll(".module-card").forEach((card) => {
    card.addEventListener("click", () => selectModule(card.dataset.id));
  });
}

function renderLegacyReferences() {
  if (!state.archived.length) {
    els.legacyList.innerHTML = "<p>No archived references are registered.</p>";
    return;
  }
  els.legacyList.innerHTML = state.archived
    .map((item) => `<div class="legacy-item">
      <strong>${escapeHtml(item.title)}</strong>
      <code>${escapeHtml(item.path)}</code>
      <span>${escapeHtml(item.description)}</span>
    </div>`)
    .join("");
}

async function selectModule(moduleId) {
  const payload = await fetchJson(`/api/modules/${moduleId}`);
  state.selectedModule = payload.module;
  renderModules();
  els.moduleDetail.classList.remove("empty-state");
  els.moduleDetail.innerHTML = `<h2>${escapeHtml(payload.module.title)}</h2>
    <p>${escapeHtml(payload.module.description)}</p>
    <dl>
      <dt>Category</dt><dd>${escapeHtml(payload.module.category)}</dd>
      <dt>Script</dt><dd><code>${escapeHtml(payload.module.script_path)}</code></dd>
      <dt>Command</dt><dd><code>${escapeHtml(payload.module.command_path)}</code></dd>
      <dt>Risk</dt><dd>${escapeHtml(payload.module.risk_level)}</dd>
    </dl>`;
  els.jobForm.hidden = false;
  els.argumentsInput.value = "--help";
  els.pathsInput.value = "";
}

function setJobStatus(text, stateName = "idle") {
  els.jobStatus.textContent = text;
  els.jobStatus.dataset.state = stateName;
}

function appendLog(text) {
  els.jobLog.textContent = text;
  els.jobLog.scrollTop = els.jobLog.scrollHeight;
}

function buildJobPayload() {
  return {
    arguments: els.argumentsInput.value,
    paths: els.pathsInput.value
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean),
  };
}

async function runSelectedJob(event) {
  event.preventDefault();
  if (!state.selectedModule) return;
  setJobStatus("Starting", "running");
  appendLog("");
  els.runJobBtn.disabled = true;
  els.cancelJobBtn.disabled = false;
  try {
    const response = await fetchJson("/api/jobs", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        module_id: state.selectedModule.id,
        payload: buildJobPayload(),
      }),
    });
    state.activeJobId = response.job.id;
    pollJob();
  } catch (error) {
    setJobStatus("Failed", "failed");
    appendLog(error.message);
    els.runJobBtn.disabled = false;
    els.cancelJobBtn.disabled = true;
  }
}

async function pollJob() {
  if (!state.activeJobId) return;
  try {
    const response = await fetchJson(`/api/jobs/${state.activeJobId}`);
    const job = response.job;
    setJobStatus(job.status, job.status);
    appendLog((job.logs || []).join("\n"));
    if (["queued", "running"].includes(job.status)) {
      state.pollTimer = window.setTimeout(pollJob, 800);
    } else {
      els.runJobBtn.disabled = false;
      els.cancelJobBtn.disabled = true;
    }
  } catch (error) {
    setJobStatus("Failed", "failed");
    appendLog(error.message);
    els.runJobBtn.disabled = false;
    els.cancelJobBtn.disabled = true;
  }
}

async function cancelJob() {
  if (!state.activeJobId) return;
  await fetchJson(`/api/jobs/${state.activeJobId}/cancel`, {method: "POST"});
  setJobStatus("canceled", "canceled");
  els.cancelJobBtn.disabled = true;
}

async function initClientLifecycle() {
  try {
    const config = await fetchJson("/api/client-config");
    state.stopOnClose = !!config.stop_on_close;
    const interval = Math.max(Number(config.heartbeat_interval_ms || 5000), 1000);
    window.setInterval(sendHeartbeat, interval);
    sendHeartbeat();
  } catch (error) {
    return;
  }
}

async function sendHeartbeat() {
  try {
    await fetchJson("/api/client-heartbeat", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({client_id: state.clientId}),
    });
  } catch (error) {
    return;
  }
}

function notifyClientClose() {
  const payload = JSON.stringify({
    client_id: state.clientId,
    stop_on_close: state.stopOnClose,
  });
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

function installHandlers() {
  els.refreshModulesBtn.addEventListener("click", loadModules);
  els.moduleSearch.addEventListener("input", renderModules);
  els.jobForm.addEventListener("submit", runSelectedJob);
  els.cancelJobBtn.addEventListener("click", cancelJob);
  window.addEventListener("pagehide", notifyClientClose);
  window.addEventListener("beforeunload", notifyClientClose);
}

installHandlers();
loadHealth();
loadModules().catch((error) => {
  els.moduleGrid.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
});
initClientLifecycle();
