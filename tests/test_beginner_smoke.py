"""Beginner-facing import and entrypoint smoke tests."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_help(script: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / script), "--help"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_quickstart_public_import_examples_are_available():
    from solar_toolkit.cme import extract_lasco_timestamp, running_difference
    from solar_toolkit.io import read_fits_data_header, scan_files, scan_fits
    from solar_toolkit.map import get_display_extent, normalize_image
    from solar_toolkit.net import collect_links, download_url
    from solar_toolkit.time import extract_time_from_filename, nearest_by_time
    from solar_toolkit.timeseries import normalize_time_column, smooth_series
    from solar_toolkit.xray_dem import calculate_derivative, load_sxr_data

    for symbol in [
        extract_lasco_timestamp,
        running_difference,
        read_fits_data_header,
        scan_files,
        scan_fits,
        get_display_extent,
        normalize_image,
        collect_links,
        download_url,
        extract_time_from_filename,
        nearest_by_time,
        normalize_time_column,
        smooth_series,
        calculate_derivative,
        load_sxr_data,
    ]:
        assert callable(symbol)


def test_beginner_safe_entrypoint_modules_import_without_running_data_workflows():
    for module_name in [
        "scripts.aia_hmi.run_aia_euv_processor",
        "scripts.aia_hmi.sdo_aia_hmi_fits_rename",
        "scripts.tools.image_sequence_to_video",
        "scripts.tools.run_image_web_viewer",
        "scripts.data_download.goes_suvi_download_20250124",
        "scripts.data_download.stereo_a_euvi_download_20250124",
        "scripts.data_download.solo_eui_soar_query_download",
        "scripts.lasco_cme.soho_lasco_running_difference",
        "scripts.xray_dem.flare_aia_sxr_hxr_summary_plot",
        "scripts.xray_dem.neupert_sxr_derivative_hxr_comparison",
        "scripts.xray_dem.sdo_aia_dem_inversion",
    ]:
        module = importlib.import_module(module_name)
        assert module is not None


def test_beginner_safe_help_commands_do_not_start_data_workflows():
    for script in [
        "scripts/aia_hmi/run_aia_euv_processor.py",
        "scripts/aia_hmi/sdo_aia_hmi_fits_rename.py",
        "scripts/data_download/solo_eui_soar_query_download.py",
        "scripts/radio/run_radio_burst_pipeline.py",
        "scripts/radio/run_radio_raw_quality.py",
        "scripts/tools/run_image_web_viewer.py",
    ]:
        result = _run_help(script)
        assert result.returncode == 0, result.stderr
        assert "usage:" in result.stdout.lower()
