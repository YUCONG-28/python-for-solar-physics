"""Regression tests for import-safe CME and archive-download boundaries."""

from __future__ import annotations

import datetime as dt
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_MODULES = [
    "scripts.lasco_cme.soho_lasco_data_download",
    "scripts.lasco_cme.soho_lasco_image_plot",
    "scripts.lasco_cme.soho_lasco_running_difference",
    "scripts.data_download.goes_suvi_download_20250124",
    "scripts.data_download.stereo_a_euvi_download_20250124",
    "scripts.data_download.solo_eui_soar_query_download",
]
SCRIPT_PATHS = [name.replace(".", "/") + ".py" for name in SCRIPT_MODULES]


def test_lasco_download_rejects_nonpositive_interval_before_optional_import(tmp_path):
    from solar_toolkit.cme.lasco import download_lasco_jp2_sequence

    with pytest.raises(ValueError, match="interval must be positive"):
        download_lasco_jp2_sequence(
            start_time=dt.datetime(2024, 8, 8, 19),
            end_time=dt.datetime(2024, 8, 8, 20),
            interval=dt.timedelta(0),
            output_dir=tmp_path,
        )


def test_cme_and_download_scripts_import_without_io_side_effects(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("workflow I/O ran during import")

    monkeypatch.setattr(Path, "mkdir", fail)
    monkeypatch.setattr(Path, "write_text", fail)
    monkeypatch.setattr("urllib.request.urlopen", fail)
    for module_name in SCRIPT_MODULES:
        sys.modules.pop(module_name, None)
        assert importlib.import_module(module_name) is not None


@pytest.mark.parametrize("script_path", SCRIPT_PATHS)
def test_cme_and_download_cli_help_is_import_safe(script_path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / script_path), "--help"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.casefold()


def test_download_url_streams_atomically_and_replaces_empty_file(monkeypatch, tmp_path):
    from solar_toolkit.net import downloads

    destination = tmp_path / "archive.fits"
    destination.write_bytes(b"")

    class FakeResponse:
        chunks = iter((b"abc", b"def", b""))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self, size):
            assert size == 3
            return next(self.chunks)

    monkeypatch.setattr(
        downloads.urllib.request, "urlopen", lambda *a, **k: FakeResponse()
    )
    result = downloads.download_url(
        "https://example.test/archive.fits",
        destination,
        chunk_size=3,
        redownload_empty=True,
    )

    assert result.status == "downloaded"
    assert destination.read_bytes() == b"abcdef"
    assert not destination.with_suffix(".fits.part").exists()


def test_download_url_removes_partial_file_after_failure(monkeypatch, tmp_path):
    from solar_toolkit.net import downloads

    destination = tmp_path / "archive.fits"

    class BrokenResponse:
        calls = 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self, size):
            self.calls += 1
            if self.calls == 1:
                return b"partial"
            raise OSError("connection lost")

    monkeypatch.setattr(
        downloads.urllib.request, "urlopen", lambda *a, **k: BrokenResponse()
    )
    with pytest.raises(OSError, match="connection lost"):
        downloads.download_url(
            "https://example.test/archive.fits",
            destination,
            chunk_size=1024,
        )

    assert not destination.exists()
    assert not destination.with_suffix(".fits.part").exists()


def test_suvi_workflow_uses_canonical_selection_and_download(monkeypatch, tmp_path):
    from solar_toolkit.net import DownloadResult, suvi

    matching = "dr_suvi-l2-ci171_g16_s20250124T044800Z_e1_v1-0-0.fits"
    outside = "dr_suvi-l2-ci171_g16_s20250124T050000Z_e1_v1-0-0.fits"
    monkeypatch.setattr(
        suvi,
        "list_remote_links",
        lambda url: [url + matching, url + outside],
    )
    calls = []

    def fake_download(url, destination, **kwargs):
        calls.append((url, Path(destination), kwargs))
        return DownloadResult(url=url, path=Path(destination), status="downloaded")

    monkeypatch.setattr(suvi, "download_url", fake_download)
    matched, downloaded = suvi.download_goes_suvi(
        output_root=tmp_path,
        date_path="2025/01/24",
        date_stamp="20250124",
        start_hms="040000",
        end_hms="045959",
        satellites=("goes16",),
        channels=("171",),
    )

    assert (matched, downloaded) == (1, 1)
    assert calls[0][1] == tmp_path / "goes16" / "ci171" / "20250124" / matching
    assert calls[0][2]["redownload_empty"] is True


def test_soar_query_decodes_tap_metadata_without_requests(monkeypatch):
    from solar_toolkit.net import soar

    payload = {
        "metadata": [{"name": "data_item_id"}, {"name": "filename"}],
        "data": [["id-1", "eui.fits"]],
    }
    opened = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps(payload).encode()

    def fake_urlopen(url, timeout):
        opened.append((url, timeout))
        return FakeResponse()

    monkeypatch.setattr(soar.urllib.request, "urlopen", fake_urlopen)
    rows = soar.query_eui("2025-01-24 04:00:00", "2025-01-24 05:00:00")

    assert rows == [{"data_item_id": "id-1", "filename": "eui.fits"}]
    assert "QUERY=" in opened[0][0]
    assert opened[0][1] == 120


def test_lasco_running_difference_script_delegates_to_package(monkeypatch):
    script = importlib.import_module("scripts.lasco_cme.soho_lasco_running_difference")
    monkeypatch.setattr(
        script,
        "load_script_config",
        lambda *args, **kwargs: {
            "input_dir": "configured-input",
            "output_dir": "configured-output",
            "show_plot": False,
        },
    )
    calls = []
    monkeypatch.setattr(
        script,
        "render_lasco_running_differences",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    assert script.main(["--input-dir", "cli-input", "--vmin", "-10"]) == 0
    assert calls == [
        (
            ("cli-input", "configured-output"),
            {
                "show_plot": False,
                "recursive": True,
                "vmin": -10.0,
                "vmax": 49,
            },
        )
    ]
