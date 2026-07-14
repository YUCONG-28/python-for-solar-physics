from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from solar_toolkit.webapp.radio_workspace.figure_time import (
    FigureTimeValidationError,
    compute_preflight_revision,
    merge_coverage_segments,
    normalize_figure_timeline,
    normalize_temporal_binding,
    preflight_figure,
    preflight_revision_matches,
    timeline_sample_times,
)


def test_pure_figure_imports_keep_optional_web_dependencies_lazy():
    probe = textwrap.dedent("""
        import importlib
        import importlib.abc
        import sys

        class BlockOptionalWebDependencies(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                del path, target
                if fullname.partition(".")[0] in {"flask", "werkzeug"}:
                    raise ModuleNotFoundError(
                        f"blocked optional web dependency: {fullname}"
                    )
                return None

        sys.meta_path.insert(0, BlockOptionalWebDependencies())
        for module_name in (
            "solar_toolkit.webapp.radio_workspace.figure_media",
            "solar_toolkit.webapp.radio_workspace.figure_time",
            "solar_toolkit.webapp.radio_workspace.native_previews",
        ):
            importlib.import_module(module_name)

        workspace = importlib.import_module("solar_toolkit.webapp.radio_workspace")
        assert callable(workspace.create_radio_blueprint)
        assert "flask" not in sys.modules
        assert "werkzeug" not in sys.modules
        """)
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def _draft(timeline: dict, *bindings: dict) -> dict:
    return {
        "figure_schema_version": 1,
        "id": "active",
        "mode": "mosaic",
        "timeline": timeline,
        "layers": [
            {"id": f"layer-{index}", "temporal_binding": binding}
            for index, binding in enumerate(bindings, start=1)
        ],
    }


def test_timeline_normalizes_utc_and_keeps_sampling_separate_from_playback():
    still = normalize_figure_timeline(
        {"mode": "still", "selected_time_iso": "2025-01-24T12:00:00+08:00"}
    )
    assert still == {
        "mode": "still",
        "selected_time_iso": "2025-01-24T04:00:00Z",
    }

    sequence = {
        "mode": "sequence",
        "start_time_iso": "2025-01-24T04:00:00Z",
        "end_time_iso": "2025-01-24T04:00:02.5Z",
        "sample_interval_s": 1,
        "playback_fps": 24,
    }
    assert timeline_sample_times(sequence) == [
        "2025-01-24T04:00:00Z",
        "2025-01-24T04:00:01Z",
        "2025-01-24T04:00:02Z",
    ]
    assert normalize_figure_timeline(sequence)["playback_fps"] == 24.0


def test_timeline_rejects_reverse_range_and_more_than_ten_thousand_frames():
    with pytest.raises(FigureTimeValidationError, match="must not exceed"):
        normalize_figure_timeline(
            {
                "mode": "sequence",
                "start_time_iso": "2025-01-24T04:00:02Z",
                "end_time_iso": "2025-01-24T04:00:00Z",
            }
        )
    with pytest.raises(FigureTimeValidationError, match="maximum is 10000"):
        timeline_sample_times(
            {
                "mode": "sequence",
                "start_time_iso": "2025-01-24T00:00:00Z",
                "end_time_iso": "2025-01-24T03:00:00Z",
                "sample_interval_s": 1,
                "playback_fps": 10,
            }
        )


def test_series_default_tolerance_is_half_median_cadence_with_one_second_floor():
    binding = normalize_temporal_binding(
        {
            "kind": "series",
            "times_iso": [
                "2025-01-24T04:00:10Z",
                "2025-01-24T04:00:00Z",
                "2025-01-24T04:00:04Z",
            ],
        }
    )
    assert binding["tolerance_s"] == 2.5
    assert [item["time_iso"] for item in binding["samples"]] == [
        "2025-01-24T04:00:00Z",
        "2025-01-24T04:00:04Z",
        "2025-01-24T04:00:10Z",
    ]
    assert (
        normalize_temporal_binding(
            {"kind": "fixed", "time_iso": "2025-01-24T04:00:00Z"}
        )["tolerance_s"]
        == 0.0
    )


def test_spectrogram_segments_merge_only_through_one_second_gap():
    segments = merge_coverage_segments(
        [
            {"start_iso": "2025-01-24T04:00:00Z", "end_iso": "2025-01-24T04:00:10Z"},
            {"start_iso": "2025-01-24T04:00:11Z", "end_iso": "2025-01-24T04:00:20Z"},
            {
                "start_iso": "2025-01-24T04:00:21.000001Z",
                "end_iso": "2025-01-24T04:00:30Z",
            },
        ]
    )
    assert segments == [
        {
            "start_time_iso": "2025-01-24T04:00:00Z",
            "end_time_iso": "2025-01-24T04:00:20Z",
        },
        {
            "start_time_iso": "2025-01-24T04:00:21.000001Z",
            "end_time_iso": "2025-01-24T04:00:30Z",
        },
    ]
    normalized = normalize_temporal_binding(
        {"kind": "spectrogram", "coverage_segments": segments}
    )
    assert normalized["coverage_gaps"] == [
        {
            "start_time_iso": "2025-01-24T04:00:20Z",
            "end_time_iso": "2025-01-24T04:00:21.000001Z",
        }
    ]


def test_still_preflight_recommends_nearest_shared_time_and_ties_earlier():
    result = preflight_figure(
        _draft(
            {"mode": "still", "selected_time_iso": "2025-01-24T04:00:05Z"},
            {
                "kind": "series",
                "times_iso": [
                    "2025-01-24T04:00:00Z",
                    "2025-01-24T04:00:10Z",
                ],
                "tolerance_s": 0,
            },
            {
                "kind": "series",
                "times_iso": [
                    "2025-01-24T04:00:00Z",
                    "2025-01-24T04:00:20Z",
                ],
                "tolerance_s": 0,
            },
        )
    )
    assert result["status"] == "blocked"
    assert result["common_valid_time_iso"] == "2025-01-24T04:00:00Z"
    assert result["recommendation"] == {
        "action": "move_time",
        "selected_time_iso": "2025-01-24T04:00:00Z",
        "requires_confirmation": True,
    }
    assert result["layers"][0]["matches"][0]["source_time_iso"] == (
        "2025-01-24T04:00:00Z"
    )


def test_sequence_recommends_earlier_longest_common_continuous_interval():
    timeline = {
        "mode": "sequence",
        "start_time_iso": "2025-01-24T04:00:00Z",
        "end_time_iso": "2025-01-24T04:00:14Z",
        "sample_interval_s": 1,
        "playback_fps": 10,
    }
    result = preflight_figure(
        _draft(
            timeline,
            {
                "kind": "spectrogram",
                "coverage_segments": [
                    ["2025-01-24T04:00:00Z", "2025-01-24T04:00:04Z"],
                    ["2025-01-24T04:00:10Z", "2025-01-24T04:00:14Z"],
                ],
            },
            {
                "kind": "spectrogram",
                "coverage_segments": [
                    ["2025-01-24T04:00:02Z", "2025-01-24T04:00:06Z"],
                    ["2025-01-24T04:00:08Z", "2025-01-24T04:00:12Z"],
                ],
            },
        )
    )
    assert result["status"] == "blocked"
    assert result["longest_common_interval"] == {
        "start_time_iso": "2025-01-24T04:00:02Z",
        "end_time_iso": "2025-01-24T04:00:04Z",
    }
    assert result["recommendation"] == {
        "action": "trim_range",
        "start_time_iso": "2025-01-24T04:00:02Z",
        "end_time_iso": "2025-01-24T04:00:04Z",
        "estimated_frame_count": 3,
        "requires_confirmation": True,
    }


def test_irregular_series_reports_real_gap_without_interpolation():
    result = preflight_figure(
        _draft(
            {
                "mode": "sequence",
                "start_time_iso": "2025-01-24T04:00:00Z",
                "end_time_iso": "2025-01-24T04:00:12Z",
                "sample_interval_s": 1,
                "playback_fps": 10,
            },
            {
                "kind": "series",
                "times_iso": [
                    "2025-01-24T04:00:00Z",
                    "2025-01-24T04:00:04Z",
                    "2025-01-24T04:00:12Z",
                ],
            },
        )
    )
    layer = result["layers"][0]
    assert layer["tolerance_s"] == 3.0
    assert layer["missing_count"] == 1
    assert layer["missing_intervals"] == [
        {
            "start_time_iso": "2025-01-24T04:00:08Z",
            "end_time_iso": "2025-01-24T04:00:08Z",
            "sample_count": 1,
        }
    ]
    assert layer["matches"][8]["reason"] == "outside_frame_tolerance"


def test_fixed_frame_has_zero_default_tolerance_and_no_silent_hold():
    strict = preflight_figure(
        _draft(
            {
                "mode": "sequence",
                "start_time_iso": "2025-01-24T04:00:00Z",
                "end_time_iso": "2025-01-24T04:00:02Z",
                "sample_interval_s": 1,
                "playback_fps": 10,
            },
            {"kind": "fixed", "time_iso": "2025-01-24T04:00:00Z"},
        )
    )
    assert strict["status"] == "blocked"
    assert strict["layers"][0]["missing_count"] == 2
    assert all(
        item["fallback_applied"] is None for item in strict["layers"][0]["matches"]
    )

    explicit = preflight_figure(
        _draft(
            {"mode": "still", "selected_time_iso": "2025-01-24T04:00:01Z"},
            {
                "kind": "fixed",
                "time_iso": "2025-01-24T04:00:00Z",
                "fallback": "hold_nearest",
            },
        )
    )
    assert explicit["status"] == "ready"
    assert explicit["global_strict_missing_count"] == 1
    assert explicit["layers"][0]["matches"][0]["annotation_required"] is True
    assert explicit["warnings"][0]["fallback_policy"] == "hold_nearest"


def test_spectrogram_out_of_range_note_is_explicit_and_hides_cursor():
    timeline = {"mode": "still", "selected_time_iso": "2025-01-24T04:00:20Z"}
    binding = {
        "kind": "spectrogram",
        "coverage_segments": [["2025-01-24T04:00:00Z", "2025-01-24T04:00:10Z"]],
    }
    strict = preflight_figure(_draft(timeline, binding))
    assert strict["status"] == "blocked"
    assert strict["recommendation"]["selected_time_iso"] == ("2025-01-24T04:00:10Z")

    fallback = preflight_figure(
        _draft(timeline, {**binding, "fallback": "out_of_range_note"})
    )
    match = fallback["layers"][0]["matches"][0]
    assert fallback["status"] == "ready"
    assert match["cursor_visible"] is False
    assert match["fallback_applied"] == "out_of_range_note"
    assert fallback["global_strict_missing_count"] == 1


def test_unknown_binding_blocks_until_user_classifies_the_layer():
    result = preflight_figure(
        _draft(
            {"mode": "still", "selected_time_iso": "2025-01-24T04:00:00Z"},
            {},
        )
    )
    assert result["status"] == "blocked"
    assert result["issues"][0]["code"] == "time_classification_required"
    assert result["recommendation"]["action"] == "resolve_layers"

    timeless = preflight_figure(
        _draft(
            {"mode": "still", "selected_time_iso": "2025-01-24T04:00:00Z"},
            {"kind": "timeless"},
        )
    )
    assert timeless["status"] == "ready"
    assert timeless["common_valid_time_iso"] == "2025-01-24T04:00:00Z"


def test_revision_binds_full_draft_and_sources_but_ignores_previous_preflight():
    draft = _draft(
        {"mode": "still", "selected_time_iso": "2025-01-24T04:00:00Z"},
        {"kind": "timeless"},
    )
    first = compute_preflight_revision(
        draft, {"layer-1": {"sha256": "abc", "size": 10}}
    )
    reordered = {
        "layers": draft["layers"],
        "mode": draft["mode"],
        "id": draft["id"],
        "timeline": draft["timeline"],
        "figure_schema_version": 1,
        "preflight_revision": "old-value",
    }
    assert (
        compute_preflight_revision(
            reordered, {"layer-1": {"size": 10, "sha256": "abc"}}
        )
        == first
    )
    assert preflight_revision_matches(
        draft, first, {"layer-1": {"sha256": "abc", "size": 10}}
    )

    moved = {**draft, "canvas": {"width": 1601, "height": 1200}}
    assert (
        compute_preflight_revision(moved, {"layer-1": {"sha256": "abc", "size": 10}})
        != first
    )
    assert (
        compute_preflight_revision(
            draft, {"layer-1": {"sha256": "changed", "size": 10}}
        )
        != first
    )


def test_preflight_is_json_serializable_and_ignores_hidden_layers():
    draft = _draft(
        {"mode": "still", "selected_time_iso": "2025-01-24T04:00:00Z"},
        {"kind": "timeless"},
        {},
    )
    draft["layers"][1]["visible"] = False
    result = preflight_figure(draft)
    assert result["status"] == "ready"
    assert result["layers"][1]["status"] == "ignored"
    json.dumps(result, allow_nan=False)

    draft["layers"][0]["visible"] = False
    empty = preflight_figure(draft)
    assert empty["status"] == "blocked"
    assert empty["issues"][0]["code"] == "no_visible_layers"


def test_preflight_output_can_be_loaded_by_the_versioned_contract():
    from solar_toolkit.webapp.radio_workspace.contracts import RadioFigurePreflight

    draft = _draft(
        {"mode": "still", "selected_time_iso": "2025-01-24T04:00:00Z"},
        {"kind": "timeless"},
    )
    draft["workspace_id"] = "workspace-one"
    fingerprints = {"layer-1": {"sha256": "abc"}}
    result = preflight_figure(draft, source_fingerprints=fingerprints)
    contract = RadioFigurePreflight.from_dict(result)

    assert contract.workspace_id == "workspace-one"
    assert contract.missing_count == 0
    assert contract.common_valid_time == "2025-01-24T04:00:00Z"
    assert contract.source_fingerprints == fingerprints


def test_invalid_duplicate_series_times_and_unconfirmed_fallback_names_fail_closed():
    with pytest.raises(FigureTimeValidationError, match="unique timestamps"):
        normalize_temporal_binding(
            {
                "kind": "series",
                "times_iso": [
                    "2025-01-24T04:00:00Z",
                    "2025-01-24T04:00:00+00:00",
                ],
            }
        )
    with pytest.raises(FigureTimeValidationError, match="invalid for spectrogram"):
        normalize_temporal_binding(
            {
                "kind": "spectrogram",
                "coverage_segments": [["2025-01-24T04:00:00Z", "2025-01-24T04:00:10Z"]],
                "fallback": "hold_last",
            }
        )
