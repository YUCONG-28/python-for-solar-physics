const STORAGE_KEYS = {
  settings: "solarToolkit.imageViewer.v1.settings",
  folders: "solarToolkit.imageViewer.v1.folders",
  theme: "solarToolkit.imageViewer.v1.theme",
};

const SUPPORTED_OUTPUT_FORMATS = new Set(["mp4", "gif", "webm"]);
const DEFAULT_OUTPUT_FORMAT = normalizeOutputFormat(document.body?.dataset.defaultOutputFormat || "mp4");

const DEFAULT_SETTINGS = {
  recursive: false,
  fps: 5,
  loop: true,
  layoutMode: "fit",
  syncView: true,
  syncRoi: true,
  outputDir: "outputs/image_web_viewer",
  prefix: "image_viewer",
  quality: "low",
  exportMode: "composite",
  outputFormat: DEFAULT_OUTPUT_FORMAT,
  stopOnClose: true,
  theme: "auto",
};

const PRELOAD_BEHIND_FRAMES = 2;
const PRELOAD_SECONDS_AHEAD = 0.75;
const MIN_PRELOAD_AHEAD_FRAMES = 4;
const MAX_PRELOAD_AHEAD_FRAMES = 24;
const MIN_CACHE_ENTRIES = 96;
const MAX_CACHE_ENTRIES = 256;
const MAX_PRELOAD_CONCURRENCY = 6;

const state = {
  sessionId: null,
  groups: [],
  maxFrames: 0,
  frame: 0,
  animationFrameId: null,
  playbackLastMs: 0,
  playbackAccumulatorMs: 0,
  playing: false,
  roiMode: false,
  activeRoiNorm: null,
  activePanelIndex: null,
  layoutMode: "fit",
  panels: [],
  clientId: makeClientId(),
  serverStopOnClose: true,
  heartbeatTimer: null,
  recording: false,
  mediaRecorder: null,
  recordingChunks: [],
  recordingCanvas: null,
  recordingTimer: null,
  recordingStream: null,
};

const frameCache = new Map();
const preloadQueue = [];
const queuedPreloadKeys = new Set();
let preloadActiveCount = 0;
let cacheTouchCounter = 0;
const mediaTheme = window.matchMedia("(prefers-color-scheme: dark)");

const els = {
  appShell: document.getElementById("appShell"),
  sidebar: document.getElementById("sidebar"),
  sidebarToggleBtn: document.getElementById("sidebarToggleBtn"),
  mobileSidebarBtn: document.getElementById("mobileSidebarBtn"),
  folderInput: document.getElementById("folderInput"),
  recursiveInput: document.getElementById("recursiveInput"),
  loadBtn: document.getElementById("loadBtn"),
  loadStatus: document.getElementById("loadStatus"),
  prevBtn: document.getElementById("prevBtn"),
  playBtn: document.getElementById("playBtn"),
  nextBtn: document.getElementById("nextBtn"),
  fpsInput: document.getElementById("fpsInput"),
  frameSlider: document.getElementById("frameSlider"),
  frameText: document.getElementById("frameText"),
  loopInput: document.getElementById("loopInput"),
  fitLayoutBtn: document.getElementById("fitLayoutBtn"),
  landscapeLayoutBtn: document.getElementById("landscapeLayoutBtn"),
  portraitLayoutBtn: document.getElementById("portraitLayoutBtn"),
  syncViewInput: document.getElementById("syncViewInput"),
  syncRoiInput: document.getElementById("syncRoiInput"),
  roiBtn: document.getElementById("roiBtn"),
  clearRoiBtn: document.getElementById("clearRoiBtn"),
  resetViewBtn: document.getElementById("resetViewBtn"),
  themeInput: document.getElementById("themeInput"),
  saveSettingsBtn: document.getElementById("saveSettingsBtn"),
  clearSettingsBtn: document.getElementById("clearSettingsBtn"),
  settingsStatus: document.getElementById("settingsStatus"),
  stopOnCloseInput: document.getElementById("stopOnCloseInput"),
  formatInput: document.getElementById("formatInput"),
  exportModeInput: document.getElementById("exportModeInput"),
  outputDirInput: document.getElementById("outputDirInput"),
  prefixInput: document.getElementById("prefixInput"),
  qualityInput: document.getElementById("qualityInput"),
  startFrameInput: document.getElementById("startFrameInput"),
  endFrameInput: document.getElementById("endFrameInput"),
  targetWidthInput: document.getElementById("targetWidthInput"),
  targetHeightInput: document.getElementById("targetHeightInput"),
  exportRoiInput: document.getElementById("exportRoiInput"),
  exportBtn: document.getElementById("exportBtn"),
  exportStatus: document.getElementById("exportStatus"),
  recordBtn: document.getElementById("recordBtn"),
  recordStatus: document.getElementById("recordStatus"),
  stageStatus: document.getElementById("stageStatus"),
  viewerGrid: document.getElementById("viewerGrid"),
};

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function normalizeOutputFormat(value) {
  const outputFormat = String(value || "mp4").trim().toLowerCase();
  return SUPPORTED_OUTPUT_FORMATS.has(outputFormat) ? outputFormat : "mp4";
}

function getPlaybackFps() {
  return clamp(Number(els.fpsInput.value) || DEFAULT_SETTINGS.fps, 0.2, 60);
}

function makeClientId() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function getFrameUrl(groupIndex, frameIndex) {
  return `/api/image/${state.sessionId}/${groupIndex}/${frameIndex}`;
}

function setStatus(element, text, isError = false) {
  element.textContent = text;
  element.classList.toggle("error", isError);
}

function setControlsEnabled(enabled) {
  const controls = [
    els.prevBtn,
    els.playBtn,
    els.nextBtn,
    els.frameSlider,
    els.roiBtn,
    els.clearRoiBtn,
    els.resetViewBtn,
    els.exportBtn,
    els.recordBtn,
  ];
  for (const control of controls) control.disabled = !enabled;
}

function loadJson(key, fallback) {
  try {
    const value = localStorage.getItem(key);
    return value ? JSON.parse(value) : fallback;
  } catch {
    return fallback;
  }
}

function saveJson(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    setStatus(els.settingsStatus, "Browser storage is unavailable.", true);
  }
}

function removeStored(key) {
  try {
    localStorage.removeItem(key);
  } catch {
    // Ignore storage cleanup failures in private/restricted browser modes.
  }
}

function collectSettings() {
  return {
    recursive: els.recursiveInput.checked,
    fps: clamp(Number(els.fpsInput.value) || DEFAULT_SETTINGS.fps, 0.2, 60),
    loop: els.loopInput.checked,
    layoutMode: state.layoutMode,
    syncView: els.syncViewInput.checked,
    syncRoi: els.syncRoiInput.checked,
    outputDir: els.outputDirInput.value.trim() || DEFAULT_SETTINGS.outputDir,
    prefix: els.prefixInput.value.trim() || DEFAULT_SETTINGS.prefix,
    quality: els.qualityInput.value,
    exportMode: els.exportModeInput.value,
    outputFormat: normalizeOutputFormat(els.formatInput.value),
    stopOnClose: els.stopOnCloseInput.checked,
    theme: els.themeInput.value,
  };
}

function saveRememberedSettings(showMessage = true) {
  saveJson(STORAGE_KEYS.settings, collectSettings());
  saveJson(STORAGE_KEYS.folders, els.folderInput.value);
  try {
    localStorage.setItem(STORAGE_KEYS.theme, els.themeInput.value);
  } catch {
    // The settings object already captures the theme when storage works.
  }
  if (showMessage) setStatus(els.settingsStatus, "Settings saved in this browser.");
}

function clearRememberedSettings() {
  removeStored(STORAGE_KEYS.settings);
  removeStored(STORAGE_KEYS.folders);
  removeStored(STORAGE_KEYS.theme);
  setStatus(els.settingsStatus, "Remembered settings cleared.");
}

function applyStoredPreferences() {
  const settings = {...DEFAULT_SETTINGS, ...loadJson(STORAGE_KEYS.settings, {})};
  const folders = loadJson(STORAGE_KEYS.folders, null);
  const storedTheme = safeReadStorage(STORAGE_KEYS.theme) || settings.theme || "auto";

  if (typeof folders === "string") els.folderInput.value = folders;
  els.recursiveInput.checked = Boolean(settings.recursive);
  els.fpsInput.value = settings.fps;
  els.loopInput.checked = Boolean(settings.loop);
  els.syncViewInput.checked = settings.syncView !== false;
  els.syncRoiInput.checked = settings.syncRoi !== false;
  els.outputDirInput.value = settings.outputDir || DEFAULT_SETTINGS.outputDir;
  els.prefixInput.value = settings.prefix || DEFAULT_SETTINGS.prefix;
  els.qualityInput.value = settings.quality || DEFAULT_SETTINGS.quality;
  els.exportModeInput.value = settings.exportMode || DEFAULT_SETTINGS.exportMode;
  els.formatInput.value = normalizeOutputFormat(settings.outputFormat || DEFAULT_SETTINGS.outputFormat);
  els.stopOnCloseInput.checked = settings.stopOnClose !== false;
  applyTheme(storedTheme);
  applyLayoutMode(settings.layoutMode || DEFAULT_SETTINGS.layoutMode);
}

function safeReadStorage(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function applyTheme(mode) {
  const themeMode = ["auto", "light", "dark"].includes(mode) ? mode : "auto";
  const resolved = themeMode === "auto"
    ? (mediaTheme.matches ? "dark" : "light")
    : themeMode;
  document.documentElement.dataset.themeMode = themeMode;
  document.documentElement.dataset.theme = resolved;
  els.themeInput.value = themeMode;
}

function updateFrameUI() {
  const total = state.maxFrames;
  els.frameSlider.max = Math.max(total - 1, 0);
  els.frameSlider.value = state.frame;
  els.frameText.textContent = total > 0 ? `${state.frame + 1} / ${total}` : "0 / 0";
  els.startFrameInput.max = Math.max(total, 1);
  els.endFrameInput.max = Math.max(total, 1);
  els.endFrameInput.placeholder = total > 0 ? `last (${total})` : "last";
  els.stageStatus.textContent = total > 0
    ? `${state.groups.length} folder(s), frame ${state.frame + 1} of ${total}`
    : "Load one or more folders to start.";
}

function stopPlayback() {
  if (state.animationFrameId !== null) cancelAnimationFrame(state.animationFrameId);
  state.animationFrameId = null;
  state.playbackAccumulatorMs = 0;
  state.playbackLastMs = 0;
  state.playing = false;
  els.playBtn.textContent = "Play";
}

function startPlayback() {
  if (!state.sessionId || state.maxFrames <= 0) return;
  stopPlayback();
  warmFrameWindow(state.frame, {direction: 1, highPriority: true});
  state.playing = true;
  state.playbackLastMs = performance.now();
  els.playBtn.textContent = "Pause";
  state.animationFrameId = requestAnimationFrame(playbackTick);
}

function playbackTick(now) {
  if (!state.playing) return;
  const fps = getPlaybackFps();
  const frameMs = 1000 / fps;
  state.playbackAccumulatorMs += now - state.playbackLastMs;
  state.playbackLastMs = now;
  let steps = Math.min(4, Math.floor(state.playbackAccumulatorMs / frameMs));
  if (steps > 0) {
    state.playbackAccumulatorMs %= frameMs;
    while (steps > 0 && state.playing) {
      if (!stepFrame(1, {deferUntilReady: true})) break;
      steps -= 1;
    }
  }
  if (state.playing) state.animationFrameId = requestAnimationFrame(playbackTick);
}

function togglePlayback() {
  if (state.playing) stopPlayback();
  else startPlayback();
}

function stepFrame(delta, options = {}) {
  if (state.maxFrames <= 0) return false;
  let nextFrame = state.frame + delta;
  if (nextFrame >= state.maxFrames) {
    if (els.loopInput.checked) nextFrame = nextFrame % state.maxFrames;
    else {
      nextFrame = state.maxFrames - 1;
      stopPlayback();
    }
  }
  if (nextFrame < 0) nextFrame = els.loopInput.checked ? state.maxFrames - 1 : 0;
  return showFrame(nextFrame, {...options, direction: Math.sign(delta) || 1});
}

function showFrame(frameIndex, options = {}) {
  if (state.maxFrames <= 0) return false;
  const targetFrame = clamp(frameIndex, 0, state.maxFrames - 1);
  if (options.deferUntilReady && targetFrame !== state.frame && !isFrameReady(targetFrame)) {
    warmFrameWindow(targetFrame, {direction: options.direction || 1, highPriority: true});
    els.stageStatus.textContent = `Preloading frame ${targetFrame + 1}...`;
    return false;
  }
  state.frame = targetFrame;
  updateFrameUI();
  for (const panel of state.panels) panel.showFrame(state.frame, {deferUntilReady: Boolean(options.deferUntilReady)});
  warmFrameWindow(state.frame, {direction: options.direction || 1});
  return true;
}

async function loadFolders() {
  const folders = els.folderInput.value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
  if (!folders.length) {
    setStatus(els.loadStatus, "Enter at least one folder.", true);
    return;
  }
  if (state.recording) stopLiveRecording();
  stopPlayback();
  setStatus(els.loadStatus, "Loading...");
  setControlsEnabled(false);

  try {
    const response = await fetch("/api/load", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({folders, recursive: els.recursiveInput.checked}),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      throw new Error(payload.error || "Folder load failed.");
    }
    resetFramePreloadState();
    state.sessionId = payload.session_id;
    state.groups = payload.groups;
    state.maxFrames = payload.max_frames || 0;
    state.frame = 0;
    state.activeRoiNorm = null;
    state.activePanelIndex = null;
    renderPanels();
    applyLayoutMode(state.layoutMode);
    updateFrameUI();
    setControlsEnabled(state.maxFrames > 0);
    setStatus(els.loadStatus, `${state.groups.length} folders, ${state.maxFrames} frames.`);
    saveRememberedSettings(false);
    showFrame(0);
  } catch (error) {
    state.sessionId = null;
    state.groups = [];
    state.maxFrames = 0;
    state.panels = [];
    els.viewerGrid.innerHTML = "";
    updateFrameUI();
    setStatus(els.loadStatus, error.message, true);
  }
}

function renderPanels() {
  els.viewerGrid.innerHTML = "";
  state.panels = state.groups.map((group) => {
    const panel = new ImagePanel(group);
    els.viewerGrid.appendChild(panel.root);
    return panel;
  });
  state.viewerResizeObserver?.disconnect();
  state.viewerResizeObserver = new ResizeObserver(() => {
    for (const panel of state.panels) panel.resizeCanvas();
  });
  for (const panel of state.panels) state.viewerResizeObserver.observe(panel.canvas);
}

function applyLayoutMode(mode) {
  state.layoutMode = ["fit", "landscape", "portrait"].includes(mode) ? mode : "fit";
  els.viewerGrid.dataset.layout = state.layoutMode;
  els.viewerGrid.dataset.count = String(state.groups.length);
  for (const button of [els.fitLayoutBtn, els.landscapeLayoutBtn, els.portraitLayoutBtn]) {
    button.classList.toggle("active", button.dataset.layoutMode === state.layoutMode);
  }
  requestAnimationFrame(() => {
    for (const panel of state.panels) panel.resizeCanvas();
  });
}

function resetAllViews() {
  for (const panel of state.panels) panel.resetView();
}

function setActivePanel(panel) {
  state.activePanelIndex = panel.group.index;
  for (const item of state.panels) {
    item.root.classList.toggle("active-source", item === panel);
  }
}

function setGlobalRoi(roi, sourcePanel) {
  state.activeRoiNorm = roi;
  setActivePanel(sourcePanel);
  if (els.syncRoiInput.checked) {
    for (const panel of state.panels) panel.localRoi = roi;
  } else {
    for (const panel of state.panels) panel.localRoi = panel === sourcePanel ? roi : null;
  }
  for (const panel of state.panels) panel.draw();
}

function clearRoi() {
  state.roiMode = false;
  state.activeRoiNorm = null;
  els.roiBtn.classList.remove("active");
  els.exportRoiInput.checked = false;
  for (const panel of state.panels) {
    panel.localRoi = null;
    panel.pendingRoi = null;
    panel.draw();
  }
}

function syncViewFrom(sourcePanel) {
  setActivePanel(sourcePanel);
  if (!els.syncViewInput.checked) return;
  for (const panel of state.panels) {
    if (panel !== sourcePanel) panel.applyView(sourcePanel.view);
  }
}

function readOptionalInt(element) {
  const value = String(element.value || "").trim();
  return value === "" ? null : Number.parseInt(value, 10);
}

function buildExportPayload() {
  const startOneBased = Math.max(1, readOptionalInt(els.startFrameInput) || 1);
  const endOneBased = readOptionalInt(els.endFrameInput);
  return {
    session_id: state.sessionId,
    mode: els.exportModeInput.value,
    format: normalizeOutputFormat(els.formatInput.value),
    output_dir: els.outputDirInput.value.trim() || DEFAULT_SETTINGS.outputDir,
    file_prefix: els.prefixInput.value.trim() || DEFAULT_SETTINGS.prefix,
    fps: clamp(Number(els.fpsInput.value) || DEFAULT_SETTINGS.fps, 0.2, 60),
    quality: els.qualityInput.value,
    start_frame: startOneBased - 1,
    end_frame: endOneBased,
    target_width: readOptionalInt(els.targetWidthInput),
    target_height: readOptionalInt(els.targetHeightInput),
    use_roi: els.exportRoiInput.checked && !!state.activeRoiNorm,
    roi: state.activeRoiNorm,
  };
}

function summarizeExport(payload) {
  const paths = [];
  if (payload.composite?.path) paths.push(payload.composite.path);
  if (payload.separate?.paths) paths.push(...payload.separate.paths);
  if (paths.length) return `Saved ${paths.length} video(s).`;
  if (payload.composite?.reason) return `Composite failed: ${payload.composite.reason}`;
  if (payload.separate?.failures?.length) return payload.separate.failures.join("; ");
  return "Export finished.";
}

async function exportVideo() {
  if (!state.sessionId) return;
  setStatus(els.exportStatus, "Exporting...");
  els.exportBtn.disabled = true;
  try {
    saveRememberedSettings(false);
    const response = await fetch("/api/export-video", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(buildExportPayload()),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "Export failed.");
    setStatus(els.exportStatus, summarizeExport(payload));
  } catch (error) {
    setStatus(els.exportStatus, error.message, true);
  } finally {
    els.exportBtn.disabled = false;
  }
}

function chooseRecordingMimeType() {
  if (!window.MediaRecorder) return "";
  for (const mimeType of [
    "video/webm;codecs=vp9",
    "video/webm;codecs=vp8",
    "video/webm",
  ]) {
    if (MediaRecorder.isTypeSupported(mimeType)) return mimeType;
  }
  return "";
}

function recordingFrameBounds() {
  const rects = state.panels
    .map((panel) => panel.canvas.getBoundingClientRect())
    .filter((rect) => rect.width > 0 && rect.height > 0);
  if (!rects.length) return els.viewerGrid.getBoundingClientRect();
  const left = Math.min(...rects.map((rect) => rect.left));
  const top = Math.min(...rects.map((rect) => rect.top));
  const right = Math.max(...rects.map((rect) => rect.right));
  const bottom = Math.max(...rects.map((rect) => rect.bottom));
  return {
    left,
    top,
    width: right - left,
    height: bottom - top,
  };
}

function ensureRecordingCanvas() {
  if (!state.recordingCanvas) {
    state.recordingCanvas = document.createElement("canvas");
  }
  const bounds = recordingFrameBounds();
  const ratio = window.devicePixelRatio || 1;
  const width = Math.max(320, Math.floor(bounds.width * ratio));
  const height = Math.max(220, Math.floor(bounds.height * ratio));
  if (state.recordingCanvas.width !== width || state.recordingCanvas.height !== height) {
    state.recordingCanvas.width = width;
    state.recordingCanvas.height = height;
  }
  return {canvas: state.recordingCanvas, bounds, ratio};
}

function renderRecordingFrame() {
  const {canvas, bounds, ratio} = ensureRecordingCanvas();
  const ctx = canvas.getContext("2d", {alpha: false});
  ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--stage").trim() || "#11161f";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  for (const panel of state.panels) {
    const rect = panel.canvas.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) continue;
    ctx.drawImage(
      panel.canvas,
      (rect.left - bounds.left) * ratio,
      (rect.top - bounds.top) * ratio,
      rect.width * ratio,
      rect.height * ratio,
    );
  }
}

function resetRecordingState() {
  if (state.recordingTimer !== null) window.clearInterval(state.recordingTimer);
  state.recordingTimer = null;
  if (state.recordingStream) {
    for (const track of state.recordingStream.getTracks()) track.stop();
  }
  state.recordingStream = null;
  state.mediaRecorder = null;
  state.recording = false;
  els.recordBtn.textContent = "Start Recording";
}

async function startLiveRecording() {
  if (!state.sessionId) return;
  if (!window.MediaRecorder || !HTMLCanvasElement.prototype.captureStream) {
    setStatus(els.recordStatus, "This browser cannot record canvas streams.", true);
    return;
  }

  renderRecordingFrame();
  const fps = clamp(Number(els.fpsInput.value) || DEFAULT_SETTINGS.fps, 0.2, 60);
  const mimeType = chooseRecordingMimeType();
  const stream = state.recordingCanvas.captureStream(fps);
  const options = mimeType ? {mimeType} : {};
  state.recordingChunks = [];
  state.recordingStream = stream;
  try {
    state.mediaRecorder = new MediaRecorder(stream, options);
  } catch (error) {
    resetRecordingState();
    setStatus(els.recordStatus, error.message, true);
    return;
  }

  state.mediaRecorder.addEventListener("dataavailable", (event) => {
    if (event.data && event.data.size > 0) state.recordingChunks.push(event.data);
  });
  state.mediaRecorder.addEventListener("stop", () => {
    const blob = new Blob(state.recordingChunks, {type: mimeType || "video/webm"});
    uploadLiveRecording(blob).finally(resetRecordingState);
  });

  const frameMs = Math.max(50, Math.round(1000 / fps));
  state.recordingTimer = window.setInterval(renderRecordingFrame, frameMs);
  state.recording = true;
  els.recordBtn.textContent = "Stop Recording";
  setStatus(els.recordStatus, "Recording...");
  state.mediaRecorder.start();
}

function stopLiveRecording() {
  if (!state.mediaRecorder || state.mediaRecorder.state === "inactive") {
    resetRecordingState();
    return;
  }
  if (state.recordingTimer !== null) window.clearInterval(state.recordingTimer);
  state.recordingTimer = null;
  state.recording = false;
  els.recordBtn.disabled = true;
  els.recordBtn.textContent = "Start Recording";
  setStatus(els.recordStatus, "Saving...");
  state.mediaRecorder.stop();
}

function toggleRecording() {
  if (state.recording) stopLiveRecording();
  else startLiveRecording();
}

async function uploadLiveRecording(blob) {
  if (!blob || blob.size === 0) {
    setStatus(els.recordStatus, "Recording produced no frames.", true);
    return;
  }

  const outputFormat = normalizeOutputFormat(els.formatInput.value);
  const formData = new FormData();
  formData.append("recording", blob, "recording.webm");
  formData.append("format", outputFormat);
  formData.append("output_dir", els.outputDirInput.value.trim() || DEFAULT_SETTINGS.outputDir);
  formData.append("file_prefix", els.prefixInput.value.trim() || DEFAULT_SETTINGS.prefix);
  formData.append("fps", String(clamp(Number(els.fpsInput.value) || DEFAULT_SETTINGS.fps, 0.2, 60)));
  formData.append("quality", els.qualityInput.value);

  try {
    saveRememberedSettings(false);
    const response = await fetch("/api/save-recording", {
      method: "POST",
      body: formData,
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "Recording save failed.");
    setStatus(els.recordStatus, `Saved ${payload.format.toUpperCase()} recording.`);
  } catch (error) {
    setStatus(els.recordStatus, error.message, true);
  } finally {
    els.recordBtn.disabled = !state.sessionId;
  }
}

function cacheKey(groupIndex, frameIndex) {
  return `${state.sessionId}:${groupIndex}:${frameIndex}`;
}

function touchCacheEntry(entry) {
  cacheTouchCounter += 1;
  entry.lastUsedAt = cacheTouchCounter;
}

function getPreloadAheadFrameCount() {
  return Math.round(clamp(
    Math.ceil(getPlaybackFps() * PRELOAD_SECONDS_AHEAD),
    MIN_PRELOAD_AHEAD_FRAMES,
    MAX_PRELOAD_AHEAD_FRAMES,
  ));
}

function getFrameCacheCapacity() {
  const groupCount = Math.max(1, state.groups.length);
  const windowFrames = getPreloadAheadFrameCount() + PRELOAD_BEHIND_FRAMES + 1;
  return Math.round(clamp(windowFrames * groupCount * 2, MIN_CACHE_ENTRIES, MAX_CACHE_ENTRIES));
}

function normalizePreloadFrame(frameIndex) {
  if (state.maxFrames <= 0) return null;
  if (els.loopInput.checked) {
    return ((frameIndex % state.maxFrames) + state.maxFrames) % state.maxFrames;
  }
  if (frameIndex < 0 || frameIndex >= state.maxFrames) return null;
  return frameIndex;
}

function getCachedImageIfReady(groupIndex, frameIndex) {
  const entry = frameCache.get(cacheKey(groupIndex, frameIndex));
  if (!entry || entry.status !== "ready") return null;
  touchCacheEntry(entry);
  return entry.image;
}

function isFrameReady(frameIndex) {
  const normalizedFrame = normalizePreloadFrame(frameIndex);
  if (normalizedFrame === null) return false;
  for (const group of state.groups) {
    if (normalizedFrame >= group.count) continue;
    const entry = frameCache.get(cacheKey(group.index, normalizedFrame));
    if (!entry || !["ready", "error"].includes(entry.status)) return false;
  }
  return true;
}

function loadCachedImage(groupIndex, frameIndex) {
  const key = cacheKey(groupIndex, frameIndex);
  let entry = frameCache.get(key);
  if (entry) {
    touchCacheEntry(entry);
    return entry.promise;
  }

  const image = new Image();
  image.decoding = "async";
  image.loading = "eager";
  const promise = new Promise((resolve, reject) => {
    image.onload = async () => {
      try {
        if (image.decode) await image.decode();
      } catch {
        // Some browsers reject decode for already-loaded images; onload is enough.
      }
      entry.status = "ready";
      touchCacheEntry(entry);
      resolve(image);
    };
    image.onerror = () => {
      entry.status = "error";
      entry.error = new Error("image failed to load");
      touchCacheEntry(entry);
      reject(entry.error);
    };
  });
  entry = {image, promise, status: "loading", lastUsedAt: 0, error: null};
  touchCacheEntry(entry);
  frameCache.set(key, entry);
  image.src = getFrameUrl(groupIndex, frameIndex);
  pruneFrameCache();
  return promise;
}

function pruneFrameCache() {
  const capacity = getFrameCacheCapacity();
  while (frameCache.size > capacity) {
    let oldestKey = null;
    let oldestUsedAt = Number.POSITIVE_INFINITY;
    for (const [key, entry] of frameCache.entries()) {
      if (entry.status === "loading") continue;
      if (entry.lastUsedAt < oldestUsedAt) {
        oldestUsedAt = entry.lastUsedAt;
        oldestKey = key;
      }
    }
    if (oldestKey === null) return;
    frameCache.delete(oldestKey);
  }
}

function queuePreloadImage(groupIndex, frameIndex, highPriority = false) {
  const key = cacheKey(groupIndex, frameIndex);
  const entry = frameCache.get(key);
  if (entry) {
    touchCacheEntry(entry);
    return;
  }
  if (queuedPreloadKeys.has(key)) {
    if (highPriority) {
      const queuedIndex = preloadQueue.findIndex((item) => item.key === key);
      if (queuedIndex > 0) {
        const [item] = preloadQueue.splice(queuedIndex, 1);
        preloadQueue.unshift(item);
      }
    }
    return;
  }
  const item = {groupIndex, frameIndex, key};
  queuedPreloadKeys.add(key);
  if (highPriority) preloadQueue.unshift(item);
  else preloadQueue.push(item);
  processPreloadQueue();
}

function processPreloadQueue() {
  while (preloadActiveCount < MAX_PRELOAD_CONCURRENCY && preloadQueue.length > 0) {
    const item = preloadQueue.shift();
    queuedPreloadKeys.delete(item.key);
    preloadActiveCount += 1;
    loadCachedImage(item.groupIndex, item.frameIndex)
      .catch(() => {})
      .finally(() => {
        preloadActiveCount -= 1;
        pruneFrameCache();
        processPreloadQueue();
      });
  }
}

function warmFrameWindow(frameIndex, options = {}) {
  if (!state.sessionId) return;
  const ahead = getPreloadAheadFrameCount();
  const direction = options.direction === -1 ? -1 : 1;
  const startOffset = direction > 0 ? -PRELOAD_BEHIND_FRAMES : -ahead;
  const endOffset = direction > 0 ? ahead : PRELOAD_BEHIND_FRAMES;
  for (let offset = startOffset; offset <= endOffset; offset += 1) {
    const candidate = normalizePreloadFrame(frameIndex + offset);
    if (candidate === null) continue;
    for (const group of state.groups) {
      if (candidate >= group.count) continue;
      queuePreloadImage(group.index, candidate, Boolean(options.highPriority) || offset === 0);
    }
  }
  pruneFrameCache();
}

function resetFramePreloadState() {
  frameCache.clear();
  preloadQueue.length = 0;
  queuedPreloadKeys.clear();
}

class ImagePanel {
  constructor(group) {
    this.group = group;
    this.view = {scale: 1, centerX: 0.5, centerY: 0.5};
    this.drag = null;
    this.pendingRoi = null;
    this.localRoi = null;
    this.image = new Image();
    this.imageLoaded = false;
    this.currentFrameIndex = -1;
    this.drawRect = null;
    this.drawScheduled = false;

    this.root = document.createElement("article");
    this.root.className = "viewer-slot";
    this.root.innerHTML = `
      <header>
        <div>
          <h2>${escapeHtml(group.name)}</h2>
          <span>${escapeHtml(group.folder)}</span>
        </div>
        <strong>${group.count}</strong>
      </header>
      <div class="canvas-shell">
        <canvas></canvas>
      </div>
      <footer><span class="frame-badge">No frame</span></footer>
    `;
    this.canvas = this.root.querySelector("canvas");
    this.ctx = this.canvas.getContext("2d", {alpha: false});
    this.badge = this.root.querySelector(".frame-badge");
    this.installEvents();
  }

  installEvents() {
    this.canvas.addEventListener("wheel", (event) => {
      event.preventDefault();
      if (!this.imageLoaded) return;
      const point = this.canvasPoint(event);
      const anchor = this.screenToImageNorm(point) || {x: 0.5, y: 0.5};
      const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
      this.zoomAround(point, anchor, this.view.scale * factor);
      syncViewFrom(this);
    });

    this.canvas.addEventListener("mousedown", (event) => {
      this.startDrag(this.canvasPoint(event));
    });

    window.addEventListener("mousemove", (event) => {
      if (!this.drag || this.drag.pointer !== "mouse") return;
      this.updateDrag(this.canvasPoint(event));
    });

    window.addEventListener("mouseup", () => {
      if (this.drag?.pointer === "mouse") this.finishDrag();
    });

    this.canvas.addEventListener("touchstart", (event) => {
      if (event.touches.length === 0) return;
      event.preventDefault();
      if (event.touches.length >= 2 && this.imageLoaded) {
        this.startPinch(event);
      } else {
        this.startDrag(this.canvasPoint(event.touches[0]), "touch");
      }
    }, {passive: false});

    this.canvas.addEventListener("touchmove", (event) => {
      if (!this.drag) return;
      event.preventDefault();
      if (this.drag.type === "pinch" && event.touches.length >= 2) {
        this.updatePinch(event);
      } else if (event.touches.length > 0) {
        this.updateDrag(this.canvasPoint(event.touches[0]));
      }
    }, {passive: false});

    this.canvas.addEventListener("touchend", () => {
      if (this.drag?.pointer === "touch" || this.drag?.type === "pinch") this.finishDrag();
    });

    this.canvas.addEventListener("dblclick", () => this.resetView());
  }

  startDrag(point, pointer = "mouse") {
    setActivePanel(this);
    if (state.roiMode) {
      this.drag = {type: "roi", pointer, start: point, end: point};
      this.pendingRoi = this.drag;
      this.draw();
      return;
    }
    const metrics = this.computeDrawMetrics(this.view.scale);
    this.drag = {
      type: "pan",
      pointer,
      start: point,
      centerX: this.view.centerX,
      centerY: this.view.centerY,
      drawWidth: metrics.drawWidth,
      drawHeight: metrics.drawHeight,
    };
  }

  updateDrag(point) {
    if (!this.drag) return;
    if (this.drag.type === "pan") {
      this.view.centerX = this.drag.centerX - (point.x - this.drag.start.x) / this.drag.drawWidth;
      this.view.centerY = this.drag.centerY - (point.y - this.drag.start.y) / this.drag.drawHeight;
      this.clampView();
      this.draw();
      syncViewFrom(this);
      return;
    }
    if (this.drag.type === "roi") {
      this.drag.end = point;
      this.pendingRoi = this.drag;
      this.draw();
    }
  }

  finishDrag() {
    if (!this.drag) return;
    if (this.drag.type === "roi") {
      const roi = this.roiFromDrag(this.drag);
      if (roi) {
        setGlobalRoi(roi, this);
        els.exportRoiInput.checked = true;
      }
      this.pendingRoi = null;
      this.draw();
    }
    this.drag = null;
  }

  startPinch(event) {
    const first = this.canvasPoint(event.touches[0]);
    const second = this.canvasPoint(event.touches[1]);
    const mid = midpoint(first, second);
    this.drag = {
      type: "pinch",
      pointer: "touch",
      startDistance: distance(first, second),
      startScale: this.view.scale,
      anchor: this.screenToImageNorm(mid) || {x: 0.5, y: 0.5},
    };
    setActivePanel(this);
  }

  updatePinch(event) {
    const first = this.canvasPoint(event.touches[0]);
    const second = this.canvasPoint(event.touches[1]);
    const mid = midpoint(first, second);
    const ratio = distance(first, second) / Math.max(1, this.drag.startDistance);
    this.zoomAround(mid, this.drag.anchor, this.drag.startScale * ratio);
    syncViewFrom(this);
  }

  zoomAround(point, anchor, scale) {
    this.view.scale = clamp(scale, 1, 40);
    const metrics = this.computeDrawMetrics(this.view.scale);
    this.view.centerX = anchor.x - (point.x - this.canvas.width / 2) / metrics.drawWidth;
    this.view.centerY = anchor.y - (point.y - this.canvas.height / 2) / metrics.drawHeight;
    this.clampView();
    this.draw();
  }

  resizeCanvas() {
    const rect = this.canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    const width = Math.max(320, Math.floor(rect.width * ratio));
    const height = Math.max(220, Math.floor(rect.height * ratio));
    if (this.canvas.width !== width || this.canvas.height !== height) {
      this.canvas.width = width;
      this.canvas.height = height;
    }
    this.clampView();
    this.draw();
  }

  showFrame(frameIndex, options = {}) {
    this.currentFrameIndex = frameIndex;
    if (frameIndex >= this.group.count) {
      this.imageLoaded = false;
      this.badge.textContent = "Missing";
      this.draw();
      return;
    }
    this.badge.textContent = `${frameIndex + 1} / ${this.group.count}`;
    const readyImage = getCachedImageIfReady(this.group.index, frameIndex);
    if (readyImage) {
      this.image = readyImage;
      this.imageLoaded = true;
      this.clampView();
      this.draw();
      return;
    }
    const cachedEntry = frameCache.get(cacheKey(this.group.index, frameIndex));
    if (cachedEntry?.status === "error") {
      this.imageLoaded = false;
      this.badge.textContent = "Missing";
      this.draw();
      return;
    }

    const keepCurrentImage = Boolean(options.deferUntilReady && this.imageLoaded);
    if (!keepCurrentImage) {
      this.imageLoaded = false;
      this.draw();
    }
    loadCachedImage(this.group.index, frameIndex)
      .then((image) => {
        if (this.currentFrameIndex !== frameIndex) return;
        this.image = image;
        this.imageLoaded = true;
        this.clampView();
        this.draw();
      })
      .catch(() => {
        if (this.currentFrameIndex !== frameIndex) return;
        if (!keepCurrentImage) this.imageLoaded = false;
        this.badge.textContent = "Missing";
        this.draw();
      });
  }

  applyView(view) {
    this.view = {...view};
    this.clampView();
    this.draw();
  }

  resetView() {
    this.view = {scale: 1, centerX: 0.5, centerY: 0.5};
    this.clampView();
    this.draw();
  }

  computeDrawMetrics(scale = this.view.scale) {
    const width = this.canvas.width || 960;
    const height = this.canvas.height || 640;
    if (!this.imageLoaded) {
      return {drawWidth: width, drawHeight: height, fit: 1};
    }
    const fit = Math.min(width / this.image.naturalWidth, height / this.image.naturalHeight);
    return {
      drawWidth: this.image.naturalWidth * fit * scale,
      drawHeight: this.image.naturalHeight * fit * scale,
      fit,
    };
  }

  clampView() {
    this.view.scale = clamp(Number(this.view.scale) || 1, 1, 40);
    const metrics = this.computeDrawMetrics(this.view.scale);
    this.view.centerX = clampAxisCenter(this.view.centerX, this.canvas.width, metrics.drawWidth);
    this.view.centerY = clampAxisCenter(this.view.centerY, this.canvas.height, metrics.drawHeight);
  }

  draw() {
    if (this.drawScheduled) return;
    this.drawScheduled = true;
    requestAnimationFrame(() => {
      this.drawScheduled = false;
      this.drawNow();
    });
  }

  drawNow() {
    const ctx = this.ctx;
    const width = this.canvas.width || 960;
    const height = this.canvas.height || 640;
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--canvas").trim() || "#0d1117";
    ctx.fillRect(0, 0, width, height);
    this.drawRect = null;

    if (!this.imageLoaded) {
      ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--muted").trim() || "#7d8796";
      ctx.font = `${Math.max(16, Math.round(width / 48))}px system-ui`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(this.badge.textContent === "Missing" ? "Missing frame" : "Loading...", width / 2, height / 2);
      return;
    }

    this.clampView();
    const metrics = this.computeDrawMetrics(this.view.scale);
    const x = width / 2 - this.view.centerX * metrics.drawWidth;
    const y = height / 2 - this.view.centerY * metrics.drawHeight;
    this.drawRect = {x, y, w: metrics.drawWidth, h: metrics.drawHeight};
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, width, height);
    ctx.clip();
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(this.image, x, y, metrics.drawWidth, metrics.drawHeight);
    ctx.restore();

    if (this.localRoi) this.drawRoi(this.localRoi, "#ffcc33");
    if (this.pendingRoi) this.drawDragRoi(this.pendingRoi);
  }

  drawRoi(roi, color) {
    if (!this.drawRect) return;
    const ctx = this.ctx;
    const x = this.drawRect.x + roi.x * this.drawRect.w;
    const y = this.drawRect.y + roi.y * this.drawRect.h;
    const w = roi.w * this.drawRect.w;
    const h = roi.h * this.drawRect.h;
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = Math.max(2, Math.round(this.canvas.width / 420));
    ctx.setLineDash([10, 6]);
    ctx.strokeRect(x, y, w, h);
    ctx.restore();
  }

  drawDragRoi(drag) {
    const roi = this.roiFromDrag(drag);
    if (roi) this.drawRoi(roi, "#49d17d");
  }

  roiFromDrag(drag) {
    if (!this.drawRect) return null;
    const start = this.screenToImageNorm(drag.start);
    const end = this.screenToImageNorm(drag.end);
    if (!start || !end) return null;
    const x1 = clamp(Math.min(start.x, end.x), 0, 1);
    const y1 = clamp(Math.min(start.y, end.y), 0, 1);
    const x2 = clamp(Math.max(start.x, end.x), 0, 1);
    const y2 = clamp(Math.max(start.y, end.y), 0, 1);
    if (x2 - x1 < 0.002 || y2 - y1 < 0.002) return null;
    return {x: x1, y: y1, w: x2 - x1, h: y2 - y1};
  }

  screenToImageNorm(point) {
    if (!this.drawRect) return null;
    return {
      x: (point.x - this.drawRect.x) / this.drawRect.w,
      y: (point.y - this.drawRect.y) / this.drawRect.h,
    };
  }

  canvasPoint(event) {
    const rect = this.canvas.getBoundingClientRect();
    const scaleX = this.canvas.width / rect.width;
    const scaleY = this.canvas.height / rect.height;
    return {
      x: (event.clientX - rect.left) * scaleX,
      y: (event.clientY - rect.top) * scaleY,
    };
  }
}

function clampAxisCenter(center, canvasLength, drawLength) {
  if (!Number.isFinite(center) || drawLength <= 0 || canvasLength <= 0) return 0.5;
  if (drawLength <= canvasLength) return 0.5;
  const margin = canvasLength / (2 * drawLength);
  return clamp(center, margin, 1 - margin);
}

function distance(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function midpoint(a, b) {
  return {x: (a.x + b.x) / 2, y: (a.y + b.y) / 2};
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = String(value);
  return div.innerHTML;
}

function toggleSidebar(forceOpen = null) {
  const collapse = forceOpen === null ? !els.appShell.classList.contains("sidebar-collapsed") : !forceOpen;
  els.appShell.classList.toggle("sidebar-collapsed", collapse);
  els.sidebarToggleBtn.textContent = collapse ? ">>" : "<<";
}

async function initClientLifecycle() {
  try {
    const response = await fetch("/api/client-config");
    const config = await response.json();
    state.serverStopOnClose = Boolean(config.stop_on_close);
    if (!state.serverStopOnClose) {
      els.stopOnCloseInput.checked = false;
      els.stopOnCloseInput.disabled = true;
      els.stopOnCloseInput.title = "This server was started with --keep-alive-after-close.";
    }
    await sendHeartbeat();
    const intervalMs = Number(config.heartbeat_interval_ms) || 5000;
    state.heartbeatTimer = window.setInterval(sendHeartbeat, intervalMs);
  } catch {
    state.serverStopOnClose = false;
  }
}

async function sendHeartbeat() {
  try {
    await fetch("/api/client-heartbeat", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({client_id: state.clientId}),
      keepalive: true,
    });
  } catch {
    // The service may already be stopping; no user action is needed.
  }
}

function notifyClientClose() {
  const payload = JSON.stringify({
    client_id: state.clientId,
    stop_on_close: state.serverStopOnClose && els.stopOnCloseInput.checked,
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
  }).catch(() => {});
}

function installEventHandlers() {
  els.loadBtn.addEventListener("click", loadFolders);
  els.playBtn.addEventListener("click", togglePlayback);
  els.prevBtn.addEventListener("click", () => stepFrame(-1));
  els.nextBtn.addEventListener("click", () => stepFrame(1));
  els.frameSlider.addEventListener("input", () => showFrame(Number(els.frameSlider.value)));
  els.fpsInput.addEventListener("change", () => {
    if (state.playing) startPlayback();
  });
  els.fitLayoutBtn.addEventListener("click", () => applyLayoutMode("fit"));
  els.landscapeLayoutBtn.addEventListener("click", () => applyLayoutMode("landscape"));
  els.portraitLayoutBtn.addEventListener("click", () => applyLayoutMode("portrait"));
  els.roiBtn.addEventListener("click", () => {
    state.roiMode = !state.roiMode;
    els.roiBtn.classList.toggle("active", state.roiMode);
  });
  els.clearRoiBtn.addEventListener("click", clearRoi);
  els.resetViewBtn.addEventListener("click", resetAllViews);
  els.exportBtn.addEventListener("click", exportVideo);
  els.recordBtn.addEventListener("click", toggleRecording);
  els.sidebarToggleBtn.addEventListener("click", () => toggleSidebar());
  els.mobileSidebarBtn.addEventListener("click", () => toggleSidebar(true));
  els.themeInput.addEventListener("change", () => {
    applyTheme(els.themeInput.value);
    saveRememberedSettings(false);
  });
  els.saveSettingsBtn.addEventListener("click", () => saveRememberedSettings(true));
  els.clearSettingsBtn.addEventListener("click", clearRememberedSettings);
  els.syncRoiInput.addEventListener("change", () => {
    if (state.activeRoiNorm && state.activePanelIndex !== null) {
      const source = state.panels.find((panel) => panel.group.index === state.activePanelIndex) || state.panels[0];
      setGlobalRoi(state.activeRoiNorm, source);
    }
  });

  for (const element of [
    els.recursiveInput,
    els.fpsInput,
    els.loopInput,
    els.syncViewInput,
    els.syncRoiInput,
    els.outputDirInput,
    els.prefixInput,
    els.qualityInput,
    els.formatInput,
    els.exportModeInput,
    els.stopOnCloseInput,
  ]) {
    element.addEventListener("change", () => saveRememberedSettings(false));
  }

  window.addEventListener("keydown", (event) => {
    if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) return;
    if (event.code === "Space") {
      event.preventDefault();
      togglePlayback();
    } else if (event.code === "ArrowLeft") {
      stepFrame(-1);
    } else if (event.code === "ArrowRight") {
      stepFrame(1);
    } else if (event.code === "Escape") {
      toggleSidebar(false);
    }
  });

  window.addEventListener("resize", () => {
    for (const panel of state.panels) panel.resizeCanvas();
  });
  window.addEventListener("pagehide", notifyClientClose);
  window.addEventListener("beforeunload", notifyClientClose);
  mediaTheme.addEventListener("change", () => {
    if (els.themeInput.value === "auto") applyTheme("auto");
  });
}

installEventHandlers();
applyStoredPreferences();
toggleSidebar(!window.matchMedia("(max-width: 900px)").matches);
initClientLifecycle();
