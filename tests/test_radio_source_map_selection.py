from __future__ import annotations

import json

import pytest


def _selection(*, mode: str, candidate_id: str, item: dict) -> dict:
    return {
        "schema_version": 1,
        "mode": mode,
        "candidate_ids": [candidate_id],
        "items": [dict(item, candidate_id=candidate_id)],
    }


def test_workspace_selection_filters_multi_band_slots_by_original_index(tmp_path):
    from solar_toolkit.radio import source_map_workflow as workflow

    slots = [
        [(str(tmp_path / "slot0_rr.fits"), str(tmp_path / "slot0_ll.fits"))],
        [(str(tmp_path / "slot1_rr.fits"), str(tmp_path / "slot1_ll.fits"))],
    ]
    selection = _selection(
        mode="multi_band",
        candidate_id="slot-0001",
        item={"slot_index": 1, "paths": workflow._source_map_slot_file_paths(slots[1])},
    )

    selected = workflow._selected_workspace_slot_items(slots, selection)

    assert selected == [(1, slots[1])]

    stale = _selection(
        mode="multi_band",
        candidate_id="slot-0001",
        item={"slot_index": 1, "paths": [str(tmp_path / "other.fits")]},
    )
    with pytest.raises(ValueError, match="no longer matches"):
        workflow._selected_workspace_slot_items(slots, stale)


def test_workspace_selection_filters_single_files_and_requires_rrll_pair(tmp_path):
    from solar_toolkit.radio import source_map_workflow as workflow

    rr_path = tmp_path / "149MHz" / "RR" / "sample.fits"
    ll_path = tmp_path / "149MHz" / "LL" / "sample.fits"
    rr_path.parent.mkdir(parents=True)
    ll_path.parent.mkdir(parents=True)
    rr_path.write_bytes(b"rr")
    ll_path.write_bytes(b"ll")

    selection = _selection(
        mode="single_band",
        candidate_id="file-0001",
        item={
            "run_path": str(ll_path),
            "paths": [str(rr_path), str(ll_path)],
        },
    )
    assert workflow._selected_workspace_files(
        selection,
        {"combine_polarizations": True, "polarization": "RR+LL"},
    ) == [str(ll_path)]

    with pytest.raises(ValueError, match="matched RR/LL"):
        workflow._selected_workspace_files(
            _selection(
                mode="single_band",
                candidate_id="file-0001",
                item={"run_path": str(rr_path), "paths": [str(rr_path)]},
            ),
            {"combine_polarizations": True, "polarization": "RR+LL"},
        )

    assert workflow._selected_workspace_files(
        _selection(
            mode="single_band",
            candidate_id="file-0001",
            item={"run_path": str(rr_path), "paths": [str(rr_path)]},
        ),
        {"combine_polarizations": False, "polarization": "RR"},
    ) == [str(rr_path)]


def test_source_map_run_uses_only_selected_multi_band_slot(monkeypatch, tmp_path):
    from solar_toolkit.radio import source_map_workflow as workflow

    slots = [
        [(str(tmp_path / "slot0_rr.fits"), str(tmp_path / "slot0_ll.fits"))],
        [(str(tmp_path / "slot1_rr.fits"), str(tmp_path / "slot1_ll.fits"))],
    ]
    selection = _selection(
        mode="multi_band",
        candidate_id="slot-0001",
        item={"slot_index": 1, "paths": workflow._source_map_slot_file_paths(slots[1])},
    )
    plotted: list[tuple[int, list]] = []
    monkeypatch.setattr(workflow, "_build_multi_band_slots", lambda _cfg: slots)
    monkeypatch.setattr(workflow, "_estimate_safe_workers", lambda **_kwargs: 1)
    monkeypatch.setattr(
        workflow, "_should_precompute_fixed_band_ranges", lambda _cfg: False
    )
    monkeypatch.setattr(workflow, "_spectrogram_panel_enabled", lambda _cfg: False)
    monkeypatch.setattr(
        workflow,
        "plot_multi_band_slot",
        lambda slot_idx, slot, *_args, **_kwargs: plotted.append((slot_idx, slot)),
    )

    workflow.run_source_map(
        {
            "mode": "multi_band",
            "data": {
                "multi_band_root": str(tmp_path),
                "selected_source_map_json": json.dumps(selection),
                "combine_polarizations": True,
                "polarization": "RR+LL",
                "max_workers": 1,
            },
            "display": {"color_range_mode": "auto", "show_plot": False},
            "features": {"spectrogram_panel": False},
        },
        argv=[],
    )

    assert plotted == [(1, slots[1])]
