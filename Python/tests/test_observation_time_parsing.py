"""Lightweight tests for observation-time parsing examples."""

from datetime import datetime


def test_observation_time_difference_seconds():
    dt0 = datetime.strptime("20250124043739681", "%Y%m%d%H%M%S%f")
    dt1 = datetime.strptime("2025-01-24T033001Z", "%Y-%m-%dT%H%M%SZ")

    assert dt0 == datetime(2025, 1, 24, 4, 37, 39, 681000)
    assert dt1 == datetime(2025, 1, 24, 3, 30, 1)
    assert (dt0 - dt1).total_seconds() == 4058.681
