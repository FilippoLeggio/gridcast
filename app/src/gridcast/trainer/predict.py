"""Batch prediction: forecast tomorrow's hourly load with the champion model."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import mlflow
import pandas as pd
import sqlalchemy as sa
from mlflow.tracking import MlflowClient

from gridcast.common.db import upsert_forecasts
from gridcast.common.features import FEATURE_COLUMNS
from gridcast.trainer.dataset import load_dataset
from gridcast.trainer.train import BASELINE, CHAMPION_ALIAS, MODEL_NAME

LOCAL_TZ = ZoneInfo("Europe/Rome")


def target_day_bounds(day: date) -> tuple[datetime, datetime]:
    """UTC instants of local midnight at the start and at the end of an Italian day.

    The hours in between are 23, 24 or 25, depending on daylight saving changes.
    """
    start_local = datetime.combine(day, time.min, tzinfo=LOCAL_TZ)
    end_local = datetime.combine(day + timedelta(days=1), time.min, tzinfo=LOCAL_TZ)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def predict_day(engine: sa.Engine, day: date) -> dict:
    """Forecast every hour of an Italian day and store it. Fails if any hour lacks weather."""
    start, end = target_day_bounds(day)
    expected = pd.date_range(start, end, freq="h", inclusive="left")

    # Resolve the alias once, then load that exact version: the alias may move meanwhile.
    version = MlflowClient().get_model_version_by_alias(MODEL_NAME, CHAMPION_ALIAS).version
    model = mlflow.lightgbm.load_model(f"models:/{MODEL_NAME}/{version}")

    features = load_dataset(engine, start, end)
    with_weather = features.index[features["temperature_c"].notna()]
    missing = expected.difference(with_weather)
    if len(missing) > 0:
        raise RuntimeError(
            f"no weather for {len(missing)} of {len(expected)} hours of {day}: "
            "run the weather ingest first"
        )
    features = features.loc[expected]

    predicted = model.predict(features[FEATURE_COLUMNS])
    issued_at = datetime.now(UTC)
    rows = [
        {
            "target_ts": ts,
            "forecast_mw": float(forecast),
            "baseline_mw": None if pd.isna(baseline) else float(baseline),
            "model_name": MODEL_NAME,
            "model_version": str(version),
            "issued_at": issued_at,
        }
        for ts, forecast, baseline in zip(expected, predicted, features[BASELINE], strict=True)
    ]
    with engine.begin() as conn:
        written = upsert_forecasts(conn, rows)

    return {
        "day": day,
        "hours": len(expected),
        "model_version": version,
        "rows_written": written,
        "missing_lags": int(features[["load_lag_48h", "load_lag_168h"]].isna().any(axis=1).sum()),
        "forecast": pd.Series(predicted, index=expected.tz_convert(LOCAL_TZ)),
    }
