# Keywords that trigger sanitization (case-insensitive)
import logging
from dataclasses import replace
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from src.api.calendar_source_info import CalendarSourceInfo
from src.api.types import EventType, GoogleEventData, STATUS_OK, STATUS_CANCELLED, MappingEvent
from src.clients.settings_on_disk import SETTINGS, GOOGLE_COLOR_AS_HEX
from src.services.env import SENSITIVE_KEYWORDS
from src.util.date_util import to_rfc3339
from src.util.exceptions import InvalidDataError

""" Google has fixed color ids, 11-20 = calendar, 1-10 = event """
""" OLD OFF"""
CALENDAR_TO_EVENT_COLOR_MAP = {
    "0": None,  # or omit colorId → use calendar color in UI
    "1": "1",  # Lavender
    "2": "2",  # Sage
    "3": "3",  # Grape  # close
    "4": "4",  # Flamingo #no matching cal
    "5": "5",  # Banana
    "6": "6",  # Tangerine # no matching cal
    "7": "7",  # Peacock
    "8": "8",  # Graphite
    "9": "9",  # Blueberry
    "10": "10",  # Basil     #close
    "11": "11",  # Tomato
    "12": "5",  # Banana (calendar) → Banana (event)
    "13": "2",  # Sage (calendar) → Sage (event)
    "14": "7",  # Peacock (calendar) → Peacock (event)
    "15": "4",  # Cobalt -> ?
    "16": "9",  # Blueberry (calendar) → Blueberry (event)
    "17": "1",  # Lavender (calendar) → Lavender (event)
    "18": "3",  # Wisteria → Grape (closest purple)
    "19": "8",  # Graphite (calendar) → Graphite (event)
    "20": "10",  # Birch → Basil (closest green-ish neutral)
}

logger = logging.getLogger(__name__)


class EventConverter:

    @classmethod
    def sanitize_event(cls, event: EventType) -> EventType:
        """
        Sanitize sensitive events by replacing summary/description
        with 'Private Event' when keywords are detected.
        """

        def contains_sensitive(text: Optional[str]) -> bool:
            if not text:
                return False
            t = text.lower()
            return any(keyword in t for keyword in SENSITIVE_KEYWORDS)

        summary = event.summary
        description = event.description
        visibility = event.visibility

        if (
                contains_sensitive(summary)
                or contains_sensitive(description)
                or visibility == "private"
        ):
            return replace(
                event,
                summary="Private Event",
                description="Private Event",
                visibility=None
            )
        return event

    @classmethod
    def to_google_mirror_event(cls, event: EventType) -> GoogleEventData:
        # Build top-level event dict, omitting optional None fields
        data: Dict[str, Any] = {
            "summary": event.summary,
            "description": event.description,
            "start": event.start,
            "end": event.end,
        }
        private: Dict[str, Any] = {
            "sync.type": "event_mapping",
            "source.event_id": event.source_event_id,
            "source.calendar_id": event.source_calendar_id,
            "source.updated_at": event.updated_at,
            "lastSyncedAt": event.last_synced_at
        }
        # prefer the hex colors if they are present
        if event.foreground_color:
            data["foregroundColor"] = event.foreground_color
            data["backgroundColor"] = event.background_color
        elif event.color_id is not None:
            data["colorId"] = event.color_id

        if event.visibility is not None:
            data["visibility"] = event.visibility

        if event.location is not None:
            data["location"] = event.location

        if event.iCalUID is not None:
            private["iCalUID"] = event.iCalUID

        data["extendedProperties"] = {
            "private": private
        }

        return GoogleEventData(data)

    @classmethod
    def from_event_to_mapping(cls, evt: EventType, mirror_event_id) -> MappingEvent:
        # because the event has no id on a creation, we pass in the event and the mirror_id
        if not mirror_event_id: raise InvalidDataError("No mirror id on conversion")

        return MappingEvent(
            status=STATUS_OK,
            mirror_event_id=mirror_event_id,
            source_calendar_id=evt.source_calendar_id,
            source_event_id=evt.source_event_id,
            last_synced_at=evt.last_synced_at,
            updated_at=evt.updated_at
        )

    @classmethod
    def to_event_data(cls, evt: GoogleEventData, cal: CalendarSourceInfo, is_from_mirror: bool = False) -> EventType:
        """ None is not a valid value in the Google data """

        data = evt.data
        status_raw = data.get("status")

        if status_raw == "cancelled":
            status = STATUS_CANCELLED
        else:
            status = STATUS_OK

        my_id = data.get("id")
        if not my_id: raise InvalidDataError("no id on fetch")

        if is_from_mirror:
            extended = data.get("extendedProperties") or {}
            private = extended.get("private") or {}
            source_event_id: str = private.get("source.event_id", "")
            source_calendar_id: str = private.get("source.calendar_id", "")
            updated_at: str = private.get("source.updated_at", "")
            mirror_event_id = my_id
            if not source_event_id:
                logger.error(f"Misaligned or bad data : {mirror_event_id}")
        else:
            private = {}
            source_event_id = my_id
            mirror_event_id = None
            source_calendar_id = cal.id
            updated_at= str(data.get("updated"))  # the date is a simple date string

        return EventType(
            status=status,
            source_calendar_id=source_calendar_id,
            source_event_id=source_event_id,
            mirror_event_id=mirror_event_id,
            start=data.get("start"),
            end=data.get("end"),

            summary=data.get("summary", ""),
            description=data.get("description", ""),
            color_id=data.get("colorId", "0"),
            foreground_color=data.get("foregroundColor"),
            background_color=data.get("backgroundColor"),
            visibility=data.get("visibility"),
            location=data.get("location"),
            iCalUID=data.get("iCalUID"),

            updated_at=updated_at,
            last_synced_at=str(private.get("lastSyncedAt", "")),

        )

    @classmethod
    def mirror_ish(cls, event: EventType, source_calendar: CalendarSourceInfo,
                   sync_time: datetime = datetime.now(timezone.utc)) -> EventType:
        """
        Produce a modified EventType representing the mirrored version.
        Since EventType is frozen, we construct a new one.
        """

        # Build modified summary/location
        new_summary = f"{source_calendar.short_id}:{event.summary}"
        new_location = (
            f"{source_calendar.name}:{event.location}"
            if event.location
            else source_calendar.name
        )

        if (SETTINGS.get(GOOGLE_COLOR_AS_HEX)) or event.foreground_color:
            return replace(
                event,
                summary=new_summary,
                location=new_location,
                foreground_color=source_calendar.foreground_color,
                background_color=source_calendar.background_color,
                last_synced_at=to_rfc3339(sync_time)
            )
        else:
            return replace(
                event,
                summary=new_summary,
                location=new_location,
                color_id=source_calendar.color_id_for_event,
                last_synced_at=to_rfc3339(sync_time)
            )
