(function installSolarToolkitMedia(global) {
  "use strict";

  const SUPPORTED_OUTPUT_FORMATS = new Set(["mp4", "gif", "webm"]);

  function normalizeOutputFormat(value, fallback = "mp4") {
    const normalizedFallback = String(fallback || "mp4").trim().toLowerCase();
    const normalized = String(value || normalizedFallback).trim().toLowerCase().replace(/^\./, "");
    if (SUPPORTED_OUTPUT_FORMATS.has(normalized)) return normalized;
    return SUPPORTED_OUTPUT_FORMATS.has(normalizedFallback) ? normalizedFallback : "mp4";
  }

  function normalizeQuality(value, fallback = "high") {
    const normalizedFallback = String(fallback || "high").trim().toLowerCase();
    const normalized = String(value || normalizedFallback).trim().toLowerCase();
    if (normalized === "low" || normalized === "high") return normalized;
    return normalizedFallback === "low" ? "low" : "high";
  }

  function evenDimension(value, minimum = 2) {
    const floor = Math.max(2, Math.floor(Number(minimum) || 2));
    const parsed = Math.max(floor, Math.floor(Number(value) || floor));
    return parsed % 2 === 0 ? parsed : Math.max(floor, parsed - 1);
  }

  function normalizeEvenSize(width, height, minimumWidth = 2, minimumHeight = 2) {
    return {
      width: evenDimension(width, minimumWidth),
      height: evenDimension(height, minimumHeight),
    };
  }

  function supportsStreamingUpload() {
    if (global.location.protocol !== "https:") return false;
    const navigation = global.performance?.getEntriesByType?.("navigation")?.[0];
    if (!new Set(["h2", "h3"]).has(navigation?.nextHopProtocol)) return false;
    if (!global.ReadableStream || !global.TransformStream || !global.Request) return false;
    try {
      let duplexAccessed = false;
      const request = new Request(global.location.href, {
        method: "POST",
        body: new ReadableStream(),
        get duplex() {
          duplexAccessed = true;
          return "half";
        },
      });
      return duplexAccessed && !request.headers.has("Content-Type");
    } catch {
      return false;
    }
  }

  async function createCanvasRecorder(options) {
    const media = global.Mediabunny;
    const canvas = options?.canvas;
    if (!media || !global.VideoEncoder) {
      throw new Error("This browser does not support deterministic video recording.");
    }
    const isHtmlCanvas = global.HTMLCanvasElement && canvas instanceof global.HTMLCanvasElement;
    const isOffscreenCanvas = global.OffscreenCanvas && canvas instanceof global.OffscreenCanvas;
    if (!isHtmlCanvas && !isOffscreenCanvas) {
      throw new TypeError("A canvas is required for video recording.");
    }

    const requestedFormat = normalizeOutputFormat(options?.format, "mp4");
    const sourceFormat = requestedFormat === "mp4" ? "mp4" : "webm";
    const quality = normalizeQuality(options?.quality, "high");
    const frameRate = Math.max(0.2, Number(options?.fps) || 30);
    const bitrate = quality === "high" ? media.QUALITY_HIGH : media.QUALITY_LOW;
    const codecChoices = sourceFormat === "mp4" ? ["avc"] : ["vp9", "vp8"];
    const codec = await media.getFirstEncodableVideoCodec(codecChoices, {
      width: canvas.width,
      height: canvas.height,
      bitrate,
      framerate: frameRate,
    });
    if (!codec) {
      const label = sourceFormat === "mp4" ? "AVC" : "VP9 or VP8";
      throw new Error(`This browser cannot encode ${label} at the selected size.`);
    }

    const targetMode = options?.targetMode === "stream" ? "stream" : "buffer";
    let target;
    if (targetMode === "stream") {
      if (!options?.writable) throw new TypeError("A writable stream target is required.");
      target = new media.AppendOnlyStreamTarget(options.writable);
    } else {
      target = new media.BufferTarget();
    }
    const outputFormat = sourceFormat === "mp4"
      ? new media.Mp4OutputFormat({fastStart: "fragmented"})
      : new media.WebMOutputFormat(targetMode === "stream" ? {appendOnly: true} : {});
    const output = new media.Output({format: outputFormat, target});
    const videoSource = new media.CanvasSource(canvas, {
      codec,
      bitrate,
      framerate: frameRate,
      latencyMode: "quality",
      keyFrameInterval: 2,
      alpha: "discard",
      contentHint: options?.contentHint || "detail",
    });
    output.addVideoTrack(videoSource, {frameRate});
    await output.start();

    return {
      requestedFormat,
      sourceFormat,
      codec,
      frameRate,
      targetMode,
      get state() {
        return output.state;
      },
      async addFrame(timestamp, duration, encodeOptions = {}) {
        await videoSource.add(timestamp, duration, encodeOptions);
      },
      async finalize() {
        await output.finalize();
        return {
          buffer: targetMode === "buffer" ? target.buffer : null,
          requestedFormat,
          sourceFormat,
          codec,
        };
      },
      async cancel() {
        if (!["canceled", "finalized"].includes(output.state)) await output.cancel();
      },
    };
  }

  global.SolarToolkitMedia = Object.freeze({
    createCanvasRecorder,
    evenDimension,
    normalizeEvenSize,
    normalizeOutputFormat,
    normalizeQuality,
    supportsStreamingUpload,
  });
})(window);
