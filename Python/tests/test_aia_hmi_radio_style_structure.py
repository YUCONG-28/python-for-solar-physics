"""Lightweight checks for the radio-style AIA/HMI module layout."""

from __future__ import annotations

from pathlib import Path


def test_aia_compatibility_entrypoint_reexports_core_api():
    from scripts.aia_hmi import sdo_aia_euv_processor as compat
    from scripts.aia_hmi.core import aia_cli, aia_config, aia_processor

    assert compat.AIAConfig is aia_config.AIAConfig
    assert compat.process_aia_fits is aia_processor.process_aia_fits
    assert compat.build_parser is aia_cli.build_parser
    assert compat.config_from_args is aia_cli.config_from_args
    assert compat.main is aia_cli.main


def test_recommended_run_entrypoint_delegates_to_core_cli():
    from scripts.aia_hmi import run_aia_euv_processor
    from scripts.aia_hmi.core import aia_cli

    assert run_aia_euv_processor.main is aia_cli.main


def test_aia_cli_builds_existing_mosaic_difference_config():
    from scripts.aia_hmi.core.aia_cli import build_parser, config_from_args

    parser = build_parser()
    args = parser.parse_args(
        [
            "--mode",
            "mosaic",
            "--waves",
            "94",
            "171",
            "--draw-original",
            "--draw-difference",
            "--difference-method",
            "running",
            "--difference-output-mode",
            "both",
            "--difference-vlim-by-wave",
            "94:7",
            "171:34",
            "--mosaic-ncols",
            "2",
        ]
    )

    cfg = config_from_args(args)

    assert cfg.mode == "mosaic"
    assert cfg.multi_band_composite is True
    assert cfg.multi_band_wavelengths == (94, 171)
    assert cfg.difference_wavelengths == (94, 171)
    assert cfg.draw_original is True
    assert cfg.draw_difference is True
    assert cfg.difference_method == "running"
    assert cfg.difference_output_mode == "both"
    assert cfg.difference_vlim_by_wave == {94: 7.0, 171: 34.0}
    assert cfg.mosaic_ncols == 2


def test_aia_io_orders_and_slices_fits_files(tmp_path):
    from scripts.aia_hmi.core.aia_io import resolve_files

    files = [
        tmp_path / "aia.lev1_euv_12s.2025-01-24T033013Z.171.image_lev1.fits",
        tmp_path / "aia.lev1_euv_12s.2025-01-24T033001Z.171.image_lev1.fits",
        tmp_path / "aia.lev1_euv_12s.2025-01-24T033025Z.171.image_lev1.fits",
    ]
    for path in files:
        path.write_text("", encoding="utf-8")

    selected = resolve_files(Path(tmp_path), start_idx=1, end_idx=3)

    assert [path.name for path in selected] == [
        "aia.lev1_euv_12s.2025-01-24T033013Z.171.image_lev1.fits",
        "aia.lev1_euv_12s.2025-01-24T033025Z.171.image_lev1.fits",
    ]


def test_aia_difference_resolves_fixed_limits_without_image_data():
    from scripts.aia_hmi.core.aia_config import AIAConfig
    from scripts.aia_hmi.core.aia_difference import (
        resolve_fixed_difference_limits_for_wave,
    )

    cfg = AIAConfig(
        difference_norm_mode="fixed",
        difference_vmin=-12.0,
        difference_vmax=34.0,
    )

    assert resolve_fixed_difference_limits_for_wave(171, cfg) == (-12.0, 34.0)


def test_aia_mosaic_layout_and_slot_order_are_lightweight():
    from scripts.aia_hmi.core.aia_config import AIAConfig
    from scripts.aia_hmi.core.aia_mosaic import layout_grid, mosaic_slot_wavelengths

    cfg = AIAConfig(
        mode="mosaic",
        multi_band_wavelengths=(94, 171),
        draw_original=True,
        draw_difference=True,
        difference_wavelengths=(171,),
        mosaic_difference_inline=True,
    )

    assert layout_grid(5) == (2, 3)
    assert mosaic_slot_wavelengths(cfg) == (94, 171)
