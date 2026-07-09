"""Documentation consistency checks for current public project docs."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

CURRENT_DOCS = [
    "CODE_ORGANIZATION_MANIFEST.md",
    "README.md",
    "docs/FUNCTION_MAP.md",
    "docs/FINAL_CODE_RETENTION_AND_REMOVAL_PLAN.md",
    "docs/LEGACY_AND_REVIEW_FILES.md",
    "docs/MAIN_FILES.md",
    "docs/PROJECT_CLEANUP_REPORT.md",
    "docs/README.md",
    "docs/REFACTOR_BASELINE.md",
    "docs/quickstart.md",
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
            "CODE_ORGANIZATION_MANIFEST.md",
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


def _local_markdown_target_exists(base_dir: Path, target: str) -> bool:
    normalized_target = target.replace("\\", "/")
    target_path = Path(*PurePosixPath(normalized_target).parts)
    return (base_dir / target_path).resolve().exists()


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
        if not _local_markdown_target_exists(doc_dir, link)
        and not _local_markdown_target_exists(REPO_ROOT, link)
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


def test_beginner_quickstart_is_linked_from_current_docs():
    for doc_path in [
        "README.md",
        "docs/README.md",
        "docs/MAIN_FILES.md",
        "docs/project_structure.md",
        "docs/script_index.md",
    ]:
        text = (REPO_ROOT / doc_path).read_text(encoding="utf-8")
        assert "quickstart.md" in text


def test_current_docs_explain_sunpy_style_base_packages():
    required_packages = [
        "solar_toolkit.time",
        "solar_toolkit.io",
        "solar_toolkit.data",
        "solar_toolkit.map",
        "solar_toolkit.timeseries",
        "solar_toolkit.net",
        "solar_toolkit.cme",
        "solar_toolkit.xray_dem",
    ]
    docs = [
        (REPO_ROOT / "README.md").read_text(encoding="utf-8"),
        (REPO_ROOT / "docs" / "FUNCTION_MAP.md").read_text(encoding="utf-8"),
        (REPO_ROOT / "docs" / "quickstart.md").read_text(encoding="utf-8"),
    ]

    for package in required_packages:
        assert any(package in text for text in docs), package


def test_current_docs_mark_compatibility_paths_as_deprecated():
    docs = "\n".join(
        [
            (REPO_ROOT / "README.md").read_text(encoding="utf-8"),
            (REPO_ROOT / "docs" / "FUNCTION_MAP.md").read_text(encoding="utf-8"),
            (REPO_ROOT / "docs" / "LEGACY_AND_REVIEW_FILES.md").read_text(
                encoding="utf-8"
            ),
            (
                REPO_ROOT / "scripts" / "aia_hmi" / "docs" / "AIA_ENTRYPOINTS.md"
            ).read_text(encoding="utf-8"),
            (
                REPO_ROOT / "scripts" / "radio" / "docs" / "RADIO_MIGRATION_NOTES.md"
            ).read_text(encoding="utf-8"),
        ]
    )

    for path in [
        "scripts.radio.core.*",
        "scripts.aia_hmi.core.*",
        "scripts/radio/legacy/",
    ]:
        assert path in docs
    assert "deprecated compatibility" in docs
    assert "DeprecationWarning" not in docs


def test_current_docs_do_not_claim_drift_spectrogram_is_unmigrated():
    docs = "\n".join(
        (REPO_ROOT / doc_path).read_text(encoding="utf-8") for doc_path in CURRENT_DOCS
    )

    stale_claims = [
        "unmigrated drift/spectrogram",
        "drift/spectrogram helpers remain under",
        "drift/spectrogram helpers remain unmigrated",
    ]

    assert [claim for claim in stale_claims if claim in docs] == []


def test_new_public_facade_modules_are_importable_without_running_workflows():
    from solar_toolkit import visualization, webapp
    from solar_toolkit.visualization import radio_source_video
    from solar_toolkit.webapp import cli

    assert "radio_source_video" in visualization.__all__
    assert "cli" in webapp.__all__
    assert radio_source_video.VideoExportOptions is not None
    assert callable(cli.build_parser)


def test_quickstart_uses_project_interpreter_for_local_validation():
    text = (REPO_ROOT / "docs" / "quickstart.md").read_text(encoding="utf-8")

    assert r"D:\miniforge3\envs\solarphysics_env\python.exe" in text
    assert "PYTEST_DISABLE_PLUGIN_AUTOLOAD" in text
    assert "-m compileall -q solar_toolkit scripts tests examples" in text
    assert "tests\\test_imports.py" in text


@pytest.mark.parametrize("doc_path", MAINTAINED_MARKDOWN_DOCS)
def test_maintained_docs_do_not_contain_common_mojibake(doc_path):
    text = (REPO_ROOT / doc_path).read_text(encoding="utf-8")

    found = [marker for marker in MOJIBAKE_MARKERS if marker in text]

    assert found == []
