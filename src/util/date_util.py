from datetime import datetime, timezone
from typing import Optional, Any
from zoneinfo import ZoneInfo

from src.services.env import MIRROR_MONTHS_MIN, MIRROR_MONTHS_MAX, LOCAL_TZ


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


def google_to_datetime(obj: dict) -> datetime:
    # Timed event
    if "dateTime" in obj:
        # Parse Google's local datetime (no offset)
        dt = datetime.fromisoformat(obj["dateTime"])
        tz = ZoneInfo(obj["timeZone"])
        dt = dt.replace(tzinfo=tz)

        return dt

    # All-day event
    if "date" in obj:
        dt = datetime.fromisoformat(obj["date"])
        return dt.replace(tzinfo=LOCAL_TZ)
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


def adjust_to_first_of_month(offset: int) -> datetime:
    now = datetime.now()

    year = now.year + (now.month - 1 + offset) // 12
    month = (now.month - 1 + offset) % 12 + 1

    return datetime(year, month, 1, 0, 0, 0, 0)


def min_mirror_date() -> datetime:
    return adjust_to_first_of_month(MIRROR_MONTHS_MIN).astimezone()


# google's interface is less than and excluding this point
def max_mirror_date() -> datetime:
    return adjust_to_first_of_month(MIRROR_MONTHS_MAX).astimezone()


def current_sync_token_datestamp() -> datetime:
    return datetime.now()
