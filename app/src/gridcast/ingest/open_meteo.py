"""Client for the public Open-Meteo API"""

from dataclasses import dataclass
from datetime import UTC, date, datetime

import httpx

from gridcast.common.http import api_retry

LOCATIONS = {
    "milano": (45.4642, 9.19),
    "roma": (41.9028, 12.4964),
    "napoli": (40.8518, 14.2681),
    "torino": (45.0703, 7.6869),
    "bologna": (44.4949, 11.3426),
    "palermo": (38.1157, 13.3615),
}

HOURLY_VARIABLES = "temperature_2m,shortwave_radiation"


@dataclass(frozen=True)
class WeatherPoint:
    location: str
    temperature_c: float | None
    ts: datetime
    shortwave_radiation_wm2: float | None


def parse_hourly(payload: dict, location: str) -> list[WeatherPoint]:
    """Turn the hourly block of the response into one point per hour.

    Times are requested with timezone=UTC and arrive without an offset, so UTC is attached here.
    """
    hourly = payload["hourly"]
    timestamps = [datetime.fromisoformat(t).replace(tzinfo=UTC) for t in hourly["time"]]
    temperatures = hourly["temperature_2m"]
    radiation = hourly["shortwave_radiation"]

    for name, values in (("temperature_2m", temperatures), ("shortwave_radiation", radiation)):
        if len(values) != len(timestamps):
            raise ValueError(
                f"series {name!r} has {len(values)} values for {len(timestamps)} timestamps"
            )

    return [
        WeatherPoint(location=location, ts=ts, temperature_c=temp, shortwave_radiation_wm2=rad)
        for ts, temp, rad in zip(timestamps, temperatures, radiation, strict=True)
    ]


def _base_params(location: str) -> dict:
    latitude, longitude = LOCATIONS[location]
    # parse_hourly relies on timezone=UTC: change the two together.
    return {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": HOURLY_VARIABLES,
        "timezone": "UTC",
    }


@api_retry
def fetch_archive(
    client: httpx.Client, location: str, start: date, end: date
) -> list[WeatherPoint]:
    """Fetch hourly weather data for whole local days from start to end, both included."""
    response = client.get(
        "/archive",
        params={
            **_base_params(location),
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
    )
    response.raise_for_status()
    return parse_hourly(response.json(), location)


@api_retry
def fetch_forecast(
    client: httpx.Client, location: str, past_days: int, forecast_days: int
) -> list[WeatherPoint]:
    """Fetch hourly weather data for whole local days from start to end, both included."""
    response = client.get(
        "/forecast",
        params={**_base_params(location), "past_days": past_days, "forecast_days": forecast_days},
    )
    response.raise_for_status()
    return parse_hourly(response.json(), location)
