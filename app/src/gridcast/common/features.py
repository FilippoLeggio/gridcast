"""Feature engineering shared by the trainer and the API, to avoid training-serving skew."""

from collections.abc import Mapping

import holidays
import numpy as np
import pandas as pd

LOCAL_TZ = "Europe/Rome"

# Heuristic national weights by approximate regional demand: see README, "Known limitations".
WEATHER_WEIGHTS: dict[str, float] = {
    "milano": 0.30,
    "torino": 0.15,
    "bologna": 0.15,
    "roma": 0.20,
    "napoli": 0.12,
    "palermo": 0.08,
}

# Degree-day bases: below 18 °C buildings need heating, above 22 °C cooling.
HEATING_BASE_C = 18.0
COOLING_BASE_C = 22.0

# Model inputs, in a fixed order shared by training and serving.
FEATURE_COLUMNS: list[str] = [
    "temperature_c",
    "shortwave_radiation_wm2",
    "heating_degrees",
    "cooling_degrees",
    "hour",
    "day_of_week",
    "is_weekend",
    "is_holiday",
    "doy_sin",
    "doy_cos",
    "load_lag_48h",
    "load_lag_168h",
]


def hourly_load(power: pd.DataFrame) -> pd.Series:
    """Mean load per hour in MW, indexed by the start of each UTC hour, at any input resolution."""
    hours = power["ts"].dt.floor("h")
    load = power.groupby(hours)["value_mw"].mean().dropna()
    load.index.name = "ts"
    return load.rename("load_mw")


def weighted_weather(weather: pd.DataFrame, weights: Mapping[str, float]) -> pd.DataFrame:
    """Weighted national average per hour, renormalizing weights over the cities with a value."""
    city_weight = weather["location"].map(weights)
    averages = {}
    for column in ("temperature_c", "shortwave_radiation_wm2"):
        # A city counts in an hour only if it has both a weight and a value.
        has_value = weather[column].notna() & city_weight.notna()
        parts = pd.DataFrame(
            {
                "ts": weather["ts"],
                "weighted_sum": (weather[column] * city_weight).where(has_value, 0.0),
                "weight_sum": city_weight.where(has_value, 0.0),
            }
        )
        sums = parts.groupby("ts")[["weighted_sum", "weight_sum"]].sum()
        # Hours where no city has a value become NaN instead of a division by zero.
        averages[column] = sums["weighted_sum"] / sums["weight_sum"].replace(0.0, np.nan)
    result = pd.DataFrame(averages)
    result.index.name = "ts"
    return result


def calendar_features(index: pd.DatetimeIndex) -> pd.DataFrame:
    """Calendar features in Italian local time, indexed like the input UTC index."""
    local = index.tz_convert(LOCAL_TZ)
    italian_holidays = holidays.country_holidays("IT", years=sorted(set(local.year)))
    # Day of the year on a circle, so that 31 December sits next to 1 January.
    angle = 2 * np.pi * (local.dayofyear.to_numpy() - 1) / 365.25
    return pd.DataFrame(
        {
            "hour": local.hour,
            "day_of_week": local.dayofweek,
            "is_weekend": (local.dayofweek >= 5).astype(int),
            "is_holiday": [int(day in italian_holidays) for day in local.date],
            "doy_sin": np.sin(angle),
            "doy_cos": np.cos(angle),
        },
        index=index,
    )


def build_features(load: pd.Series, weather: pd.DataFrame) -> pd.DataFrame:
    """Target and model inputs for every hour that has weather, load included where known."""
    index = weather.index
    features = pd.DataFrame(index=index)
    features["load_mw"] = load.reindex(index)

    features["temperature_c"] = weather["temperature_c"]
    features["shortwave_radiation_wm2"] = weather["shortwave_radiation_wm2"]
    features["heating_degrees"] = (HEATING_BASE_C - weather["temperature_c"]).clip(lower=0)
    features["cooling_degrees"] = (weather["temperature_c"] - COOLING_BASE_C).clip(lower=0)

    features = features.join(calendar_features(index))

    # Time-based lags: the value 48 h earlier, not 48 rows earlier.
    features["load_lag_48h"] = load.shift(48, freq="h").reindex(index)
    features["load_lag_168h"] = load.shift(168, freq="h").reindex(index)

    return features[["load_mw", *FEATURE_COLUMNS]]
