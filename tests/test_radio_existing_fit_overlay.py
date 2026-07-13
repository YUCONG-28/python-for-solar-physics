from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from astropy.io import fits

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_center_csv(path: Path) -> None:
    pd.DataFrame(
        [
            {
                "obs_time": "2025-01-24T04:48:40",
                "freq_mhz": 149.0,
                "polarization": "LCP",
                "center_x_arcsec": 10.0,
                "center_y_arcsec": 20.0,
                "center_method": "threshold",
                "quality_flag": "ok",
                "source_label": "main",
            },
            {
                "obs_time": "2025-01-24T04:48:41",
                "freq_mhz": 149.0,
                "polarization": "LCP",
                "center_x_arcsec": 12.0,
                "center_y_arcsec": 22.0,
                "center_method": "threshold",
                "quality_flag": "ok",
                "source_label": "main",
            },
        ]
    ).to_csv(path, index=False)


def _write_gaussian_csv(path: Path) -> None:
    pd.DataFrame(
        [
            {
                "time": "2025-01-24T04:48:40",
                "freq": 164.0,
                "polarization": "RR+LL",
                "center_x_arcsec": -8.0,
                "center_y_arcsec": 15.0,
                "quality_flag": "ok",
                "overlay_valid": True,
            }
        ]
    ).to_csv(path, index=False)


def _write_aia_fits(path: Path) -> None:
    hdu = fits.PrimaryHDU(data=np.arange(256, dtype=np.float32).reshape(16, 16))
    hdu.header.update(
        {
            "DATE-OBS": "2025-01-24T04:48:40",
            "WAVELNTH": 171,
            "CRPIX1": 8.5,
            "CRPIX2": 8.5,
            "CRVAL1": 0.0,
            "CRVAL2": 0.0,
            "CDELT1": 2.0,
            "CDELT2": 2.0,
            "CUNIT1": "arcsec",
            "CUNIT2": "arcsec",
        }
    )
    hdu.writeto(path)


def test_cli_import_and_help_are_lazy_and_non_interactive():
    code = """
import sys
import solar_toolkit.radio.existing_fit_overlay_cli
assert 'pandas' not in sys.modules
assert 'matplotlib.pyplot' not in sys.modules
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    imported = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert imported.returncode == 0, imported.stderr

    help_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "solar_toolkit.radio.existing_fit_overlay_cli",
            "--help",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert help_result.returncode == 0, help_result.stderr
    assert "--center-csv" in help_result.stdout
    assert "--gaussian-csv" in help_result.stdout
    assert "--aia-fits" in help_result.stdout
    assert "--output-dir" in help_result.stdout


def test_service_renders_existing_tables_with_optional_aia_without_fitting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import matplotlib.pyplot as plt

    from solar_toolkit.radio.existing_fit_overlay import (
        ExistingFitOverlayRequest,
        render_existing_fit_overlay,
    )

    center_csv = tmp_path / "centers.csv"
    gaussian_csv = tmp_path / "gaussian.csv"
    aia_fits = tmp_path / "aia_171.fits"
    _write_center_csv(center_csv)
    _write_gaussian_csv(gaussian_csv)
    _write_aia_fits(aia_fits)
    previous_figures = set(plt.get_fignums())
    monkeypatch.setattr(
        plt,
        "show",
        lambda: (_ for _ in ()).throw(AssertionError("plt.show must not be called")),
    )

    result = render_existing_fit_overlay(
        ExistingFitOverlayRequest(
            center_csv=center_csv,
            gaussian_csv=gaussian_csv,
            aia_fits=aia_fits,
            output_dir=tmp_path / "overlay",
            width=480,
            height=320,
            marker_size=8,
        )
    )

    assert result.rendered_rows == 3
    assert result.image_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert result.metadata_path.is_file()
    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert metadata["fitting_performed"] is False
    assert metadata["row_counts"] == {
        "center_table": 2,
        "gaussian_table": 1,
        "rendered": 3,
    }
    assert metadata["frequencies_mhz"] == [149.0, 164.0]
    assert metadata["center_methods"] == ["gaussian", "threshold"]
    assert metadata["aia_background"]["wavelength"] == "171"
    assert metadata["artifacts"]["overlay_image"] == str(result.image_path)
    assert set(plt.get_fignums()) == previous_figures


@pytest.mark.parametrize("table_kind", ["center", "gaussian"])
def test_service_accepts_either_existing_table(tmp_path: Path, table_kind: str):
    from solar_toolkit.radio.existing_fit_overlay import (
        ExistingFitOverlayRequest,
        render_existing_fit_overlay,
    )

    table_path = tmp_path / f"{table_kind}.csv"
    if table_kind == "center":
        _write_center_csv(table_path)
    else:
        _write_gaussian_csv(table_path)
    request = ExistingFitOverlayRequest(
        center_csv=table_path if table_kind == "center" else None,
        gaussian_csv=table_path if table_kind == "gaussian" else None,
        output_dir=tmp_path / "output",
        width=320,
        height=240,
    )

    result = render_existing_fit_overlay(request)

    assert result.rendered_rows == (2 if table_kind == "center" else 1)
    assert result.image_path.is_file()


def test_service_requires_at_least_one_existing_table(tmp_path: Path):
    from solar_toolkit.radio.existing_fit_overlay import ExistingFitOverlayRequest

    with pytest.raises(ValueError, match="center_csv"):
        ExistingFitOverlayRequest(output_dir=tmp_path)


def test_catalog_exposes_typed_artifact_path_fields_and_runner_validation(
    tmp_path: Path,
):
    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
        get_action,
    )

    action = get_action("context-overlays", "existing-fit-overlay")
    fields = {str(field["name"]): field for field in action.input_schema}
    assert action.command_module == "solar_toolkit.radio.existing_fit_overlay_cli"
    assert action.section == "main"
    assert action.run_required_any_fields == ("center_csv", "gaussian_csv")
    assert action.accepts_artifacts == (
        "center-table",
        "gaussian-table",
        "aia-fits",
    )
    assert action.produces_artifacts == ("overlay-metadata", "overlay-image")
    assert all(fields[name]["path"] for name in ("center_csv", "gaussian_csv"))
    assert fields["aia_fits"]["path"] is True

    allowed = tmp_path / "allowed"
    blocked = tmp_path / "blocked"
    allowed.mkdir()
    blocked.mkdir()
    center_csv = allowed / "centers.csv"
    blocked_csv = blocked / "gaussian.csv"
    _write_center_csv(center_csv)
    _write_gaussian_csv(blocked_csv)
    store = RadioWorkspaceStore(allowed / "output", allowed_roots=[allowed])
    workspace = store.create_workspace(workspace_id="existing-fit-overlay")
    manager = RadioRunManager(
        store,
        repo_root=REPO_ROOT,
        python_executable=sys.executable,
    )
    try:
        resolved = manager.resolve_request(
            workspace.id,
            "context-overlays",
            "existing-fit-overlay",
            {"form": {"center_csv": str(center_csv)}},
        )
        command = resolved["command"]
        assert command[1:3] == [
            "-m",
            "solar_toolkit.radio.existing_fit_overlay_cli",
        ]
        assert command[command.index("--center-csv") + 1] == str(center_csv)
        assert "--output-dir" in command
        with pytest.raises(PermissionError, match="outside allowed roots"):
            manager.resolve_request(
                workspace.id,
                "context-overlays",
                "existing-fit-overlay",
                {"form": {"gaussian_csv": str(blocked_csv)}},
            )
        with pytest.raises(ValueError, match="at least one"):
            manager.start(
                workspace.id,
                "context-overlays",
                "existing-fit-overlay",
                {"form": {}},
            )
    finally:
        manager.close(cancel_running=True)


def test_workspace_action_runs_independently_and_indexes_both_outputs(tmp_path: Path):
    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
    )

    allowed = tmp_path / "allowed"
    allowed.mkdir()
    center_csv = allowed / "centers.csv"
    _write_center_csv(center_csv)
    store = RadioWorkspaceStore(allowed / "output", allowed_roots=[allowed])
    workspace = store.create_workspace(workspace_id="existing-fit-run")
    manager = RadioRunManager(
        store,
        repo_root=REPO_ROOT,
        python_executable=sys.executable,
    )
    try:
        manifest = manager.start(
            workspace.id,
            "context-overlays",
            "existing-fit-overlay",
            {
                "form": {
                    "center_csv": str(center_csv),
                    "width": 320,
                    "height": 240,
                    "markers_only": True,
                }
            },
        )
        completed = manager.wait(workspace.id, manifest.id, timeout=30.0)

        assert completed.status == "succeeded", completed.error
        indexed = {
            artifact.relative_path: artifact.artifact_type
            for artifact in completed.artifacts
        }
        assert indexed == {
            "existing_fit_overlay.png": "overlay-image",
            "existing_fit_overlay_metadata.json": "overlay-metadata",
        }
        assert completed.provenance["dependencies_auto_run"] is False
        assert completed.input_sources == []
    finally:
        manager.close(cancel_running=True)
