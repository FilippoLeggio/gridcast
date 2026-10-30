"""Client for the public Energy-Charts API (Fraunhofer ISE, data licensed CC BY 4.0)."""

from dataclasses import dataclass
from datetime import UTC, date, datetime

import httpx

from gridcast.common.http import api_retry

# Derived percentages: not stored, they can be computed from the power series.
EXCLUDED_SERIES = {"Renewable share of load", "Renewable share of generation"}


@dataclass(frozen=True)
class PowerPoint:
    country: str
    series: str
    ts: datetime
    value_mw: float | None


def parse_public_power(payload: dict, country: str) -> list[PowerPoint]:
    """Turn the column-oriented API response into one row per series and timestamp."""
    timestamps = [datetime.fromtimestamp(s, tz=UTC) for s in payload["unix_seconds"]]
    points: list[PowerPoint] = []
    for production_type in payload["production_types"]:
        name = production_type["name"]
        if name in EXCLUDED_SERIES:
            continue
        values = production_type["data"]
        if len(values) != len(timestamps):
            raise ValueError(
                f"series {name!r} has {len(values)} values for {len(timestamps)} timestamps"
            )
        points.extend(
            PowerPoint(country, name, ts, value)
            for ts, value in zip(timestamps, values, strict=True)
        )
    return points


@api_retry
def fetch_public_power(
    client: httpx.Client, country: str, start: date, end: date
) -> list[PowerPoint]:
    """Fetch power data for whole local days from start to end, both included."""
    response = client.get(
        "/public_power",
        params={"country": country, "start": start.isoformat(), "end": end.isoformat()},
    )
    response.raise_for_status()
    return parse_public_power(response.json(), country)
