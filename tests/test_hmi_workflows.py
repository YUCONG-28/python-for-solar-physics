"""Import-safety and execution contracts for the public HMI workflows."""

from __future__ import annotations

import contextlib
import datetime as dt
import importlib
import sys
from pathlib import Path

import astropy.coordinates
import astropy.units as u
import matplotlib.pyplot as plt
import pytest
import sunpy.coordinates
import sunpy.map


@pytest.mark.parametrize(
    "module_name",
    [
        "solar_toolkit.hmi.magnetogram",
        "solar_toolkit.hmi.overlay",
        "scripts.aia_hmi.sdo_hmi_magnetogram_plot",
        "scripts.aia_hmi.sdo_aia_hmi_overlay",
    ],
)
def test_hmi_module_imports_do_not_touch_observation_directories(
    module_name,
    monkeypatch,
):
    def fail(*args, **kwargs):
        raise AssertionError("module import touched an observation directory")

    monkeypatch.setattr(Path, "iterdir", fail)
    monkeypatch.setattr(Path, "mkdir", fail)
    sys.modules.pop(module_name, None)

    importlib.import_module(module_name)


def test_magnetogram_workflow_returns_generated_paths(monkeypatch, tmp_path):
    from solar_toolkit.hmi.magnetogram import run_magnetogram_workflow

    input_dir = tmp_path / "hmi"
    output_dir = tmp_path / "plots"
    input_dir.mkdir()
    names = [
        "hmi.M_45s.20250124_044800_TAI.1.fits",
        "hmi.M_45s.20250124_045000_TAI.1.fits",
    ]
    for name in names:
        (input_dir / name).write_bytes(b"fits")

    class FakeAxes:
        pass

    class FakeFigure:
        def add_subplot(self, **kwargs):
            return FakeAxes()

    class FakeMap:
        coordinate_frame = object()
        wcs = object()

        def submap(self, bottom_left, *, top_right):
            return self

        def reproject_to(self, target_wcs):
            return self

        def plot(self, *, axes):
            return None

    def fake_map_factory(value, *, sequence=False):
        if sequence:
            values = list(value)
            if values and isinstance(values[0], Path):
                return [FakeMap() for _ in values]
            return values
        return value if isinstance(value, FakeMap) else FakeMap()

    monkeypatch.setattr(sunpy.map, "Map", fake_map_factory)
    monkeypatch.setattr(astropy.coordinates, "SkyCoord", lambda **kwargs: object())
    monkeypatch.setattr(
        sunpy.coordinates,
        "propagate_with_solar_surface",
        contextlib.nullcontext,
    )
    monkeypatch.setattr(plt, "figure", lambda: FakeFigure())
    monkeypatch.setattr(plt, "title", lambda *args, **kwargs: None)
    monkeypatch.setattr(plt, "show", lambda: None)
    monkeypatch.setattr(plt, "close", lambda *args: None)

    def fake_savefig(path, **kwargs):
        Path(path).write_bytes(b"png")

    monkeypatch.setattr(plt, "savefig", fake_savefig)

    outputs = run_magnetogram_workflow(input_dir, output_dir)

    assert outputs == [output_dir / f"{names[0]}.png"]
    assert outputs[0].read_bytes() == b"png"


def test_overlay_workflow_returns_time_named_outputs(monkeypatch, tmp_path):
    from solar_toolkit._utils import memory
    from solar_toolkit.hmi import processing as hmi_processing
    from solar_toolkit.hmi.overlay import run_overlay_workflow
    from solar_toolkit.io import discovery
    from solar_toolkit.map import operations as map_operations
    from solar_toolkit.time import formatting
    from solar_toolkit.visualization import plotting

    aia_dir = tmp_path / "aia"
    hmi_dir = tmp_path / "hmi"
    output_dir = tmp_path / "overlay"
    aia_dir.mkdir()
    hmi_dir.mkdir()
    aia_times = [
        dt.datetime(2025, 5, 3, 4, 48, 0),
        dt.datetime(2025, 5, 3, 4, 49, 0),
    ]
    hmi_times = [
        dt.datetime(2025, 5, 3, 4, 48, 5),
        dt.datetime(2025, 5, 3, 4, 49, 5),
    ]
    aia_files = [
        (aia_dir / f"aia-{index}.fits", value) for index, value in enumerate(aia_times)
    ]
    hmi_files = [
        (hmi_dir / f"hmi-{index}.fits", value) for index, value in enumerate(hmi_times)
    ]

    class FakeAxes:
        def axis(self, *args):
            return (0, 1, 0, 1)

        def legend(self, **kwargs):
            return None

        def set_title(self, *args, **kwargs):
            return None

    class FakeFigure:
        def add_subplot(self, **kwargs):
            return FakeAxes()

    class FakeMap:
        coordinate_frame = object()
        wcs = object()

        def submap(self, bottom_left, *, top_right):
            return self

        def plot(self, **kwargs):
            return None

        def draw_grid(self, **kwargs):
            return None

        def draw_contours(self, *args, **kwargs):
            return None

    def fake_sorted_files(folder):
        return aia_files if Path(folder) == aia_dir else hmi_files

    monkeypatch.setattr(plotting, "setup_chinese_font", lambda: None)
    monkeypatch.setattr(discovery, "get_sorted_fits_files", fake_sorted_files)
    monkeypatch.setattr(memory, "optimized_gc_collect", lambda: None)
    monkeypatch.setattr(memory, "monitor_memory_usage", lambda *args: {})
    monkeypatch.setattr(
        hmi_processing,
        "create_magnetic_contour_levels",
        lambda level: u.Quantity([-level.value, level.value], level.unit),
    )
    monkeypatch.setattr(
        map_operations,
        "normalize_aia_exposure",
        lambda solar_map: solar_map,
    )
    monkeypatch.setattr(
        map_operations,
        "align_maps_to_reference",
        lambda solar_map, target_wcs: solar_map,
    )
    monkeypatch.setattr(
        hmi_processing,
        "process_hmi_magnetic_field",
        lambda solar_map, threshold, sigma: solar_map,
    )
    monkeypatch.setattr(
        plotting,
        "create_figure_with_white_background",
        lambda figsize: (FakeFigure(), FakeAxes()),
    )
    monkeypatch.setattr(
        formatting,
        "format_time_for_display",
        lambda value: value.strftime("%Y-%m-%d %H:%M:%S"),
    )
    monkeypatch.setattr(
        formatting,
        "format_time_for_filename",
        lambda value: value.strftime("%Y%m%d_%H%M%S"),
    )
    monkeypatch.setattr(sunpy.map, "Map", lambda value: FakeMap())
    monkeypatch.setattr(astropy.coordinates, "SkyCoord", lambda **kwargs: object())
    monkeypatch.setattr(plt, "show", lambda: None)
    monkeypatch.setattr(plt, "close", lambda *args: None)

    def fake_savefig(path, **kwargs):
        Path(path).write_bytes(b"png")

    monkeypatch.setattr(plt, "savefig", fake_savefig)

    outputs = run_overlay_workflow(
        aia_dir,
        hmi_dir,
        output_dir,
        show_progress=False,
    )

    assert outputs == [
        output_dir / "20250503_044800.png",
        output_dir / "20250503_044900.png",
    ]
    assert all(path.read_bytes() == b"png" for path in outputs)


def test_magnetogram_script_main_forwards_explicit_arguments(monkeypatch, tmp_path):
    from scripts.aia_hmi import sdo_hmi_magnetogram_plot as script

    captured = {}
    monkeypatch.setattr(
        script, "load_script_config", lambda *args: script._DEFAULT_CONFIG
    )
    monkeypatch.setattr(
        script,
        "run_magnetogram_workflow",
        lambda **kwargs: captured.update(kwargs) or [tmp_path / "output.png"],
    )

    status = script.main(
        [
            "--data-dir",
            "input",
            "--output-dir",
            "output",
            "--roi-bounds",
            "1",
            "2",
            "3",
            "4",
            "--frame-count",
            "2",
            "--dpi",
            "150",
            "--show-plot",
        ]
    )

    assert status == 0
    assert captured == {
        "data_dir": "input",
        "output_dir": "output",
        "roi_bounds": (1.0, 2.0, 3.0, 4.0),
        "frame_count": 2,
        "show_plot": True,
        "dpi": 150,
    }


def test_overlay_script_main_forwards_explicit_arguments(monkeypatch, tmp_path):
    from scripts.aia_hmi import sdo_aia_hmi_overlay as script

    captured = {}
    monkeypatch.setattr(
        script, "load_script_config", lambda *args: script._DEFAULT_CONFIG
    )
    monkeypatch.setattr(
        script,
        "run_overlay_workflow",
        lambda **kwargs: captured.update(kwargs) or [tmp_path / "output.png"],
    )

    status = script.main(
        [
            "--input-dir-aia",
            "aia",
            "--input-dir-hmi",
            "hmi",
            "--output-dir",
            "output",
            "--no-show-progress",
        ]
    )

    assert status == 0
    assert captured["input_dir_aia"] == "aia"
    assert captured["input_dir_hmi"] == "hmi"
    assert captured["output_dir"] == "output"
    assert captured["roi_bounds"] == (-700.0, -100.0, -100.0, 400.0)
    assert captured["threshold_gauss"] == 0.0
    assert captured["gaussian_sigma"] == 3.0
    assert captured["vmin"] == 16.0
    assert captured["vmax"] == 6666.0
    assert captured["contour_level_gauss"] == 50.0
    assert captured["max_time_diff_seconds"] == 24.0
    assert captured["dpi"] == 300
    assert captured["show_plot"] is False
    assert captured["show_progress"] is False
