"""Fail-closed filesystem-root policy for local web applications."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..layout import RuntimeLayout

CONFIG_ENV = "SOLAR_APPS_CONFIG"
ROOTS_ENV = "SOLAR_APPS_ALLOWED_ROOTS"


class AllowedRootPolicyError(ValueError):
    """Raised when filesystem access would be implicit or overly broad."""


def _split_path_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(os.pathsep) if item.strip()]


def _workspace_is_within(candidate: Path, workspace_root: Path) -> bool:
    try:
        workspace_root.relative_to(candidate)
    except ValueError:
        return False
    return True


def normalize_allowed_roots(
    values: Sequence[str | os.PathLike[str]],
    *,
    workspace_root: Path | None = None,
) -> tuple[Path, ...]:
    """Resolve explicit roots and reject a workspace-wide access boundary."""

    workspace = (
        workspace_root.expanduser().resolve()
        if workspace_root is not None
        else RuntimeLayout.discover().repo_root
    )
    normalized: list[Path] = []
    seen: set[str] = set()
    for value in values:
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            raise AllowedRootPolicyError(
                f"Allowed roots must be absolute paths: {value!s}"
            )
        candidate = candidate.resolve(strict=False)
        if _workspace_is_within(candidate, workspace):
            raise AllowedRootPolicyError(
                "The complete workspace, a drive root, or a workspace ancestor "
                "cannot be an application allowed root."
            )
        key = os.path.normcase(str(candidate))
        if key not in seen:
            seen.add(key)
            normalized.append(candidate)
    return tuple(normalized)


def _read_config_roots(path: Path) -> list[str]:
    if not path.exists():
        return []

    import yaml

    with path.open("r", encoding="utf-8") as handle:
        data: Any = yaml.safe_load(handle) or {}
    if not isinstance(data, Mapping):
        raise AllowedRootPolicyError("Local application config must be a mapping.")
    apps = data.get("apps", {})
    if not isinstance(apps, Mapping):
        raise AllowedRootPolicyError("The config 'apps' section must be a mapping.")
    roots = apps.get("allowed_roots", [])
    if roots is None:
        return []
    if isinstance(roots, str):
        return _split_path_list(roots)
    if not isinstance(roots, Sequence) or isinstance(roots, (bytes, bytearray)):
        raise AllowedRootPolicyError("apps.allowed_roots must be a list of paths.")
    if not all(isinstance(item, str) for item in roots):
        raise AllowedRootPolicyError("Every allowed root must be a string path.")
    return list(roots)


def configured_allowed_roots(
    *,
    cli_value: str | None = None,
    environ: Mapping[str, str] | None = None,
    config_path: Path | None = None,
    workspace_root: Path | None = None,
) -> tuple[Path, ...]:
    """Resolve roots using CLI, environment, then YAML precedence."""

    env = os.environ if environ is None else environ
    if cli_value is not None:
        values = _split_path_list(cli_value)
    elif ROOTS_ENV in env:
        values = _split_path_list(env[ROOTS_ENV])
    else:
        selected_config = config_path
        if selected_config is None:
            configured = env.get(CONFIG_ENV)
            selected_config = (
                Path(configured)
                if configured
                else RuntimeLayout.discover(environ=env).config_path
            )
        values = _read_config_roots(selected_config.expanduser())
    return normalize_allowed_roots(values, workspace_root=workspace_root)


def prepare_allowed_root_args(
    argv: Sequence[str],
    *,
    environ: Mapping[str, str] | None = None,
    config_path: Path | None = None,
    workspace_root: Path | None = None,
) -> list[str]:
    """Validate/inject ``--allowed-roots`` for a forwarded web CLI."""

    cleaned: list[str] = []
    cli_value: str | None = None
    index = 0
    while index < len(argv):
        item = argv[index]
        if item == "--allowed-roots":
            if cli_value is not None:
                raise AllowedRootPolicyError("--allowed-roots may be provided once.")
            if index + 1 >= len(argv):
                raise AllowedRootPolicyError("--allowed-roots requires a value.")
            cli_value = argv[index + 1]
            index += 2
            continue
        if item.startswith("--allowed-roots="):
            if cli_value is not None:
                raise AllowedRootPolicyError("--allowed-roots may be provided once.")
            cli_value = item.split("=", 1)[1]
            index += 1
            continue
        cleaned.append(item)
        index += 1

    roots = configured_allowed_roots(
        cli_value=cli_value,
        environ=environ,
        config_path=config_path,
        workspace_root=workspace_root,
    )
    if not roots:
        raise AllowedRootPolicyError(
            "No application allowed roots are configured. Provide --allowed-roots, "
            f"{ROOTS_ENV}, or apps.allowed_roots in the Local config."
        )
    cleaned.extend(["--allowed-roots", os.pathsep.join(map(str, roots))])
    return cleaned
