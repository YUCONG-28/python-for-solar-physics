"""Machine-readable provenance for radio science products.

English: Record the resolved ROI, thresholds, Gaussian choices, WCS policy,
and Newkirk assumptions beside generated products.

中文：在射电科学输出旁记录最终采用的 ROI、阈值、Gaussian 设置、WCS
策略与 Newkirk 假设，便于复现和真实数据对照。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from .io import write_json_file

__all__ = [
    "build_radio_provenance",
    "resolve_provenance_output_dir",
    "write_radio_provenance",
]

_ROI_MARKERS = ("roi", "extent")
_THRESHOLD_MARKERS = (
    "color_range",
    "fixed_band_vmin",
    "fixed_band_vmax",
    "threshold",
    "percentile",
    "sigma_clip",
    "min_pixels",
    "max_pixels",
    "min_peak",
    "snr",
)
_GAUSSIAN_MARKERS = ("gaussian", "fit_background", "fit_input", "source_mask")
_WCS_MARKERS = ("wcs", "origin", "coordinate")


def _package_version() -> str:
    try:
        return version("solar-physics-toolkit")
    except PackageNotFoundError:
        return "0+unknown"


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _matching_values(config: Mapping[str, Any], markers: tuple[str, ...]) -> dict:
    matches: dict[str, Any] = {}

    def visit(mapping: Mapping[str, Any], prefix: str = "") -> None:
        for raw_key, value in mapping.items():
            key = str(raw_key)
            dotted = f"{prefix}.{key}" if prefix else key
            normalized = key.casefold()
            if any(marker in normalized for marker in markers):
                matches[dotted] = _json_value(value)
            if isinstance(value, Mapping):
                visit(value, dotted)

    visit(config)
    return matches


def build_radio_provenance(
    config: Mapping[str, Any],
    *,
    newkirk_config: Mapping[str, Any] | None = None,
    config_source: str | None = None,
    cli_overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a JSON-safe record of resolved radio science assumptions."""

    resolved = dict(config or {})
    supplied_overrides = {
        str(key): _json_value(value)
        for key, value in dict(cli_overrides or {}).items()
        if value not in (None, "", False)
    }
    return {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "software": {"name": "solar-toolkit", "version": _package_version()},
        "config_source": config_source,
        "precedence": [
            "CLI arguments",
            "explicit configuration file or object",
            "path-only environment variables",
            "package defaults",
        ],
        "cli_overrides": supplied_overrides,
        "science": {
            "roi": _matching_values(resolved, _ROI_MARKERS),
            "thresholds": _matching_values(resolved, _THRESHOLD_MARKERS),
            "gaussian": _matching_values(resolved, _GAUSSIAN_MARKERS),
            "wcs": _matching_values(resolved, _WCS_MARKERS),
            "newkirk": _json_value(dict(newkirk_config or {})),
        },
    }


def resolve_provenance_output_dir(config: Mapping[str, Any]) -> Path | None:
    """Resolve an explicit output directory without falling back to the CWD."""

    output_section = config.get("output", {})
    if not isinstance(output_section, Mapping):
        output_section = {}
    output_dir = output_section.get("output_dir") or config.get("output_dir")
    if not output_dir:
        return None
    base = Path(str(output_dir)).expanduser()
    analysis_subdir = output_section.get("analysis_subdir") or config.get(
        "analysis_subdir"
    )
    if analysis_subdir and str(analysis_subdir).casefold() != "auto":
        base /= str(analysis_subdir)
    return base


def write_radio_provenance(
    output_dir: str | Path,
    config: Mapping[str, Any],
    *,
    newkirk_config: Mapping[str, Any] | None = None,
    config_source: str | None = None,
    cli_overrides: Mapping[str, Any] | None = None,
    filename: str = "radio_run_provenance.json",
) -> Path:
    """Write radio provenance beside generated analysis products."""

    payload = build_radio_provenance(
        config,
        newkirk_config=newkirk_config,
        config_source=config_source,
        cli_overrides=cli_overrides,
    )
    return write_json_file(Path(output_dir) / filename, payload)
