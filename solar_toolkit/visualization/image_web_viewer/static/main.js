const state = {
  sessionId: null,
  groups: [],
  maxFrames: 0,
  frame: 0,
  timer: null,
  playing: false,
  roiMode: false,
  activeRoiNorm: null,
  panels: [],
};

const els = {
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
  syncZoomInput: document.getElementById("syncZoomInput"),
  roiBtn: document.getElementById("roiBtn"),
  clearRoiBtn: document.getElementById("clearRoiBtn"),
  resetViewBtn: document.getElementById("resetViewBtn"),
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
  viewerGrid: document.getElementById("viewerGrid"),
};

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
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
  ];
  for (const control of controls) control.disabled = !enabled;
}

function updateFrameUI() {
  const total = state.maxFrames;
  els.frameSlider.max = Math.max(total - 1, 0);
  els.frameSlider.value = state.frame;
  els.frameText.textContent = total > 0 ? `${state.frame + 1} / ${total}` : "0 / 0";
  els.startFrameInput.max = Math.max(total, 1);
  els.endFrameInput.max = Math.max(total, 1);
  els.endFrameInput.placeholder = total > 0 ? `last (${total})` : "last";
}

function stopPlayback() {
  if (state.timer) clearInterval(state.timer);
  state.timer = null;
  state.playing = false;
  els.playBtn.textContent = "Play";
}

function startPlayback() {
  if (!state.sessionId || state.maxFrames <= 0) return;
  stopPlayback();
  state.playing = true;
  els.playBtn.textContent = "Pause";
  const fps = clamp(Number(els.fpsInput.value) || 5, 0.2, 60);
  state.timer = setInterval(() => stepFrame(1), Math.max(20, 1000 / fps));
}

function togglePlayback() {
  if (state.playing) stopPlayback();
  else startPlayback();
}

function stepFrame(delta) {
  if (state.maxFrames <= 0) return;
  let nextFrame = state.frame + delta;
  if (nextFrame >= state.maxFrames) {
    if (els.loopInput.checked) nextFrame = 0;
    else {
      nextFrame = state.maxFrames - 1;
      stopPlayback();
    }
  }
  if (nextFrame < 0) nextFrame = els.loopInput.checked ? state.maxFrames - 1 : 0;
  showFrame(nextFrame);
}

function showFrame(frameIndex) {
  if (state.maxFrames <= 0) return;
  state.frame = clamp(frameIndex, 0, state.maxFrames - 1);
  updateFrameUI();
  for (const panel of state.panels) panel.showFrame(state.frame);
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
    state.sessionId = payload.session_id;
    state.groups = payload.groups;
    state.maxFrames = payload.max_frames || 0;
    state.frame = 0;
    state.activeRoiNorm = null;
    renderPanels();
    updateFrameUI();
    setControlsEnabled(state.maxFrames > 0);
    setStatus(els.loadStatus, `${state.groups.length} folders, ${state.maxFrames} frames.`);
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

function resetAllViews() {
  for (const panel of state.panels) panel.resetView();
}

function setGlobalRoi(roi) {
  state.activeRoiNorm = roi;
  for (const panel of state.panels) panel.draw();
}

function clearRoi() {
  state.roiMode = false;
  state.activeRoiNorm = null;
  els.roiBtn.classList.remove("active");
  els.exportRoiInput.checked = false;
  for (const panel of state.panels) {
    panel.pendingRoi = null;
    panel.draw();
  }
}

function syncViewFrom(sourcePanel) {
  if (!els.syncZoomInput.checked) return;
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
    output_dir: els.outputDirInput.value.trim() || "outputs/image_web_viewer",
    file_prefix: els.prefixInput.value.trim() || "image_viewer",
    fps: clamp(Number(els.fpsInput.value) || 5, 0.2, 60),
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

class ImagePanel {
  constructor(group) {
    this.group = group;
    this.view = {scale: 1, offsetX: 0, offsetY: 0};
    this.drag = null;
    this.pendingRoi = null;
    this.image = new Image();
    this.imageLoaded = false;
    this.drawRect = null;

    this.root = document.createElement("article");
    this.root.className = "image-panel";
    this.root.innerHTML = `
      <header>
        <div>
          <h2>${escapeHtml(group.name)}</h2>
          <span>${escapeHtml(group.folder)}</span>
        </div>
        <strong>${group.count}</strong>
      </header>
      <canvas width="960" height="640"></canvas>
      <footer><span class="frame-badge">No frame</span></footer>
    `;
    this.canvas = this.root.querySelector("canvas");
    this.ctx = this.canvas.getContext("2d", {alpha: false});
    this.badge = this.root.querySelector(".frame-badge");

    this.image.onload = () => {
      this.imageLoaded = true;
      this.draw();
    };
    this.image.onerror = () => {
      this.imageLoaded = false;
      this.draw();
    };
    this.installEvents();
  }

  installEvents() {
    this.canvas.addEventListener("wheel", (event) => {
      event.preventDefault();
      if (!this.imageLoaded) return;
      const point = this.canvasPoint(event);
      const previousScale = this.view.scale;
      const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
      this.view.scale = clamp(this.view.scale * factor, 0.2, 20);
      const ratio = this.view.scale / previousScale;
      this.view.offsetX = point.x - (point.x - this.view.offsetX) * ratio;
      this.view.offsetY = point.y - (point.y - this.view.offsetY) * ratio;
      this.draw();
      syncViewFrom(this);
    });

    this.canvas.addEventListener("mousedown", (event) => {
      const point = this.canvasPoint(event);
      if (state.roiMode) {
        this.drag = {type: "roi", start: point, end: point};
        this.pendingRoi = this.drag;
      } else {
        this.drag = {
          type: "pan",
          start: point,
          offsetX: this.view.offsetX,
          offsetY: this.view.offsetY,
        };
      }
    });

    window.addEventListener("mousemove", (event) => {
      if (!this.drag) return;
      const point = this.canvasPoint(event);
      if (this.drag.type === "pan") {
        this.view.offsetX = this.drag.offsetX + point.x - this.drag.start.x;
        this.view.offsetY = this.drag.offsetY + point.y - this.drag.start.y;
        this.draw();
        syncViewFrom(this);
      } else {
        this.drag.end = point;
        this.pendingRoi = this.drag;
        this.draw();
      }
    });

    window.addEventListener("mouseup", () => {
      if (!this.drag) return;
      if (this.drag.type === "roi") {
        const roi = this.roiFromDrag(this.drag);
        if (roi) {
          setGlobalRoi(roi);
          els.exportRoiInput.checked = true;
        }
        this.pendingRoi = null;
      }
      this.drag = null;
    });

    this.canvas.addEventListener("dblclick", () => this.resetView());
  }

  resizeCanvas() {
    this.draw();
  }

  showFrame(frameIndex) {
    if (frameIndex >= this.group.count) {
      this.imageLoaded = false;
      this.badge.textContent = "Missing";
      this.draw();
      return;
    }
    this.badge.textContent = `${frameIndex + 1} / ${this.group.count}`;
    this.imageLoaded = false;
    this.image.src = `${getFrameUrl(this.group.index, frameIndex)}?t=${Date.now()}`;
  }

  applyView(view) {
    this.view = {...view};
    this.draw();
  }

  resetView() {
    this.view = {scale: 1, offsetX: 0, offsetY: 0};
    this.draw();
  }

  draw() {
    const ctx = this.ctx;
    const width = this.canvas.width;
    const height = this.canvas.height;
    ctx.fillStyle = "#0d1117";
    ctx.fillRect(0, 0, width, height);
    this.drawRect = null;

    if (!this.imageLoaded) {
      ctx.fillStyle = "#7d8796";
      ctx.font = "20px system-ui";
      ctx.textAlign = "center";
      ctx.fillText(this.badge.textContent === "Missing" ? "Missing frame" : "Loading...", width / 2, height / 2);
      return;
    }

    const fit = Math.min(width / this.image.naturalWidth, height / this.image.naturalHeight);
    const drawWidth = this.image.naturalWidth * fit * this.view.scale;
    const drawHeight = this.image.naturalHeight * fit * this.view.scale;
    const x = (width - drawWidth) / 2 + this.view.offsetX;
    const y = (height - drawHeight) / 2 + this.view.offsetY;
    this.drawRect = {x, y, w: drawWidth, h: drawHeight};
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(this.image, x, y, drawWidth, drawHeight);

    if (state.activeRoiNorm) this.drawRoi(state.activeRoiNorm, "#ffcc33");
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
    ctx.lineWidth = 3;
    ctx.setLineDash([8, 5]);
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

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = String(value);
  return div.innerHTML;
}

els.loadBtn.addEventListener("click", loadFolders);
els.playBtn.addEventListener("click", togglePlayback);
els.prevBtn.addEventListener("click", () => stepFrame(-1));
els.nextBtn.addEventListener("click", () => stepFrame(1));
els.frameSlider.addEventListener("input", () => showFrame(Number(els.frameSlider.value)));
els.fpsInput.addEventListener("change", () => {
  if (state.playing) startPlayback();
});
els.roiBtn.addEventListener("click", () => {
  state.roiMode = !state.roiMode;
  els.roiBtn.classList.toggle("active", state.roiMode);
});
els.clearRoiBtn.addEventListener("click", clearRoi);
els.resetViewBtn.addEventListener("click", resetAllViews);
els.exportBtn.addEventListener("click", exportVideo);

window.addEventListener("keydown", (event) => {
  if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) return;
  if (event.code === "Space") {
    event.preventDefault();
    togglePlayback();
  } else if (event.code === "ArrowLeft") {
    stepFrame(-1);
  } else if (event.code === "ArrowRight") {
    stepFrame(1);
  }
});
