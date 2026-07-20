"""Single source of truth for the nine applications and ten interfaces."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InterfaceSpec:
    id: str
    title: str
    surface: str
    route: str | None = None


@dataclass(frozen=True)
class FrontendSpec:
    id: str
    title: str
    entry_module: str
    toolkit: str
    interfaces: tuple[InterfaceSpec, ...]


FRONTENDS: tuple[FrontendSpec, ...] = (
    FrontendSpec(
        "workbench",
        "Solar Physics Workbench",
        "solar_apps.frontends.workbench.cli",
        "flask",
        (
            InterfaceSpec("workbench", "Workbench", "browser", "/"),
            InterfaceSpec("radio-workspace", "Radio Workspace", "browser", "/radio"),
        ),
    ),
    FrontendSpec(
        "image-viewer",
        "Image Sequence Viewer",
        "solar_apps.frontends.image_viewer.cli",
        "flask",
        (InterfaceSpec("image-viewer", "Image Viewer", "browser", "/"),),
    ),
    FrontendSpec(
        "image-composer",
        "Image Composer",
        "solar_apps.frontends.image_composer.cli",
        "pyside6",
        (InterfaceSpec("image-composer", "Image Composer", "desktop"),),
    ),
    FrontendSpec(
        "bad-frame-review",
        "Radio Bad Frame Review",
        "solar_apps.frontends.radio_bad_frame_review.cli",
        "flask",
        (InterfaceSpec("bad-frame-review", "Bad Frame Review", "browser", "/"),),
    ),
    FrontendSpec(
        "source-map",
        "Radio Source Map",
        "solar_apps.frontends.radio.source_map.cli",
        "flask",
        (InterfaceSpec("source-map", "Source Map", "browser", "/"),),
    ),
    FrontendSpec(
        "dart-spectrogram",
        "DART Spectrogram",
        "solar_apps.frontends.radio.dart_spectrogram.dart_spectrogram_launcher",
        "streamlit",
        (InterfaceSpec("dart-spectrogram", "DART Spectrogram", "browser"),),
    ),
    FrontendSpec(
        "roi-lightcurve",
        "Radio ROI Light Curve",
        "solar_apps.frontends.radio.roi_lightcurve.roi_lightcurve_launcher",
        "streamlit",
        (InterfaceSpec("roi-lightcurve", "ROI Light Curve", "browser"),),
    ),
    FrontendSpec(
        "radio-composite",
        "Radio Composite Figure",
        "solar_apps.frontends.radio.composite_figure.composite_figure_launcher",
        "streamlit",
        (InterfaceSpec("radio-composite", "Radio Composite Figure", "browser"),),
    ),
    FrontendSpec(
        "source-trajectory",
        "Radio Source Trajectory",
        "solar_apps.frontends.radio.source_trajectory.source_app_launcher",
        "streamlit",
        (InterfaceSpec("source-trajectory", "Source Trajectory", "browser"),),
    ),
)

INTERFACES: tuple[InterfaceSpec, ...] = tuple(
    interface for frontend in FRONTENDS for interface in frontend.interfaces
)


def get_frontend(frontend_id: str) -> FrontendSpec:
    for frontend in FRONTENDS:
        if frontend.id == frontend_id:
            return frontend
    raise KeyError(f"Unknown frontend: {frontend_id}")


__all__ = [
    "FRONTENDS",
    "INTERFACES",
    "FrontendSpec",
    "InterfaceSpec",
    "get_frontend",
]
