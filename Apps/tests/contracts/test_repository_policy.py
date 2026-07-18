"""Public Apps architecture, privacy, and repository-boundary contracts."""

from __future__ import annotations

import ast
import re
from pathlib import Path

APPS_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = APPS_ROOT.parent
APP_PACKAGE = APPS_ROOT / "solar_apps"
PYTHON_PACKAGE = REPO_ROOT / "Python" / "solar_toolkit"

PRIVATE_IGNORE_RULES = {
    "/Local/",
    "/Local-migration-backup/",
    "/2023/",
    "/2024/",
    "/2025/",
    "/2026/",
    "/overview/",
}
FORBIDDEN_PUBLIC_NAMES = {
    "PUBLIC_BASE.md",
    "SHA256SUMS",
    "requirements.local.txt",
    "pytest.ini",
}
FORBIDDEN_PUBLIC_DIRECTORIES = {"legacy", "legacy_tests", "history"}
USER_PROFILE_PATH = re.compile(
    r"\b[A-Z]:[\\/]+Users[\\/]+"
    r"(?!(?:<user>|<username>|%USERNAME%)(?:[\\/]|$))"
    r"[^\\/\s`'\"]+",
    re.IGNORECASE,
)
PRIVATE_EMAIL = re.compile(r"\b[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@gmail\.com\b", re.I)
MACHINE_ABSOLUTE_PATH = re.compile(r"\b[A-Z]:[\\/](?![\\/])", re.I)
AUTHOR_METADATA = re.compile(r"(?:@" + "author|\b" + r"author\s*:)", re.I)


def _python_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _module_references(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    names = _imports(path)
    module_name = re.compile(r"^solar_apps(?:\.[A-Za-z_]\w*)+$")
    names.update(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and module_name.fullmatch(node.value)
    )
    return names


def _text_files(root: Path):
    for path in sorted(
        candidate for candidate in root.rglob("*") if candidate.is_file()
    ):
        raw = path.read_bytes()
        if b"\0" not in raw:
            yield path, raw.decode("utf-8", errors="replace")


def test_public_partition_and_private_runtime_layout_are_explicit() -> None:
    assert APP_PACKAGE.is_dir()
    assert PYTHON_PACKAGE.is_dir()
    assert (REPO_ROOT / "ARCHITECTURE.md").is_file()

    ignore_rules = {
        line.strip()
        for line in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert PRIVATE_IGNORE_RULES <= ignore_rules


def test_apps_contains_one_fail_closed_public_config_template() -> None:
    templates = sorted(
        path.relative_to(APPS_ROOT).as_posix()
        for path in (APPS_ROOT / "configs").rglob("*")
        if path.is_file()
    )
    assert templates == ["configs/examples/paths.example.yaml"]
    content = (APPS_ROOT / templates[0]).read_text(encoding="utf-8")
    assert "allowed_roots: []" in content
    assert "Users/" not in content and "Users\\" not in content


def test_apps_has_no_historical_manifest_or_legacy_tree() -> None:
    forbidden_files = [
        path.relative_to(APPS_ROOT).as_posix()
        for path in APPS_ROOT.rglob("*")
        if path.is_file() and path.name in FORBIDDEN_PUBLIC_NAMES
    ]
    forbidden_directories = [
        path.relative_to(APPS_ROOT).as_posix()
        for path in APPS_ROOT.rglob("*")
        if path.is_dir() and path.name.casefold() in FORBIDDEN_PUBLIC_DIRECTORIES
    ]
    assert forbidden_files == []
    assert forbidden_directories == []


def test_public_library_never_imports_application_namespace() -> None:
    offenders = [
        path.relative_to(PYTHON_PACKAGE).as_posix()
        for path in _python_files(PYTHON_PACKAGE)
        if any(
            name == "solar_apps" or name.startswith("solar_apps.")
            for name in _imports(path)
        )
    ]
    assert offenders == []


def test_solar_apps_internal_dependency_direction() -> None:
    offenders: list[str] = []
    policies = {
        "platform": (
            "solar_apps.cli",
            "solar_apps.frontends",
            "solar_apps.ui",
            "solar_apps.workflows",
        ),
        "ui": (
            "solar_apps.cli",
            "solar_apps.frontends",
            "solar_apps.workflows",
        ),
        "workflows": (
            "solar_apps.cli",
            "solar_apps.frontends",
            "solar_apps.ui",
        ),
        "frontends": ("solar_apps.cli",),
    }
    for area, forbidden_prefixes in policies.items():
        for path in _python_files(APP_PACKAGE / area):
            imported = _module_references(path)
            if any(name.startswith(forbidden_prefixes) for name in imported):
                offenders.append(path.relative_to(APP_PACKAGE).as_posix())
    assert offenders == []


def test_production_sources_do_not_mutate_import_paths_or_use_fixed_parent_depth() -> (
    None
):
    offenders: list[str] = []
    fixed_parent = re.compile(r"Path\(__file__\).*?\.parents\s*\[", re.DOTALL)
    for path in _python_files(APP_PACKAGE):
        text = path.read_text(encoding="utf-8-sig")
        if (
            "sys.path.insert(" in text
            or "sys.path.append(" in text
            or fixed_parent.search(text)
        ):
            offenders.append(path.relative_to(APP_PACKAGE).as_posix())
    assert offenders == []


def test_production_package_contains_no_test_modules() -> None:
    offenders = [
        path.relative_to(APP_PACKAGE).as_posix()
        for path in _python_files(APP_PACKAGE)
        if path.name.startswith("test_") or path.name.endswith("_test.py")
    ]
    assert offenders == []


def test_apps_text_contains_no_private_profile_or_email() -> None:
    offenders: list[str] = []
    for path, text in _text_files(APPS_ROOT):
        reasons = []
        is_test_file = (APPS_ROOT / "tests") in path.parents
        if USER_PROFILE_PATH.search(text):
            reasons.append("Windows user profile")
        if PRIVATE_EMAIL.search(text):
            reasons.append("private email")
        if not is_test_file and MACHINE_ABSOLUTE_PATH.search(text):
            reasons.append("machine absolute path")
        if not is_test_file and AUTHOR_METADATA.search(text):
            reasons.append("personal author metadata")
        if reasons:
            offenders.append(
                f"{path.relative_to(APPS_ROOT).as_posix()}: {', '.join(reasons)}"
            )
    assert offenders == []


def test_required_frontend_and_vendor_assets_are_present() -> None:
    assets = [
        path.relative_to(APP_PACKAGE).as_posix()
        for path in APP_PACKAGE.rglob("*")
        if path.is_file()
    ]
    assert any(path.endswith(".html") for path in assets)
    assert any(path.endswith(".css") for path in assets)
    assert any(path.endswith(".js") for path in assets)
    assert any(path.endswith("mediabunny-1.50.8.cjs") for path in assets)
    assert any(path.endswith("mediabunny-MPL-2.0.txt") for path in assets)
    assert any(path.endswith("NOTICE.txt") for path in assets)


def test_apps_has_no_observation_or_generated_data_artifacts() -> None:
    blocked_suffixes = (
        ".avi",
        ".csv",
        ".db",
        ".fit",
        ".fits",
        ".gif",
        ".h5",
        ".hdf5",
        ".jpg",
        ".json",
        ".jsonl",
        ".mkv",
        ".mov",
        ".mp4",
        ".nc",
        ".npy",
        ".npz",
        ".parquet",
        ".pdf",
        ".pkl",
        ".png",
        ".sqlite",
        ".tsv",
        ".webp",
        ".xls",
        ".xlsx",
    )
    offenders = [
        path.relative_to(APPS_ROOT).as_posix()
        for path in APPS_ROOT.rglob("*")
        if path.is_file() and path.name.casefold().endswith(blocked_suffixes)
    ]
    assert offenders == []
