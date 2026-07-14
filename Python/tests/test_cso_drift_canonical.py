"""Canonical result identity and compatibility semantics for CSO drift lines."""

from __future__ import annotations

import datetime as dt
import math

import matplotlib.dates as mdates
import pytest

from solar_toolkit.radio import cso_workflow, drift_rate


def test_cso_drift_result_is_the_canonical_result_type():
    assert cso_workflow.DriftRateResult is drift_rate.DriftRateResult


def test_canonical_drift_calculation_keeps_sorted_and_flagged_defaults():
    reverse_line = {
        "t_start": "2025-05-03T07:15:20",
        "t_end": "2025-05-03T07:15:10",
        "f_start_mhz": 100.0,
        "f_end_mhz": 200.0,
    }

    result = drift_rate.calculate_drift_rate_from_line(reverse_line)

    assert result.label == "drift_001"
    assert result.mode == "manual"
    assert result.t_start == dt.datetime(2025, 5, 3, 7, 15, 10)
    assert result.t_end == dt.datetime(2025, 5, 3, 7, 15, 20)
    assert result.f_start_mhz == 200.0
    assert result.f_end_mhz == 100.0
    assert result.duration_s == 10.0
    assert result.bandwidth_mhz == -100.0
    assert result.drift_rate_mhz_s == -10.0
    assert result.quality_flag == "ok"
    assert result.warning == "endpoints_sorted_by_time"

    zero_line = {
        "t_start": "2025-05-03T07:15:10",
        "t_end": "2025-05-03T07:15:10",
        "f_start_mhz": 100.0,
        "f_end_mhz": 200.0,
    }
    zero_result = drift_rate.calculate_drift_rate_from_line(zero_line)

    assert math.isnan(zero_result.drift_rate_mhz_s)
    assert math.isnan(zero_result.abs_drift_rate_mhz_s)
    assert zero_result.quality_flag == "invalid_zero_duration"
    assert zero_result.warning == "zero_duration"


def test_cso_drift_calculation_keeps_numeric_fallback_and_click_order():
    t_start = dt.datetime(2025, 5, 3, 7, 15, 20)
    t_end = dt.datetime(2025, 5, 3, 7, 15, 10)
    reverse_line = {
        "t_start": "invalid but numeric fallback wins",
        "t_end": "invalid but numeric fallback wins",
        "t_start_num": mdates.date2num(t_start),
        "t_end_num": mdates.date2num(t_end),
        "f_start_mhz": 100.0,
        "f_end_mhz": 200.0,
        "color": "cyan",
    }

    result = cso_workflow.calculate_drift_rate_from_line(reverse_line)

    assert type(result) is drift_rate.DriftRateResult
    assert result.label == "drift"
    assert result.mode == "manual_endpoint"
    assert result.t_start == t_start
    assert result.t_end == t_end
    assert result.f_start_mhz == 100.0
    assert result.f_end_mhz == 200.0
    assert result.duration_s == -10.0
    assert result.bandwidth_mhz == 100.0
    assert result.drift_rate_mhz_s == -10.0
    assert result.abs_drift_rate_mhz_s == 10.0
    assert result.color == "cyan"
    assert result.quality_flag == "ok"
    assert result.warning == ""

    zero_line = {
        "t_start": "2025-05-03T07:15:10",
        "t_end": "2025-05-03T07:15:10",
        "f_start_mhz": 100.0,
        "f_end_mhz": 200.0,
    }
    with pytest.raises(ValueError, match="zero-duration line"):
        cso_workflow.calculate_drift_rate_from_line(zero_line)


def test_cso_public_calculator_delegates_through_the_canonical_helper(monkeypatch):
    sentinel = object()
    captured = {}

    def fake_calculate(line, **kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(
        drift_rate,
        "_calculate_drift_rate_from_line",
        fake_calculate,
    )
    line = {
        "t_start": "2025-05-03T07:15:10",
        "t_end": "2025-05-03T07:15:20",
        "f_start_mhz": 200.0,
        "f_end_mhz": 100.0,
    }

    assert cso_workflow.calculate_drift_rate_from_line(line) is sentinel
    assert captured["profile"] is drift_rate._CSO_DRIFT_RATE_PROFILE
    assert captured["t_start"] == dt.datetime(2025, 5, 3, 7, 15, 10)
    assert captured["t_end"] == dt.datetime(2025, 5, 3, 7, 15, 20)
