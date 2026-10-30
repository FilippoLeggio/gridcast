from datetime import UTC, datetime

import pytest

from gridcast.ingest.energy_charts import parse_public_power

# Two quarter-hours on 1 January 2026, UTC.
PAYLOAD = {
    "unix_seconds": [1767225600, 1767226500],
    "production_types": [
        {"name": "Load", "data": [30000.0, 29500.5]},
        {"name": "Fossil hard coal", "data": [None, 120.0]},
        {"name": "Renewable share of load", "data": [40.1, 41.0]},
    ],
    "deprecated": False,
}


def test_one_row_per_series_and_timestamp() -> None:
    points = parse_public_power(PAYLOAD, "it")
    assert len(points) == 4
    assert {p.series for p in points} == {"Load", "Fossil hard coal"}


def test_timestamps_are_utc() -> None:
    points = parse_public_power(PAYLOAD, "it")
    assert points[0].ts == datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    assert points[1].ts == datetime(2026, 1, 1, 0, 15, tzinfo=UTC)


def test_missing_values_stay_null() -> None:
    points = parse_public_power(PAYLOAD, "it")
    coal = [p.value_mw for p in points if p.series == "Fossil hard coal"]
    assert coal == [None, 120.0]


def test_misaligned_series_raises() -> None:
    # Three timestamps, but the solar series only has two values.
    payload = {
        "unix_seconds": [1767225600, 1767226500, 1767227400],
        "production_types": [
            {"name": "Load", "data": [30000.0, 29500.5, 29100.0]},
            {"name": "Solar", "data": [0.0, 0.0]},
        ],
        "deprecated": False,
    }

    with pytest.raises(ValueError, match="'Solar' has 2 values for 3 timestamps"):
        parse_public_power(payload, "it")
