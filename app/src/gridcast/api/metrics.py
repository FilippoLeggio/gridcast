"""Prometheus metrics of the API: HTTP traffic,
plus data and forecast health read from the database."""

import logging
from collections.abc import Iterator
from datetime import datetime, timedelta

import sqlalchemy as sa
from prometheus_client import Histogram
from prometheus_client.core import GaugeMetricFamily, Metric
from prometheus_client.registry import Collector
from sqlalchemy.exc import SQLAlchemyError

from gridcast.common.timeutil import LOCAL_TZ, target_day_bounds

logger = logging.getLogger(__name__)

# Buckets include the latency SLO threshold (250 ms), so the SLO can be computed exactly.
REQUEST_DURATION = Histogram(
    "gridcast_http_request_duration_seconds",
    "Duration of HTTP requests handled by the API.",
    ["method", "route", "status"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

FRESHNESS = sa.text("""
    SELECT EXTRACT(EPOCH FROM now() - max(ts))
    FROM energy_power WHERE country = 'it' AND series = 'Load'
""")

FORECAST_HOURS = sa.text("""
    SELECT count(*) FROM forecasts WHERE target_ts >= :start AND target_ts < :end
""")

LATEST_MODEL = sa.text("""
    SELECT model_version, EXTRACT(EPOCH FROM max(issued_at))
    FROM forecasts GROUP BY model_version ORDER BY max(issued_at) DESC LIMIT 1
""")

# Forecasts of the last 7 days against the hourly mean of the actual load.
MAPE_7D = sa.text("""
    WITH actual AS (
        SELECT date_trunc('hour', ts) AS hour, avg(value_mw) AS load_mw
        FROM energy_power
        WHERE country = 'it' AND series = 'Load' AND ts >= now() - interval '7 days'
        GROUP BY 1
    )
    SELECT
            avg(abs(f.forecast_mw - a.load_mw) / a.load_mw) * 100,
            avg(abs(f.baseline_mw - a.load_mw) / a.load_mw)
                FILTER (WHERE f.baseline_mw IS NOT NULL)* 100,
            count(*)
    FROM forecasts f JOIN actual a ON a.hour = f.target_ts
    WHERE f.target_ts >= now() - interval '7 days'
""")


def _gauge(
    name: str, doc: str, value: float, labels: dict[str, str] | None = None
) -> GaugeMetricFamily:
    family = GaugeMetricFamily(name, doc, labels=list(labels or {}))
    family.add_metric(list((labels or {}).values()), value)
    return family


class DatabaseCollector(Collector):
    """Reads data and forecast health from the database at every scrape."""

    def __init__(self, engine: sa.Engine) -> None:
        self.engine = engine

    def collect(self) -> Iterator[Metric]:
        start, end = target_day_bounds(datetime.now(LOCAL_TZ).date() + timedelta(days=1))
        try:
            with self.engine.connect() as conn:
                freshness = conn.execute(FRESHNESS).scalar()
                hours_tomorrow = conn.execute(FORECAST_HOURS, {"start": start, "end": end}).scalar()
                latest = conn.execute(LATEST_MODEL).first()
                model_mape, baseline_mape, matched_hours = conn.execute(MAPE_7D).one()
        except SQLAlchemyError:
            # Never fail the whole scrape: report the problem as a metric of its own.
            logger.exception("metrics queries failed")
            yield _gauge(
                "gridcast_metrics_db_up", "1 if the metrics queries reached the database.", 0
            )
            return

        yield _gauge("gridcast_metrics_db_up", "1 if the metrics queries reached the database.", 1)
        if freshness is not None:
            yield _gauge(
                "gridcast_data_freshness_seconds",
                "Age of the latest hour of actual load.",
                float(freshness),
            )
        expected = (end - start) // timedelta(hours=1)
        yield _gauge(
            "gridcast_forecast_missing_hours_tomorrow",
            "Hours of tomorrow (Italian day) without a forecast.",
            expected - hours_tomorrow,
        )
        if latest is not None:
            version, issued_at = latest
            yield _gauge(
                "gridcast_forecast_model_info",
                "Model version of the latest forecasts (value is always 1).",
                1,
                {"version": str(version)},
            )
            yield _gauge(
                "gridcast_forecast_last_issued_timestamp_seconds",
                "When the latest forecast was written.",
                float(issued_at),
            )
        if matched_hours:
            mape = GaugeMetricFamily(
                "gridcast_mape_7d_percent",
                "MAPE over the last 7 days of forecast hours with actual load.",
                labels=["forecaster"],
            )
            mape.add_metric(["model"], float(model_mape))
            if baseline_mape is not None:
                mape.add_metric(["baseline"], float(baseline_mape))
            yield mape
