"""Shared display contract for spatial radio images.

The contract describes presentation-only choices for source maps and reference
maps.  It does not own scientific preprocessing, Gaussian fitting, residual
normalization, spectrogram scaling, light-curve transforms, or overlay
contours.  Those remain workflow-specific scientific decisions.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields, replace
from typing import Any, Literal

import numpy as np

Transform = Literal["linear", "log10"]
RangeMode = Literal["auto", "global", "fixed"]
RangeScope = Literal["frame", "global", "per_band"]
AutoMethod = Literal["percentile", "fixed_percentile", "minmax"]
RenderProfile = Literal["preview", "export"]


@dataclass(frozen=True, slots=True)
class SpatialRadioDisplay:
    """Validated spatial-radio display settings.

    ``vmin`` and ``vmax`` are expressed in the raw intensity unit.  For a
    ``log10`` display they are transformed only when normalization is built.
    ``ui_theme`` is intentionally absent: application chrome must never alter
    scientific exports or their cache identity.
    """

    cmap: str = "hot"
    bad_color: str = "#000080"
    transform: Transform = "linear"
    range_mode: RangeMode = "auto"
    range_scope: RangeScope = "frame"
    auto_method: AutoMethod = "fixed_percentile"
    percentiles: tuple[float, float] = (99.7, 99.99)
    vmin: float | None = None
    vmax: float | None = None
    # Per-band limits are stored in displayed coordinates because existing
    # Source Map and ROI workflows precompute them after transformation.
    band_limits: tuple[tuple[str, float, float], ...] = ()
    unit: str | None = None
    fov: tuple[float, float, float, float] | None = None
    render_profile: RenderProfile = "export"

    def __post_init__(self) -> None:
        if not str(self.cmap).strip():
            raise ValueError("cmap must be non-empty")
        if not str(self.bad_color).strip():
            raise ValueError("bad_color must be non-empty")
        if self.transform not in {"linear", "log10"}:
            raise ValueError("transform must be 'linear' or 'log10'")
        if self.range_mode not in {"auto", "global", "fixed"}:
            raise ValueError("range_mode must be auto, global, or fixed")
        if self.range_scope not in {"frame", "global", "per_band"}:
            raise ValueError("range_scope must be frame, global, or per_band")
        if self.auto_method not in {"percentile", "fixed_percentile", "minmax"}:
            raise ValueError(
                "auto_method must be percentile, fixed_percentile, or minmax"
            )
        low, high = (float(value) for value in self.percentiles)
        if not (0.0 <= low < high <= 100.0):
            raise ValueError("percentiles must satisfy 0 <= low < high <= 100")
        object.__setattr__(self, "percentiles", (low, high))
        for name in ("vmin", "vmax"):
            value = getattr(self, name)
            if value is not None and not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        normalized_band_limits: list[tuple[str, float, float]] = []
        for key, low, high in self.band_limits:
            numeric_low, numeric_high = float(low), float(high)
            if not math.isfinite(numeric_low) or not math.isfinite(numeric_high):
                raise ValueError("band limits must be finite")
            if numeric_low >= numeric_high:
                raise ValueError("each band limit must satisfy vmin < vmax")
            normalized_band_limits.append((str(key), numeric_low, numeric_high))
        object.__setattr__(self, "band_limits", tuple(normalized_band_limits))
        if self.range_mode == "fixed":
            if (self.vmin is None) != (self.vmax is None):
                raise ValueError("fixed shared range requires both vmin and vmax")
            has_shared = self.vmin is not None and self.vmax is not None
            if not has_shared and not self.band_limits:
                raise ValueError("fixed range requires shared or per-band limits")
            if not has_shared:
                pass
            elif float(self.vmin) >= float(self.vmax):
                raise ValueError("vmin must be less than vmax")
            if has_shared and self.transform == "log10" and float(self.vmax) <= 0:
                raise ValueError("log10 fixed range requires vmax > 0")
        if self.unit is not None:
            normalized_unit = str(self.unit).strip()
            object.__setattr__(self, "unit", normalized_unit or None)
        if self.fov is not None:
            values = tuple(float(value) for value in self.fov)
            if len(values) != 4 or not all(math.isfinite(value) for value in values):
                raise ValueError("fov must contain four finite arcsec values")
            xmin, xmax, ymin, ymax = values
            if xmin >= xmax or ymin >= ymax:
                raise ValueError("fov must satisfy xmin < xmax and ymin < ymax")
            object.__setattr__(self, "fov", values)
        if self.render_profile not in {"preview", "export"}:
            raise ValueError("render_profile must be preview or export")

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, Any] | SpatialRadioDisplay | None,
        *,
        base: SpatialRadioDisplay | None = None,
    ) -> SpatialRadioDisplay:
        """Create a contract from canonical or legacy Source Map keys."""

        if isinstance(value, cls):
            return value if base is None else replace(base, **value.to_dict())
        if not value:
            return base or cls()
        raw = dict(value)
        normalized: dict[str, Any] = {}
        aliases = {
            "radio_cmap": "cmap",
            "colormap": "cmap",
            "background_bad_color": "bad_color",
            "radio_colorbar_unit": "unit",
            "color_range_mode": "range_mode",
            "per_band_range_method": "auto_method",
            "per_band_percentiles": "percentiles",
            "fixed_vmin": "vmin",
            "fixed_vmax": "vmax",
            "limits_by_frequency": "band_limits",
            "per_frequency_limits": "band_limits",
            "profile": "render_profile",
        }
        canonical_names = {field.name for field in fields(cls)}
        for key, item in raw.items():
            target = aliases.get(str(key), str(key))
            if target in canonical_names:
                normalized[target] = item
        if isinstance(normalized.get("band_limits"), Mapping):
            normalized["band_limits"] = tuple(
                (str(key), float(limits[0]), float(limits[1]))
                for key, limits in sorted(
                    normalized["band_limits"].items(), key=lambda item: str(item[0])
                )
                if isinstance(limits, (list, tuple)) and len(limits) >= 2
            )
        if "band_limits" not in normalized:
            lows = raw.get("fixed_band_vmins")
            highs = raw.get("fixed_band_vmaxs")
            freqs = raw.get("multi_band_freqs")
            if isinstance(lows, (list, tuple)) and isinstance(highs, (list, tuple)):
                keys = freqs if isinstance(freqs, (list, tuple)) else range(len(lows))
                normalized["band_limits"] = tuple(
                    (str(key), float(low), float(high))
                    for key, low, high in zip(keys, lows, highs)
                )

        legacy_mode = str(normalized.get("range_mode", "")).strip().lower()
        if "transform" in normalized:
            transform = str(normalized["transform"]).strip().lower()
            normalized["transform"] = (
                "log10" if transform in {"log", "log10", "log10 positive"} else "linear"
            )
        if legacy_mode in {"auto percentile", "auto_percentile", "percentile"}:
            normalized["range_mode"] = "auto"
        elif legacy_mode in {"manual", "manual min/max", "manual_minmax"}:
            normalized["range_mode"] = "fixed"
        if legacy_mode == "fixed_per_band":
            normalized["range_mode"] = "auto"
            normalized["range_scope"] = "per_band"
        elif legacy_mode == "global":
            normalized["range_scope"] = "global"
        if "range_scope" not in normalized and "use_per_band_colormap" in raw:
            normalized["range_scope"] = (
                "per_band" if bool(raw["use_per_band_colormap"]) else "global"
            )
        if "range_scope" in normalized:
            scope = str(normalized["range_scope"]).strip().lower()
            normalized["range_scope"] = {
                "per frequency": "per_band",
                "per_frequency": "per_band",
                "shared/global": "global",
                "shared": "global",
            }.get(scope, scope)
        if "percentiles" not in normalized:
            low = raw.get("low_percentile")
            high = raw.get("high_percentile")
            if low not in (None, "") and high not in (None, ""):
                normalized["percentiles"] = (low, high)
        if "vmin" not in normalized and raw.get("manual_min") not in (None, ""):
            normalized["vmin"] = raw["manual_min"]
        if "vmax" not in normalized and raw.get("manual_max") not in (None, ""):
            normalized["vmax"] = raw["manual_max"]
        if "fov" not in normalized and bool(raw.get("use_custom_lim", False)):
            xlim = raw.get("custom_xlim")
            ylim = raw.get("custom_ylim")
            if _pair(xlim) and _pair(ylim):
                normalized["fov"] = (
                    float(xlim[0]),
                    float(xlim[1]),
                    float(ylim[0]),
                    float(ylim[1]),
                )
        if "fov" not in normalized and bool(raw.get("use_custom_fov", False)):
            fov_values = tuple(
                raw.get(key)
                for key in (
                    "x_min_arcsec",
                    "x_max_arcsec",
                    "y_min_arcsec",
                    "y_max_arcsec",
                )
            )
            if all(value not in (None, "") for value in fov_values):
                normalized["fov"] = fov_values
        return replace(base or cls(), **normalized)

    @classmethod
    def resolve(
        cls,
        *,
        source_map_defaults: Mapping[str, Any] | SpatialRadioDisplay | None = None,
        saved: Mapping[str, Any] | SpatialRadioDisplay | None = None,
        event: Mapping[str, Any] | SpatialRadioDisplay | None = None,
        ui_cli: Mapping[str, Any] | SpatialRadioDisplay | None = None,
        scientific_constraints: Mapping[str, Any] | SpatialRadioDisplay | None = None,
    ) -> SpatialRadioDisplay:
        """Resolve settings using the documented low-to-high precedence.

        Source Map defaults < saved settings < event recipe < current UI/CLI
        values < immutable scientific constraints.
        """

        resolved = cls.from_mapping(source_map_defaults)
        for layer in (saved, event, ui_cli, scientific_constraints):
            if layer:
                resolved = cls.from_mapping(layer, base=resolved)
        return resolved

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["percentiles"] = list(self.percentiles)
        if self.fov is not None:
            payload["fov"] = list(self.fov)
        payload["band_limits"] = [list(item) for item in self.band_limits]
        return payload

    def sidecar_payload(self) -> dict[str, Any]:
        """Return schema-1's optional, JSON-safe ``display`` block."""

        return self.to_dict()

    def cache_payload(self) -> dict[str, Any]:
        """Return material display inputs for deterministic cache signatures."""

        return self.to_dict()

    def cache_signature(self) -> str:
        """Hash material display settings; UI theme is not part of the input."""

        encoded = json.dumps(
            self.cache_payload(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def apply_to_legacy_config(self, config: Mapping[str, Any]) -> dict[str, Any]:
        """Return a copy with established Source Map keys synchronized."""

        result = dict(config)
        result["radio_cmap"] = self.cmap
        result["cmap"] = self.cmap
        result["background_bad_color"] = self.bad_color
        result["per_band_range_method"] = self.auto_method
        result["per_band_percentiles"] = list(self.percentiles)
        result["use_per_band_colormap"] = self.range_scope == "per_band"
        result["color_range_mode"] = self.range_mode
        result["fixed_vmin"] = self.vmin
        result["fixed_vmax"] = self.vmax
        if self.band_limits:
            result["fixed_band_vmins"] = [item[1] for item in self.band_limits]
            result["fixed_band_vmaxs"] = [item[2] for item in self.band_limits]
        result["radio_colorbar_unit"] = self.unit
        result["use_custom_lim"] = self.fov is not None
        if self.fov is not None:
            xmin, xmax, ymin, ymax = self.fov
            result["custom_xlim"] = (xmin, xmax)
            result["custom_ylim"] = (ymin, ymax)
        result["_spatial_display"] = self.to_dict()
        return result

    def transformed(self, values: Any) -> np.ndarray:
        """Transform an image for display without mutating scientific input."""

        array = np.asarray(values, dtype=np.float64)
        if self.transform == "linear":
            return array.copy()
        output = np.full(array.shape, np.nan, dtype=np.float64)
        valid = np.isfinite(array) & (array > 0)
        output[valid] = np.log10(array[valid])
        return output

    def display_limits(
        self, values: Any, *, band: str | float | int | None = None
    ) -> tuple[float, float]:
        """Resolve limits in displayed coordinates for one image/sample set."""

        transformed = self.transformed(values)
        finite = transformed[np.isfinite(transformed)]
        if not finite.size:
            return (0.0, 1.0)
        if self.range_mode == "fixed":
            selected_band = None
            if band is not None:
                key = str(band)
                selected_band = next(
                    (
                        (low, high)
                        for name, low, high in self.band_limits
                        if name == key
                    ),
                    None,
                )
            if selected_band is not None:
                return _non_degenerate(*selected_band)
            if self.vmin is None or self.vmax is None:
                return _non_degenerate(*self.band_limits[0][1:])
            raw = np.asarray((self.vmin, self.vmax), dtype=np.float64)
            if self.transform == "log10":
                if raw[0] <= 0:
                    low = float(np.min(finite))
                else:
                    low = math.log10(float(raw[0]))
                high = math.log10(float(raw[1]))
                return _non_degenerate(low, high)
            return _non_degenerate(float(raw[0]), float(raw[1]))
        if self.auto_method == "minmax" or self.range_mode == "global":
            return _non_degenerate(float(np.min(finite)), float(np.max(finite)))
        low, high = np.nanpercentile(finite, self.percentiles)
        return _non_degenerate(float(low), float(high))

    def matplotlib_cmap(self):
        """Return an isolated Matplotlib colormap with the configured bad color."""

        from matplotlib import colormaps

        return colormaps.get_cmap(self.cmap).with_extremes(bad=self.bad_color)


SOURCE_MAP_DISPLAY_DEFAULT = SpatialRadioDisplay()


def spatial_display_for_source_map(
    config: Mapping[str, Any],
    *,
    transform: Transform,
    render_profile: RenderProfile = "export",
) -> SpatialRadioDisplay:
    """Resolve a legacy Source Map config while preserving scientific transform."""

    saved = config.get("saved_display")
    explicit = config.get("spatial_display") or config.get("display_contract")
    return SpatialRadioDisplay.resolve(
        source_map_defaults=SOURCE_MAP_DISPLAY_DEFAULT,
        saved=saved if isinstance(saved, Mapping) else None,
        event=config,
        ui_cli=explicit if isinstance(explicit, Mapping) else None,
        scientific_constraints={
            "transform": transform,
            "render_profile": render_profile,
        },
    )


def spatial_display_for_reference(
    config: Mapping[str, Any] | None,
    *,
    saved: Mapping[str, Any] | None = None,
    event: Mapping[str, Any] | None = None,
    scientific_constraints: Mapping[str, Any] | None = None,
) -> SpatialRadioDisplay:
    """Resolve ROI/Workbench spatial reference settings with the same contract."""

    ui_cli = dict(config or {})
    ui_cli.setdefault("render_profile", "preview")
    return SpatialRadioDisplay.resolve(
        source_map_defaults=SOURCE_MAP_DISPLAY_DEFAULT,
        saved=saved,
        event=event,
        ui_cli=ui_cli,
        scientific_constraints=scientific_constraints,
    )


def _pair(value: Any) -> bool:
    return isinstance(value, (list, tuple)) and len(value) == 2


def _non_degenerate(low: float, high: float) -> tuple[float, float]:
    if low < high:
        return low, high
    delta = max(abs(low) * 1e-6, 1e-12)
    return low - delta, high + delta
