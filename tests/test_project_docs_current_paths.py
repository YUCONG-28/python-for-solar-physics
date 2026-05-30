"""Documentation consistency checks for current public project docs."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

CURRENT_DOCS = [
    "README.md",
    "docs/FINAL_CODE_RETENTION_AND_REMOVAL_PLAN.md",
    "docs/LEGACY_AND_REVIEW_FILES.md",
    "docs/MAIN_FILES.md",
    "docs/PROJECT_CLEANUP_REPORT.md",
    "docs/README.md",
    "docs/REFACTOR_BASELINE.md",
    "docs/project_structure.md",
    "docs/script_index.md",
    "scripts/aia_hmi/docs/AIA_ENTRYPOINTS.md",
    "scripts/radio/docs/README.md",
]

MOJIBAKE_MARKERS = [
    "\u9225",
    "\u20ac?",
    "\u6d93",
    "\u9365",
    "\u7edb",
    "\ufffd",
]

DOCS_ROOT_DOCS = sorted(
    path.relative_to(REPO_ROOT).as_posix() for path in (REPO_ROOT / "docs").glob("*.md")
)

MAINTAINED_MARKDOWN_DOCS = sorted(
    set(
        [
            "README.md",
            "examples/README.md",
            "docs/assets/README.md",
            "scripts/aia_hmi/docs/AIA_ENTRYPOINTS.md",
        ]
    )
    | set(DOCS_ROOT_DOCS)
    | {
        path.relative_to(REPO_ROOT).as_posix()
        for path in (REPO_ROOT / "scripts").glob("*/docs/*.md")
    }
)


def _extract_script_paths(text: str) -> set[str]:
    paths = set(re.findall(r"`(scripts[/\\][^`]+?\.py)`", text))
    paths.update(re.findall(r"python\s+(scripts[/\\][^\s`]+?\.py)", text))
    return {path.replace("\\", "/") for path in paths}


def _extract_local_markdown_links(text: str) -> set[str]:
    links = set()
    for target in re.findall(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", text):
        target = target.split("#", 1)[0].strip()
        if (
            not target
            or target.startswith(("http://", "https://", "mailto:", "#"))
            or not target.lower().endswith(".md")
        ):
            continue
        links.add(target)
    for target in re.findall(r"`([^`]+?\.md)`", text):
        if not target.startswith(("http://", "https://", "mailto:", "#")):
            links.add(target)
    return links


@pytest.mark.parametrize("doc_path", CURRENT_DOCS)
def test_current_doc_script_paths_exist(doc_path):
    text = (REPO_ROOT / doc_path).read_text(encoding="utf-8")
    paths = _extract_script_paths(text)

    missing = sorted(path for path in paths if not (REPO_ROOT / path).exists())

    assert missing == []


@pytest.mark.parametrize("doc_path", CURRENT_DOCS)
def test_current_doc_local_markdown_links_exist(doc_path):
    text = (REPO_ROOT / doc_path).read_text(encoding="utf-8")
    links = _extract_local_markdown_links(text)
    doc_dir = (REPO_ROOT / doc_path).parent

    missing = sorted(
        link
        for link in links
        if not (doc_dir / link.replace("/", "\\")).resolve().exists()
        and not (REPO_ROOT / link.replace("/", "\\")).resolve().exists()
    )

    assert missing == []


@pytest.mark.parametrize(
    "doc_path",
    [
        "README.md",
        "docs/MAIN_FILES.md",
        "docs/script_index.md",
        "scripts/aia_hmi/docs/AIA_ENTRYPOINTS.md",
    ],
)
def test_aia_recommended_entrypoint_is_current(doc_path):
    text = (REPO_ROOT / doc_path).read_text(encoding="utf-8")

    assert "scripts/aia_hmi/run_aia_euv_processor.py" in text


@pytest.mark.parametrize("doc_path", MAINTAINED_MARKDOWN_DOCS)
def test_maintained_docs_do_not_contain_common_mojibake(doc_path):
    text = (REPO_ROOT / doc_path).read_text(encoding="utf-8")

    found = [marker for marker in MOJIBAKE_MARKERS if marker in text]

    assert found == []
