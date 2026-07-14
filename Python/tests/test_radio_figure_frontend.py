from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RADIO_HTML = REPO_ROOT / "solar_toolkit/webapp/templates/radio.html"
RADIO_JS = REPO_ROOT / "solar_toolkit/webapp/static/radio.js"
COMPOSER_JS = REPO_ROOT / "solar_toolkit/webapp/static/radio_figure_composer.js"


def test_figure_studio_is_local_english_and_loaded_before_workspace_app():
    template = RADIO_HTML.read_text(encoding="utf-8")
    composer = COMPOSER_JS.read_text(encoding="utf-8")
    combined = template + composer

    assert template.index("radio_figure_composer.js") < template.index("radio.js")
    for marker in (
        "Figure Studio",
        "Add to Figure",
        "Mosaic",
        "Single",
        "Unified Timeline",
        "Run Preflight",
        "Figure Exports",
    ):
        assert marker in combined
    assert not re.search(r"[\u4e00-\u9fff]", combined)
    assert "<iframe" not in combined.casefold()
    assert "https://cdn" not in combined.casefold()


def test_layout_v2_and_action_dom_are_lazy_by_default():
    javascript = RADIO_JS.read_text(encoding="utf-8")
    template = RADIO_HTML.read_text(encoding="utf-8")

    assert "const UI_LAYOUT_VERSION = 2" in javascript
    assert "enabled_modules: required" in javascript
    assert "collapsed_modules: state.modules.map" in javascript
    assert "if (!collapsed)" in javascript
    assert "function mountActionBody(module, action, card)" in javascript
    assert 'card.dataset.mounted === "true"' in javascript
    assert 'data-role="action-body"' in template
    assert 'class="parameter-config"' in template
    assert 'data-role="action-body" class="action-body" hidden' in template


def test_composer_uses_controlled_sources_and_versioned_export_preflight():
    composer = COMPOSER_JS.read_text(encoding="utf-8")

    assert "const FIGURE_SCHEMA_VERSION = 1" in composer
    assert "const normalized = /(?:Z|[+-]\\d{2}:?\\d{2})$/i.test(raw)" in composer
    assert "`${raw}Z`" in composer
    assert 'source?.type === "artifact"' in composer
    assert 'source?.type === "preview"' in composer
    assert (
        "Figure sources must use a registered preview or workspace artifact" in composer
    )
    assert "/sources/previews`" in composer
    assert 'form.append("figure"' in composer
    assert 'form.append("preflight"' in composer
    assert 'form.append("manifest"' in composer
    assert 'form.append("preflight_revision"' in composer
    assert "state.preflightDraft = serializeDraft({activeOnly: true})" in composer
    assert "state.preflight.sample_times_iso" in composer
    assert "buildExportFile(exportDraft, authoritativeTimes)" in composer
    assert "drawComposition(canvas, times[index], false, exportDraft)" in composer
    assert "preflight_layer_matches" in composer
    assert "function applySingleSourceAspect(layer)" in composer
    assert "image.naturalWidth" in composer
    assert "canvas_user_set" in composer
    assert "const MAX_IMAGE_CACHE_ITEMS = 64" in composer
    assert "function trimImageCache" in composer
    assert "state.draftRevision += 1" in composer
    assert "savingRevision === state.draftRevision" in composer
    assert "saveInFlight: null" in composer
    assert "savePending: false" in composer
    assert "state.saveInFlight = drainDraftSaves()" in composer
    assert "while (state.savePending && state.workspaceId)" in composer
    assert "body: {draft: savingDraft}" in composer
    assert "async function cancelExport()" in composer
    assert "duration_s:" in composer
    assert "built.times.length / exportDraft.timeline.playback_fps" in composer
    assert "savedSingleId" in composer
    assert "Advanced time fallback" in RADIO_HTML.read_text(encoding="utf-8")


def test_composer_time_fallback_and_series_contracts_are_explicit():
    javascript = RADIO_JS.read_text(encoding="utf-8")
    composer = COMPOSER_JS.read_text(encoding="utf-8")

    for fallback in ("none", "hold_nearest", "hold_last", "out_of_range_note"):
        assert fallback in composer
    assert "fallback_policy" in composer
    assert "match.source || match" in composer
    assert "frame_index" in composer
    assert "Add adjacent spectrogram input and rebuild Preview" in composer
    assert "Resolve Coverage" in composer
    assert 'new CustomEvent("radio:resolve-spectrogram-coverage"' in composer
    assert "async function replacePreview" in composer
    assert "addPreview, replacePreview" in composer
    assert "recommended common UTC time" in composer
    assert "Requested UTC" in composer
    assert "No common UTC time is available" in composer
    assert "Cancel Export Attempt" in composer
    assert "timeline_decisions" in composer
    assert "layer_decisions" in composer
    assert (
        "All ${allMatches.length} decisions are retained in export provenance"
        in composer
    )
    assert "addSeries.disabled = duplicateTimes.size > 0" in javascript
    assert "item.series_key === artifact.series_key && item.observed_at" in javascript
    assert "figurePreviewMetadata" in javascript
    assert "function figureUtcIsoValue(value)" in javascript
    assert "`${raw}Z`" in javascript
    assert "time_iso: observed" in javascript
    assert "new Date(observed).toISOString()" not in javascript
    assert 'const safeKeys = ["adapter", "title", "kind"' in javascript


def test_spectrogram_coverage_navigation_never_previews_or_runs_automatically():
    javascript = RADIO_JS.read_text(encoding="utf-8")
    start = javascript.index(
        "  function navigateToSpectrogramCoverageResolver(detail = {})"
    )
    end = javascript.index("  function populatePresets()", start)
    resolver = javascript[start:end]

    assert 'const actionId = "rebuild-spectrogram-coverage"' in resolver
    assert "mountActionBody(module, action, card)" in resolver
    assert "body.hidden = false" in resolver
    assert "scrollIntoView" in resolver
    assert "previewAction" not in resolver
    assert "runAction" not in resolver
    assert "/preview" not in resolver
    assert "/runs" not in resolver
    assert 'window.addEventListener("radio:resolve-spectrogram-coverage"' in javascript
    assert 'preview.adapter === "spectrogram-coverage"' in javascript
    assert 'replace.textContent = "Replace Figure Layer"' in javascript
    assert "getFigureComposer().replacePreview({" in javascript
