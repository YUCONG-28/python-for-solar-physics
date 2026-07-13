"""Focused contracts for the package-owned trajectory media service."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from solar_toolkit.radio import trajectory_media_cli


def test_help_surface_is_lazy_and_documents_optional_aia_export():
    script = """
import sys
from solar_toolkit.radio import trajectory_media_cli
try:
    trajectory_media_cli.main(['--help'])
except SystemExit as exc:
    assert exc.code == 0
else:
    raise AssertionError('--help did not exit')
assert 'numpy' not in sys.modules
assert 'pandas' not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    for option in (
        "--centers",
        "--output-dir",
        "--format",
        "--frame-mode",
        "--plot-layout",
        "--start-frame",
        "--end-frame",
        "--aia-dir",
        "--use-aia",
    ):
        assert option in result.stdout
    assert "AIA backgrounds are optional" in result.stdout


def test_run_filters_centers_and_delegates_to_shared_video_export(
    tmp_path, monkeypatch
):
    centers_path = tmp_path / "centers.csv"
    centers_path.write_text(
        "obs_time,freq_mhz,polarization,center_x_arcsec,center_y_arcsec,"
        "center_method,quality_flag\n"
        "2025-01-24T04:48:45,149,LCP,10,20,threshold,ok\n"
        "2025-01-24T04:48:46,149,LCP,11,21,threshold,ok\n"
        "2025-01-24T04:48:47,164,RCP,12,22,gaussian,ok\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "workspace" / "artifacts"
    observed = {}

    from solar_toolkit.visualization import radio_source_video

    def fake_export(centers, times, **kwargs):
        observed.update(centers=centers, times=times, **kwargs)
        return Path(kwargs["options"].out_path)

    monkeypatch.setattr(radio_source_video, "export_radio_source_video", fake_export)

    result = trajectory_media_cli.run(
        centers_path,
        output_dir,
        output_format="gif",
        freqs=[149],
        polarizations=["LCP"],
        center_methods=["threshold"],
        frame_mode="current",
        tail_n=3,
        plot_layout="facets",
        facet_by="polarization",
        fps=4.0,
        width=960,
        height=640,
        theme="dark",
        marker_size=12,
        start_frame=1,
        end_frame=2,
    )

    assert result == output_dir.resolve() / "radio_source_trajectory.gif"
    assert output_dir.is_dir()
    assert observed["centers"]["freq_mhz"].tolist() == [149.0, 149.0]
    assert observed["centers"]["polarization"].tolist() == ["LCP", "LCP"]
    assert len(observed["times"]) == 2
    assert observed["frame_mode"] == "current"
    assert observed["tail_n"] == 3
    assert observed["plot_layout"] == "facets"
    assert observed["facet_by"] == "polarization"
    assert observed["aia_table"] is None
    options = observed["options"]
    assert options.output_format == "gif"
    assert options.include_aia is False
    assert options.fps == 4.0
    assert (options.width, options.height) == (960, 640)
    assert options.theme_mode == "dark"
    assert options.marker_size == 12
    assert (options.start_frame, options.end_frame) == (1, 2)


def test_run_rejects_empty_filtered_selection_before_media_export(
    tmp_path, monkeypatch
):
    centers_path = tmp_path / "centers.csv"
    centers_path.write_text(
        "obs_time,freq_mhz,polarization,center_x_arcsec,center_y_arcsec,"
        "center_method,quality_flag\n"
        "2025-01-24T04:48:45,149,LCP,10,20,threshold,ok\n",
        encoding="utf-8",
    )

    from solar_toolkit.visualization import radio_source_video

    monkeypatch.setattr(
        radio_source_video,
        "export_radio_source_video",
        lambda *_args, **_kwargs: pytest.fail("media export should not run"),
    )

    with pytest.raises(ValueError, match="No center rows remain"):
        trajectory_media_cli.run(centers_path, tmp_path, freqs=[238])


def test_main_parses_filters_and_prints_generated_path(tmp_path, monkeypatch, capsys):
    output_path = tmp_path / "radio_source_trajectory.webm"
    observed = {}

    def fake_run(**kwargs):
        observed.update(kwargs)
        return output_path

    monkeypatch.setattr(trajectory_media_cli, "run", fake_run)

    result = trajectory_media_cli.main(
        [
            "--centers",
            "centers.csv",
            "--output-dir",
            str(tmp_path),
            "--format",
            "webm",
            "--freqs",
            "149,164",
            "--polarizations",
            "LCP,RCP",
            "--center-methods",
            "threshold,gaussian",
            "--start-frame",
            "2",
            "--end-frame",
            "5",
        ]
    )

    assert result == 0
    assert observed["output_format"] == "webm"
    assert observed["freqs"] == [149.0, 164.0]
    assert observed["polarizations"] == ["LCP", "RCP"]
    assert observed["center_methods"] == ["threshold", "gaussian"]
    assert (observed["start_frame"], observed["end_frame"]) == (2, 5)
    assert capsys.readouterr().out.strip() == f"Trajectory media: {output_path}"
