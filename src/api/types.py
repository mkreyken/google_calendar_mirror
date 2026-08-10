from dataclasses import dataclass
from typing import Optional, Dict, Any

STATUS_OK = "ok"
STATUS_BAD = "bad"
STATUS_CANCELLED = "cancelled"
STATUS_DELETED = "deleted"


@dataclass(frozen=True)
class EventType:
    status: str
    source_event_id: str
    source_calendar_id: str
    mirror_event_id: Optional[str]
    start: Any
    end: Any

    summary: str
    description: str
    color_id: str
    foreground_color: Optional[str]
    background_color: Optional[str]
    visibility: Optional[str]
    location: Optional[str]
    iCalUID: Optional[str]
    updated_at: str
    last_synced_at: str


@dataclass(frozen=True)
class CalendarChangeData:
    source_calendar: CalendarSourceInfo
    mode: str
    changed_events: list[GoogleEventData]
    next_sync_token: Optional[str]


@dataclass(frozen=True)
class GoogleEventData:
    data: Dict[str, Any]


@dataclass(frozen=True)
class CalendarPageData:
    google_events: list[GoogleEventData]
    # for syncing across multiple pages
    next_sync_token: Optional[str]
    # across one page
    next_page_token: Optional[str]


@dataclass(frozen=True)
class MappingEvent:
    mirror_event_id: str
    source_calendar_id: str
    source_event_id: str
    last_synced_at: str
    updated_at: str
    status: str


@dataclass
class BadEvent:
    mirror_event_id: str


@dataclass(frozen=True)
class CalendarSourceInfo:
    name: str
    id: str
    color_id_for_event: str
    color_id: str
    foreground_color: str
    background_color: str
    short_id: str


@dataclass(frozen=True)
class AclInfo:
    email: str
    role: str
