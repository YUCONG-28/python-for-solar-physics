from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image

from solar_apps.frontends.image_composer.catalog import (
    discover_images,
    extract_timestamp,
    scan_folder,
    timestamp_from_filename,
)


def _image(path: Path, color: str = "red", *, exif=None) -> None:
    image = Image.new("RGB", (20, 12), color)
    if exif is None:
        image.save(path)
    else:
        image.save(path, exif=exif)


def test_discovery_is_non_recursive_and_naturally_sorted(tmp_path: Path) -> None:
    _image(tmp_path / "frame10.png")
    _image(tmp_path / "frame2.png")
    _image(tmp_path / "frame1.jpg")
    nested = tmp_path / "nested"
    nested.mkdir()
    _image(nested / "frame0.png")
    (tmp_path / "notes.txt").write_text("ignore", encoding="utf-8")

    assert [path.name for path in discover_images(tmp_path)] == [
        "frame1.jpg",
        "frame2.png",
        "frame10.png",
    ]
    assert [record.ordinal for record in scan_folder(tmp_path)] == [1, 2, 3]


def test_filename_timestamp_patterns_include_fractional_seconds() -> None:
    expected = datetime(2026, 7, 17, 14, 30, 25, 250_000)
    assert timestamp_from_filename("CameraA_20260717_143025.250.png") == expected
    assert timestamp_from_filename("CameraB_2026-07-17_14-30-25-250.jpg") == expected
    assert timestamp_from_filename("bad_20260230_120000.png") is None


def test_exif_priority_and_subseconds_win_over_filename_and_mtime(
    tmp_path: Path,
) -> None:
    path = tmp_path / "camera_20260717_143025.900.jpg"
    exif = Image.Exif()
    exif[36867] = "2026:07:17 14:30:24"
    exif[37521] = "125"
    exif[36868] = "2026:07:17 14:30:23"
    exif[306] = "2026:07:17 14:30:22"
    _image(path, exif=exif)
    os.utime(path, (1_700_000_000, 1_700_000_000))

    timestamp, source = extract_timestamp(path)

    assert timestamp == datetime(2026, 7, 17, 14, 30, 24, 125_000)
    assert source == "exif:DateTimeOriginal"


@pytest.mark.parametrize(
    ("time_tag", "subsecond_tag", "expected_source"),
    [
        (36868, 37522, "exif:DateTimeDigitized"),
        (306, 37520, "exif:DateTime"),
    ],
)
def test_secondary_exif_time_sources(
    tmp_path: Path,
    time_tag: int,
    subsecond_tag: int,
    expected_source: str,
) -> None:
    path = tmp_path / f"source_{time_tag}.jpg"
    exif = Image.Exif()
    exif[time_tag] = "2026:07:17 14:30:24"
    exif[subsecond_tag] = "75"
    _image(path, exif=exif)

    timestamp, source = extract_timestamp(path)

    assert timestamp == datetime(2026, 7, 17, 14, 30, 24, 750_000)
    assert source == expected_source


def test_filename_then_mtime_fallback(tmp_path: Path) -> None:
    named = tmp_path / "image_20260717_143025.png"
    _image(named)
    assert extract_timestamp(named) == (
        datetime(2026, 7, 17, 14, 30, 25),
        "filename",
    )

    fallback = tmp_path / "plain.png"
    _image(fallback)
    os.utime(fallback, (1_700_000_000, 1_700_000_000))
    timestamp, source = extract_timestamp(fallback)
    assert timestamp == datetime.fromtimestamp(1_700_000_000)
    assert source == "mtime"
