from __future__ import annotations

from pathlib import Path

from solar_apps.ui.theme import (
    apply_plotly_chrome,
    normalize_theme_mode,
    streamlit_theme_css,
)


def test_theme_mode_defaults_to_auto() -> None:
    assert normalize_theme_mode(None) == "auto"
    assert normalize_theme_mode("unsupported") == "auto"


def test_explicit_streamlit_light_overrides_system_media_tokens() -> None:
    css = streamlit_theme_css("light")
    assert "@media (prefers-color-scheme: dark)" in css
    assert "html:root:root:root" in css
    assert "color-scheme: light" in css
    assert "--solar-bg: #f4f7fb" in css


def test_explicit_streamlit_dark_overrides_system_media_tokens() -> None:
    css = streamlit_theme_css("dark")
    assert "html:root:root:root" in css
    assert "color-scheme: dark" in css
    assert "--solar-bg: #0b1120" in css


def test_auto_streamlit_theme_keeps_live_media_query() -> None:
    css = streamlit_theme_css("auto")
    assert "@media (prefers-color-scheme: dark)" in css
    assert "html:root:root:root" not in css


def test_streamlit_controls_use_source_map_semantic_accent() -> None:
    css = streamlit_theme_css("dark")
    assert '[data-testid="stSelectbox"] div[role="group"]' in css
    assert '[data-testid="stCheckbox"] label[data-selected="true"]' in css
    assert '[data-testid="stRadioOption"][data-selected="true"]' in css
    assert '[data-testid="stSlider"]' in css
    assert "background: var(--solar-accent) !important" in css


def test_streamlit_light_overrides_framework_text_inputs_and_buttons() -> None:
    css = streamlit_theme_css("light")

    assert '[data-testid="stWidgetLabel"] p' in css
    assert '[data-testid="stCaptionContainer"] p' in css
    assert '[data-baseweb="input"] input' in css
    assert '[data-baseweb="select"] input' in css
    assert '[data-testid="stBaseButton-secondary"]' in css
    assert "-webkit-text-fill-color: var(--solar-text) !important" in css
    assert 'button[kind="primary"] :where(p, span)' in css
    assert "color: #ffffff !important" in css


def test_plotly_chrome_does_not_change_scientific_trace_values() -> None:
    import plotly.graph_objects as go

    figure = go.Figure(go.Heatmap(z=[[1.0, 2.0]], colorscale="Hot", zmin=1.0, zmax=2.0))
    before = figure.data[0].to_plotly_json()
    apply_plotly_chrome(figure, "dark")

    assert figure.data[0].to_plotly_json() == before
    assert figure.layout.paper_bgcolor == "#0b1120"


def test_legacy_browser_state_is_read_only_after_whitelisted_import() -> None:
    apps_root = Path(__file__).resolve().parents[3]
    viewer = (
        apps_root / "solar_apps" / "frontends" / "image_viewer" / "static" / "main.js"
    ).read_text(encoding="utf-8")
    radio = (
        apps_root / "solar_apps" / "frontends" / "workbench" / "static" / "radio.js"
    ).read_text(encoding="utf-8")
    state_client = (
        apps_root / "solar_apps" / "ui" / "theme_assets" / "state.js"
    ).read_text(encoding="utf-8")

    assert "localStorage.setItem" not in viewer + radio + state_client
    assert "localStorage.removeItem" not in viewer + radio + state_client
    assert "legacyMappings" in state_client
    assert "MAX_LEGACY_BYTES" in state_client
