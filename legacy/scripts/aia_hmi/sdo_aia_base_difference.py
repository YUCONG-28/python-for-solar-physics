"""Compatibility wrapper for the legacy SDO/AIA base-difference script.

This file is a compatibility wrapper.
Main implementation lives in scripts/aia_hmi/sdo_aia_euv_processor.py.
Legacy defaults are preserved below when possible.

The historical script computed exposure-normalized base differences with:
current frame - first selected frame. The shared processor now owns that
implementation; this wrapper only maps legacy defaults into the main entry
point.
"""

from __future__ import annotations

from pathlib import Path

LEGACY_DEFAULTS = {
    "data_dir": "D:/Flare/JSOCdata/All/AIA_131_pro/",
    "output_dir": "D:/Flare/JSOCdata/All/AIA_131_pro/difference_two_plot_min/",
    "show_plot": False,
    "start_idx": 99,
    "end_idx": 200,
    "wavelength": 131,
    "difference_method": "base",
    "reference_rule": "first selected FITS file, sliced_files[0]",
    "difference_base_index": None,
    "roi_bounds": (180, 520, -340, 20),
    "difference_vmin": -888,
    "difference_vmax": 888,
    "difference_cmap_mode": "band",
    "legacy_cmap": "sdoaia131",
    "legacy_reference_output_name": "{base_filename}.png",
    "legacy_difference_output_name": "{current_filename}_diff_from_base.png",
    "legacy_derotation": "propagate_with_solar_surface around cutout reproject",
    "exposure_normalized": True,
}


def _load_processor():
    try:
        from scripts.aia_hmi.sdo_aia_euv_processor import AIAConfig, process_aia_fits
    except ModuleNotFoundError:  # pragma: no cover - supports direct script execution
        from sdo_aia_euv_processor import AIAConfig, process_aia_fits

    return AIAConfig, process_aia_fits


def build_legacy_config_kwargs() -> dict:
    """Return processor keyword arguments without importing the processor."""

    return {
        "mode": "single",
        "data_path": str(Path(LEGACY_DEFAULTS["data_dir"])),
        "start_idx": int(LEGACY_DEFAULTS["start_idx"]),
        "end_idx": int(LEGACY_DEFAULTS["end_idx"]),
        "roi_bounds": LEGACY_DEFAULTS["roi_bounds"],
        "use_band_subdirs": False,
        "multi_band_wavelengths": (int(LEGACY_DEFAULTS["wavelength"]),),
        "difference_wavelengths": (int(LEGACY_DEFAULTS["wavelength"]),),
        "draw_original": False,
        "draw_difference": True,
        "difference_method": "base",
        "difference_output_mode": "single",
        "difference_base_index": LEGACY_DEFAULTS["difference_base_index"],
        "difference_norm_mode": "fixed",
        "difference_vmin": float(LEGACY_DEFAULTS["difference_vmin"]),
        "difference_vmax": float(LEGACY_DEFAULTS["difference_vmax"]),
        "difference_cmap_mode": str(LEGACY_DEFAULTS["difference_cmap_mode"]),
        "difference_save_reference": False,
        "difference_show_colorbar": False,
        # The main processor applies derotation by full-map reprojection when
        # enabled. Keep it off here to avoid changing the historical subtraction
        # semantics beyond the shared processor's existing implementation.
        "difference_derotate": False,
    }


def build_legacy_config():
    """Map legacy defaults to the shared AIA processor configuration."""

    AIAConfig, _process_aia_fits = _load_processor()
    return AIAConfig(**build_legacy_config_kwargs())


def main() -> None:
    print(
        "Compatibility wrapper: use "
        "scripts/aia_hmi/sdo_aia_euv_processor.py for new AIA base differences."
    )
    print(
        "Running with preserved legacy defaults where the main processor supports them."
    )
    print(
        "Legacy output folder/name patterns are documented in "
        "docs/AIA_WRAPPER_REFACTOR_REPORT.md; the shared processor uses its "
        "standard difference output layout."
    )
    AIAConfig, process_aia_fits = _load_processor()
    process_aia_fits(AIAConfig(**build_legacy_config_kwargs()))


if __name__ == "__main__":
    main()
