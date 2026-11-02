"""Time helpers shared by trainer and API: Italian days expressed as UTC intervals."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Europe/Rome")


def target_day_bounds(day: date) -> tuple[datetime, datetime]:
    """UTC instants of local midnight at the start and at the end of an Italian day.

    The hours in between are 23, 24 or 25, depending on daylight saving changes.
    """
    start_local = datetime.combine(day, time.min, tzinfo=LOCAL_TZ)
    end_local = datetime.combine(day + timedelta(days=1), time.min, tzinfo=LOCAL_TZ)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)
