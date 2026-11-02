"""Build the modelling dataset from the database, using the shared feature functions."""

from datetime import datetime, timedelta

import pandas as pd
import sqlalchemy as sa

from gridcast.common.features import (
    WEATHER_WEIGHTS,
    build_features,
    hourly_load,
    weighted_weather,
)
from gridcast.common.tables import energy_power, weather_hourly

# Load history needed before the first hour, to compute the longest lag.
MAX_LAG = timedelta(hours=168)


def _read(conn: sa.Connection, query: sa.Select) -> pd.DataFrame:
    frame = pd.read_sql(query, conn)
    # Normalize to UTC whatever the time zone of the database session is.
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    return frame


def load_dataset(
    engine: sa.Engine, start: datetime, end: datetime, country: str = "it"
) -> pd.DataFrame:
    """Target and features for every hour in [start, end) that has weather data."""
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start and end must be timezone-aware")

    power_query = sa.select(energy_power.c.ts, energy_power.c.value_mw).where(
        energy_power.c.country == country,
        energy_power.c.series == "Load",
        energy_power.c.ts >= start - MAX_LAG,
        energy_power.c.ts < end,
    )
    weather_query = sa.select(weather_hourly).where(
        weather_hourly.c.ts >= start,
        # One extra hour: radiation is realigned from the following hour.
        weather_hourly.c.ts < end + timedelta(hours=1),
    )
    with engine.connect() as conn:
        power = _read(conn, power_query)
        weather = _read(conn, weather_query)

    features = build_features(hourly_load(power), weighted_weather(weather, WEATHER_WEIGHTS))
    return features[features.index < pd.Timestamp(end)]
