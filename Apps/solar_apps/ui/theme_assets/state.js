(function () {
  "use strict";

  const controllers = new Map();
  const MAX_LEGACY_BYTES = 32768;
  const EXCLUDED_FIELD = /(?:^|[._:-])(result|results|task|job|cache|artifact|run[_-]id|roi[_-]json[_-]payload|drift[_-]lines[_-]json)(?:$|[._:-])/i;

  function eligible(element) {
    if (!element || element.disabled || element.dataset.noPersist != null) return false;
    const type = String(element.type || "").toLowerCase();
    return !["button", "submit", "reset", "file", "password", "hidden"].includes(type);
  }

  function fieldKey(element) {
    const localKey = element.dataset.stateKey || element.id || element.name || "";
    const scope = document.documentElement.dataset.interfaceId || document.documentElement.dataset.frontendId || "frontend";
    return localKey ? `${scope}.${localKey}` : "";
  }

  function read(element) {
    if (element.type === "checkbox" || element.type === "radio") return Boolean(element.checked);
    if (element.multiple) return Array.from(element.selectedOptions).map((item) => item.value);
    return element.value;
  }

  function write(element, value) {
    if (element.type === "checkbox" || element.type === "radio") element.checked = Boolean(value);
    else if (element.multiple && Array.isArray(value)) {
      Array.from(element.options).forEach((option) => { option.selected = value.includes(option.value); });
    } else if (value != null) element.value = String(value);
  }

  function controls() {
    return Array.from(document.querySelectorAll("input[id], select[id], textarea[id], [data-state-key]"))
      .filter(eligible)
      .filter((element) => fieldKey(element) && !EXCLUDED_FIELD.test(fieldKey(element)));
  }

  function boundedPrimitive(value) {
    if (typeof value === "boolean" || typeof value === "number" || value == null) return value;
    if (typeof value === "string" && value.length <= MAX_LEGACY_BYTES) return value;
    if (Array.isArray(value) && value.length <= 128) {
      const items = value.map(String);
      return items.every((item) => item.length <= MAX_LEGACY_BYTES) ? items : undefined;
    }
    return undefined;
  }

  function readLegacyMappings(mappings) {
    const fields = {};
    for (const mapping of mappings || []) {
      if (!mapping || typeof mapping.key !== "string") continue;
      let raw = null;
      try { raw = localStorage.getItem(mapping.key); } catch { raw = null; }
      const limit = Math.min(Number(mapping.maxBytes) || MAX_LEGACY_BYTES, MAX_LEGACY_BYTES);
      if (raw == null || raw.length > limit) continue;
      if (mapping.field) {
        let value = raw;
        if (mapping.parseJson === true) {
          try { value = JSON.parse(raw); } catch { continue; }
        }
        const accepted = boundedPrimitive(value);
        if (accepted !== undefined) fields[String(mapping.field)] = accepted;
      }
      if (mapping.fields && typeof mapping.fields === "object") {
        let parsed;
        try { parsed = JSON.parse(raw); } catch { continue; }
        if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") continue;
        for (const [legacyName, currentName] of Object.entries(mapping.fields)) {
          const accepted = boundedPrimitive(parsed[legacyName]);
          if (accepted !== undefined) fields[String(currentName)] = accepted;
        }
      }
    }
    return fields;
  }

  async function request(endpoint, options) {
    const response = await fetch(endpoint, options);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) throw new Error(payload.error || `UI state request failed (${response.status})`);
    return payload;
  }

  function collectFields(extraFields) {
    const fields = {...(extraFields || {})};
    for (const element of controls()) fields[fieldKey(element)] = read(element);
    return fields;
  }

  async function init(frontendId, options) {
    const config = options || {};
    const endpoint = config.endpoint || "/api/ui-state";
    const legacyTheme = localStorage.getItem(`solarToolkit.${frontendId}.v1.theme`) ||
      (config.legacyThemeKeys || []).map((key) => localStorage.getItem(key)).find(Boolean) ||
      (document.querySelector("[data-theme-selector]") || {}).value || "";
    let remote = {theme: "auto", fields: {}};
    let found = false;
    try {
      const response = await request(endpoint);
      remote = response.state || remote;
      found = response.found === true;
    } catch (error) {
      console.warn("Persistent UI state is unavailable; continuing with in-memory state.", error);
    }

    const shouldImportLegacy = !found || remote.legacy_imported !== true;
    const legacyFields = shouldImportLegacy ? readLegacyMappings(config.legacyMappings) : {};
    const restoredFields = {...legacyFields, ...(remote.fields || {})};
    const selectedTheme = shouldImportLegacy
      ? (legacyTheme || remote.theme || "auto")
      : (remote.theme || "auto");
    if (window.SolarTheme) window.SolarTheme.apply(selectedTheme, frontendId, false);
    for (const element of controls()) {
      const key = fieldKey(element);
      if (Object.prototype.hasOwnProperty.call(restoredFields, key)) write(element, restoredFields[key]);
    }

    let timer = null;
    let extraFields = {...legacyFields};
    async function save(additionalFields) {
      if (additionalFields && typeof additionalFields === "object") {
        extraFields = {...extraFields, ...additionalFields};
      }
      const fields = collectFields(extraFields);
      const theme = document.documentElement.dataset.themeMode || "auto";
      try {
        const response = await request(endpoint, {
          method: "PATCH",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({theme, fields, legacy_imported: true}),
        });
        remote = response.state || {...remote, theme, fields, legacy_imported: true};
        return remote;
      } catch (error) {
        console.warn("Could not persist latest UI state.", error);
        return {...remote, theme, fields};
      }
    }
    function schedule() {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => save(), 300);
    }
    async function reset() {
      try { await request(endpoint, {method: "DELETE"}); } catch (error) { console.warn(error); }
      extraFields = {};
      if (window.SolarTheme) window.SolarTheme.resetUiState(frontendId, config.storagePrefixes);
    }

    const controller = {endpoint, frontendId, save, reset, state: {...remote, theme: selectedTheme, fields: restoredFields}};
    controllers.set(frontendId, controller);
    window.dispatchEvent(new CustomEvent("solar-ui-state-restored", {
      detail: {frontendId, state: controller.state, importedLegacy: shouldImportLegacy},
    }));

    controls().forEach((element) => {
      element.addEventListener("input", schedule);
      element.addEventListener("change", schedule);
    });
    window.addEventListener("solar-theme-change", schedule);
    window.addEventListener("solar-ui-state-save", (event) => {
      if (!event.detail?.frontendId || event.detail.frontendId === frontendId) save(event.detail?.fields || {});
    });
    document.querySelectorAll("form").forEach((form) => form.addEventListener("submit", () => save()));
    window.addEventListener("beforeunload", () => {
      const fields = collectFields(extraFields);
      fetch(endpoint, {
        method: "PATCH", headers: {"Content-Type": "application/json"}, keepalive: true,
        body: JSON.stringify({theme: document.documentElement.dataset.themeMode || "auto", fields, legacy_imported: true}),
      }).catch(() => {});
    });

    document.querySelectorAll("[data-reset-ui-state]").forEach((button) => {
      button.addEventListener("click", async (event) => {
        event.preventDefault();
        event.stopImmediatePropagation();
        if (config.confirmReset !== false && !window.confirm("Reset saved UI state for this application?")) return;
        await reset();
        window.location.reload();
      }, {capture: true});
    });
    if (shouldImportLegacy) controller.state = await save(legacyFields);
    return controller.state;
  }

  async function saveFields(frontendId, fields) {
    const controller = controllers.get(frontendId);
    if (!controller) return null;
    controller.state = await controller.save(fields || {});
    return controller.state;
  }

  function state(frontendId) {
    return controllers.get(frontendId)?.state || null;
  }

  window.SolarUiState = {init, saveFields, state};
})();
