"""Filesystem-aware path identity and containment helpers."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def path_key(value: str | os.PathLike[str], *, platform: str | None = None) -> str:
    """Return a stable comparison key using native case behavior."""

    normalized = os.path.normpath(str(value).strip())
    selected = platform or sys.platform
    if selected == "win32" or selected == "darwin":
        return normalized.casefold()
    return normalized


def path_is_within(
    path: str | os.PathLike[str],
    root: str | os.PathLike[str],
) -> bool:
    """Compare resolved paths without allowing symlink escapes."""

    candidate = Path(path).expanduser().resolve(strict=False)
    resolved_root = Path(root).expanduser().resolve(strict=False)
    try:
        candidate.relative_to(resolved_root)
        return True
    except ValueError:
        pass
    if sys.platform != "darwin":
        return False
    # Default APFS is case-insensitive while pathlib comparison is lexical.
    # samefile preserves correctness on both case-sensitive and insensitive APFS.
    for ancestor in (candidate, *candidate.parents):
        if not ancestor.exists():
            continue
        try:
            if os.path.samefile(ancestor, resolved_root):
                return True
        except OSError:
            continue
    return False


__all__ = ["path_is_within", "path_key"]
