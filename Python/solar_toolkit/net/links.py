"""HTML link collection and filtering.

English: Parse links from HTML and select them using case-insensitive suffix
and substring filters.

中文：解析 HTML 链接，并使用不区分大小写的后缀和文本条件进行筛选。
"""

from __future__ import annotations

import html.parser
import urllib.parse
from collections.abc import Sequence


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


__all__ = ["collect_links", "filter_links"]
