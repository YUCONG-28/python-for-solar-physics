(function () {
  "use strict";

  const tokenPromises = new Map();

  async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.error || `Native dialog request failed (${response.status})`);
    }
    return payload;
  }

  async function tokenFor(endpoint) {
    if (!tokenPromises.has(endpoint)) {
      tokenPromises.set(endpoint, requestJson(endpoint).then((payload) => payload.token));
    }
    return tokenPromises.get(endpoint);
  }

  async function select(options = {}) {
    const endpoint = options.endpoint || "/api/native-path-dialog";
    const token = await tokenFor(endpoint);
    const payload = await requestJson(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Native-Dialog-Token": token,
      },
      body: JSON.stringify({
        mode: options.mode,
        title: options.title || "Select local path",
        initial_path: options.initialPath || "",
        extensions: options.extensions || [],
        default_suffix: options.defaultSuffix || "",
        memory_context: options.memoryContext || {
          frontend: document.documentElement.dataset.frontendId || "frontend",
          operation: options.operation || document.documentElement.dataset.interfaceId || "default",
          field: options.field || options.targetId || "path",
        },
      }),
    });
    return payload.status === "selected" ? (payload.paths || []) : [];
  }

  function pathKey(value) {
    return String(value || "").trim().replace(/\//g, "\\").replace(/\\+$/, "").toLocaleLowerCase();
  }

  function appendUniqueLines(existingText, additions) {
    const lines = String(existingText || "").split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
    const seen = new Set(lines.map(pathKey));
    for (const raw of additions || []) {
      const value = String(raw || "").trim();
      const key = pathKey(value);
      if (value && !seen.has(key)) {
        seen.add(key);
        lines.push(value);
      }
    }
    return lines.join("\n");
  }

  window.SolarNativePathDialog = {appendUniqueLines, select};
})();
