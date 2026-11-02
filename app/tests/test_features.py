from datetime import UTC, datetime

import pandas as pd
import pytest

from gridcast.common.features import (
    build_features,
    calendar_features,
    hourly_load,
    weighted_weather,
)


def _utc(*args: int) -> pd.Timestamp:
    return pd.Timestamp(datetime(*args, tzinfo=UTC))


def test_hourly_load_averages_quarter_hours() -> None:
    power = pd.DataFrame(
        {
            "ts": [_utc(2025, 3, 10, 8, m) for m in (0, 15, 30, 45)] + [_utc(2025, 3, 10, 9)],
            "value_mw": [100.0, 110.0, 120.0, 130.0, 200.0],
        }
    )
    load = hourly_load(power)
    assert load.name == "load_mw"
    assert load[_utc(2025, 3, 10, 8)] == pytest.approx(115.0)
    assert load[_utc(2025, 3, 10, 9)] == pytest.approx(200.0)


def test_hourly_load_ignores_nulls() -> None:
    power = pd.DataFrame(
        {
            "ts": [_utc(2025, 3, 10, 8, m) for m in (0, 15, 30, 45)],
            "value_mw": [100.0, None, 120.0, 140.0],
        }
    )
    assert hourly_load(power)[_utc(2025, 3, 10, 8)] == pytest.approx(120.0)


def test_weighted_weather_renormalizes_when_a_city_is_missing() -> None:
    h1, h2 = _utc(2025, 7, 1, 12), _utc(2025, 7, 1, 13)
    weather = pd.DataFrame(
        {
            "location": ["a", "b", "b"],
            "ts": [h1, h1, h2],
            "temperature_c": [10.0, 20.0, 20.0],
            "shortwave_radiation_wm2": [0.0, 0.0, 0.0],
        }
    )
    out = weighted_weather(weather, {"a": 0.75, "b": 0.25})
    assert out.loc[h1, "temperature_c"] == pytest.approx(12.5)
    assert out.loc[h2, "temperature_c"] == pytest.approx(20.0)


def test_calendar_uses_italian_local_time_across_dst() -> None:
    # 29 March 2026: clocks go forward, so 01:00 UTC is already 03:00 in Rome.
    idx = pd.DatetimeIndex([_utc(2026, 3, 29, 0), _utc(2026, 3, 29, 1)])
    assert list(calendar_features(idx)["hour"]) == [1, 3]


def test_calendar_flags_italian_holidays() -> None:
    # 2 June (Republic Day) and Christmas are holidays, 3 June is not.
    idx = pd.DatetimeIndex([_utc(2026, 6, 2, 10), _utc(2026, 6, 3, 10), _utc(2026, 12, 25, 10)])
    assert list(calendar_features(idx)["is_holiday"]) == [1, 0, 1]


def test_lags_are_time_based_not_positional() -> None:
    hours = pd.date_range(_utc(2025, 1, 1, 0), periods=200, freq="h")
    # Load equals the hour number, with hour 100 missing.
    load = pd.Series(range(200), index=hours, dtype=float, name="load_mw").drop(hours[100])
    weather = pd.DataFrame({"temperature_c": 10.0, "shortwave_radiation_wm2": 0.0}, index=hours)
    feats = build_features(load, weather)

    # The gap sits between these hours and their lags: a positional shift would be off by one.
    assert feats.loc[hours[120], "load_lag_48h"] == 72.0
    assert feats.loc[hours[190], "load_lag_168h"] == 22.0
    # 48 hours after the missing hour, the lag is unknown.
    assert pd.isna(feats.loc[hours[148], "load_lag_48h"])
    # The target stays unknown where load is missing, but the row exists.
    assert pd.isna(feats.loc[hours[100], "load_mw"])
    # Degree features from a constant 10 °C.
    assert feats.loc[hours[0], "heating_degrees"] == pytest.approx(8.0)
    assert feats.loc[hours[0], "cooling_degrees"] == pytest.approx(0.0)
