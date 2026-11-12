"""HTTP API: serves stored forecasts and their accuracy against actual load."""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Annotated

import sqlalchemy as sa
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest
from pydantic import BaseModel
from starlette.routing import Match

from gridcast.api.metrics import REQUEST_DURATION, DatabaseCollector
from gridcast.common.config import Settings
from gridcast.common.db import create_db_engine
from gridcast.common.tables import forecasts
from gridcast.common.timeutil import LOCAL_TZ, target_day_bounds


class HourlyForecast(BaseModel):
    target_time: datetime  # Italian local time, with its UTC offset
    forecast_mw: float
    baseline_mw: float | None


class ForecastResponse(BaseModel):
    day: date
    model_name: str
    model_version: str
    issued_at: datetime
    hours: list[HourlyForecast]


class DailyAccuracy(BaseModel):
    day: date
    hours: int
    model_mape: float
    baseline_mape: float | None


class AccuracyResponse(BaseModel):
    days: list[DailyAccuracy]
    model_mape: float | None
    baseline_mape: float | None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # One connection pool for the whole process, created at startup, closed at shutdown.
    app.state.engine = create_db_engine(Settings().database_url)
    # Data and forecast health, read from the database at every Prometheus scrape.
    collector = DatabaseCollector(app.state.engine)
    REGISTRY.register(collector)
    try:
        yield
    finally:
        # Unregister so that a new app instance (tests, reloads) can register its own.
        REGISTRY.unregister(collector)
        app.state.engine.dispose()


app = FastAPI(title="GridCast API", version="0.1.0", lifespan=lifespan)


def _route_template(request: Request) -> str:
    """The route pattern (e.g. /forecast), never the raw path, to keep label cardinality bounded."""
    for route in request.app.router.routes:
        match, _ = route.matches(request.scope)
        if match == Match.FULL:
            return route.path
    return "unmatched"


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    start = time.perf_counter()
    status = 500  # recorded if the handler raises
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        REQUEST_DURATION.labels(request.method, _route_template(request), str(status)).observe(
            time.perf_counter() - start
        )


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    # A plain def runs in a worker thread: the collector's database queries
    #  never block the event loop.
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


def get_engine(request: Request) -> sa.Engine:
    return request.app.state.engine


EngineDep = Annotated[sa.Engine, Depends(get_engine)]


@app.get("/healthz")
def healthz() -> dict:
    """Liveness: the process answers. Never touches the database."""
    return {"status": "ok"}


@app.get("/readyz")
def readyz(engine: EngineDep) -> dict:
    """Readiness: the database is reachable, so the API can serve requests."""
    try:
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
    except sa.exc.SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ready"}


@app.get("/forecast", response_model=ForecastResponse)
def get_forecast(engine: EngineDep, day: date | None = None) -> ForecastResponse:
    """Hourly forecast for an Italian day, tomorrow by default."""
    day = day or datetime.now(LOCAL_TZ).date() + timedelta(days=1)
    start, end = target_day_bounds(day)
    query = (
        sa.select(forecasts)
        .where(forecasts.c.target_ts >= start, forecasts.c.target_ts < end)
        .order_by(forecasts.c.target_ts)
    )
    with engine.connect() as conn:
        rows = conn.execute(query).all()
    if not rows:
        raise HTTPException(status_code=404, detail=f"no forecast for {day}")

    return ForecastResponse(
        day=day,
        model_name=rows[0].model_name,
        model_version=rows[0].model_version,
        issued_at=rows[0].issued_at,
        hours=[
            HourlyForecast(
                target_time=row.target_ts.astimezone(LOCAL_TZ),
                forecast_mw=row.forecast_mw,
                baseline_mw=row.baseline_mw,
            )
            for row in rows
        ],
    )


# Actual load is averaged per hour, then compared with the stored forecast of that hour.
ACCURACY_SQL = sa.text(
    """
    WITH actual AS (
        SELECT date_trunc('hour', ts) AS hour_ts, avg(value_mw) AS actual_mw
        FROM energy_power
        WHERE country = 'it' AND series = 'Load' AND ts >= :start AND ts < :end
        GROUP BY 1
    )
    SELECT (f.target_ts AT TIME ZONE 'Europe/Rome')::date AS day,
           count(*) AS hours,
           avg(abs(f.forecast_mw - a.actual_mw) / a.actual_mw) * 100 AS model_mape,
           avg(abs(f.baseline_mw - a.actual_mw) / a.actual_mw) * 100 AS baseline_mape
    FROM forecasts f
    JOIN actual a ON a.hour_ts = f.target_ts
    WHERE f.target_ts >= :start AND f.target_ts < :end
    GROUP BY 1
    ORDER BY 1
    """
)


@app.get("/accuracy", response_model=AccuracyResponse)
def get_accuracy(
    engine: EngineDep,
    days: Annotated[int, Query(ge=1, le=90, description="Past days to evaluate.")] = 7,
) -> AccuracyResponse:
    """Forecast error over the last days, compared with the naive baseline."""
    today = datetime.now(LOCAL_TZ).date()
    start, _ = target_day_bounds(today - timedelta(days=days))
    _, end = target_day_bounds(today)  # today included, possibly partial
    with engine.connect() as conn:
        rows = conn.execute(ACCURACY_SQL, {"start": start, "end": end}).all()

    daily = [DailyAccuracy(**row._mapping) for row in rows]
    total_hours = sum(d.hours for d in daily)

    def weighted(values: list[tuple[float | None, int]]) -> float | None:
        known = [(v, h) for v, h in values if v is not None]
        hours = sum(h for _, h in known)
        return sum(v * h for v, h in known) / hours if hours else None

    return AccuracyResponse(
        days=daily,
        model_mape=weighted([(d.model_mape, d.hours) for d in daily]) if total_hours else None,
        baseline_mape=weighted([(d.baseline_mape, d.hours) for d in daily]),
    )
