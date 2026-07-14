"""Stable public-export contracts for visualization and web-app modules."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

PUBLIC_EXPORTS = {
    "solar_toolkit.visualization.image_web_viewer.export": {
        "ExportConfig",
        "build_composite_frame",
        "export_composite_video",
        "export_separate_videos",
        "normalize_roi",
        "sanitize_filename",
    },
    "solar_toolkit.visualization.image_web_viewer.media": {
        "MediaProcessingError",
        "normalize_even_size",
        "normalize_output_format",
        "normalize_recording_source_format",
        "probe_video",
        "resolve_ffmpeg",
        "resolve_ffprobe",
        "sanitize_filename",
        "save_browser_recording",
        "save_browser_recording_stream",
        "transcode_recording",
        "write_media_from_frames",
        "write_media_from_paths",
    },
    "solar_toolkit.visualization.image_web_viewer.server": {
        "ClientLifecycle",
        "IMAGE_EXTENSIONS",
        "configured_roots",
        "create_app",
        "is_under_allowed_root",
        "natural_key",
        "normalize_allowed_roots",
        "scan_images",
    },
    "solar_toolkit.visualization.radio_source_trajectory": {
        "FACET_BY_OPTIONS",
        "MARKER_SYMBOL_OPTIONS",
        "PLOT_LAYOUT_FACETS",
        "PLOT_LAYOUT_OVERLAY",
        "PLOT_LAYOUTS",
        "add_lr_compare_segments",
        "aia_colormap_name",
        "aia_plotly_colorscale",
        "apply_aia_colormap_to_uint8",
        "build_trajectory_figure",
        "export_trajectory_html",
        "frequency_marker_key",
        "marker_symbol_for_frequency",
        "normalize_marker_symbol_by_frequency",
        "resolve_theme_palette",
    },
    "solar_toolkit.webapp.cli": {
        "build_parser",
        "main",
        "parse_allowed_roots",
    },
    "solar_toolkit.webapp.registry": {
        "ArchivedReference",
        "FeatureModule",
        "WorkflowRegistry",
        "default_registry",
        "split_cli_arguments",
    },
    "solar_toolkit.webapp.runner": {
        "JobContext",
        "JobRecord",
        "JobRunner",
        "PopenLike",
        "default_python_executable",
        "ensure_allowed_path",
        "normalize_arguments",
        "prepend_conda_dll_paths_to_env",
        "validate_payload_paths",
    },
    "solar_toolkit.webapp.server": {"create_app"},
}


@pytest.mark.parametrize("module_name", sorted(PUBLIC_EXPORTS))
def test_app_module_has_exact_explicit_public_exports(module_name):
    """Each application module exposes only its stable project API."""
    module = importlib.import_module(module_name)
    exports = module.__all__

    assert isinstance(exports, list)
    assert len(exports) == len(set(exports))
    assert set(exports) == PUBLIC_EXPORTS[module_name]
    assert all(not name.startswith("_") for name in exports)
    assert all(hasattr(module, name) for name in exports)


@pytest.mark.parametrize("module_name", sorted(PUBLIC_EXPORTS))
def test_app_star_import_matches_explicit_public_exports(module_name):
    """Star imports do not leak Flask, Plotly, NumPy, or stdlib helpers."""
    namespace: dict[str, object] = {}

    exec(f"from {module_name} import *", {}, namespace)

    assert set(namespace) == PUBLIC_EXPORTS[module_name]


def test_compatibility_media_alias_has_static_explicit_all():
    """Static API checks can inspect the media compatibility source file."""
    path = (
        REPO_ROOT / "solar_toolkit" / "visualization" / "image_web_viewer" / "media.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assignments = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        )
    ]

    assert len(assignments) == 1
    assert (
        set(ast.literal_eval(assignments[0].value))
        == PUBLIC_EXPORTS["solar_toolkit.visualization.image_web_viewer.media"]
    )
