"""Repository-level guards for generated observation products."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PRODUCT_GLOBS = [
    "*.csv",
    "*.xlsx",
    "*.json",
    "*.mp4",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.npy",
]
ALLOWED_PREFIXES = ("docs/assets/",)


def test_git_does_not_track_unreviewed_generated_products():
    try:
        result = subprocess.run(
            ["git", "ls-files", *PRODUCT_GLOBS],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
    except FileNotFoundError:
        pytest.skip("git is not available in this environment")

    tracked = [line.strip().replace("\\", "/") for line in result.stdout.splitlines()]
    unexpected = [
        path for path in tracked if path and not path.startswith(ALLOWED_PREFIXES)
    ]

    assert unexpected == []
