from __future__ import annotations

from pathlib import Path


def test_collect_and_filter_links_from_html():
    from solar_toolkit.net import collect_links, filter_links

    html = '<a href="a.fits">A</a><a href="/root/b.txt">B</a><a href="sub/c.FITS">C</a>'
    links = collect_links(html, base_url="https://example.test/data/")

    assert links == [
        "https://example.test/data/a.fits",
        "https://example.test/root/b.txt",
        "https://example.test/data/sub/c.FITS",
    ]
    assert filter_links(links, suffixes=[".fits"], contains=["sub"]) == [
        "https://example.test/data/sub/c.FITS"
    ]


def test_download_url_skip_overwrite_and_fetch(monkeypatch, tmp_path):
    from solar_toolkit.net import download_url

    target = tmp_path / "file.bin"
    target.write_bytes(b"old")

    assert (
        download_url("https://example.test/file.bin", target, overwrite=False).status
        == "skipped"
    )

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b"new"

    monkeypatch.setattr(
        "urllib.request.urlopen", lambda url, timeout=30: FakeResponse()
    )
    result = download_url("https://example.test/file.bin", target, overwrite=True)

    assert result.status == "downloaded"
    assert Path(result.path).read_bytes() == b"new"
