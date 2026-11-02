from datetime import UTC, date, datetime

import pandas as pd

from gridcast.trainer.predict import target_day_bounds


def _hours(day: date) -> int:
    start, end = target_day_bounds(day)
    return len(pd.date_range(start, end, freq="h", inclusive="left"))


def test_normal_day_has_24_hours() -> None:
    assert _hours(date(2026, 11, 3)) == 24


def test_spring_forward_day_has_23_hours() -> None:
    assert _hours(date(2026, 3, 29)) == 23


def test_fall_back_day_has_25_hours() -> None:
    assert _hours(date(2026, 10, 25)) == 25


def test_day_starts_at_italian_midnight() -> None:
    start, _ = target_day_bounds(date(2026, 11, 3))
    assert start == datetime(2026, 11, 2, 23, 0, tzinfo=UTC)
