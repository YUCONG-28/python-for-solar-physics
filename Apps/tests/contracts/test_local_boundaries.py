"""Architecture and fail-closed filesystem contracts for Apps/."""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from solar_apps.platform.paths.allowed_roots import (
    AllowedRootPolicyError,
    configured_allowed_roots,
    normalize_allowed_roots,
    prepare_allowed_root_args,
)

APPS_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = APPS_ROOT.parent
PUBLIC_PACKAGE = REPO_ROOT / "Python" / "solar_toolkit"
PLATFORM_PACKAGE = APPS_ROOT / "solar_apps" / "platform"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_public_library_does_not_depend_on_apps_namespace() -> None:
    offenders = [
        str(path.relative_to(PUBLIC_PACKAGE))
        for path in PUBLIC_PACKAGE.rglob("*.py")
        if any(
            name == "solar_apps" or name.startswith("solar_apps.")
            for name in _imports(path)
        )
    ]
    assert not offenders, f"Public modules import solar_apps: {offenders}"


def test_platform_does_not_depend_on_ui_frontends_or_workflows() -> None:
    forbidden = (
        "solar_apps.cli",
        "solar_apps.ui",
        "solar_apps.frontends",
        "solar_apps.workflows",
    )
    offenders: list[str] = []
    for path in PLATFORM_PACKAGE.rglob("*.py"):
        if any(
            name == prefix or name.startswith(prefix + ".")
            for name in _imports(path)
            for prefix in forbidden
        ):
            offenders.append(str(path.relative_to(PLATFORM_PACKAGE)))
    assert not offenders, f"Platform imports a higher application layer: {offenders}"


def test_allowed_roots_fail_closed_without_explicit_configuration(
    tmp_path: Path,
) -> None:
    missing_config = tmp_path / "missing.yaml"
    assert (
        configured_allowed_roots(
            environ={}, config_path=missing_config, workspace_root=REPO_ROOT
        )
        == ()
    )
    with pytest.raises(AllowedRootPolicyError, match="No application allowed roots"):
        prepare_allowed_root_args(
            [], environ={}, config_path=missing_config, workspace_root=REPO_ROOT
        )


@pytest.mark.parametrize("candidate", (REPO_ROOT, REPO_ROOT.parent))
def test_workspace_and_ancestor_are_rejected(candidate: Path) -> None:
    with pytest.raises(AllowedRootPolicyError, match="complete workspace"):
        normalize_allowed_roots([candidate], workspace_root=REPO_ROOT)


def test_explicit_subdirectory_is_normalized_and_forwarded(tmp_path: Path) -> None:
    data_root = tmp_path / "observations"
    forwarded = prepare_allowed_root_args(
        ["--host", "127.0.0.1", "--allowed-roots", str(data_root)],
        environ={},
        workspace_root=REPO_ROOT,
    )
    assert forwarded[:2] == ["--host", "127.0.0.1"]
    assert forwarded[-2:] == ["--allowed-roots", str(data_root.resolve())]


def test_environment_roots_override_yaml(tmp_path: Path) -> None:
    yaml_root = tmp_path / "yaml"
    env_root = tmp_path / "env"
    config = tmp_path / "paths.local.yaml"
    config.write_text(
        f"apps:\n  allowed_roots:\n    - '{yaml_root.as_posix()}'\n",
        encoding="utf-8",
    )
    roots = configured_allowed_roots(
        environ={"SOLAR_APPS_ALLOWED_ROOTS": str(env_root)},
        config_path=config,
        workspace_root=REPO_ROOT,
    )
    assert roots == (env_root.resolve(),)
    assert os.pathsep not in str(roots[0])
