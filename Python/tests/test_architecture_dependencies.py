"""Architecture guards for the installable public package."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "solar_toolkit"
FORBIDDEN_ROOTS = {"examples", "legacy", "scripts"}


def _forbidden_imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        for name in names:
            if name.partition(".")[0] in FORBIDDEN_ROOTS:
                found.append((node.lineno, name))
    return found


def test_installable_package_does_not_import_repository_workflows():
    """Library code must not depend on uninstalled repository-only modules."""

    violations: list[str] = []
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        for line, imported in _forbidden_imports(path):
            relative = path.relative_to(REPO_ROOT).as_posix()
            violations.append(f"{relative}:{line} imports {imported}")

    assert violations == []


def test_public_python_modules_declare_explicit_exports():
    """Non-private public modules define ``__all__`` instead of leaking imports."""

    missing: list[str] = []
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        if path.name == "__init__.py" or path.name.startswith("_"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        has_all = any(
            isinstance(node, (ast.Assign, ast.AnnAssign))
            and (
                any(
                    isinstance(target, ast.Name) and target.id == "__all__"
                    for target in node.targets
                )
                if isinstance(node, ast.Assign)
                else isinstance(node.target, ast.Name) and node.target.id == "__all__"
            )
            for node in tree.body
        )
        if not has_all:
            missing.append(path.relative_to(REPO_ROOT).as_posix())

    assert missing == []


def _import_time_nodes(tree: ast.AST):
    """Yield executable AST nodes without descending into functions/classes."""

    stack = list(getattr(tree, "body", []))
    while stack:
        node = stack.pop()
        yield node
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda),
        ):
            continue
        stack.extend(ast.iter_child_nodes(node))


def test_package_imports_do_not_change_global_matplotlib_policy():
    """Backend/font policy is applied only when a plotting workflow runs."""

    violations: list[str] = []
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in _import_time_nodes(tree):
            if isinstance(node, ast.Call):
                rendered = ast.unparse(node.func)
                if rendered == "matplotlib.use" or "rcParams" in rendered:
                    relative = path.relative_to(REPO_ROOT).as_posix()
                    violations.append(f"{relative}:{node.lineno} calls {rendered}")
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                if "rcParams" in ast.unparse(node):
                    relative = path.relative_to(REPO_ROOT).as_posix()
                    violations.append(f"{relative}:{node.lineno} assigns rcParams")

    assert violations == []


def test_package_imports_do_not_read_data_or_start_workflows():
    """Module bodies contain declarations only, not local-data/application work."""

    blocked_calls = {
        "Fido.fetch",
        "Fido.search",
        "apply_config_to_object",
        "glob.glob",
        "load_script_config",
        "os.makedirs",
        "os.mkdir",
        "plt.show",
        "webbrowser.open",
    }
    blocked_suffixes = (
        ".glob",
        ".iterdir",
        ".mkdir",
        ".rglob",
        ".serve_forever",
    )
    violations: list[str] = []
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in _import_time_nodes(tree):
            if not isinstance(node, ast.Call):
                continue
            rendered = ast.unparse(node.func)
            if rendered in blocked_calls or rendered.endswith(blocked_suffixes):
                relative = path.relative_to(REPO_ROOT).as_posix()
                violations.append(f"{relative}:{node.lineno} calls {rendered}")

    assert violations == []
