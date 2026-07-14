"""Compatibility wrapper for the legacy SDO/AIA running-difference script.

This file is a compatibility wrapper.
Main implementation lives in scripts/aia_hmi/sdo_aia_euv_processor.py.
Legacy defaults are preserved below when possible.

The historical script computed exposure-normalized running differences with:
current frame - immediately previous selected frame. The shared processor now
owns that implementation; this wrapper only maps legacy defaults into the main
entry point.
"""

from __future__ import annotations

from pathlib import Path

LEGACY_DEFAULTS = {
    "data_dir": "data/aia/94",
    "output_dir": "outputs/aia/running_difference/94",
    "show_plot": False,
    "start_idx": 150,
    "end_idx": 450,
    "wavelength": 94,
    "difference_method": "running",
    "reference_rule": "current selected FITS file minus immediately previous selected FITS file",
    "roi_bounds": (600, 1210, -280, 100),
    "difference_vmin": -777,
    "difference_vmax": 777,
    "difference_cmap_mode": "band",
    "legacy_cmap": "sdoaia94",
    "legacy_reference_output_name": "{first_filename}.png",
    "legacy_difference_output_name": "{current_filename}_diff.png",
    "legacy_derotation": "no solar derotation; direct cutout reproject to first cutout WCS",
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
        "difference_method": "running",
        "difference_output_mode": "single",
        "difference_norm_mode": "fixed",
        "difference_vmin": float(LEGACY_DEFAULTS["difference_vmin"]),
        "difference_vmax": float(LEGACY_DEFAULTS["difference_vmax"]),
        "difference_cmap_mode": str(LEGACY_DEFAULTS["difference_cmap_mode"]),
        "difference_save_reference": False,
        "difference_show_colorbar": False,
        "difference_derotate": False,
    }


def build_legacy_config():
    """Map legacy defaults to the shared AIA processor configuration."""

    AIAConfig, _process_aia_fits = _load_processor()
    return AIAConfig(**build_legacy_config_kwargs())


def main() -> None:
    print(
        "Compatibility wrapper: use "
        "scripts/aia_hmi/sdo_aia_euv_processor.py for new AIA running differences."
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
