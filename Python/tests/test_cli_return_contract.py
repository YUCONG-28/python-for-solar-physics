"""Static and focused behavioral checks for command entry-point contracts."""

from __future__ import annotations

import ast
import inspect
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from typing import get_type_hints

import pytest

PACKAGE_CLI_MODULES = (
    "solar_toolkit.aia.cli",
    "solar_toolkit.aia.lightcurve_extraction",
    "solar_toolkit.aia.lightcurve_plot",
    "solar_toolkit.data.stereo_manifest",
    "solar_toolkit.hmi.fits_rename",
    "solar_toolkit.hmi.overlay_cli",
    "solar_toolkit.net.jsoc",
    "solar_toolkit.radio.centers",
    "solar_toolkit.radio.cli",
    "solar_toolkit.radio.cso_workflow",
    "solar_toolkit.radio.overlay_cli",
    "solar_toolkit.radio.pipeline_cli",
    "solar_toolkit.radio.quicklook",
    "solar_toolkit.radio.raw_quality_cli",
    "solar_toolkit.radio.source_map_cli",
    "solar_toolkit.radio.source_app",
    "solar_toolkit.radio.source_app_launcher",
    "solar_toolkit.radio.trajectory_cli",
    "solar_toolkit.visualization.image_web_viewer.cli",
    "solar_toolkit.visualization.stereo_euvi_overview",
    "solar_toolkit.visualization.stereo_euvi_roi_movie",
    "solar_toolkit.visualization.suvi_quadrant",
    "solar_toolkit.visualization.video_cli",
    "solar_toolkit.webapp.cli",
    "solar_toolkit.xray_dem._flare_summary",
    "solar_toolkit.xray_dem._goes_lightcurve",
    "solar_toolkit.xray_dem._neupert_comparison",
    "solar_toolkit.xray_dem._neupert_timing",
    "solar_toolkit.xray_dem.aia_dem_inversion",
    "solar_toolkit.xray_dem.aia_hxi_overlay",
    "solar_toolkit.xray_dem.dem_radio_source_overlay",
    "solar_toolkit.xray_dem.hxi_image",
    "solar_toolkit.xray_dem.hxi_lightcurve",
    "solar_toolkit.xray_dem.hxi_sxr_comparison",
)

THIN_PUBLIC_SCRIPT_MODULES = (
    "scripts.aia_hmi.run_aia_euv_processor",
    "scripts.aia_hmi.sdo_aia_jsoc_download_20250124",
    "scripts.aia_hmi.sdo_aia_lightcurve_extraction",
    "scripts.aia_hmi.sdo_aia_lightcurve_plot",
    "scripts.aia_hmi.sdo_aia_time_distance_diagram",
    "scripts.aia_hmi.sdo_aia_hmi_fits_rename",
    "scripts.aia_hmi.sdo_aia_hmi_overlay",
    "scripts.aia_hmi.sdo_hmi_magnetogram_plot",
    "scripts.data_download.goes_suvi_download_20250124",
    "scripts.data_download.solo_eui_soar_query_download",
    "scripts.data_download.stereo_a_euvi_download_20250124",
    "scripts.lasco_cme.soho_lasco_data_download",
    "scripts.lasco_cme.soho_lasco_image_plot",
    "scripts.lasco_cme.soho_lasco_running_difference",
    "scripts.radio.export_radio_source_trajectory",
    "scripts.radio.extract_radio_centers",
    "scripts.radio.run_aia_radio_hmi_overlay",
    "scripts.radio.run_radio_burst_pipeline",
    "scripts.radio.run_radio_raw_quality",
    "scripts.radio.run_radio_source_app_managed",
    "scripts.radio.run_radio_source_map",
    "scripts.stereo_suvi.goes_suvi_0448_quadrant_plot",
    "scripts.stereo_suvi.stereo_euvi_0448_overview_plot",
    "scripts.stereo_suvi.stereo_euvi_manifest_by_wavelength",
    "scripts.stereo_suvi.stereo_euvi_roi_movie",
    "scripts.tools.image_sequence_to_video",
    "scripts.tools.run_image_web_viewer",
    "scripts.tools.run_solar_webapp",
    "scripts.xray_dem.flare_aia_sxr_hxr_summary_plot",
    "scripts.xray_dem.goes_sxr_lightcurve_plot",
    "scripts.xray_dem.asos_hxi_goes_sxr_comparison",
    "scripts.xray_dem.asos_hxi_image_plot",
    "scripts.xray_dem.dem_radio_source_overlay",
    "scripts.xray_dem.hessi_hxr_lightcurve_plot",
    "scripts.xray_dem.neupert_sxr_derivative_hxr_comparison",
    "scripts.xray_dem.neupert_timing_error_analysis",
    "scripts.xray_dem.sdo_aia_asos_hxi_overlay",
    "scripts.xray_dem.sdo_aia_dem_inversion",
)

CONTRACT_ONLY_SCRIPT_PATHS = ()


@pytest.mark.parametrize("module_name", PACKAGE_CLI_MODULES)
def test_package_cli_main_has_argv_and_integer_return(module_name):
    main = import_module(module_name).main
    signature = inspect.signature(main)

    assert signature.parameters["argv"].default is None
    assert get_type_hints(main)["return"] is int


@pytest.mark.parametrize("module_name", THIN_PUBLIC_SCRIPT_MODULES)
def test_thin_public_script_main_has_argv_and_integer_return(module_name):
    main = import_module(module_name).main
    signature = inspect.signature(main)

    assert signature.parameters["argv"].default is None
    assert get_type_hints(main)["return"] is int


@pytest.mark.parametrize("script_path", CONTRACT_ONLY_SCRIPT_PATHS, ids=str)
def test_standalone_script_main_contract_is_static_and_explicit(script_path):
    tree = ast.parse(script_path.read_text(encoding="utf-8-sig"), filename=script_path)
    main = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )

    positional = [*main.args.posonlyargs, *main.args.args]
    assert [argument.arg for argument in positional] == ["argv"]
    assert len(main.args.defaults) == 1
    assert isinstance(main.args.defaults[0], ast.Constant)
    assert main.args.defaults[0].value is None
    assert isinstance(main.returns, ast.Name)
    assert main.returns.id == "int"
    assert all(
        return_node.value is not None
        for return_node in ast.walk(main)
        if isinstance(return_node, ast.Return)
    )

    main_guard = next(
        node
        for node in tree.body
        if isinstance(node, ast.If) and "__main__" in ast.unparse(node.test)
    )
    assert len(main_guard.body) == 1
    exit_statement = main_guard.body[0]
    assert isinstance(exit_statement, ast.Raise)
    assert isinstance(exit_statement.exc, ast.Call)
    assert isinstance(exit_statement.exc.func, ast.Name)
    assert exit_statement.exc.func.id == "SystemExit"
    assert ast.unparse(exit_statement.exc.args[0]) == "main()"


def test_radio_data_returning_workflows_are_wrapped_by_integer_mains(monkeypatch):
    from solar_toolkit.radio import centers, quicklook, raw_quality_cli, trajectory_cli

    monkeypatch.setattr(centers, "run_center_extraction", lambda _argv: object())
    monkeypatch.setattr(
        quicklook,
        "run_gaussian_newkirk_quicklook",
        lambda **_kwargs: {"input_csv": "input.csv"},
    )
    monkeypatch.setattr(raw_quality_cli, "run_raw_quality", lambda **_kwargs: object())
    monkeypatch.setattr(raw_quality_cli, "_print_summary", lambda _result: None)
    monkeypatch.setattr(
        trajectory_cli,
        "run_trajectory_export",
        lambda *_args, **_kwargs: Path("trajectory.html"),
    )

    assert centers.main([]) == 0
    assert quicklook.main([]) == 0
    assert raw_quality_cli.main([]) == 0
    assert trajectory_cli.main(["--centers", "input.csv", "--out", "out.html"]) == 0


def test_canonical_aia_cli_returns_success_after_processing(monkeypatch):
    from solar_toolkit.aia import cli as cli_impl

    config = SimpleNamespace(
        data_path="input",
        multi_band_wavelengths=(171,),
    )
    calls = []
    monkeypatch.setattr(cli_impl, "config_from_args", lambda _args: config)
    monkeypatch.setattr(cli_impl, "_actual_mode", lambda _config: "single")
    monkeypatch.setattr(
        cli_impl,
        "_configure_matplotlib_backend",
        lambda mode: calls.append(("backend", mode)),
    )
    monkeypatch.setattr(
        cli_impl,
        "process_aia_fits",
        lambda received: calls.append(("process", received)),
    )

    assert cli_impl.main([]) == 0
    assert calls[-1] == ("process", config)
