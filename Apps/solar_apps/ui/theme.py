"""Source Map semantic theme shared by every application frontend."""

from __future__ import annotations

from importlib.resources import files
from typing import Any, Literal

ThemeMode = Literal["auto", "light", "dark"]
THEME_MODES: tuple[ThemeMode, ...] = ("auto", "light", "dark")


def normalize_theme_mode(value: object) -> ThemeMode:
    """Return a supported mode, defaulting invalid or missing values to Auto."""

    candidate = str(value or "auto").strip().casefold()
    return candidate if candidate in THEME_MODES else "auto"  # type: ignore[return-value]


def _asset_text(name: str) -> str:
    return (
        files("solar_apps.ui.theme_assets").joinpath(name).read_text(encoding="utf-8")
    )


def register_theme_assets(app: Any, *, url_prefix: str = "/assets/solar-theme") -> None:
    """Expose the immutable shared CSS and controller from a Flask application."""

    from flask import Response

    endpoint = f"solar_theme_{len(app.url_map._rules)}"
    app.add_url_rule(
        f"{url_prefix}.css",
        endpoint=f"{endpoint}_css",
        view_func=lambda: Response(
            _asset_text("theme.css"), content_type="text/css; charset=utf-8"
        ),
    )
    app.add_url_rule(
        f"{url_prefix}.js",
        endpoint=f"{endpoint}_js",
        view_func=lambda: Response(
            _asset_text("theme.js"),
            content_type="application/javascript; charset=utf-8",
        ),
    )
    app.add_url_rule(
        f"{url_prefix}-state.js",
        endpoint=f"{endpoint}_state_js",
        view_func=lambda: Response(
            _asset_text("state.js"),
            content_type="application/javascript; charset=utf-8",
        ),
    )


def streamlit_theme_css(mode: object = "auto") -> str:
    """Return semantic CSS for Streamlit without altering scientific canvases."""

    selected = normalize_theme_mode(mode)
    css = _asset_text("theme.css")
    streamlit_rules = """
.stApp, [data-testid="stAppViewContainer"] {
  background: var(--solar-bg);
  color: var(--solar-text);
}
[data-testid="stHeader"], [data-testid="stSidebar"] {
  background: var(--solar-surface);
  color: var(--solar-text);
  border-color: var(--solar-border);
}
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea,
[data-testid="stSidebar"] select {
  background: var(--solar-surface-raised);
  color: var(--solar-text);
}
button[kind="primary"] {
  background: var(--solar-accent) !important;
  border-color: var(--solar-accent) !important;
  color: #ffffff !important;
}
button[kind="primary"]:hover {
  background: var(--solar-accent-hover) !important;
  border-color: var(--solar-accent-hover) !important;
}
[data-baseweb="select"] > div {
  background: var(--solar-surface-raised) !important;
  border-color: var(--solar-border) !important;
  color: var(--solar-text) !important;
}
[data-baseweb="select"]:focus-within > div {
  border-color: var(--solar-focus) !important;
  box-shadow: 0 0 0 1px var(--solar-focus) !important;
}
[data-testid="stSelectbox"] div[role="group"] {
  background: var(--solar-surface-raised) !important;
  border-color: var(--solar-border) !important;
  color: var(--solar-text) !important;
}
[data-testid="stSelectbox"] div[role="group"]:has(input:focus) {
  border-color: var(--solar-focus) !important;
  box-shadow: 0 0 0 1px var(--solar-focus) !important;
}
[data-testid="stCheckbox"] label > div:first-of-type {
  border-color: var(--solar-border-strong) !important;
}
[data-testid="stCheckbox"] label[data-selected="true"] > div:first-of-type {
  background: var(--solar-accent) !important;
  border-color: var(--solar-accent) !important;
}
[data-testid="stRadioOption"][data-selected="true"] > div > div > div:first-child {
  background: var(--solar-accent) !important;
}
[data-testid="stSlider"] [role="group"] > div > div:has(input[type="range"]) {
  background: var(--solar-accent) !important;
}
"""
    if selected == "auto":
        return css + streamlit_rules
    tokens = {
        "light": {
            "bg": "#f4f7fb",
            "surface": "#ffffff",
            "muted_surface": "#edf2f8",
            "raised": "#ffffff",
            "text": "#172033",
            "muted": "#5d6b80",
            "border": "#c9d4e3",
            "strong": "#9cabc0",
            "accent": "#2563eb",
            "hover": "#1d4ed8",
            "focus": "#60a5fa",
        },
        "dark": {
            "bg": "#0b1120",
            "surface": "#111a2c",
            "muted_surface": "#182338",
            "raised": "#162137",
            "text": "#e7edf7",
            "muted": "#a9b5c8",
            "border": "#33435d",
            "strong": "#53647e",
            "accent": "#60a5fa",
            "hover": "#93c5fd",
            "focus": "#93c5fd",
        },
    }[selected]
    explicit = f"""
html:root:root:root {{
  color-scheme: {selected};
  --solar-bg: {tokens['bg']};
  --solar-surface: {tokens['surface']};
  --solar-surface-muted: {tokens['muted_surface']};
  --solar-surface-raised: {tokens['raised']};
  --solar-text: {tokens['text']};
  --solar-text-muted: {tokens['muted']};
  --solar-border: {tokens['border']};
  --solar-border-strong: {tokens['strong']};
  --solar-accent: {tokens['accent']};
  --solar-accent-hover: {tokens['hover']};
  --solar-focus: {tokens['focus']};
}}
"""
    return css + explicit + streamlit_rules


def render_streamlit_theme(
    st: Any,
    *,
    frontend_id: str,
    state_store: Any | None = None,
    path_memory: Any | None = None,
) -> ThemeMode:
    """Render persistent theme/reset controls and inject the shared Streamlit skin."""

    saved = state_store.load(default={}) if state_store is not None else {}
    default = normalize_theme_mode(
        saved.get("theme") if isinstance(saved, dict) else None
    )
    key = f"{frontend_id}_theme_mode"
    if key not in st.session_state:
        st.session_state[key] = default
    with st.sidebar:
        selected = normalize_theme_mode(
            st.selectbox(
                "Theme",
                options=list(THEME_MODES),
                index=list(THEME_MODES).index(
                    normalize_theme_mode(st.session_state[key])
                ),
                key=key,
                format_func=lambda value: value.title(),
            )
        )
        if state_store is not None:
            state_store.update({"theme": selected})
        if st.button("Reset UI State", key=f"{frontend_id}_reset_ui_state"):
            remembered_fields = (
                saved.get("fields", {}) if isinstance(saved, dict) else {}
            )
            if state_store is not None:
                state_store.save(
                    {"theme": "auto", "fields": {}, "legacy_imported": True}
                )
            if path_memory is not None:
                path_memory.reset(frontend=frontend_id)
            if isinstance(remembered_fields, dict):
                for field in remembered_fields:
                    st.session_state.pop(str(field), None)
            for item in tuple(st.session_state):
                if item.startswith(f"{frontend_id}_"):
                    del st.session_state[item]
            st.rerun()
    st.markdown(
        f"<style>{streamlit_theme_css(selected)}</style>", unsafe_allow_html=True
    )
    return selected


def apply_plotly_chrome(figure: Any, mode: object) -> Any:
    """Theme Plotly chrome without changing traces, colorscales, or z ranges."""

    selected = normalize_theme_mode(mode)
    if selected == "auto":
        return figure
    dark = selected == "dark"
    figure.update_layout(
        paper_bgcolor="#0b1120" if dark else "#ffffff",
        plot_bgcolor="#111a2c" if dark else "#f4f7fb",
        font={"color": "#e7edf7" if dark else "#172033"},
    )
    grid = "#33435d" if dark else "#c9d4e3"
    figure.update_xaxes(gridcolor=grid, zerolinecolor=grid)
    figure.update_yaxes(gridcolor=grid, zerolinecolor=grid)
    return figure


class QtThemeController:
    """Apply the semantic palette to Qt and follow system changes in Auto mode."""

    def __init__(
        self,
        application: Any,
        *,
        state_store: Any | None = None,
        path_memory: Any | None = None,
        frontend_id: str = "image-composer",
    ) -> None:
        self.application = application
        self.state_store = state_store
        self.path_memory = path_memory
        self.frontend_id = frontend_id
        saved = state_store.load(default={}) if state_store is not None else {}
        self.mode = normalize_theme_mode(
            saved.get("theme") if isinstance(saved, dict) else None
        )
        hints = application.styleHints()
        signal = getattr(hints, "colorSchemeChanged", None)
        if signal is not None:
            signal.connect(self._system_theme_changed)
        self.apply()

    def _system_theme_changed(self, *_args: object) -> None:
        if self.mode == "auto":
            self.apply()

    def effective_mode(self) -> ThemeMode:
        if self.mode != "auto":
            return self.mode
        scheme = str(self.application.styleHints().colorScheme()).casefold()
        return "dark" if "dark" in scheme else "light"

    def set_mode(self, mode: object) -> ThemeMode:
        self.mode = normalize_theme_mode(mode)
        if self.state_store is not None:
            self.state_store.update({"theme": self.mode})
        self.apply()
        return self.mode

    def reset(self) -> None:
        if self.state_store is not None:
            self.state_store.save(
                {"theme": "auto", "fields": {}, "legacy_imported": True}
            )
        if self.path_memory is not None:
            self.path_memory.reset(frontend=self.frontend_id)
        self.mode = "auto"
        self.apply()

    def apply(self) -> None:
        from PySide6.QtGui import QColor, QPalette

        dark = self.effective_mode() == "dark"
        colors = (
            {
                "window": "#0b1120",
                "surface": "#111a2c",
                "alternate": "#182338",
                "text": "#e7edf7",
                "muted": "#a9b5c8",
                "border": "#33435d",
                "accent": "#60a5fa",
                "highlighted": "#071120",
            }
            if dark
            else {
                "window": "#f4f7fb",
                "surface": "#ffffff",
                "alternate": "#edf2f8",
                "text": "#172033",
                "muted": "#5d6b80",
                "border": "#c9d4e3",
                "accent": "#2563eb",
                "highlighted": "#ffffff",
            }
        )
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(colors["window"]))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(colors["text"]))
        palette.setColor(QPalette.ColorRole.Base, QColor(colors["surface"]))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors["alternate"]))
        palette.setColor(QPalette.ColorRole.Text, QColor(colors["text"]))
        palette.setColor(QPalette.ColorRole.Button, QColor(colors["surface"]))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors["text"]))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(colors["accent"]))
        palette.setColor(
            QPalette.ColorRole.HighlightedText, QColor(colors["highlighted"])
        )
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(colors["surface"]))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(colors["text"]))
        palette.setColor(QPalette.ColorRole.Link, QColor(colors["accent"]))
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(colors["muted"]))
        self.application.setPalette(palette)
        self.application.setStyleSheet(
            "QWidget { color: %(text)s; }"
            " QMainWindow, QDialog { background: %(window)s; }"
            " QGroupBox, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,"
            " QListView, QTreeView { background: %(surface)s; border-color: %(border)s; }"
            " QPushButton { background: %(surface)s; border: 1px solid %(border)s;"
            " border-radius: 6px; padding: 5px 9px; }"
            " QPushButton:focus, QLineEdit:focus, QComboBox:focus {"
            " border: 2px solid %(accent)s; }" % colors
        )


__all__ = [
    "THEME_MODES",
    "ThemeMode",
    "apply_plotly_chrome",
    "QtThemeController",
    "normalize_theme_mode",
    "register_theme_assets",
    "render_streamlit_theme",
    "streamlit_theme_css",
]
