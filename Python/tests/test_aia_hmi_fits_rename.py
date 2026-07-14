"""Tests for AIA/HMI FITS filename normalization."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "aia_hmi"
    / "sdo_aia_hmi_fits_rename.py"
)


def load_rename_module():
    spec = importlib.util.spec_from_file_location(
        "sdo_aia_hmi_fits_rename", MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    return path


def test_renames_aia_1600_uv_files(tmp_path):
    module = load_rename_module()
    source = touch(tmp_path / ".2024-01-10T062928Z.1600.image_lev1.fits")

    summary = module.rename_fits_files(tmp_path)

    assert summary.renamed == 1
    assert not source.exists()
    assert (
        tmp_path / "aia.lev1_uv_24s.2024-01-10T062928Z.1600.image_lev1.fits"
    ).exists()


def test_renames_all_aia_euv_wavelengths(tmp_path):
    module = load_rename_module()
    for wavelength in ["94", "131", "171", "193", "211", "304", "335"]:
        touch(tmp_path / f".2025-01-24T033001Z.{wavelength}.image_lev1.fits")

    summary = module.rename_fits_files(tmp_path)

    assert summary.renamed == 7
    for wavelength in ["94", "131", "171", "193", "211", "304", "335"]:
        expected = (
            tmp_path
            / f"aia.lev1_euv_12s.2025-01-24T033001Z.{wavelength}.image_lev1.fits"
        )
        assert expected.exists()


def test_renames_hmi_magnetogram_files_without_leading_dot(tmp_path):
    module = load_rename_module()
    source = touch(tmp_path / "20250124_033000_TAI.2.magnetogram.fits")

    summary = module.rename_fits_files(tmp_path)

    assert summary.renamed == 1
    assert not source.exists()
    assert (tmp_path / "hmi.M_45s.20250124_033000_TAI.2.magnetogram.fits").exists()


def test_skips_already_standard_filename(tmp_path):
    module = load_rename_module()
    source = touch(tmp_path / "aia.lev1_euv_12s.2025-01-24T033001Z.94.image_lev1.fits")

    summary = module.rename_fits_files(tmp_path)

    assert summary.skipped == 1
    assert source.exists()


def test_skips_conflicts_without_overwriting(tmp_path):
    module = load_rename_module()
    source = touch(tmp_path / ".2025-01-24T033001Z.94.image_lev1.fits")
    target = touch(tmp_path / "aia.lev1_euv_12s.2025-01-24T033001Z.94.image_lev1.fits")
    target.write_text("existing", encoding="utf-8")

    summary = module.rename_fits_files(tmp_path)

    assert summary.conflicts == 1
    assert source.exists()
    assert target.read_text(encoding="utf-8") == "existing"


def test_reports_unrecognized_fits_files(tmp_path):
    module = load_rename_module()
    source = touch(tmp_path / "unknown_product.fits")

    summary = module.rename_fits_files(tmp_path)

    assert summary.unrecognized == 1
    assert source.exists()


def test_recursively_renames_subdirectory_files(tmp_path):
    module = load_rename_module()
    source = touch(tmp_path / "nested" / ".2025-01-24T033001Z.171.image_lev1.fits")

    summary = module.rename_fits_files(tmp_path)

    assert summary.renamed == 1
    assert not source.exists()
    assert (
        tmp_path / "nested" / "aia.lev1_euv_12s.2025-01-24T033001Z.171.image_lev1.fits"
    ).exists()


def test_dry_run_does_not_rename(tmp_path):
    module = load_rename_module()
    source = touch(tmp_path / ".2025-01-24T033001Z.304.image_lev1.FITS")

    summary = module.rename_fits_files(tmp_path, dry_run=True)

    assert summary.planned == 1
    assert source.exists()
    assert not (
        tmp_path / "aia.lev1_euv_12s.2025-01-24T033001Z.304.image_lev1.FITS"
    ).exists()


def test_main_uses_code_configured_path_when_cli_path_is_omitted(monkeypatch):
    module = load_rename_module()
    calls = []

    def fake_rename(directory, dry_run=False):
        calls.append((directory, dry_run))
        return module.RenameSummary()

    monkeypatch.setattr(module, "TARGET_FOLDER", "D:/configured/data")
    monkeypatch.setattr(module, "DRY_RUN", True)
    monkeypatch.setattr(module, "rename_fits_files", fake_rename)

    assert module.main([]) == 0
    assert calls == [("D:/configured/data", True)]


def test_main_cli_path_takes_precedence_over_configured_path(monkeypatch):
    module = load_rename_module()
    calls = []

    def fake_rename(directory, dry_run=False):
        calls.append((directory, dry_run))
        return module.RenameSummary()

    monkeypatch.setattr(module, "TARGET_FOLDER", "D:/configured/data")
    monkeypatch.setattr(module, "DRY_RUN", True)
    monkeypatch.setattr(module, "rename_fits_files", fake_rename)

    assert module.main(["D:/cli/data"]) == 0
    assert calls == [("D:/cli/data", True)]


def test_main_dry_run_flag_overrides_false_code_default(monkeypatch):
    module = load_rename_module()
    calls = []

    def fake_rename(directory, dry_run=False):
        calls.append((directory, dry_run))
        return module.RenameSummary()

    monkeypatch.setattr(module, "DRY_RUN", False)
    monkeypatch.setattr(module, "rename_fits_files", fake_rename)

    assert module.main(["D:/cli/data", "--dry-run"]) == 0
    assert calls == [("D:/cli/data", True)]
