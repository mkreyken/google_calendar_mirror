from datetime import datetime, timezone
from typing import Optional, Any
from zoneinfo import ZoneInfo

from src.services.env import MIRROR_MONTHS_MIN, MIRROR_MONTHS_MAX


def google_to_rfc3339(obj: Any) -> str:
    # Timed event
    if "dateTime" in obj:
        dt = datetime.fromisoformat(obj["dateTime"])
        tz = ZoneInfo(obj["timeZone"])
        dt = dt.replace(tzinfo=tz)
        return dt.isoformat()

    # All-day event
    if "date" in obj:
        return obj["date"]

    raise RuntimeError("no date conversion setup")


def calendar_tz_name(dt: datetime) -> str:
    if dt.tzinfo is None:
        return "UTC"

    tz = dt.tzinfo
    # ZoneInfo (Python 3.9+)
    if hasattr(tz, "key"):
        return tz.key or "UTC"

    # pytz
    if hasattr(tz, "zone"):
        return tz.zone or "UTC"

    # datetime.timezone or other: use tzname(), but prefer UTC if not meaningful
    name = tz.tzname(dt)
    if name and name != "UTC":
        return name
    return "UTC"


def to_rfc3339(dt: Optional[datetime]) -> str:
    """ No datetime values should be used in the event object, they should all be JSON"""
    if dt is None:
        return ""
    if dt.tzinfo is None:
        # Assume local time -> convert to UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def from_rfc3339(value: str) -> datetime:
    """Convert an RFC3339 timestamp back into a timezone-aware datetime."""

    # Normalize Z → +00:00 so datetime.fromisoformat can parse it
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    # Parse using built-in ISO parser
    dt = datetime.fromisoformat(value)

    # Ensure timezone-aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt


def add_months(offset: int) -> datetime:
    now = datetime.now()

    # Calculate target year and month
    year = now.year + (now.month - 1 + offset) // 12
    month = (now.month - 1 + offset) % 12 + 1

    # Clamp the day to the last valid day of the target month
    # (e.g., moving from Jan 31 → Feb becomes Feb 28 or 29)
    from calendar import monthrange
    last_day = monthrange(year, month)[1]
    day = min(now.day, last_day)

    return datetime(year, month, day, now.hour, now.minute, now.second, now.microsecond)


def min_mirror_date() -> datetime:
    return add_months(MIRROR_MONTHS_MIN).astimezone()


def max_mirror_date() -> datetime:
    return add_months(MIRROR_MONTHS_MAX).astimezone()


def current_sync_token_datestamp() -> datetime:
    return datetime.now()


from datetime import datetime

def should_run_full_sync(last_sync_dt: datetime) -> bool:
    """
    Determines if a full sync is required based on date thresholds.
    Replaces old YYYYMMDD integer logic with proper datetime handling.
    """

    current_dt = current_sync_token_datestamp()   # must return datetime

    # 1. Month rollover (year rollover included automatically)
    if (current_dt.year, current_dt.month) > (last_sync_dt.year, last_sync_dt.month):
        return True

    # 2. Day difference within same month
    days_since_last_sync = (current_dt.date() - last_sync_dt.date()).days

    # "Every 5 days unless the last sync was 2 days ago"
    if days_since_last_sync >= 5 and days_since_last_sync != 2:
        return True

    return False

