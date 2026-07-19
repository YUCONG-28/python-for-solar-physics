from __future__ import annotations

import json
from pathlib import Path

import pytest

from solar_apps.frontends.image_composer.models import (
    ComposerProject,
    FolderSource,
    LayoutSlot,
)
from solar_apps.frontends.image_composer.project import (
    ProjectFormatError,
    load_project,
    project_to_dict,
    save_project,
)


def test_project_round_trip_preserves_layout_but_not_catalog_records(
    tmp_path: Path,
) -> None:
    folder_path = tmp_path / "images"
    folder_path.mkdir()
    folder = FolderSource(
        id="folder_a",
        path=folder_path,
        name="Camera A",
        start_index=20,
        end_index=100,
        offset_seconds=2.3,
    )
    slot = LayoutSlot.create("folder_a", 7, x=12.5, y=30.0)
    slot.rotation = 14.0
    slot.opacity = 0.75
    slot.fit = "cover"
    slot.preview_relative_path = "preview.png"
    project = ComposerProject(folders=[folder], slots=[slot])
    project.matching.master_folder_id = folder.id
    project.export.output_path = str(tmp_path / "movie.mp4")

    saved = save_project(tmp_path / "layout", project)
    restored = load_project(saved)

    assert saved.name == "layout.fic.json"
    assert restored.folders[0].records == []
    assert restored.folders[0].resolved is True
    assert restored.folders[0].start_index == 20
    assert restored.slots[0].rotation == 14.0
    assert restored.slots[0].fit == "cover"
    assert restored.slots[0].preview_relative_path == "preview.png"
    assert project_to_dict(restored)["schema_version"] == 1


def test_unknown_project_schema_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "future.fic.json"
    path.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
    with pytest.raises(ProjectFormatError, match="Unsupported"):
        load_project(path)


def test_missing_folder_loads_as_unresolved(tmp_path: Path) -> None:
    path = tmp_path / "missing.fic.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "folders": [
                    {
                        "id": "missing",
                        "path": str(tmp_path / "not-there"),
                        "start_index": 1,
                        "end_index": 5,
                    }
                ],
                "slots": [],
            }
        ),
        encoding="utf-8",
    )
    project = load_project(path)
    assert project.folders[0].resolved is False
