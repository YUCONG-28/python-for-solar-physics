from __future__ import annotations

from pathlib import Path

from solar_apps.platform.paths.memory import PathMemoryContext, RecentPathMemory
from solar_apps.platform.state import StateStore


def _memory(tmp_path: Path, root: Path) -> RecentPathMemory:
    return RecentPathMemory(
        StateStore(
            tmp_path / "recent.json",
            "recent_paths",
            allowed_keys=("field", "operation", "frontend", "global"),
        ),
        (root,),
    )


def test_recent_paths_use_six_level_precedence(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    directories = {
        name: root / name
        for name in ("current", "field", "operation", "frontend", "global")
    }
    for directory in directories.values():
        directory.mkdir(parents=True)
    context = PathMemoryContext("source-map", "export", "output")
    memory = _memory(tmp_path, root)
    state = {
        "field": {"source-map|export|output|save_file": str(directories["field"])},
        "operation": {"source-map|export|save_file": str(directories["operation"])},
        "frontend": {"source-map|save_file": str(directories["frontend"])},
        "global": {"save_file": str(directories["global"])},
    }
    memory.store.save(state)

    assert memory.resolve_initial(
        context=context,
        dialog_mode="save_file",
        current_value=str(directories["current"] / "figure.png"),
    ) == str(directories["current"].resolve())
    assert memory.resolve_initial(context=context, dialog_mode="save_file") == str(
        directories["field"].resolve()
    )
    directories["field"].rmdir()
    assert memory.resolve_initial(context=context, dialog_mode="save_file") == str(
        directories["operation"].resolve()
    )
    directories["operation"].rmdir()
    assert memory.resolve_initial(context=context, dialog_mode="save_file") == str(
        directories["frontend"].resolve()
    )
    directories["frontend"].rmdir()
    assert memory.resolve_initial(context=context, dialog_mode="save_file") == str(
        directories["global"].resolve()
    )
    directories["global"].rmdir()
    assert memory.resolve_initial(context=context, dialog_mode="save_file") == str(
        root.resolve()
    )


def test_remembered_file_and_save_as_store_parent_only(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    root.mkdir()
    source = root / "input.fits"
    source.write_text("data", encoding="utf-8")
    context = PathMemoryContext("source-map", "load", "input")
    memory = _memory(tmp_path, root)
    memory.remember(context=context, dialog_mode="open_file", paths=(source,))
    state = memory.store.load()
    assert set(state["field"].values()) == {str(root.resolve())}

    memory.remember(
        context=PathMemoryContext("source-map", "export", "output"),
        dialog_mode="save_file",
        paths=(root / "figure.png",),
    )
    state = memory.store.load()
    assert str(root / "figure.png") not in str(state)
    assert memory.resolve_initial(
        context=PathMemoryContext("source-map", "export", "output"),
        dialog_mode="save_file",
    ) == str(root.resolve())


def test_removed_or_outside_memory_is_revalidated_and_never_reused(
    tmp_path: Path,
) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    context = PathMemoryContext("viewer", "load", "input")
    memory = _memory(tmp_path, allowed)
    memory.store.save(
        {
            "field": {"viewer|load|input|open_file": str(outside)},
            "operation": {},
            "frontend": {},
            "global": {"open_file": str(outside)},
        }
    )
    assert memory.resolve_initial(context=context, dialog_mode="open_file") == str(
        allowed.resolve()
    )


def test_corrupt_memory_falls_back_without_overwriting_typed_value(
    tmp_path: Path,
) -> None:
    allowed = tmp_path / "allowed"
    typed = allowed / "typed"
    typed.mkdir(parents=True)
    memory = _memory(tmp_path, allowed)
    memory.store.path.write_text("broken", encoding="utf-8")
    assert memory.resolve_initial(
        context=PathMemoryContext("viewer", "load", "input"),
        dialog_mode="open_file",
        current_value=str(typed / "missing.fits"),
    ) == str(typed.resolve())
