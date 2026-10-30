"""Client for the public Energy-Charts API (Fraunhofer ISE, data licensed CC BY 4.0)."""

from dataclasses import dataclass
from datetime import UTC, date, datetime

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

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


def _is_retryable(error: BaseException) -> bool:
    """Retry network failures, rate limiting and server errors; never client errors."""
    if isinstance(error, httpx.TransportError):
        return True
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        return status == 429 or status >= 500
    return False


@retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)
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
