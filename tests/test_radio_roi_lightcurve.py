from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from astropy.io import fits

from solar_toolkit.radio.centers import iter_radio_images
from solar_toolkit.radio.roi_lightcurve import (
    RadioRoi,
    build_radio_roi_artifacts,
    build_radio_roi_mask,
    extract_radio_roi_lightcurve,
    measure_radio_roi,
    radio_roi_from_json,
    write_radio_roi_products,
)
from solar_toolkit.radio.roi_lightcurve_app import (
    build_file_manifest,
    discover_frequency_options,
    parse_row_selection_expression,
    selection_to_radio_roi,
)


def _header(
    *,
    freq: float = 149.0,
    date_obs: str = "2025-01-24T04:48:45",
    bunit: str = "K",
    cdelt1: float = 1.0,
    cdelt2: float = 1.0,
) -> fits.Header:
    header = fits.Header()
    header["NAXIS"] = 2
    header["NAXIS1"] = 4
    header["NAXIS2"] = 4
    header["CTYPE1"] = "HPLN-TAN"
    header["CTYPE2"] = "HPLT-TAN"
    header["CUNIT1"] = "arcsec"
    header["CUNIT2"] = "arcsec"
    header["CRPIX1"] = 1.0
    header["CRPIX2"] = 1.0
    header["CRVAL1"] = 0.0
    header["CRVAL2"] = 0.0
    header["CDELT1"] = cdelt1
    header["CDELT2"] = cdelt2
    header["FREQ"] = freq
    header["FREQUNIT"] = "MHz"
    header["DATE-OBS"] = date_obs
    header["BUNIT"] = bunit
    return header


def _write_fits(path: Path, data: np.ndarray, header: fits.Header) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fits.PrimaryHDU(data=np.asarray(data, dtype=float), header=header).writeto(path)
    return path


def test_box_roi_mask_and_raw_statistics_are_in_hpc_arcsec():
    data = np.arange(16, dtype=float).reshape(4, 4)
    roi = RadioRoi.from_box(1.0, 1.0, 2.0, 2.0)

    mask = build_radio_roi_mask(_header(), data.shape, roi)
    measurement = measure_radio_roi(data, _header(), roi)

    assert int(mask.sum()) == 4
    assert measurement["quality_flag"] == "ok"
    assert measurement["raw_sum"] == pytest.approx(30.0)
    assert measurement["raw_mean"] == pytest.approx(7.5)
    assert measurement["raw_peak"] == pytest.approx(10.0)


def test_lasso_selection_and_reverse_box_selection_build_roi_geometry():
    box_event = {
        "selection": {
            "box": [{"x": [2.0, 1.0], "y": [2.0, 1.0]}],
        }
    }
    lasso_event = {
        "selection": {
            "lasso": [{"x": [0.0, 2.0, 1.0], "y": [0.0, 0.0, 2.0]}],
        }
    }

    box = selection_to_radio_roi(box_event, mode="box")
    lasso = selection_to_radio_roi(lasso_event, mode="lasso")

    assert box is not None
    assert box.kind == "box"
    assert box.bounds_arcsec == {
        "left": 1.0,
        "bottom": 1.0,
        "right": 2.0,
        "top": 2.0,
    }
    assert lasso is not None
    assert lasso.kind == "polygon"
    assert len(lasso.vertices_arcsec) == 3


def test_missing_spatial_wcs_is_reported_as_quality_flag():
    header = fits.Header()
    data = np.ones((2, 2), dtype=float)
    roi = RadioRoi.from_box(0.0, 0.0, 1.0, 1.0)

    measurement = measure_radio_roi(data, header, roi)

    assert measurement["quality_flag"] == "invalid_wcs"
    assert "CTYPE1" in measurement["quality_detail"]


def test_radec_wcs_is_rejected_for_hpln_roi_measurement():
    header = _header()
    header["CTYPE1"] = "RA---TAN"
    header["CTYPE2"] = "DEC--TAN"
    data = np.ones((4, 4), dtype=float)
    roi = RadioRoi.from_box(0.0, 0.0, 1.0, 1.0)

    measurement = measure_radio_roi(data, header, roi)

    assert measurement["quality_flag"] == "invalid_wcs"
    assert "non-HPLN" in measurement["quality_detail"]


def test_extract_radio_roi_lightcurve_pairs_lcp_rcp_as_raw_sum(tmp_path):
    root = tmp_path / "radio"
    data_l = np.ones((4, 4), dtype=float)
    data_r = np.full((4, 4), 2.0, dtype=float)
    _write_fits(root / "149MHz" / "LL" / "l_20250124044845.fits", data_l, _header())
    _write_fits(root / "149MHz" / "RR" / "r_20250124044845.fits", data_r, _header())
    roi = RadioRoi.from_box(-0.5, -0.5, 3.5, 3.5)

    df = extract_radio_roi_lightcurve(root, roi, polarization="L+R", recursive=True)

    assert len(df) == 1
    row = df.iloc[0]
    assert row["quality_flag"] == "ok"
    assert row["polarization"] == "L+R"
    assert row["raw_sum"] == pytest.approx(48.0)
    assert row["raw_mean"] == pytest.approx(3.0)
    assert row["paired_filepath"]


def test_extract_radio_roi_lightcurve_records_mismatched_pairs(tmp_path):
    root = tmp_path / "radio"
    _write_fits(root / "149MHz" / "LL" / "l.fits", np.ones((4, 4)), _header())
    _write_fits(root / "149MHz" / "RR" / "r.fits", np.ones((3, 3)), _header())
    roi = RadioRoi.from_box(-0.5, -0.5, 3.5, 3.5)

    df = extract_radio_roi_lightcurve(root, roi, polarization="L+R", recursive=True)

    assert set(df["quality_flag"]) == {"mismatched_pair", "unmatched_pair"}
    assert any("shape mismatch" in detail for detail in df["quality_detail"])


def test_extract_radio_roi_lightcurve_uses_exact_selected_files(tmp_path):
    root = tmp_path / "radio"
    selected = _write_fits(
        root / "selected_20250124044845.fits", np.ones((4, 4)), _header()
    )
    ignored = _write_fits(
        root / "ignored_20250124044846.fits", np.full((4, 4), 9.0), _header()
    )
    roi = RadioRoi.from_box(-0.5, -0.5, 3.5, 3.5)

    df = extract_radio_roi_lightcurve(
        root,
        roi,
        files=[selected],
        polarization="L+R",
        recursive=True,
    )

    assert len(df) == 1
    assert Path(df.iloc[0]["filepath"]) == selected
    assert str(ignored) not in set(df["filepath"])
    assert df.iloc[0]["raw_sum"] == pytest.approx(16.0)


def test_file_manifest_is_path_only_and_does_not_load_image_arrays(
    tmp_path, monkeypatch
):
    root = tmp_path / "radio"
    _write_fits(
        root / "149MHz" / "LL" / "l_20250124044845.fits", np.ones((4, 4)), _header()
    )

    import solar_toolkit.radio.roi_lightcurve_app as app

    monkeypatch.setattr(
        app,
        "iter_radio_images",
        lambda *_args, **_kwargs: pytest.fail("manifest should not load image arrays"),
    )

    manifest = build_file_manifest(root, recursive=True)

    assert len(manifest) == 1
    assert manifest.iloc[0]["relative_path"].endswith("l_20250124044845.fits")
    assert manifest.iloc[0]["inferred_polarization"] == "LCP"


def test_frequency_discovery_and_manifest_frequency_filter_are_path_only(
    tmp_path, monkeypatch
):
    root = tmp_path / "radio"
    _write_fits(
        root / "149MHz" / "LL" / "149MHz_20250124044845.fits",
        np.ones((4, 4)),
        _header(freq=149.0),
    )
    _write_fits(
        root / "238MHz" / "RR" / "238MHz_20250124044846.fits",
        np.ones((4, 4)),
        _header(freq=238.0),
    )

    import solar_toolkit.radio.roi_lightcurve_app as app

    monkeypatch.setattr(
        app,
        "iter_radio_images",
        lambda *_args, **_kwargs: pytest.fail(
            "frequency scan should not load image arrays"
        ),
    )

    frequencies = discover_frequency_options(root, recursive=True)
    manifest = build_file_manifest(root, recursive=True, freqs=[238.0])

    assert list(frequencies["freq_mhz"]) == [149.0, 238.0]
    assert list(frequencies["file_count"]) == [1, 1]
    assert len(manifest) == 1
    assert manifest.iloc[0]["row"] == 1
    assert manifest.iloc[0]["inferred_freq_mhz"] == pytest.approx(238.0)


def test_quick_file_number_parser_supports_single_values_and_ranges():
    assert parse_row_selection_expression("1, 3, 8-10, 3") == [1, 3, 8, 9, 10]
    assert parse_row_selection_expression("") == []
    with pytest.raises(ValueError, match="increasing"):
        parse_row_selection_expression("10-8")
    with pytest.raises(ValueError, match="Invalid"):
        parse_row_selection_expression("1, x")


def test_write_radio_roi_products_roundtrips_json_csv_and_pngs(tmp_path):
    root = tmp_path / "radio"
    fits_path = _write_fits(root / "sum.fits", np.ones((4, 4)), _header())
    roi = RadioRoi.from_box(-0.5, -0.5, 3.5, 3.5)
    df = extract_radio_roi_lightcurve(root, roi, polarization="L+R", recursive=True)

    products = write_radio_roi_products(
        df,
        roi,
        tmp_path / "out",
        run_metadata={"radio_dir": str(root), "reference": str(fits_path)},
        unique_run=False,
    )

    assert products["csv"].exists()
    assert products["json"].exists()
    assert products["reference_png"].exists()
    assert products["lightcurve_png"].exists()
    saved = json.loads(products["json"].read_text(encoding="utf-8"))
    loaded = radio_roi_from_json(saved)
    assert loaded.roi_id == roi.roi_id
    csv_df = pd.read_csv(products["csv"])
    assert list(csv_df["raw_sum"]) == [16.0]


def test_export_artifacts_and_product_writer_support_selected_outputs(tmp_path):
    root = tmp_path / "radio"
    _write_fits(root / "sum.fits", np.ones((4, 4)), _header())
    roi = RadioRoi.from_box(-0.5, -0.5, 3.5, 3.5)
    df = extract_radio_roi_lightcurve(root, roi, polarization="L+R", recursive=True)

    artifacts = build_radio_roi_artifacts(
        df,
        roi,
        selected_products=("csv", "json"),
    )
    saved = json.loads(artifacts["json"].decode("utf-8"))
    products = write_radio_roi_products(
        df,
        roi,
        tmp_path / "subset",
        selected_products=("json",),
        unique_run=False,
    )

    assert set(artifacts) == {"csv", "json"}
    assert set(saved["outputs"]) == {"csv", "json"}
    assert products["json"].exists()
    assert "csv" not in products
    assert not (tmp_path / "subset" / "radio_roi_statistics.csv").exists()
    with pytest.raises(ValueError, match="At least one"):
        build_radio_roi_artifacts(df, roi, selected_products=())
    with pytest.raises(ValueError, match="Unknown export products"):
        write_radio_roi_products(
            df,
            roi,
            tmp_path / "bad",
            selected_products=("fits",),
            unique_run=False,
        )


def test_reference_artifact_supports_multi_reference_display_config(tmp_path):
    root = tmp_path / "radio"
    first = _write_fits(
        root / "149MHz" / "LL" / "149MHz_20250124044845.fits",
        np.ones((4, 4)),
        _header(freq=149.0),
    )
    second = _write_fits(
        root / "238MHz" / "LL" / "238MHz_20250124044845.fits",
        np.full((4, 4), 2.0),
        _header(freq=238.0),
    )
    roi = RadioRoi.from_box(-0.5, -0.5, 3.5, 3.5)
    df = extract_radio_roi_lightcurve(root, roi, polarization="LCP", recursive=True)
    references = [next(iter_radio_images(first)), next(iter_radio_images(second))]

    artifacts = build_radio_roi_artifacts(
        df,
        roi,
        reference_images=references,
        display_config={
            "colormap": "hot",
            "range_mode": "Auto percentile",
            "range_scope": "Shared/global",
            "shared_limits": [0.0, 2.0],
            "use_custom_fov": True,
            "x_min_arcsec": -1.0,
            "x_max_arcsec": 4.0,
            "y_min_arcsec": -1.0,
            "y_max_arcsec": 4.0,
        },
        selected_products=("reference_png", "json"),
        run_metadata={"display_config": {"colormap": "hot"}},
    )

    saved = json.loads(artifacts["json"].decode("utf-8"))
    assert artifacts["reference_png"].startswith(b"\x89PNG")
    assert saved["settings"]["display_config"]["colormap"] == "hot"
