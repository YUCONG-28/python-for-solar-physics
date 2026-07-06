"""Network and archive helper namespace.

English: Small reusable helpers for collecting links, filtering archive
results, and downloading files into explicit user-selected locations.

中文: 联网归档辅助工具命名空间, 提供链接收集、结果过滤和显式目标路径下载能力。
"""

from __future__ import annotations

import html.parser
import urllib.parse
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DownloadResult:
    """Result returned by ``download_url``."""

    url: str
    path: Path
    status: str


class _LinkParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        if tag.lower() != "a":
            return
        attrs_dict = dict(attrs)
        href = attrs_dict.get("href")
        if href:
            self.links.append(href)


def collect_links(html_text: str, *, base_url: str | None = None) -> list[str]:
    """Collect links from an HTML directory listing or page."""

    parser = _LinkParser()
    parser.feed(html_text)
    if base_url is None:
        return parser.links
    return [urllib.parse.urljoin(base_url, href) for href in parser.links]


def filter_links(
    links: Sequence[str],
    *,
    suffixes: Sequence[str] | None = None,
    contains: Sequence[str] | None = None,
) -> list[str]:
    """Filter links by case-insensitive suffix and required text fragments."""

    normalized_suffixes = None
    if suffixes is not None:
        normalized_suffixes = tuple(suffix.casefold() for suffix in suffixes)
    required = [text.casefold() for text in contains or []]
    filtered = []
    for link in links:
        lowered = link.casefold()
        if normalized_suffixes is not None and not lowered.endswith(
            normalized_suffixes
        ):
            continue
        if required and not all(text in lowered for text in required):
            continue
        filtered.append(link)
    return filtered


def download_url(
    url: str,
    destination: str | Path,
    *,
    overwrite: bool = False,
    timeout: float = 30,
) -> DownloadResult:
    """Download ``url`` to ``destination`` unless it exists and overwrite is false."""

    output = Path(destination)
    if output.exists() and not overwrite:
        return DownloadResult(url=url, path=output, status="skipped")
    output.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=timeout) as response:
        output.write_bytes(response.read())
    return DownloadResult(url=url, path=output, status="downloaded")


__all__ = [
    "DownloadResult",
    "collect_links",
    "download_url",
    "filter_links",
]
