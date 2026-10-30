"""Command line entry point for data ingestion."""

import time
from dataclasses import asdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import typer

from gridcast.common.config import Settings
from gridcast.common.db import create_db_engine, track_run, upsert_power, upsert_weather
from gridcast.ingest.energy_charts import fetch_public_power
from gridcast.ingest.open_meteo import LOCATIONS, WeatherPoint, fetch_archive, fetch_forecast

# Energy-Charts interprets start and end as local Italian days.
LOCAL_TZ = ZoneInfo("Europe/Rome")
app = typer.Typer(help="GridCast data ingestion.", no_args_is_help=True)

USER_AGENT = "gridcast/0.1 (portfolio project)"


def _http_client(base_url: str, settings: Settings) -> httpx.Client:
    return httpx.Client(
        base_url=base_url,
        timeout=settings.http_timeout_seconds,
        headers={"User-Agent": USER_AGENT},
    )


def _ingest_energy(settings: Settings, country: str, start: date, end: date) -> None:
    engine = create_db_engine(settings.database_url)
    with (
        track_run(engine, "energy-charts") as run,
        _http_client(settings.energy_charts_url, settings) as client,
    ):
        points = fetch_public_power(client, country, start, end)
        with engine.begin() as conn:
            run["rows"] = upsert_power(conn, [asdict(p) for p in points])
    typer.echo(
        f"{country} {start}..{end}: {len(points)} points fetched, {run['rows']} rows written"
    )


@app.command()
def energy(
    days: int = typer.Option(3, help="Days to fetch, ending today. Recent days are re-read."),
    country: str = typer.Option("it", help="Country code."),
) -> None:
    """Fetch recent power data, re-reading the last days to pick up revised values."""
    end = datetime.now(LOCAL_TZ).date()
    _ingest_energy(Settings(), country, end - timedelta(days=days - 1), end)


@app.command()
def backfill_energy(
    start: datetime = typer.Option(..., formats=["%Y-%m-%d"], help="First day."),
    end: datetime = typer.Option(..., formats=["%Y-%m-%d"], help="Last day, included."),
    country: str = typer.Option("it", help="Country code."),
    chunk_days: int = typer.Option(30, help="Days per request."),
    pause_seconds: float = typer.Option(2.0, help="Pause between requests."),
) -> None:
    """Load history in chunks, pausing between requests to respect the API rate limits."""
    settings = Settings()
    chunk_start = start.date()
    while chunk_start <= end.date():
        chunk_end = min(chunk_start + timedelta(days=chunk_days - 1), end.date())
        _ingest_energy(settings, country, chunk_start, chunk_end)
        chunk_start = chunk_end + timedelta(days=1)
        time.sleep(pause_seconds)


def _has_values(point: WeatherPoint) -> bool:
    # Archive hours not yet published come back as nulls: never let them overwrite a forecast.
    return point.temperature_c is not None or point.shortwave_radiation_wm2 is not None


@app.command()
def weather(
    past_days: int = typer.Option(3, help="Past days to re-read, covering the archive delay."),
    forecast_days: int = typer.Option(2, help="Days ahead to fetch, today included."),
) -> None:
    """Fetch recent and upcoming hourly weather for every location."""
    settings = Settings()
    engine = create_db_engine(settings.database_url)
    with (
        track_run(engine, "open-meteo") as run,
        _http_client(settings.open_meteo_forecast_url, settings) as client,
    ):
        for location in LOCATIONS:
            points = fetch_forecast(client, location, past_days, forecast_days)
            with engine.begin() as conn:
                written = upsert_weather(conn, [asdict(p) for p in points])
            run["rows"] += written
            typer.echo(f"{location}: {len(points)} hours fetched, {written} rows written")


@app.command()
def backfill_weather(
    start: datetime = typer.Option(..., formats=["%Y-%m-%d"], help="First day."),
    end: datetime = typer.Option(..., formats=["%Y-%m-%d"], help="Last day, included."),
    location: str = typer.Option("", help="Load only this location; all if empty."),
    pause_seconds: float = typer.Option(2.0, help="Pause between locations."),
) -> None:
    """Load observed hourly weather from the archive, one request per location."""
    if location and location not in LOCATIONS:
        raise typer.BadParameter(f"unknown location {location!r}, choose from {list(LOCATIONS)}")
    locations = [location] if location else list(LOCATIONS)

    settings = Settings()
    engine = create_db_engine(settings.database_url)
    with (
        track_run(engine, "open-meteo-archive") as run,
        _http_client(settings.open_meteo_archive_url, settings) as client,
    ):
        for name in locations:
            fetched = fetch_archive(client, name, start.date(), end.date())
            points = [p for p in fetched if _has_values(p)]
            with engine.begin() as conn:
                written = upsert_weather(conn, [asdict(p) for p in points])
            run["rows"] += written
            typer.echo(
                f"{name} {start.date()}..{end.date()}: "
                f"{len(points)} of {len(fetched)} hours kept, {written} rows written"
            )
            time.sleep(pause_seconds)
