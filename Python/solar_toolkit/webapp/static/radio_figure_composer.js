(function radioFigureComposerModule() {
  "use strict";

  const FIGURE_SCHEMA_VERSION = 1;
  const MAX_LAYERS = 32;
  const MAX_SIDE = 8192;
  const MAX_PIXELS = 40000000;
  const MAX_FRAMES = 10000;
  const MAX_IMAGE_BYTES = 25 * 1024 * 1024;
  const MAX_VIDEO_BYTES = 512 * 1024 * 1024;
  const MAX_IMAGE_CACHE_ITEMS = 64;

  const byId = (id) => document.getElementById(id);
  const clamp = (value, minimum, maximum) => Math.min(maximum, Math.max(minimum, value));
  const copy = (value) => JSON.parse(JSON.stringify(value));
  const uid = (prefix) => `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;

  function isoValue(value) {
    if (!value) return "";
    const raw = String(value).trim();
    // Every Figure Studio field is explicitly UTC. Native datetime-local
    // controls otherwise reinterpret an unzoned value in the browser's local
    // timezone and silently shift the scientific timeline.
    const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(raw) ? raw : `${raw}Z`;
    const date = new Date(normalized);
    return Number.isFinite(date.getTime()) ? date.toISOString() : "";
  }

  function localDateTimeValue(value) {
    const iso = isoValue(value);
    return iso ? iso.replace(/Z$/, "").slice(0, 23) : "";
  }

  function sourceKey(source) {
    if (!source) return "missing";
    if (source.type === "artifact") return `artifact:${source.run_id}:${source.artifact_id}`;
    if (source.type === "preview") return `preview:${source.preview_id}`;
    return JSON.stringify(source);
  }

  function controlledSource(source) {
    if (source?.type === "artifact" && source.run_id && source.artifact_id) {
      return {type: "artifact", run_id: String(source.run_id), artifact_id: String(source.artifact_id)};
    }
    if (source?.type === "preview" && source.preview_id) {
      const result = {type: "preview", preview_id: String(source.preview_id)};
      if (source.fingerprint) result.fingerprint = String(source.fingerprint);
      return result;
    }
    throw new Error("Figure sources must use a registered preview or workspace artifact.");
  }

  function defaultDraft(workspaceId) {
    const now = new Date().toISOString();
    return {
      figure_schema_version: FIGURE_SCHEMA_VERSION,
      workspace_id: workspaceId || "",
      mode: "mosaic",
      canvas: {width: 1600, height: 1200, background: "#ffffff", export_scale: 1},
      timeline: {
        mode: "still",
        selected_time_iso: now,
        start_time_iso: "",
        end_time_iso: "",
        sample_interval_s: 1,
        playback_fps: 10,
        format: "mp4",
      },
      layers: [],
      metadata: {single_layer_id: "", timeline_user_set: false, canvas_user_set: false, single_aspect_applied_to: ""},
    };
  }

  function normalizeDraft(value, workspaceId) {
    const base = defaultDraft(workspaceId);
    const source = value && typeof value === "object" ? value : {};
    const canvas = source.canvas || {};
    const timeline = source.timeline || {};
    base.mode = source.mode === "single" ? "single" : "mosaic";
    base.canvas.width = clamp(Math.round(Number(canvas.width) || 1600), 1, MAX_SIDE);
    base.canvas.height = clamp(Math.round(Number(canvas.height) || 1200), 1, MAX_SIDE);
    base.canvas.background = /^#[0-9a-f]{6}$/i.test(canvas.background || "") ? canvas.background : "#ffffff";
    base.canvas.export_scale = clamp(Number(canvas.export_scale) || 1, 0.25, 4);
    base.timeline = {...base.timeline, ...timeline};
    if (!isoValue(base.timeline.selected_time_iso)) base.timeline.selected_time_iso = new Date().toISOString();
    base.metadata = {...base.metadata, ...(source.metadata || {})};
    base.timeline.mode = timeline.mode === "sequence" ? "sequence" : "still";
    base.timeline.sample_interval_s = Math.max(0.001, Number(timeline.sample_interval_s) || 1);
    base.timeline.playback_fps = clamp(Number(timeline.playback_fps) || 10, 0.2, 60);
    base.timeline.format = (timeline.animation_format || timeline.format) === "webm" ? "webm" : "mp4";
    base.layers = (Array.isArray(source.layers) ? source.layers : []).slice(0, MAX_LAYERS).map((layer, index) => ({
      id: String(layer.id || uid("layer")),
      title: String(layer.title || `Layer ${index + 1}`),
      source: copy(layer.source || {}),
      temporal_binding: copy(layer.temporal_binding || {kind: "unknown"}),
      frame: {
        x: Number(layer.frame?.x) || 0,
        y: Number(layer.frame?.y) || 0,
        width: Math.max(1, Number(layer.frame?.width) || 640),
        height: Math.max(1, Number(layer.frame?.height) || 480),
      },
      transform: {
        scale: Math.max(0.01, Number(layer.transform?.scale) || 1),
        offset_x: Number(layer.transform?.offset_x) || 0,
        offset_y: Number(layer.transform?.offset_y) || 0,
        fit: layer.transform?.fit === "fill" ? "fill" : "fit",
      },
      crop: {
        x: clamp(Number(layer.crop?.x) || 0, 0, 1),
        y: clamp(Number(layer.crop?.y) || 0, 0, 1),
        width: clamp(Number(layer.crop?.width) || 1, 0.0001, 1),
        height: clamp(Number(layer.crop?.height) || 1, 0.0001, 1),
      },
      z_index: Number.isFinite(Number(layer.z_index)) ? Number(layer.z_index) : index,
      visible: layer.visible !== false,
      metadata: copy(layer.metadata || {}),
    }));
    return base;
  }

  function create(options) {
    const API = options.apiBase || "/api/radio";
    const root = options.root || byId("figureStudio");
    const request = options.request;
    const notify = options.notify || (() => {});
    const getWorkspace = options.getWorkspace || (() => null);
    const getRootToken = options.getRootToken || (() => "");
    const ensureMedia = options.ensureMedia || (async () => {});
    const state = {
      workspaceId: "",
      draft: defaultDraft(""),
      selectedLayerId: "",
      tool: "move",
      pointer: null,
      imageCache: new Map(),
      runtimeUrls: new Map(),
      drawInfo: new Map(),
      saveTimer: null,
      saveInFlight: null,
      savePending: false,
      draftRevision: 0,
      preflight: null,
      preflightDraft: null,
      exports: [],
      loading: false,
      exportCanceled: false,
      exportSession: null,
      exportController: null,
    };

    function workspaceBase() {
      if (!state.workspaceId) throw new Error("Open or create a workspace before using Figure Studio.");
      return `${API}/workspaces/${state.workspaceId}/figures`;
    }

    function writeHeaders() {
      return {"X-Radio-Root-Token": getRootToken()};
    }

    function selectedLayer() {
      return state.draft.layers.find((layer) => layer.id === state.selectedLayerId) || null;
    }

    function serializeDraft({activeOnly = false} = {}) {
      const draft = copy(state.draft);
      draft.figure_schema_version = FIGURE_SCHEMA_VERSION;
      draft.workspace_id = state.workspaceId;
      draft.timeline.animation_format = draft.timeline.format === "webm" ? "webm" : "mp4";
      delete draft.timeline.format;
      for (const layer of draft.layers) {
        if (layer.source?.type === "series") {
          layer.source.frames = (layer.source.frames || []).map((frame) => ({
            time_iso: isoValue(frame.time_iso),
            ...controlledSource(frame),
          }));
        } else {
          layer.source = controlledSource(layer.source);
        }
        delete layer.runtime_url;
      }
      if (activeOnly && draft.mode === "single") {
        const layerId = activeSingleLayerId(draft.layers, draft.metadata?.single_layer_id || state.selectedLayerId);
        draft.layers = layerId ? draft.layers.filter((layer) => layer.id === layerId) : [];
      }
      return draft;
    }

    function invalidatePreflight() {
      state.preflight = null;
      state.preflightDraft = null;
      byId("figurePreflightState").textContent = "Not run";
      byId("figurePreflightState").dataset.state = "";
      byId("figurePreflightResult").textContent = "Run preflight before export.";
      byId("applyFigureRecommendationButton").hidden = true;
      byId("exportFigureButton").disabled = true;
    }

    function scheduleSave() {
      invalidatePreflight();
      state.draftRevision += 1;
      state.savePending = true;
      window.clearTimeout(state.saveTimer);
      byId("figureSaveStatus").textContent = "Unsaved changes";
      byId("figureSaveStatus").dataset.state = "";
      if (!state.workspaceId) return;
      state.saveTimer = window.setTimeout(() => saveDraft().catch(() => {}), 500);
    }

    async function saveDraft() {
      window.clearTimeout(state.saveTimer);
      state.saveTimer = null;
      if (!state.workspaceId) return;
      state.savePending = true;
      if (state.saveInFlight) {
        await state.saveInFlight;
        if (state.savePending) return saveDraft();
        return;
      }
      state.saveInFlight = drainDraftSaves();
      try {
        await state.saveInFlight;
      } finally {
        state.saveInFlight = null;
      }
      if (state.savePending) return saveDraft();
    }

    async function drainDraftSaves() {
      while (state.savePending && state.workspaceId) {
        state.savePending = false;
        window.clearTimeout(state.saveTimer);
        state.saveTimer = null;
        const savingRevision = state.draftRevision;
        const savingDraft = serializeDraft();
        byId("figureSaveStatus").textContent = "Saving...";
        try {
          const payload = await request(`${workspaceBase()}/draft`, {
            method: "PUT",
            headers: writeHeaders(),
            body: {draft: savingDraft},
          });
          if (savingRevision === state.draftRevision) {
            state.draft = normalizeDraft(payload.draft || savingDraft, state.workspaceId);
            byId("figureSaveStatus").textContent = "Draft saved";
            byId("figureSaveStatus").dataset.state = "saved";
            renderLayerList();
            updateLayerInspector();
            render();
          }
        } catch (error) {
          if (savingRevision === state.draftRevision) {
            byId("figureSaveStatus").textContent = `Save failed: ${error.message}`;
            byId("figureSaveStatus").dataset.state = "error";
          }
        }
      }
    }

    function temporalKind(binding) {
      return String(binding?.kind || "unknown");
    }

    function updateControlsFromDraft() {
      const draft = state.draft;
      byId("figureMode").value = draft.mode;
      byId("figureCanvasWidth").value = String(draft.canvas.width);
      byId("figureCanvasHeight").value = String(draft.canvas.height);
      byId("figureCanvasBackground").value = draft.canvas.background;
      byId("figureExportScale").value = String(draft.canvas.export_scale);
      byId("figureTimelineMode").value = draft.timeline.mode;
      byId("figureSelectedTime").value = localDateTimeValue(draft.timeline.selected_time_iso);
      byId("figureStartTime").value = localDateTimeValue(draft.timeline.start_time_iso);
      byId("figureEndTime").value = localDateTimeValue(draft.timeline.end_time_iso);
      byId("figureSampleInterval").value = String(draft.timeline.sample_interval_s);
      byId("figurePlaybackFps").value = String(draft.timeline.playback_fps);
      byId("figureAnimationFormat").value = draft.timeline.format;
      byId("figureStillControls").hidden = draft.timeline.mode !== "still";
      byId("figureSequenceControls").hidden = draft.timeline.mode !== "sequence";
      updateLayerInspector();
      updateToolButtons();
    }

    function updateDraftFromControls(markTimelineChanged = false, markCanvasChanged = false) {
      const canvas = state.draft.canvas;
      canvas.width = clamp(Math.round(Number(byId("figureCanvasWidth").value) || canvas.width), 1, MAX_SIDE);
      canvas.height = clamp(Math.round(Number(byId("figureCanvasHeight").value) || canvas.height), 1, MAX_SIDE);
      canvas.background = byId("figureCanvasBackground").value || "#ffffff";
      canvas.export_scale = clamp(Number(byId("figureExportScale").value) || 1, 0.25, 4);
      state.draft.mode = byId("figureMode").value === "single" ? "single" : "mosaic";
      const timeline = state.draft.timeline;
      timeline.mode = byId("figureTimelineMode").value === "sequence" ? "sequence" : "still";
      timeline.selected_time_iso = isoValue(byId("figureSelectedTime").value);
      timeline.start_time_iso = isoValue(byId("figureStartTime").value);
      timeline.end_time_iso = isoValue(byId("figureEndTime").value);
      timeline.sample_interval_s = Math.max(0.001, Number(byId("figureSampleInterval").value) || 1);
      timeline.playback_fps = clamp(Number(byId("figurePlaybackFps").value) || 10, 0.2, 60);
      timeline.format = byId("figureAnimationFormat").value === "webm" ? "webm" : "mp4";
      if (markTimelineChanged) state.draft.metadata.timeline_user_set = true;
      if (markCanvasChanged) state.draft.metadata.canvas_user_set = true;
      byId("figureStillControls").hidden = timeline.mode !== "still";
      byId("figureSequenceControls").hidden = timeline.mode !== "sequence";
      resizeMainCanvas();
      render();
      scheduleSave();
    }

    function updateLayerInspector() {
      const layer = selectedLayer();
      byId("figureNoLayer").hidden = Boolean(layer);
      byId("figureLayerInspector").hidden = !layer;
      if (!layer) return;
      byId("figureLayerTitle").value = layer.title;
      byId("figureLayerX").value = String(Math.round(layer.frame.x));
      byId("figureLayerY").value = String(Math.round(layer.frame.y));
      byId("figureLayerWidth").value = String(Math.round(layer.frame.width));
      byId("figureLayerHeight").value = String(Math.round(layer.frame.height));
      const kind = temporalKind(layer.temporal_binding);
      byId("figureLayerTemporalKind").value = ["timeless", "fixed", "series", "spectrogram"].includes(kind) ? kind : "unknown";
      byId("figureLayerTime").value = localDateTimeValue(layer.temporal_binding?.time_iso);
      byId("figureLayerTimeLabel").hidden = !["unknown", "fixed"].includes(kind);
      byId("figureLayerTolerance").value = layer.temporal_binding?.tolerance_s == null ? "" : String(layer.temporal_binding.tolerance_s);
      const fallback = layer.temporal_binding?.fallback_policy || layer.temporal_binding?.fallback || "none";
      const fallbackSelect = byId("figureLayerFallback");
      const allowedFallbacks = kind === "spectrogram"
        ? new Set(["none", "out_of_range_note"])
        : ["fixed", "series"].includes(kind) ? new Set(["none", "hold_nearest", "hold_last"]) : new Set(["none"]);
      for (const option of fallbackSelect.options) option.disabled = !allowedFallbacks.has(option.value);
      fallbackSelect.value = allowedFallbacks.has(fallback) ? fallback : "none";
    }

    function updateSelectedLayerFromControls() {
      const layer = selectedLayer();
      if (!layer) return;
      layer.title = byId("figureLayerTitle").value.trim() || "Untitled layer";
      layer.frame.x = Number(byId("figureLayerX").value) || 0;
      layer.frame.y = Number(byId("figureLayerY").value) || 0;
      layer.frame.width = Math.max(1, Number(byId("figureLayerWidth").value) || 1);
      layer.frame.height = Math.max(1, Number(byId("figureLayerHeight").value) || 1);
      const nextKind = byId("figureLayerTemporalKind").value;
      if (nextKind !== temporalKind(layer.temporal_binding)) {
        if (nextKind === "timeless") layer.temporal_binding = {kind: "timeless"};
        else if (nextKind === "fixed") layer.temporal_binding = {kind: "fixed", time_iso: isoValue(byId("figureLayerTime").value)};
        else if (nextKind === "series") layer.temporal_binding = {...layer.temporal_binding, kind: "series", samples: layer.temporal_binding?.samples || []};
        else if (nextKind === "spectrogram") layer.temporal_binding = {...layer.temporal_binding, kind: "spectrogram", coverage_segments: layer.temporal_binding?.coverage_segments || []};
        else layer.temporal_binding = {kind: "unknown"};
      }
      if (["unknown", "fixed"].includes(nextKind)) layer.temporal_binding.time_iso = isoValue(byId("figureLayerTime").value);
      const toleranceText = byId("figureLayerTolerance").value.trim();
      const tolerance = Number(toleranceText);
      if (toleranceText && Number.isFinite(tolerance) && tolerance >= 0) layer.temporal_binding.tolerance_s = tolerance;
      else delete layer.temporal_binding.tolerance_s;
      const allowedFallbacks = nextKind === "spectrogram"
        ? new Set(["none", "out_of_range_note"])
        : ["fixed", "series"].includes(nextKind) ? new Set(["none", "hold_nearest", "hold_last"]) : new Set(["none"]);
      layer.temporal_binding.fallback_policy = allowedFallbacks.has(byId("figureLayerFallback").value) ? byId("figureLayerFallback").value : "none";
      delete layer.temporal_binding.fallback;
      renderLayerList();
      render();
      updateLayerInspector();
      scheduleSave();
    }

    function resizeMainCanvas() {
      const canvas = byId("figureCanvas");
      if (canvas.width !== state.draft.canvas.width) canvas.width = state.draft.canvas.width;
      if (canvas.height !== state.draft.canvas.height) canvas.height = state.draft.canvas.height;
    }

    function sourceUrl(source) {
      if (source?.type === "artifact") return `${API}/workspaces/${state.workspaceId}/runs/${source.run_id}/artifacts/${source.artifact_id}`;
      if (source?.type === "preview") return `${workspaceBase()}/sources/previews/${source.preview_id}`;
      return "";
    }

    function loadImage(source) {
      const key = sourceKey(source);
      if (state.imageCache.has(key)) {
        const cached = state.imageCache.get(key);
        state.imageCache.delete(key);
        state.imageCache.set(key, cached);
        return cached;
      }
      const promise = new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = () => resolve(image);
        image.onerror = () => reject(new Error("The registered figure source could not be loaded."));
        image.src = state.runtimeUrls.get(key) || sourceUrl(source);
      });
      state.imageCache.set(key, promise);
      trimImageCache(MAX_IMAGE_CACHE_ITEMS);
      promise.then(render).catch(render);
      return promise;
    }

    function trimImageCache(limit = MAX_IMAGE_CACHE_ITEMS) {
      while (state.imageCache.size > limit) {
        const key = state.imageCache.keys().next().value;
        state.imageCache.delete(key);
        const runtimeUrl = state.runtimeUrls.get(key);
        if (runtimeUrl?.startsWith("blob:")) URL.revokeObjectURL(runtimeUrl);
        state.runtimeUrls.delete(key);
      }
    }

    async function applySingleSourceAspect(layer) {
      if (!layer || state.draft.mode !== "single" || state.draft.metadata.canvas_user_set) return;
      if (state.draft.metadata.single_aspect_applied_to === layer.id) return;
      const source = layerSourceAt(layer, currentPreviewTime());
      if (!source) return;
      try {
        const image = await loadImage(source);
        const scale = Math.min(1600 / image.naturalWidth, 1200 / image.naturalHeight);
        const width = Math.max(1, Math.round(image.naturalWidth * scale));
        const height = Math.max(1, Math.round(image.naturalHeight * scale));
        state.draft.canvas.width = width;
        state.draft.canvas.height = height;
        layer.frame = {x: 0, y: 0, width, height};
        layer.transform = {...layer.transform, scale: 1, offset_x: 0, offset_y: 0, fit: "fit"};
        state.draft.metadata.single_aspect_applied_to = layer.id;
        updateControlsFromDraft();
        render();
        scheduleSave();
      } catch (error) {
        notify(`Single-image aspect ratio could not be applied: ${error.message}`);
      }
    }

    function nearestSeriesSource(layer, timeIso) {
      const frames = layer.source?.frames || [];
      if (!frames.length) return null;
      const target = new Date(timeIso || frames[0].time_iso).getTime();
      const sorted = [...frames].sort((a, b) => new Date(a.time_iso) - new Date(b.time_iso));
      let best = sorted[0];
      let distance = Math.abs(new Date(best.time_iso).getTime() - target);
      for (const frame of sorted.slice(1)) {
        const next = Math.abs(new Date(frame.time_iso).getTime() - target);
        if (next < distance) { best = frame; distance = next; }
      }
      return controlledSource(best);
    }

    function preflightSourceAt(layer, timeIso) {
      const report = (state.preflight?.layers || []).find((item) => (item.layer_id || item.id) === layer.id);
      const matches = report?.matches || [];
      const requested = isoValue(timeIso);
      const match = matches.find((item) => isoValue(item.requested_time_iso || item.time_iso) === requested);
      if (!match) return null;
      if (match.source?.type) return controlledSource(match.source);
      if (match.type && (match.artifact_id || match.preview_id)) return controlledSource(match);
      const decision = match.source || match;
      const frames = layer.source?.frames || [];
      if (Number.isInteger(Number(decision.frame_index)) && frames[Number(decision.frame_index)]) return controlledSource(frames[Number(decision.frame_index)]);
      if (decision.artifact_id) {
        const frame = frames.find((item) => item.artifact_id === decision.artifact_id);
        if (frame) return controlledSource(frame);
      }
      return null;
    }

    function preflightMatchAt(layer, timeIso) {
      const report = (state.preflight?.layers || []).find((item) => (item.layer_id || item.id) === layer.id);
      const requested = isoValue(timeIso);
      return (report?.matches || []).find((item) => isoValue(item.requested_time_iso || item.time_iso) === requested) || null;
    }

    function layerSourceAt(layer, timeIso) {
      const matched = preflightSourceAt(layer, timeIso);
      if (matched) return matched;
      if (layer.source?.type === "series") return nearestSeriesSource(layer, timeIso);
      return controlledSource(layer.source);
    }

    function activeLayers(draft = state.draft) {
      const ordered = [...draft.layers].sort((a, b) => a.z_index - b.z_index);
      const layers = ordered.filter((layer) => layer.visible !== false);
      if (draft.mode !== "single") return layers;
      const singleId = activeSingleLayerId(ordered, draft.metadata?.single_layer_id || state.selectedLayerId);
      const selected = ordered.find((layer) => layer.id === singleId);
      return selected ? [selected] : [];
    }

    function activeSingleLayerId(layers, requestedId) {
      const selected = (layers || []).find((layer) => layer.id === requestedId);
      return selected?.visible !== false ? selected.id : "";
    }

    function fitGeometry(layer, image) {
      const crop = layer.crop;
      const sx = crop.x * image.naturalWidth;
      const sy = crop.y * image.naturalHeight;
      const sw = Math.max(1, crop.width * image.naturalWidth);
      const sh = Math.max(1, crop.height * image.naturalHeight);
      const fitScale = layer.transform.fit === "fill"
        ? Math.max(layer.frame.width / sw, layer.frame.height / sh)
        : Math.min(layer.frame.width / sw, layer.frame.height / sh);
      const scale = fitScale * layer.transform.scale;
      return {
        sx, sy, sw, sh, scale,
        dx: layer.frame.x + layer.frame.width / 2 - sw * scale / 2 + layer.transform.offset_x,
        dy: layer.frame.y + layer.frame.height / 2 - sh * scale / 2 + layer.transform.offset_y,
      };
    }

    function drawSpectrogramCursor(context, layer, geometry, timeIso) {
      if (temporalKind(layer.temporal_binding) !== "spectrogram" || !timeIso) return;
      const segments = layer.temporal_binding.coverage_segments || [];
      const current = new Date(timeIso).getTime();
      const segment = segments.find((item) => {
        const start = new Date(item.start_time_iso).getTime();
        const end = new Date(item.end_time_iso).getTime();
        return current >= start && current <= end;
      });
      if (!segment) {
        const fallback = layer.temporal_binding.fallback_policy || layer.temporal_binding.fallback;
        if (["note", "out_of_range_note"].includes(fallback)) {
          context.save();
          context.fillStyle = "rgba(8, 16, 25, 0.82)";
          context.fillRect(layer.frame.x + 8, layer.frame.y + layer.frame.height - 34, Math.max(0, layer.frame.width - 16), 26);
          context.fillStyle = "#ffcf78";
          context.font = "14px sans-serif";
          context.fillText("Current time outside displayed spectrum range", layer.frame.x + 14, layer.frame.y + layer.frame.height - 16);
          context.restore();
        }
        return;
      }
      const mapping = layer.metadata?.axis_mapping || {};
      const fullStart = mapping.start_time_iso || layer.metadata?.x_start_iso || segments[0]?.start_time_iso;
      const fullEnd = mapping.end_time_iso || layer.metadata?.x_end_iso || segments.at(-1)?.end_time_iso;
      const start = new Date(fullStart).getTime();
      const end = new Date(fullEnd).getTime();
      const ratio = end > start ? (current - start) / (end - start) : 0;
      const plotX = Number(mapping.x ?? mapping.left ?? 0);
      const plotWidth = Number(mapping.width ?? ((mapping.x1 ?? 1) - plotX));
      const sourceNormalizedX = plotX + plotWidth * clamp(ratio, 0, 1);
      const sourceX = sourceNormalizedX * geometry.imageWidth;
      const x = geometry.dx + (sourceX - geometry.sx) * geometry.scale;
      context.save();
      context.beginPath();
      context.rect(layer.frame.x, layer.frame.y, layer.frame.width, layer.frame.height);
      context.clip();
      context.strokeStyle = "#ffffff";
      context.lineWidth = 2;
      context.beginPath();
      context.moveTo(x, layer.frame.y);
      context.lineTo(x, layer.frame.y + layer.frame.height);
      context.stroke();
      context.restore();
    }

    function drawPlaceholder(context, layer, message) {
      context.save();
      context.fillStyle = "#172432";
      context.fillRect(layer.frame.x, layer.frame.y, layer.frame.width, layer.frame.height);
      context.strokeStyle = "#52677a";
      context.strokeRect(layer.frame.x, layer.frame.y, layer.frame.width, layer.frame.height);
      context.fillStyle = "#c5d2dd";
      context.font = "14px sans-serif";
      context.fillText(message, layer.frame.x + 14, layer.frame.y + 26, Math.max(0, layer.frame.width - 28));
      context.restore();
    }

    function drawLayer(context, layer, image, timeIso, interactive) {
      if (!image) return drawPlaceholder(context, layer, "Loading registered source...");
      const geometry = fitGeometry(layer, image);
      geometry.imageWidth = image.naturalWidth;
      geometry.imageHeight = image.naturalHeight;
      state.drawInfo.set(layer.id, geometry);
      context.save();
      context.beginPath();
      context.rect(layer.frame.x, layer.frame.y, layer.frame.width, layer.frame.height);
      context.clip();
      context.drawImage(image, geometry.sx, geometry.sy, geometry.sw, geometry.sh, geometry.dx, geometry.dy, geometry.sw * geometry.scale, geometry.sh * geometry.scale);
      context.restore();
      drawSpectrogramCursor(context, layer, geometry, timeIso);
      const match = preflightMatchAt(layer, timeIso);
      if (match?.annotation_required && match.source_time_iso) {
        context.save();
        context.fillStyle = "rgba(8, 16, 25, 0.82)";
        context.fillRect(layer.frame.x + 8, layer.frame.y + 8, Math.max(0, layer.frame.width - 16), 26);
        context.fillStyle = "#ffcf78";
        context.font = "14px sans-serif";
        context.fillText(`Held from ${match.source_time_iso}`, layer.frame.x + 14, layer.frame.y + 26);
        context.restore();
      }
      if (interactive && layer.id === state.selectedLayerId) {
        context.save();
        context.strokeStyle = "#29cfc0";
        context.lineWidth = Math.max(2, state.draft.canvas.width / 800);
        context.strokeRect(layer.frame.x, layer.frame.y, layer.frame.width, layer.frame.height);
        const handle = Math.max(10, state.draft.canvas.width / 120);
        context.fillStyle = "#29cfc0";
        context.fillRect(layer.frame.x + layer.frame.width - handle, layer.frame.y + layer.frame.height - handle, handle, handle);
        context.restore();
      }
    }

    function drawComposition(canvas, timeIso, interactive, draft = state.draft) {
      const context = canvas.getContext("2d", {alpha: false});
      const logicalWidth = draft.canvas.width;
      const logicalHeight = draft.canvas.height;
      const scaleX = canvas.width / logicalWidth;
      const scaleY = canvas.height / logicalHeight;
      context.save();
      context.setTransform(scaleX, 0, 0, scaleY, 0, 0);
      context.fillStyle = draft.canvas.background;
      context.fillRect(0, 0, logicalWidth, logicalHeight);
      state.drawInfo.clear();
      for (const layer of activeLayers(draft)) {
        const source = layerSourceAt(layer, timeIso);
        const cached = source ? state.imageCache.get(sourceKey(source)) : null;
        let image = null;
        if (cached) cached.then((value) => { image = value; });
        if (cached?._resolvedImage) image = cached._resolvedImage;
        if (image) drawLayer(context, layer, image, timeIso, interactive);
        else {
          drawPlaceholder(context, layer, source ? "Loading registered source..." : "No source at this time");
          if (source) {
            loadImage(source).then((loaded) => {
              const promise = state.imageCache.get(sourceKey(source));
              if (promise) promise._resolvedImage = loaded;
              if (interactive) render();
            }).catch(() => {});
          }
        }
      }
      context.restore();
    }

    function currentPreviewTime() {
      const timeline = state.draft.timeline;
      return timeline.mode === "still" ? timeline.selected_time_iso : timeline.start_time_iso;
    }

    function render() {
      if (!root || root.hidden) return;
      resizeMainCanvas();
      drawComposition(byId("figureCanvas"), currentPreviewTime(), true);
      byId("figureCanvasEmpty").hidden = state.draft.layers.length > 0;
    }

    async function preload(timeIso, draft = state.draft) {
      const sources = activeLayers(draft).map((layer) => layerSourceAt(layer, timeIso)).filter(Boolean);
      await Promise.all(sources.map(async (source) => {
        const image = await loadImage(source);
        const promise = state.imageCache.get(sourceKey(source));
        if (promise) promise._resolvedImage = image;
      }));
    }

    function renderLayerList() {
      const list = byId("figureLayerList");
      list.replaceChildren();
      const layers = [...state.draft.layers].sort((a, b) => b.z_index - a.z_index);
      for (const layer of layers) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "figure-layer-item";
        button.dataset.selected = String(layer.id === state.selectedLayerId);
        const visible = document.createElement("input");
        visible.type = "checkbox";
        visible.checked = layer.visible !== false;
        visible.ariaLabel = `Show ${layer.title}`;
        visible.addEventListener("click", (event) => event.stopPropagation());
        visible.addEventListener("change", () => { layer.visible = visible.checked; render(); scheduleSave(); });
        const title = document.createElement("span");
        title.textContent = layer.title;
        const kind = document.createElement("small");
        kind.textContent = temporalKind(layer.temporal_binding);
        button.append(visible, title, kind);
        button.addEventListener("click", () => selectLayer(layer.id));
        list.append(button);
      }
      byId("figureLayerCount").textContent = String(state.draft.layers.length);
    }

    function selectLayer(layerId) {
      state.selectedLayerId = layerId;
      state.draft.metadata.single_layer_id = layerId;
      renderLayerList();
      updateLayerInspector();
      render();
      if (state.draft.mode === "single") {
        state.draft.metadata.single_aspect_applied_to = "";
        applySingleSourceAspect(selectedLayer());
        scheduleSave();
      }
    }

    function layoutNewLayer(index) {
      const width = state.draft.mode === "single" ? state.draft.canvas.width : Math.round(state.draft.canvas.width * 0.72);
      const height = state.draft.mode === "single" ? state.draft.canvas.height : Math.round(state.draft.canvas.height * 0.56);
      const offset = (index % 8) * 28;
      return {
        x: clamp(Math.round((state.draft.canvas.width - width) / 2 + offset), 0, Math.max(0, state.draft.canvas.width - 40)),
        y: clamp(Math.round((state.draft.canvas.height - height) / 2 + offset), 0, Math.max(0, state.draft.canvas.height - 40)),
        width,
        height,
      };
    }

    function appendLayer({title, source, temporalBinding, metadata}) {
      if (state.draft.layers.length >= MAX_LAYERS) throw new Error(`A figure can contain at most ${MAX_LAYERS} layers.`);
      const layer = {
        id: uid("layer"),
        title: title || `Layer ${state.draft.layers.length + 1}`,
        source,
        temporal_binding: temporalBinding || {kind: "unknown"},
        frame: layoutNewLayer(state.draft.layers.length),
        transform: {scale: 1, offset_x: 0, offset_y: 0, fit: "fit"},
        crop: {x: 0, y: 0, width: 1, height: 1},
        z_index: state.draft.layers.length,
        visible: true,
        metadata: metadata || {},
      };
      state.draft.layers.push(layer);
      seedTimelineFromBinding(temporalBinding);
      selectLayer(layer.id);
      scheduleSave();
      return layer;
    }

    function seedTimelineFromBinding(binding) {
      if (state.draft.metadata.timeline_user_set || state.draft.layers.length > 1) return;
      let start = "";
      let end = "";
      if (binding?.kind === "fixed") start = end = isoValue(binding.time_iso);
      if (binding?.kind === "series") {
        const times = (binding.samples || []).map((item) => isoValue(item.time_iso)).filter(Boolean).sort();
        start = times[0] || "";
        end = times.at(-1) || "";
      }
      if (binding?.kind === "spectrogram") {
        const segments = binding.coverage_segments || [];
        start = isoValue(segments[0]?.start_time_iso);
        end = isoValue(segments.at(-1)?.end_time_iso);
      }
      if (!start) return;
      state.draft.timeline.selected_time_iso = start;
      state.draft.timeline.start_time_iso = start;
      state.draft.timeline.end_time_iso = end || start;
      updateControlsFromDraft();
    }

    async function ensureWorkspaceDraftLoaded() {
      const workspace = getWorkspace();
      if (!workspace?.id) throw new Error("Open or create a workspace before using Figure Studio.");
      if (state.workspaceId !== workspace.id || state.draft.workspace_id !== workspace.id) await loadDraft();
    }

    async function addPreview({blob, title, metadata = {}, temporalBinding = null}) {
      await ensureWorkspaceDraftLoaded();
      if (!blob || !String(blob.type || "").includes("png")) throw new Error("Preview registration requires a PNG snapshot.");
      const form = new FormData();
      form.append("metadata", JSON.stringify({...metadata, title: title || metadata.title || "Action preview", temporal_binding: temporalBinding || {kind: "unknown", fallback_policy: "none"}}));
      form.append("file", blob, "preview.png");
      const payload = await request(`${workspaceBase()}/sources/previews`, {method: "POST", headers: writeHeaders(), body: form});
      const source = controlledSource(payload.source || payload.preview?.source || payload.preview);
      const layer = appendLayer({title, source, temporalBinding: temporalBinding || {kind: "unknown"}, metadata});
      state.runtimeUrls.set(sourceKey(source), sourceUrl(source));
      await open();
      selectLayer(layer.id);
      notify(`${title || "Preview"} was added to Figure Studio. No analysis action was started.`, "success");
      return layer;
    }

    async function replacePreview({layerId, blob, title, metadata = {}, temporalBinding = null}) {
      await ensureWorkspaceDraftLoaded();
      if (!blob || !String(blob.type || "").includes("png")) throw new Error("Preview registration requires a PNG snapshot.");
      const layer = state.draft.layers.find((item) => item.id === layerId);
      if (!layer) throw new Error("The Figure Studio layer selected for replacement no longer exists.");
      const form = new FormData();
      form.append("metadata", JSON.stringify({...metadata, title: title || metadata.title || layer.title, temporal_binding: temporalBinding || {kind: "unknown", fallback_policy: "none"}}));
      form.append("file", blob, "preview.png");
      const payload = await request(`${workspaceBase()}/sources/previews`, {method: "POST", headers: writeHeaders(), body: form});
      const source = controlledSource(payload.source || payload.preview?.source || payload.preview);
      layer.source = source;
      layer.title = title || layer.title;
      layer.temporal_binding = temporalBinding || {kind: "unknown", fallback_policy: "none"};
      layer.metadata = metadata;
      state.runtimeUrls.set(sourceKey(source), sourceUrl(source));
      selectLayer(layer.id);
      scheduleSave();
      await open();
      notify(`${layer.title} was replaced with the rebuilt Preview. No analysis action was started.`, "success");
      return layer;
    }

    async function addArtifact({runId, artifactId, title, observedAt, metadata = {}}) {
      await ensureWorkspaceDraftLoaded();
      const source = controlledSource({type: "artifact", run_id: runId, artifact_id: artifactId});
      const temporalBinding = observedAt
        ? {kind: "fixed", time_iso: isoValue(observedAt), tolerance_s: 0, fallback_policy: "none"}
        : {kind: "unknown", fallback_policy: "none"};
      const layer = appendLayer({title, source, temporalBinding, metadata});
      await open();
      notify(`${title || "Image artifact"} was added to Figure Studio.`, "success");
      return layer;
    }

    async function addArtifactSeries({title, frames, metadata = {}}) {
      await ensureWorkspaceDraftLoaded();
      const sorted = (frames || []).filter((frame) => isoValue(frame.time_iso)).sort((a, b) => new Date(a.time_iso) - new Date(b.time_iso));
      if (sorted.length < 2) throw new Error("A figure series requires at least two time-stamped image artifacts.");
      const sourceFrames = sorted.map((frame) => ({time_iso: isoValue(frame.time_iso), ...controlledSource({type: "artifact", run_id: frame.run_id, artifact_id: frame.artifact_id})}));
      const samples = sourceFrames.map((frame, frameIndex) => ({time_iso: frame.time_iso, frame_index: frameIndex, artifact_id: frame.artifact_id}));
      const layer = appendLayer({
        title,
        source: {type: "series", frames: sourceFrames},
        temporalBinding: {kind: "series", samples, fallback_policy: "none"},
        metadata,
      });
      await open();
      notify(`${title || "Image series"} was added to Figure Studio.`, "success");
      return layer;
    }

    function applyTemplate(name) {
      const layers = state.draft.layers;
      if (!layers.length) return;
      const width = state.draft.canvas.width;
      const height = state.draft.canvas.height;
      const gap = Math.max(8, Math.round(Math.min(width, height) * 0.018));
      if (name === "vertical") {
        const cellHeight = (height - gap * (layers.length + 1)) / layers.length;
        layers.forEach((layer, index) => { layer.frame = {x: gap, y: gap + index * (cellHeight + gap), width: width - 2 * gap, height: cellHeight}; });
      } else if (name === "horizontal") {
        const cellWidth = (width - gap * (layers.length + 1)) / layers.length;
        layers.forEach((layer, index) => { layer.frame = {x: gap + index * (cellWidth + gap), y: gap, width: cellWidth, height: height - 2 * gap}; });
      } else if (name === "grid") {
        const columns = Math.ceil(Math.sqrt(layers.length));
        const rows = Math.ceil(layers.length / columns);
        const cellWidth = (width - gap * (columns + 1)) / columns;
        const cellHeight = (height - gap * (rows + 1)) / rows;
        layers.forEach((layer, index) => {
          const column = index % columns;
          const row = Math.floor(index / columns);
          layer.frame = {x: gap + column * (cellWidth + gap), y: gap + row * (cellHeight + gap), width: cellWidth, height: cellHeight};
        });
      }
      for (const layer of layers) layer.transform = {...layer.transform, scale: 1, offset_x: 0, offset_y: 0, fit: "fit"};
      updateLayerInspector();
      render();
      scheduleSave();
    }

    function updateToolButtons() {
      for (const button of root.querySelectorAll("[data-figure-tool]")) button.dataset.active = String(button.dataset.figureTool === state.tool);
    }

    function canvasPoint(event) {
      const canvas = byId("figureCanvas");
      const rect = canvas.getBoundingClientRect();
      return {x: (event.clientX - rect.left) * canvas.width / rect.width, y: (event.clientY - rect.top) * canvas.height / rect.height};
    }

    function hitLayer(point) {
      return [...activeLayers()].reverse().find((layer) => point.x >= layer.frame.x && point.x <= layer.frame.x + layer.frame.width && point.y >= layer.frame.y && point.y <= layer.frame.y + layer.frame.height) || null;
    }

    function sourcePoint(layer, point) {
      const geometry = state.drawInfo.get(layer.id);
      if (!geometry) return null;
      return {
        x: clamp((geometry.sx + (point.x - geometry.dx) / geometry.scale) / geometry.imageWidth, 0, 1),
        y: clamp((geometry.sy + (point.y - geometry.dy) / geometry.scale) / geometry.imageHeight, 0, 1),
      };
    }

    function pointerDown(event) {
      const point = canvasPoint(event);
      const layer = hitLayer(point);
      if (!layer) return;
      selectLayer(layer.id);
      const handle = Math.max(12, state.draft.canvas.width / 100);
      const resize = point.x >= layer.frame.x + layer.frame.width - handle && point.y >= layer.frame.y + layer.frame.height - handle;
      const mode = state.tool === "crop" ? "crop" : state.tool === "pan" ? "pan" : resize ? "resize" : "move";
      state.pointer = {id: event.pointerId, mode, start: point, frame: {...layer.frame}, transform: {...layer.transform}, cropStart: sourcePoint(layer, point)};
      event.currentTarget.setPointerCapture(event.pointerId);
    }

    function pointerMove(event) {
      if (!state.pointer || state.pointer.id !== event.pointerId) return;
      const layer = selectedLayer();
      if (!layer) return;
      const point = canvasPoint(event);
      const dx = point.x - state.pointer.start.x;
      const dy = point.y - state.pointer.start.y;
      if (state.pointer.mode === "move") {
        layer.frame.x = state.pointer.frame.x + dx;
        layer.frame.y = state.pointer.frame.y + dy;
      } else if (state.pointer.mode === "resize") {
        layer.frame.width = Math.max(20, state.pointer.frame.width + dx);
        layer.frame.height = Math.max(20, state.pointer.frame.height + dy);
      } else if (state.pointer.mode === "pan") {
        layer.transform.offset_x = state.pointer.transform.offset_x + dx;
        layer.transform.offset_y = state.pointer.transform.offset_y + dy;
      }
      render();
    }

    function pointerUp(event) {
      if (!state.pointer || state.pointer.id !== event.pointerId) return;
      const layer = selectedLayer();
      if (layer && state.pointer.mode === "crop") {
        const end = sourcePoint(layer, canvasPoint(event));
        const start = state.pointer.cropStart;
        if (start && end && Math.abs(end.x - start.x) > 0.002 && Math.abs(end.y - start.y) > 0.002) {
          layer.crop = {x: Math.min(start.x, end.x), y: Math.min(start.y, end.y), width: Math.abs(end.x - start.x), height: Math.abs(end.y - start.y)};
          layer.transform = {...layer.transform, scale: 1, offset_x: 0, offset_y: 0};
        }
      }
      state.pointer = null;
      updateLayerInspector();
      render();
      scheduleSave();
    }

    function wheelZoom(event) {
      const layer = selectedLayer();
      if (!layer || !hitLayer(canvasPoint(event)) || hitLayer(canvasPoint(event)).id !== layer.id) return;
      event.preventDefault();
      const factor = event.deltaY > 0 ? 0.9 : 1.1;
      layer.transform.scale = clamp(layer.transform.scale * factor, 0.05, 40);
      render();
      scheduleSave();
    }

    function resetLayer(mode) {
      const layer = selectedLayer();
      if (!layer) return;
      if (mode === "fit" || mode === "fill") layer.transform.fit = mode;
      if (["fit", "fill", "center", "reset"].includes(mode)) {
        layer.transform.scale = 1;
        layer.transform.offset_x = 0;
        layer.transform.offset_y = 0;
      }
      if (mode === "reset") layer.crop = {x: 0, y: 0, width: 1, height: 1};
      render();
      scheduleSave();
    }

    function moveLayer(delta) {
      const layer = selectedLayer();
      if (!layer) return;
      const sorted = [...state.draft.layers].sort((a, b) => a.z_index - b.z_index);
      const index = sorted.findIndex((item) => item.id === layer.id);
      const target = clamp(index + delta, 0, sorted.length - 1);
      if (index === target) return;
      [sorted[index], sorted[target]] = [sorted[target], sorted[index]];
      sorted.forEach((item, index) => { item.z_index = index; });
      renderLayerList();
      render();
      scheduleSave();
    }

    function removeLayer() {
      const layer = selectedLayer();
      if (!layer) return;
      const decisions = Array.isArray(state.draft.metadata?.layer_decisions) ? state.draft.metadata.layer_decisions : [];
      state.draft.metadata.layer_decisions = [...decisions.slice(-99), {
        action: "remove_layer",
        layer_id: layer.id,
        applied_at: new Date().toISOString(),
      }];
      state.draft.layers = state.draft.layers.filter((item) => item.id !== layer.id);
      const savedSingle = state.draft.metadata?.single_layer_id;
      state.selectedLayerId = state.draft.layers.some((layer) => layer.id === savedSingle) ? savedSingle : (state.draft.layers.at(-1)?.id || "");
      state.draft.metadata.single_layer_id = state.selectedLayerId;
      renderLayerList();
      updateLayerInspector();
      render();
      scheduleSave();
    }

    function preflightIssues(preflight) {
      return preflight.blocking_issues || preflight.blockers || preflight.issues || [];
    }

    function preflightReady(preflight) {
      if (typeof preflight.ready === "boolean") return preflight.ready;
      if (typeof preflight.can_export === "boolean") return preflight.can_export;
      return preflight.status === "ready" || (Boolean(preflight.preflight_revision) && preflightIssues(preflight).length === 0);
    }

    function renderPreflight(preflight) {
      const ready = preflightReady(preflight);
      const stateLabel = byId("figurePreflightState");
      stateLabel.textContent = ready ? "Ready" : "Blocked";
      stateLabel.dataset.state = ready ? "ready" : "blocked";
      const result = byId("figurePreflightResult");
      result.replaceChildren();
      const issues = preflightIssues(preflight);
      if (!issues.length) result.textContent = ready ? "All visible layers cover the requested unified time." : (preflight.message || "Resolve the reported time coverage before export.");
      else {
        const list = document.createElement("ul");
        list.className = "figure-preflight-issues";
        for (const issue of issues) {
          const item = document.createElement("li");
          item.textContent = typeof issue === "string" ? issue : issue.message || issue.reason || JSON.stringify(issue);
          list.append(item);
        }
        result.append(list);
      }
      const reports = document.createElement("div");
      reports.className = "figure-preflight-layers";
      for (const report of preflight.layers || []) {
        const layer = state.draft.layers.find((item) => item.id === report.layer_id);
        const details = document.createElement("details");
        details.className = "figure-preflight-layer";
        const summary = document.createElement("summary");
        const missing = Number(report.missing_count || 0);
        summary.textContent = `${layer?.title || report.layer_id}: ${report.status || (missing ? "blocked" : "ready")} · ${missing} missing`;
        details.append(summary);
        const facts = document.createElement("p");
        const firstMatch = (report.matches || []).find((item) => item.source_time_iso || item.delta_s !== undefined);
        const coverage = (report.coverage_segments || []).map((item) => `${item.start_time_iso} – ${item.end_time_iso}`).join("; ");
        facts.textContent = coverage
          ? `Coverage: ${coverage}`
          : firstMatch ? `Matched source: ${firstMatch.source_time_iso || "timeless"}; delta: ${Number(firstMatch.delta_s || 0).toFixed(3)} s` : "No source-time match is available.";
        details.append(facts);
        const allMatches = report.matches || [];
        const representative = allMatches.length <= 20
          ? allMatches
          : allMatches.filter((item, index) => index === 0 || index === allMatches.length - 1 || !item.resolved || item.fallback_applied).slice(0, 20);
        if (representative.length) {
          const table = document.createElement("table");
          table.className = "figure-match-table";
          table.innerHTML = "<thead><tr><th>Requested UTC</th><th>Source / coverage UTC</th><th>Δs</th><th>Decision</th></tr></thead>";
          const body = document.createElement("tbody");
          for (const match of representative) {
            const row = document.createElement("tr");
            const sourceTime = match.source_time_iso || (match.coverage_segment ? `${match.coverage_segment.start_time_iso} – ${match.coverage_segment.end_time_iso}` : "—");
            const decision = match.fallback_applied ? `fallback: ${match.fallback_applied}` : match.strict_match ? "strict" : match.resolved ? "resolved" : `missing: ${match.reason || "no coverage"}`;
            for (const value of [match.requested_time_iso, sourceTime, match.delta_s === undefined ? "—" : Number(match.delta_s).toFixed(3), decision]) {
              const cell = document.createElement("td");
              cell.textContent = value || "—";
              row.append(cell);
            }
            body.append(row);
          }
          table.append(body);
          details.append(table);
          if (representative.length < allMatches.length) {
            const note = document.createElement("small");
            note.textContent = `Showing ${representative.length} representative matches. All ${allMatches.length} decisions are retained in export provenance.`;
            details.append(note);
          }
        }
        if ((report.missing_intervals || []).length) {
          const missingText = document.createElement("p");
          missingText.textContent = `Missing: ${(report.missing_intervals || []).map((item) => `${item.start_time_iso} – ${item.end_time_iso}`).join("; ")}`;
          details.append(missingText);
        }
        if (report.kind === "spectrogram" && missing) {
          const help = document.createElement("p");
          help.textContent = "Add adjacent spectrogram input and rebuild Preview, then run preflight again.";
          details.append(help);
          const resolve = document.createElement("button");
          resolve.type = "button";
          resolve.className = "secondary";
          resolve.textContent = "Resolve Coverage";
          resolve.addEventListener("click", () => {
            window.dispatchEvent(new CustomEvent("radio:resolve-spectrogram-coverage", {
              detail: {layer_id: report.layer_id, layer_title: layer?.title || report.layer_id},
            }));
          });
          details.append(resolve);
        }
        if (missing && layer) {
          const remove = document.createElement("button");
          remove.type = "button";
          remove.className = "danger";
          remove.textContent = "Remove This Layer";
          remove.addEventListener("click", () => {
            if (!window.confirm(`Remove ${layer.title} from this figure?`)) return;
            state.selectedLayerId = layer.id;
            removeLayer();
            notify("The layer was removed. Run preflight again to confirm the remaining common time.", "success");
          });
          details.append(remove);
        }
        reports.append(details);
      }
      if (reports.childElementCount) result.append(reports);
      const rawRecommendation = preflight.recommended_timeline || preflight.recommendation?.timeline || preflight.suggested_timeline || preflight.recommendation;
      let recommendation = rawRecommendation;
      if (rawRecommendation?.action === "move_time") recommendation = {mode: "still", selected_time_iso: rawRecommendation.selected_time_iso};
      if (rawRecommendation?.action === "trim_range") recommendation = {mode: "sequence", start_time_iso: rawRecommendation.start_time_iso, end_time_iso: rawRecommendation.end_time_iso};
      const apply = byId("applyFigureRecommendationButton");
      apply.hidden = !recommendation || rawRecommendation?.action === "resolve_layers";
      apply._timeline = recommendation || null;
      apply._decision = rawRecommendation || null;
      if (rawRecommendation?.action === "resolve_layers") {
        const resolution = document.createElement("div");
        resolution.className = "figure-resolution-options";
        const heading = document.createElement("strong");
        heading.textContent = "No common UTC time is available. Choose an explicit resolution:";
        const list = document.createElement("ul");
        const labels = {
          supplement_adjacent_spectrogram: "Add adjacent spectrogram FITS and explicitly rebuild its Preview.",
          supplement_or_replace_source: "Add or replace a layer with a compatible Preview or artifact.",
          remove_layer: "Remove one of the insufficient layers using its button above.",
          cancel_export: "Cancel this export attempt and keep the draft unchanged.",
        };
        for (const option of rawRecommendation.options || []) {
          const item = document.createElement("li");
          item.textContent = labels[option] || String(option).replaceAll("_", " ");
          list.append(item);
        }
        const cancel = document.createElement("button");
        cancel.type = "button";
        cancel.className = "secondary";
        cancel.textContent = "Cancel Export Attempt";
        cancel.addEventListener("click", () => {
          invalidatePreflight();
          notify("The export attempt was canceled; the figure draft was not changed.");
        });
        resolution.append(heading, list, cancel);
        result.append(resolution);
      }
      byId("exportFigureButton").disabled = !ready;
    }

    async function runPreflight() {
      updateDraftFromControls();
      byId("figurePreflightState").textContent = "Checking...";
      try {
        state.preflightDraft = serializeDraft({activeOnly: true});
        const payload = await request(`${workspaceBase()}/preflight`, {method: "POST", body: {draft: state.preflightDraft}});
        state.preflight = payload.preflight || payload;
        renderPreflight(state.preflight);
        return state.preflight;
      } catch (error) {
        byId("figurePreflightState").textContent = "Failed";
        byId("figurePreflightState").dataset.state = "blocked";
        byId("figurePreflightResult").textContent = error.message;
        byId("exportFigureButton").disabled = true;
        throw error;
      }
    }

    function applyRecommendation() {
      const timeline = byId("applyFigureRecommendationButton")._timeline;
      if (!timeline) return;
      const decision = byId("applyFigureRecommendationButton")._decision || {};
      const previousTimeline = copy(state.draft.timeline);
      state.draft.timeline = {...state.draft.timeline, ...timeline};
      const decisions = Array.isArray(state.draft.metadata?.timeline_decisions) ? state.draft.metadata.timeline_decisions : [];
      state.draft.metadata.timeline_decisions = [...decisions.slice(-99), {
        action: decision.action || (timeline.mode === "sequence" ? "trim_range" : "move_time"),
        previous_timeline: previousTimeline,
        applied_timeline: copy(state.draft.timeline),
        applied_at: new Date().toISOString(),
      }];
      updateControlsFromDraft();
      render();
      scheduleSave();
      notify("The recommended common UTC time was applied. Run preflight again to confirm it.", "success");
    }

    async function saveSnapshot() {
      await saveDraft();
      const name = `Figure snapshot ${new Date().toISOString()}`;
      await request(`${workspaceBase()}/snapshots`, {method: "POST", headers: writeHeaders(), body: {draft: serializeDraft(), name}});
      notify("An immutable Figure Studio snapshot was saved.", "success");
    }

    function outputCanvas(draft = state.draft) {
      const scale = draft.canvas.export_scale;
      const width = Math.round(draft.canvas.width * scale);
      const height = Math.round(draft.canvas.height * scale);
      if (width > MAX_SIDE || height > MAX_SIDE || width * height > MAX_PIXELS) throw new Error("The scaled export exceeds the 8192 px or 40 million pixel limit.");
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      return canvas;
    }

    function canvasBlob(canvas, type = "image/png") {
      return new Promise((resolve, reject) => canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error("The browser could not encode the composition.")), type));
    }

    async function buildExportFile(exportDraft, times) {
      const timeline = exportDraft.timeline;
      const format = timeline.animation_format === "webm" ? "webm" : "mp4";
      const canvas = outputCanvas(exportDraft);
      if (state.exportCanceled) throw new DOMException("Figure export canceled", "AbortError");
      if (timeline.mode === "still") {
        await preload(times[0], exportDraft);
        drawComposition(canvas, times[0], false, exportDraft);
        const blob = await canvasBlob(canvas);
        if (blob.size > MAX_IMAGE_BYTES) throw new Error("The PNG exceeds the 25 MiB limit. Reduce canvas dimensions or export scale.");
        return {blob, filename: "figure.png", mime: "image/png", times};
      }
      await ensureMedia();
      const fps = timeline.playback_fps;
      let session;
      try {
        session = await window.SolarToolkitMedia.createCanvasRecorder({canvas, format, quality: "high", fps, targetMode: "buffer", contentHint: "detail"});
        state.exportSession = session;
      } catch (error) {
        if (format === "mp4") throw new Error(`MP4 encoding is unavailable: ${error.message}. Select WebM and export again.`);
        throw error;
      }
      try {
        for (let index = 0; index < times.length; index += 1) {
          if (state.exportCanceled) throw new DOMException("Figure export canceled", "AbortError");
          await preload(times[index], exportDraft);
          drawComposition(canvas, times[index], false, exportDraft);
          await session.addFrame(index / fps, 1 / fps, {keyFrame: index === 0});
          byId("figureSaveStatus").textContent = `Encoding ${index + 1} / ${times.length}`;
        }
        const result = await session.finalize();
        if (state.exportCanceled) throw new DOMException("Figure export canceled", "AbortError");
        const mime = format === "mp4" ? "video/mp4" : "video/webm";
        const blob = new Blob([result.buffer], {type: mime});
        if (blob.size > MAX_VIDEO_BYTES) throw new Error("The animation exceeds the 512 MiB limit. Shorten the interval or reduce dimensions.");
        return {blob, filename: `figure.${format}`, mime, times};
      } catch (error) {
        if (session && !["canceled", "finalized"].includes(session.state)) await session.cancel().catch(() => {});
        throw error;
      } finally {
        state.exportSession = null;
      }
    }

    async function exportFigure() {
      if (!state.preflight || !preflightReady(state.preflight) || !state.preflight.preflight_revision) throw new Error("Run a successful preflight for the current draft before export.");
      const button = byId("exportFigureButton");
      const cancelButton = byId("cancelFigureExportButton");
      state.exportCanceled = false;
      state.exportController = new AbortController();
      button.disabled = true;
      button.textContent = "Exporting...";
      cancelButton.hidden = false;
      try {
        const exportDraft = copy(state.preflightDraft);
        const authoritativeTimes = Array.isArray(state.preflight.sample_times_iso) ? copy(state.preflight.sample_times_iso) : [];
        if (!authoritativeTimes.length || authoritativeTimes.length > MAX_FRAMES) throw new Error("Preflight did not return a valid authoritative UTC sample list.");
        if (exportDraft.timeline.mode === "still" && authoritativeTimes.length !== 1) throw new Error("Still export requires exactly one preflight UTC sample.");
        const built = await buildExportFile(exportDraft, authoritativeTimes);
        if (state.exportCanceled) throw new DOMException("Figure export canceled", "AbortError");
        const exportLayers = state.preflightDraft?.layers || [];
        const manifest = {
          figure_schema_version: FIGURE_SCHEMA_VERSION,
          timeline: copy((state.preflightDraft || serializeDraft({activeOnly: true})).timeline),
          frame_times: built.times,
          frame_count: built.times.length,
          mime: built.mime,
          width: Math.round(exportDraft.canvas.width * exportDraft.canvas.export_scale),
          height: Math.round(exportDraft.canvas.height * exportDraft.canvas.export_scale),
          duration_s: exportDraft.timeline.mode === "sequence" ? built.times.length / exportDraft.timeline.playback_fps : 0,
          layer_decisions: exportLayers.map((layer) => ({layer_id: layer.id, temporal_binding: layer.temporal_binding})),
          preflight_layer_matches: copy(state.preflight.layers || []),
          preflight_warnings: copy(state.preflight.warnings || []),
        };
        const form = new FormData();
        form.append("figure", JSON.stringify(exportDraft));
        form.append("preflight", JSON.stringify(state.preflight));
        form.append("manifest", JSON.stringify(manifest));
        form.append("preflight_revision", state.preflight.preflight_revision);
        form.append("file", built.blob, built.filename);
        await request(`${workspaceBase()}/exports`, {method: "POST", headers: writeHeaders(), body: form, signal: state.exportController.signal});
        await loadExports();
        notify("The composed figure was exported and indexed in Figure Exports.", "success");
      } finally {
        state.exportController = null;
        state.exportSession = null;
        cancelButton.hidden = true;
        button.textContent = "Export";
        button.disabled = !(state.preflight && preflightReady(state.preflight));
        byId("figureSaveStatus").textContent = "Draft saved";
        trimImageCache(8);
      }
    }

    async function cancelExport() {
      state.exportCanceled = true;
      state.exportController?.abort();
      const session = state.exportSession;
      if (session && !["canceled", "finalized"].includes(session.state)) await session.cancel().catch(() => {});
      byId("figureSaveStatus").textContent = "Export canceled";
    }

    async function loadExports() {
      const list = byId("figureExportList");
      if (!state.workspaceId) {
        list.textContent = "Open a workspace to view figure exports.";
        return;
      }
      try {
        const payload = await request(`${workspaceBase()}/exports`);
        state.exports = payload.exports || [];
        renderExports();
      } catch (error) {
        list.textContent = `Figure exports could not be loaded: ${error.message}`;
      }
    }

    function renderExports() {
      const list = byId("figureExportList");
      list.replaceChildren();
      for (const item of state.exports) {
        const row = document.createElement("div");
        row.className = "figure-export-item";
        const label = document.createElement("span");
        const outputName = String(item.output_path || item.id).split("/").pop();
        const size = Number(item.size || 0);
        label.innerHTML = `<strong>${escapeHtml(outputName)}</strong><small>${escapeHtml(item.mime_type || "figure export")} · ${item.frame_count || 1} frame${Number(item.frame_count || 1) === 1 ? "" : "s"} · ${(size / 1024 / 1024).toFixed(2)} MiB</small>`;
        const actions = document.createElement("span");
        actions.className = "figure-export-actions";
        const preview = document.createElement("a");
        preview.className = "artifact-link";
        preview.href = `${workspaceBase()}/exports/${item.id}/preview`;
        preview.target = "_blank";
        preview.rel = "noopener noreferrer";
        preview.textContent = "Preview";
        const download = document.createElement("a");
        download.className = "artifact-link";
        download.href = `${workspaceBase()}/exports/${item.id}/download`;
        download.download = outputName || "figure";
        download.textContent = "Download";
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "danger";
        remove.textContent = "Delete";
        remove.addEventListener("click", async () => {
          await request(`${workspaceBase()}/exports/${item.id}`, {method: "DELETE", headers: writeHeaders()});
          await loadExports();
        });
        actions.append(preview, download, remove);
        row.append(label, actions);
        list.append(row);
      }
      if (!state.exports.length) list.textContent = "No composed figures have been exported.";
    }

    async function loadDraft() {
      const workspace = getWorkspace();
      state.workspaceId = workspace?.id || "";
      state.imageCache.clear();
      state.preflight = null;
      if (!state.workspaceId) {
        state.draft = defaultDraft("");
        byId("figureSaveStatus").textContent = "Configure a workspace first";
        return;
      }
      state.loading = true;
      state.draftRevision = 0;
      try {
        const payload = await request(`${workspaceBase()}/draft`);
        state.draft = normalizeDraft(payload.draft, state.workspaceId);
        byId("figureSaveStatus").textContent = "Draft loaded";
      } catch (error) {
        state.draft = defaultDraft(state.workspaceId);
        byId("figureSaveStatus").textContent = "New draft";
      } finally {
        state.loading = false;
      }
      const savedSingleId = state.draft.metadata?.single_layer_id || "";
      const visibleLayers = state.draft.layers.filter((layer) => layer.visible !== false);
      state.selectedLayerId = visibleLayers.some((layer) => layer.id === savedSingleId)
        ? savedSingleId
        : (visibleLayers.at(-1)?.id || state.draft.layers.at(-1)?.id || "");
      if (state.draft.mode === "single") state.draft.metadata.single_layer_id = state.selectedLayerId;
      updateControlsFromDraft();
      renderLayerList();
      invalidatePreflight();
      render();
    }

    async function open() {
      const workspace = getWorkspace();
      if (!workspace) {
        notify("Configure and save a workspace before opening Figure Studio.");
        return;
      }
      root.hidden = false;
      root.ariaHidden = "false";
      document.body.dataset.figureStudioOpen = "true";
      if (state.workspaceId !== workspace.id || state.loading || !state.draft.workspace_id) await loadDraft();
      else {
        updateControlsFromDraft();
        renderLayerList();
        render();
      }
      await loadExports();
    }

    function close() {
      root.hidden = true;
      root.ariaHidden = "true";
      delete document.body.dataset.figureStudioOpen;
    }

    function setWorkspace(workspace) {
      const id = workspace?.id || "";
      if (id !== state.workspaceId) {
        state.workspaceId = id;
        state.draft = defaultDraft("");
        state.imageCache.clear();
        state.preflight = null;
      }
      loadExports();
    }

    function wire() {
      byId("closeFigureStudioButton").addEventListener("click", close);
      byId("figureMode").addEventListener("change", () => {
        const previousMode = state.draft.mode;
        updateDraftFromControls();
        if (state.draft.mode === "mosaic" && previousMode === "single" && !state.draft.metadata.canvas_user_set) {
          state.draft.canvas.width = 1600;
          state.draft.canvas.height = 1200;
          state.draft.metadata.single_aspect_applied_to = "";
          updateControlsFromDraft();
          render();
          scheduleSave();
        }
        if (state.draft.mode === "single" && state.draft.layers.length) {
          state.draft.metadata.single_aspect_applied_to = "";
          applySingleSourceAspect(selectedLayer() || state.draft.layers.at(-1));
        }
      });
      for (const id of ["figureCanvasWidth", "figureCanvasHeight", "figureCanvasBackground", "figureExportScale"]) {
        byId(id).addEventListener("change", () => updateDraftFromControls(false, true));
      }
      for (const id of ["figureTimelineMode", "figureSelectedTime", "figureStartTime", "figureEndTime", "figureSampleInterval", "figurePlaybackFps", "figureAnimationFormat"]) {
        byId(id).addEventListener("change", () => updateDraftFromControls(true, false));
      }
      for (const id of ["figureLayerTitle", "figureLayerX", "figureLayerY", "figureLayerWidth", "figureLayerHeight", "figureLayerTemporalKind", "figureLayerTime", "figureLayerTolerance", "figureLayerFallback"]) {
        byId(id).addEventListener("change", updateSelectedLayerFromControls);
      }
      for (const button of root.querySelectorAll("[data-figure-tool]")) button.addEventListener("click", () => { state.tool = button.dataset.figureTool; updateToolButtons(); });
      byId("figureFitButton").addEventListener("click", () => resetLayer("fit"));
      byId("figureFillButton").addEventListener("click", () => resetLayer("fill"));
      byId("figureCenterButton").addEventListener("click", () => resetLayer("center"));
      byId("figureResetButton").addEventListener("click", () => resetLayer("reset"));
      byId("figureLayerBackward").addEventListener("click", () => moveLayer(-1));
      byId("figureLayerForward").addEventListener("click", () => moveLayer(1));
      byId("figureLayerRemove").addEventListener("click", removeLayer);
      byId("applyFigureTemplateButton").addEventListener("click", () => applyTemplate(byId("figureTemplateSelect").value));
      byId("saveFigureSnapshotButton").addEventListener("click", () => saveSnapshot().catch((error) => notify(error.message)));
      byId("runFigurePreflightButton").addEventListener("click", () => runPreflight().catch(() => {}));
      byId("applyFigureRecommendationButton").addEventListener("click", applyRecommendation);
      byId("exportFigureButton").addEventListener("click", () => exportFigure().catch((error) => notify(error.name === "AbortError" ? "Figure export canceled." : `Figure export failed: ${error.message}`)));
      byId("cancelFigureExportButton").addEventListener("click", cancelExport);
      const canvas = byId("figureCanvas");
      canvas.addEventListener("pointerdown", pointerDown);
      canvas.addEventListener("pointermove", pointerMove);
      canvas.addEventListener("pointerup", pointerUp);
      canvas.addEventListener("pointercancel", pointerUp);
      canvas.addEventListener("wheel", wheelZoom, {passive: false});
      window.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !root.hidden) close();
        if (event.key === "Delete" && !root.hidden && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) removeLayer();
      });
    }

    wire();
    return {open, close, setWorkspace, addPreview, replacePreview, addArtifact, addArtifactSeries, loadExports, serializeDraft, cancelExport};
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>'"]/g, (char) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"}[char]));
  }

  window.RadioFigureComposer = {create, FIGURE_SCHEMA_VERSION};
})();
