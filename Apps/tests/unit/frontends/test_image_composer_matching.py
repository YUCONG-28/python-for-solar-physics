from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from solar_apps.frontends.image_composer.matching import (
    MatchPlanError,
    build_match_plan,
    iter_match_rows,
    nearest_record,
)
from solar_apps.frontends.image_composer.models import (
    CanvasSettings,
    ComposerProject,
    FolderSource,
    ImageRecord,
    LayoutSlot,
    MatchSettings,
)

BASE = datetime(2026, 7, 17, 12, 0, 0)


def _folder(
    folder_id: str, root: Path, offsets: list[float], *, clock_offset: float = 0.0
) -> FolderSource:
    root.mkdir(parents=True, exist_ok=True)
    records = []
    for ordinal, seconds in enumerate(offsets, start=1):
        path = root / f"frame{ordinal}.png"
        path.touch()
        records.append(
            ImageRecord(ordinal, path, BASE + timedelta(seconds=seconds), "filename")
        )
    return FolderSource(
        id=folder_id,
        path=root,
        name=folder_id,
        records=records,
        start_index=1,
        end_index=len(records),
        offset_seconds=clock_offset,
    )


def _project(tmp_path: Path, *, strict: bool = True) -> ComposerProject:
    master = _folder("master", tmp_path / "master", [0, 1, 2])
    other = _folder("other", tmp_path / "other", [0.25, 1.25, 2.25])
    return ComposerProject(
        canvas=CanvasSettings(width=100, height=80),
        folders=[master, other],
        slots=[
            LayoutSlot.create("master", 1, x=0, y=0, width=50, height=80, z_index=0),
            LayoutSlot.create("other", 1, x=50, y=0, width=50, height=80, z_index=1),
        ],
        matching=MatchSettings(
            master_folder_id="master",
            mode="time",
            tolerance_seconds=0.5,
            strict=strict,
        ),
    )


def test_offset_and_nearest_match_with_candidate_reuse(tmp_path: Path) -> None:
    project = _project(tmp_path)
    project.folders[1].offset_seconds = -0.25

    plan = build_match_plan(project)

    assert [frame.matches["other"].record.ordinal for frame in plan] == [1, 2, 3]
    assert all(frame.matches["other"].delta_seconds == 0 for frame in plan)
    assert all(frame.emitted for frame in plan)

    project.folders[1].records = project.folders[1].records[:1]
    project.folders[1].end_index = 1
    reused = build_match_plan(project)
    assert [frame.matches["other"].record.ordinal for frame in reused] == [1, 1, 1]


def test_nearest_tie_chooses_earlier_then_lower_ordinal(tmp_path: Path) -> None:
    folder = _folder("candidate", tmp_path / "candidate", [-1, 1, -1])
    selected = nearest_record(folder, folder.records, BASE)
    assert selected.ordinal == 1


def test_strict_skips_and_non_strict_emits_but_both_record_overage(
    tmp_path: Path,
) -> None:
    strict_project = _project(tmp_path / "strict", strict=True)
    strict_project.matching.tolerance_seconds = 0.1
    strict_plan = build_match_plan(strict_project)
    assert not any(frame.emitted for frame in strict_plan)
    assert all(frame.output_frame_index is None for frame in strict_plan)

    relaxed = _project(tmp_path / "relaxed", strict=False)
    relaxed.matching.tolerance_seconds = 0.1
    relaxed_plan = build_match_plan(relaxed)
    assert all(frame.emitted for frame in relaxed_plan)
    assert all(frame.matches["other"].over_tolerance for frame in relaxed_plan)


def test_relative_index_maps_both_endpoints_half_up(tmp_path: Path) -> None:
    master = _folder("master", tmp_path / "master", [0, 1, 2, 3, 4])
    other = _folder("other", tmp_path / "other", [0, 10, 20])
    project = ComposerProject(
        canvas=CanvasSettings(width=100, height=80),
        folders=[master, other],
        slots=[LayoutSlot.create("other", 1, x=0, y=0)],
        matching=MatchSettings(master_folder_id="master", mode="relative", strict=True),
    )

    plan = build_match_plan(project)

    assert [frame.matches["other"].record.ordinal for frame in plan] == [1, 2, 2, 3, 3]
    assert all(frame.emitted for frame in plan)


def test_csv_rows_are_per_attempt_and_slot_including_skips(tmp_path: Path) -> None:
    project = _project(tmp_path)
    project.matching.tolerance_seconds = 0.1
    project.slots.append(LayoutSlot.create("other", 2, x=10, y=10, z_index=2))
    plan = build_match_plan(project)
    rows = list(iter_match_rows(project, plan))

    assert len(rows) == len(plan) * len(project.slots)
    assert {row["emitted"] for row in rows} == {False}
    assert {row["output_frame_index"] for row in rows} == {""}
    assert all("time tolerance exceeded" in row["skip_reason"] for row in rows)


def test_invalid_range_is_rejected_without_silent_clamping(tmp_path: Path) -> None:
    project = _project(tmp_path)
    project.folders[1].end_index = 99
    with pytest.raises(MatchPlanError, match="exceeds"):
        build_match_plan(project)
