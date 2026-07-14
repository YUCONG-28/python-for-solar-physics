"""Focused contracts for the structured DEM/radio workspace adapter."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_aia(path: Path) -> None:
    image = fits.ImageHDU(data=np.ones((8, 8), dtype=np.float32))
    image.header.update(
        {
            "CDELT1": 2.0,
            "CDELT2": 2.0,
            "CRVAL1": 0.0,
            "CRVAL2": 0.0,
            "CRPIX1": 4.5,
            "CRPIX2": 4.5,
            "RSUN_OBS": 960.0,
            "DATE-OBS": "2025-01-24T04:47:47",
        }
    )
    fits.HDUList([fits.PrimaryHDU(), image]).writeto(path)


def _write_radio(path: Path) -> None:
    yy, xx = np.mgrid[-1:1:8j, -1:1:8j]
    image = np.exp(-((xx**2 + yy**2) / 0.2)).astype(np.float32)
    hdu = fits.PrimaryHDU(data=image)
    hdu.header.update(
        {
            "CDELT1": 4.0,
            "CDELT2": 4.0,
            "CRVAL1": 0.0,
            "CRVAL2": 0.0,
            "CRPIX1": 4.5,
            "CRPIX2": 4.5,
            "DATE-OBS": "2025-01-24T04:47:46",
        }
    )
    hdu.writeto(path)


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    aia = tmp_path / "aia.fits"
    tb = tmp_path / "tb.npy"
    radio = tmp_path / "radio.fits"
    _write_aia(aia)
    np.save(tb, np.linspace(1.0e6, 3.0e6, 64).reshape(8, 8))
    _write_radio(radio)
    return aia, tb, radio


def test_dem_radio_cli_import_and_help_are_non_interactive():
    code = """
import sys
import solar_toolkit.xray_dem.dem_radio_cli
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

    result = subprocess.run(
        [sys.executable, "-m", "solar_toolkit.xray_dem.dem_radio_cli", "--help"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "--aia-fits" in result.stdout
    assert "--tb-data" in result.stdout
    assert "--radio-file" in result.stdout
    assert "--output-dir" in result.stdout


def test_adapter_delegates_plotting_without_show_and_restores_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from solar_toolkit.xray_dem import dem_radio_source_overlay as workflow
    from solar_toolkit.xray_dem.dem_radio_cli import (
        DemRadioOverlayRequest,
        render_dem_radio_overlay,
    )

    aia, tb, radio = _inputs(tmp_path)
    output = tmp_path / "result"
    original_config = workflow.CONFIG
    monkeypatch.setattr(
        workflow.plt,
        "show",
        lambda: (_ for _ in ()).throw(AssertionError("plt.show must not be called")),
    )

    result = render_dem_radio_overlay(
        DemRadioOverlayRequest(
            aia_fits=aia,
            tb_data=tb,
            radio_file=radio,
            output_dir=output,
            display_mode="full",
            dpi=60,
        )
    )

    assert result.image_path.is_file()
    assert result.image_path.stat().st_size > 0
    assert result.metadata_path.is_file()
    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert metadata["schema_version"] == 1
    assert metadata["radio_file"] == radio.name
    assert metadata["tb_shape"] == [8, 8]
    assert metadata["radio_shape"] == [8, 8]
    assert workflow.CONFIG is original_config


def test_adapter_rejects_directory_traversal_in_radio_pattern(tmp_path: Path):
    from solar_toolkit.xray_dem.dem_radio_cli import DemRadioOverlayRequest

    aia, tb, _ = _inputs(tmp_path)
    with pytest.raises(ValueError, match="filename pattern"):
        DemRadioOverlayRequest(
            aia_fits=aia,
            tb_data=tb,
            radio_dir=tmp_path,
            radio_pattern="../outside/*.fits",
            output_dir=tmp_path / "result",
        )


def test_cli_main_maps_structured_arguments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    from solar_toolkit.xray_dem import dem_radio_cli as cli

    aia, tb, radio = _inputs(tmp_path)
    output = tmp_path / "cli-output"
    captured = {}

    def fake_render(request):
        captured["request"] = request
        return cli.DemRadioOverlayResult(
            image_path=output / "dem_radio_overlay.png",
            metadata_path=output / "dem_radio_overlay_metadata.json",
            radio_file=radio,
            aia_time="2025-01-24 04:47:47 UT",
            radio_time="2025-01-24 04:47:46 UT",
            time_difference_seconds=None,
        )

    monkeypatch.setattr(cli, "render_dem_radio_overlay", fake_render)
    assert (
        cli.main(
            [
                "--aia-fits",
                str(aia),
                "--tb-data",
                str(tb),
                "--radio-file",
                str(radio),
                "--display-mode",
                "full",
                "--dpi",
                "72",
                "--output-dir",
                str(output),
            ]
        )
        == 0
    )

    request = captured["request"]
    assert request.aia_fits == aia.resolve()
    assert request.tb_data == tb.resolve()
    assert request.radio_file == radio.resolve()
    assert request.display_mode == "full"
    assert request.dpi == 72
    assert json.loads(capsys.readouterr().out)["radio_file"] == str(radio)


def test_radio_catalog_uses_only_typed_dem_overlay_inputs():
    from solar_toolkit.webapp.radio_workspace import get_action

    action = get_action("context-overlays", "dem-radio-overlay")
    fields = {str(field["name"]): field for field in action.input_schema}

    assert action.command_module == "solar_toolkit.xray_dem.dem_radio_cli"
    assert action.output_flag == "--output-dir"
    assert action.produces_artifacts == ("overlay-metadata", "overlay-image")
    assert action.run_required_fields == ("aia_fits", "tb_data")
    assert action.run_required_any_fields == ("radio_file", "radio_dir")
    assert "arguments" not in fields
    assert all(fields[name]["path"] for name in ("aia_fits", "tb_data"))
    assert all(fields[name]["path"] for name in ("radio_file", "radio_dir"))


def test_workspace_resolver_blocks_dem_inputs_outside_allowed_roots(tmp_path: Path):
    from solar_toolkit.webapp.radio_workspace import (
        RadioRunManager,
        RadioWorkspaceStore,
    )

    allowed = tmp_path / "allowed"
    blocked = tmp_path / "blocked"
    allowed.mkdir()
    blocked.mkdir()
    aia, _, radio = _inputs(allowed)
    blocked_tb = blocked / "tb.npy"
    np.save(blocked_tb, np.ones((8, 8)))
    store = RadioWorkspaceStore(allowed / "output", allowed_roots=[allowed])
    workspace = store.create_workspace(workspace_id="dem-paths")
    manager = RadioRunManager(
        store,
        repo_root=REPO_ROOT,
        python_executable=sys.executable,
    )
    try:
        resolved = manager.resolve_request(
            workspace.id,
            "context-overlays",
            "dem-radio-overlay",
            {
                "form": {
                    "aia_fits": str(aia),
                    "tb_data": str(allowed / "tb.npy"),
                    "radio_file": str(radio),
                }
            },
        )
        command = resolved["command"]
        assert command[1:3] == ["-m", "solar_toolkit.xray_dem.dem_radio_cli"]
        assert command[command.index("--aia-fits") + 1] == str(aia)
        assert command[command.index("--radio-file") + 1] == str(radio)
        assert "--output-dir" in command
        with pytest.raises(PermissionError, match="outside allowed roots"):
            manager.resolve_request(
                workspace.id,
                "context-overlays",
                "dem-radio-overlay",
                {
                    "form": {
                        "aia_fits": str(aia),
                        "tb_data": str(blocked_tb),
                        "radio_file": str(radio),
                    }
                },
            )
    finally:
        manager.close(cancel_running=True)
