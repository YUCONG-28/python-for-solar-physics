from __future__ import annotations

import json
from pathlib import Path

import pytest

from solar_toolkit.webapp.radio_workspace.native_previews import (
    build_native_preview,
)


def _recording_validator(calls: list[Path]):
    def validate(value):
        path = Path(value).resolve()
        calls.append(path)
        return path

    return validate


def test_lightweight_adapters_return_json_compatible_results(tmp_path):
    (tmp_path / "nested").mkdir()
    (tmp_path / "centers.csv").write_text("header\n", encoding="utf-8")
    calls: list[Path] = []

    browser = build_native_preview(
        "file-browser",
        {"path": str(tmp_path)},
        validate_path=_recording_validator(calls),
    )
    assert browser["status"] == "ready"
    assert [item["name"] for item in browser["items"]] == [
        "nested",
        "centers.csv",
    ]
    assert calls == [tmp_path.resolve()]
    json.dumps(browser)

    for adapter in ("run-index", "artifact-index"):
        result = build_native_preview(adapter, {}, validate_path=lambda value: value)
        assert result["status"] == "unavailable"
        assert result["items"] == []
        json.dumps(result)


def test_trajectory_preview_uses_canonical_table_and_plot_builder(tmp_path):
    centers = tmp_path / "centers.csv"
    centers.write_text(
        "obs_time,freq_mhz,polarization,center_x_arcsec,center_y_arcsec,"
        "center_method,quality_flag\n"
        "2025-01-24T03:00:00,20,LCP,10,20,threshold,ok\n"
        "2025-01-24T03:00:01,20,LCP,11,21,threshold,ok\n"
        "2025-01-24T03:00:01,20,RCP,13,22,threshold,ok\n",
        encoding="utf-8",
    )
    calls: list[Path] = []

    result = build_native_preview(
        "trajectory-media",
        {
            "centers": str(centers),
            "mode": "all",
            "compare_lr": True,
            "use_webgl": False,
        },
        validate_path=_recording_validator(calls),
    )

    assert result["status"] == "ready"
    assert result["kind"] == "plotly"
    assert result["metadata"]["row_count"] == 3
    assert result["metadata"]["visible_row_count"] == 3
    assert result["metadata"]["frame_count"] == 2
    assert result["figure"]["data"]
    assert calls == [centers.resolve()]
    json.dumps(result)


def test_roi_preview_skips_incompatible_fits_and_returns_selection_metadata(
    tmp_path,
):
    np = pytest.importorskip("numpy")
    fits = pytest.importorskip("astropy.io.fits")

    fits.writeto(tmp_path / "a_missing_wcs.fits", np.arange(16).reshape(4, 4))
    header = fits.Header(
        {
            "CTYPE1": "HPLN-TAN",
            "CTYPE2": "HPLT-TAN",
            "CUNIT1": "arcsec",
            "CUNIT2": "arcsec",
            "CRPIX1": 2.5,
            "CRPIX2": 2.5,
            "CRVAL1": 0.0,
            "CRVAL2": 0.0,
            "CDELT1": 5.0,
            "CDELT2": 5.0,
        }
    )
    fits.writeto(
        tmp_path / "b_compatible.fits",
        np.arange(36, dtype=float).reshape(6, 6),
        header,
    )
    calls: list[Path] = []

    result = build_native_preview(
        "roi-selection",
        {
            "radio_dir": str(tmp_path),
            "pattern": "*.fits",
            "recursive": False,
            "max_side": 32,
        },
        validate_path=_recording_validator(calls),
    )

    assert result["status"] == "ready"
    assert result["metadata"]["source_name"] == "b_compatible.fits"
    assert result["metadata"]["skipped_before_match"] == 1
    assert result["selection"]["coordinate_system"] == "HPLN/HPLT arcsec"
    assert result["selection"]["supported_modes"] == ["box", "lasso"]
    assert calls == [
        tmp_path.resolve(),
        (tmp_path / "a_missing_wcs.fits").resolve(),
        (tmp_path / "b_compatible.fits").resolve(),
        (tmp_path / "b_compatible.fits").resolve(),
    ]
    json.dumps(result)


def test_roi_preview_lists_candidates_and_rebuilds_selected_frequency_grid(tmp_path):
    np = pytest.importorskip("numpy")
    fits = pytest.importorskip("astropy.io.fits")

    paths = []
    for frequency in (149.0, 238.0, 327.0):
        header = fits.Header(
            {
                "CTYPE1": "HPLN-TAN",
                "CTYPE2": "HPLT-TAN",
                "CUNIT1": "arcsec",
                "CUNIT2": "arcsec",
                "CRPIX1": 2.5,
                "CRPIX2": 2.5,
                "CRVAL1": 0.0,
                "CRVAL2": 0.0,
                "CDELT1": 5.0,
                "CDELT2": 5.0,
                "FREQ": frequency,
                "FREQUNIT": "MHz",
                "DATE-OBS": "2025-01-24T03:00:00",
            }
        )
        path = tmp_path / f"{frequency:g}MHz.fits"
        fits.writeto(path, np.full((6, 6), frequency), header)
        paths.append(path.resolve())

    initial = build_native_preview(
        "roi-selection",
        {"radio_dir": str(tmp_path), "recursive": False, "max_side": 32},
        validate_path=lambda value: Path(value).resolve(),
    )

    assert [item["frequency_mhz"] for item in initial["candidates"]] == [
        149.0,
        238.0,
        327.0,
    ]
    assert initial["selected_files"] == [str(path) for path in paths]
    assert initial["metadata"]["candidate_count"] == 3
    assert initial["metadata"]["candidates_truncated"] is False
    assert initial["metadata"]["selected_files_scope"] == "reference_preview_only"
    assert len(initial["figure"]["data"]) == 6

    calls: list[Path] = []
    selected = build_native_preview(
        "roi-selection",
        {
            "radio_dir": str(tmp_path),
            "recursive": False,
            "max_side": 32,
            "selected_files_json": json.dumps([str(paths[1]), str(paths[0])]),
        },
        validate_path=_recording_validator(calls),
    )

    assert selected["selected_files"] == [str(paths[1]), str(paths[0])]
    assert selected["metadata"]["source_path"] == str(paths[1])
    assert len(selected["figure"]["data"]) == 4
    assert calls[:4] == [tmp_path.resolve(), *paths]
    assert calls[4:] == [paths[1], paths[0], paths[1], paths[0]]
    json.dumps(selected)


def test_path_rejection_happens_before_preview_reads(tmp_path):
    def reject(_value):
        raise PermissionError("outside allowed roots")

    with pytest.raises(PermissionError, match="outside allowed roots"):
        build_native_preview(
            "trajectory-media",
            {"centers": str(tmp_path / "centers.csv")},
            validate_path=reject,
        )


def test_drift_preview_uses_existing_image_and_metadata_without_running_upstream(
    tmp_path,
):
    image = tmp_path / "spectrogram.png"
    image.write_bytes(b"local-preview-bytes")
    metadata = tmp_path / "spectrogram.json"
    metadata.write_text(
        json.dumps(
            {
                "x_start_iso": "2025-01-24T03:21:00.000",
                "x_end_iso": "2025-01-24T03:22:00.000",
                "f_min_mhz": 20.0,
                "f_max_mhz": 80.0,
            }
        ),
        encoding="utf-8",
    )
    calls: list[Path] = []

    result = build_native_preview(
        "drift-selection",
        {
            "spectrogram_image": str(image),
            "spectrogram_metadata": str(metadata),
        },
        validate_path=_recording_validator(calls),
    )

    assert result["status"] == "ready"
    assert result["selection"]["mode"] == "two-point-lines"
    assert result["figure"]["layout"]["images"][0]["source"].startswith(
        "data:image/png;base64,"
    )
    assert calls == [image.resolve(), metadata.resolve()]
    json.dumps(result)


def test_unknown_native_preview_adapter_is_rejected():
    with pytest.raises(ValueError, match="Unknown native preview adapter"):
        build_native_preview("not-real", {}, validate_path=lambda value: value)
