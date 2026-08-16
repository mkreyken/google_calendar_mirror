"""


Why:
deleted events are lost, while edited events unless excessively changed are not

it can be resurrected (in the mirror, since these are single events)
Yes, but only within 30 days.


event = service.events().get(
    calendarId="primary",
    eventId=event_id,
    showDeleted=True
).execute()

event = {}
event["status"] = "confirmed"
event["deleted"] = False

event = service.events().patch(
    calendarId="primary",
    eventId=event_id,
    body={"status": "confirmed"}
).execute()

from datetime import datetime, timedelta

Report details: all deleted events in the last week
one_week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat() + "Z"

deleted_events = service.events().list(
    calendarId="primary",
    showDeleted=True,
    updatedMin=one_week_ago
).execute()

events = deleted_events.get("items", [])
recent_deleted = [e for e in events if e.get("status") == "canceled"]

"""
from datetime import datetime, timedelta
from typing import List, Dict

from src.api.calendar_source_info import CalendarMappingApi
from src.api.types import GoogleEventData
from src.clients.google_calendar_client import GoogleCalendarClient
from src.clients.google_mail_client import GmailTextSender
from src.clients.mirror_key_store import TokenStoreValue
from src.clients.settings_on_disk import EMAIL_TO_REPORTS, SETTINGS
from src.services.events_converter import EventConverter
from src.util.date_util import google_to_rfc3339


def deleted_events(client: GoogleCalendarClient) -> str:
    time_min = (datetime.now() - timedelta(days=7))
    lines: List[str] = []
    calendars: Dict[str, TokenStoreValue] = CalendarMappingApi.read_calendar_sources()
    for cal_id, calendar in calendars.items():
        events: list[GoogleEventData] = client.deleted_calendar_events(cal_id, time_min)
        for google_event in events:
            event = EventConverter.to_event_data(google_event, cal_id)
            line = f"Deleted on calendar {calendar.name}, {event.summary} , at {google_to_rfc3339(event.start)}"
            lines.append(line)
    return "\n".join(lines)


if __name__ == "__main__":
    gclient = GoogleCalendarClient()
    body_text = deleted_events(gclient)
    if not body_text:
        print("no results")
    else:
        subject = f"Job Run Report - {datetime.now():%Y-%m-%d %H:%M:%S}"
        sender = GmailTextSender()
        val = SETTINGS.get(EMAIL_TO_REPORTS)
        if isinstance(val, str):
            to_email = val
        else:
            raise ValueError("Email is not type str")
        sender.send_text(
            to=to_email,
            subject=subject,
            body=body_text
        )
