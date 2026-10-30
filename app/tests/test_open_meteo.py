from datetime import UTC, datetime

import pytest

from gridcast.ingest.open_meteo import parse_hourly

# Three hours on 15 January 2026, as returned with timezone=UTC.
PAYLOAD = {
    "latitude": 45.46,
    "longitude": 9.19,
    "hourly_units": {"time": "iso8601", "temperature_2m": "°C", "shortwave_radiation": "W/m²"},
    "hourly": {
        "time": ["2026-01-15T00:00", "2026-01-15T01:00", "2026-01-15T02:00"],
        "temperature_2m": [3.1, 2.8, None],
        "shortwave_radiation": [0.0, 0.0, 0.0],
    },
}


def test_one_point_per_hour() -> None:
    points = parse_hourly(PAYLOAD, "milano")
    assert len(points) == 3
    assert all(p.location == "milano" for p in points)


def test_timestamps_are_timezone_aware_utc() -> None:
    points = parse_hourly(PAYLOAD, "milano")
    assert points[0].ts == datetime(2026, 1, 15, 0, 0, tzinfo=UTC)
    assert all(p.ts.tzinfo is not None for p in points)


def test_missing_values_stay_null() -> None:
    points = parse_hourly(PAYLOAD, "milano")
    assert points[2].temperature_c is None
    assert points[2].shortwave_radiation_wm2 == 0.0


def test_misaligned_series_raises() -> None:
    payload = {
        "hourly": {
            "time": ["2026-01-15T00:00", "2026-01-15T01:00"],
            "temperature_2m": [3.1, 2.8],
            "shortwave_radiation": [0.0],
        }
    }
    with pytest.raises(ValueError):
        parse_hourly(payload, "milano")
