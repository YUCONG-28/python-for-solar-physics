(function () {
  "use strict";

  const MODES = new Set(["auto", "light", "dark"]);
  const query = window.matchMedia("(prefers-color-scheme: dark)");

  function normalize(value) {
    const candidate = String(value || "auto").toLowerCase();
    return MODES.has(candidate) ? candidate : "auto";
  }

  function key(frontendId) {
    return `solarToolkit.${frontendId || "frontend"}.v1.theme`;
  }

  function effective(mode) {
    return mode === "auto" ? (query.matches ? "dark" : "light") : mode;
  }

  function apply(mode, frontendId, _persist) {
    const selected = normalize(mode);
    const root = document.documentElement;
    root.dataset.themeMode = selected;
    root.dataset.theme = effective(selected);
    document.querySelectorAll("[data-theme-selector]").forEach((control) => {
      control.value = selected;
    });
    window.dispatchEvent(new CustomEvent("solar-theme-change", {
      detail: {mode: selected, effective: effective(selected)},
    }));
    return selected;
  }

  function resetUiState(frontendId, _prefixes) {
    // Legacy browser keys are intentionally retained as a read-only migration
    // source. Current state lives in the private Local/state backend.
    apply("auto", frontendId, false);
    window.dispatchEvent(new CustomEvent("solar-ui-state-reset", {detail: {frontendId}}));
  }

  function init(frontendId, options) {
    const config = options || {};
    document.documentElement.dataset.frontendId = frontendId;
    const legacyMode = (config.legacyThemeKeys || [])
      .map((legacyKey) => localStorage.getItem(legacyKey))
      .find(Boolean);
    const selected = normalize(localStorage.getItem(key(frontendId)) || legacyMode || config.defaultMode);
    apply(selected, frontendId, false);
    document.querySelectorAll("[data-theme-selector]").forEach((control) => {
      control.value = selected;
      control.addEventListener("change", () => apply(control.value, frontendId, true));
    });
    return selected;
  }

  query.addEventListener("change", () => {
    const root = document.documentElement;
    if (normalize(root.dataset.themeMode) === "auto") apply("auto", root.dataset.frontendId, false);
  });

  window.SolarTheme = {apply, effective, init, normalize, resetUiState};
})();
