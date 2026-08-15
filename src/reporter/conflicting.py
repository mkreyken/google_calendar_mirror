from datetime import datetime
from typing import Dict, List, Tuple

from src.api.calendar_source_info import CalendarMappingApi
from src.api.mirror_calendar_manager import MirrorCalendarManager
from src.api.types import MappingEvent
from src.clients.google_mail_client import GmailTextSender
from src.clients.settings_on_disk import EMAIL_TO_REPORTS, SETTINGS
from src.util.date_util import from_rfc3339


def find_overlaps(mapping_events: Dict[str, MappingEvent]) -> Dict[str, List[Tuple[MappingEvent, MappingEvent]]]:
    # Group by calendar
    by_calendar: Dict[str, List[MappingEvent]] = {}
    for ev in mapping_events.values():
        by_calendar.setdefault(ev.source_calendar_id, []).append(ev)

    overlaps: Dict[str, List[Tuple[MappingEvent, MappingEvent]]] = {}

    # For each calendar, find overlaps
    for cal_id, ev_list in by_calendar.items():
        # Sort by start time
        ev_list_sorted: List[MappingEvent] = sorted(ev_list, key=lambda e: from_rfc3339(e.start))

        cal_overlaps: List[Tuple[MappingEvent, MappingEvent]] = []

        # Compare each event with the next ones
        for i in range(len(ev_list_sorted) - 1):
            a: MappingEvent = ev_list_sorted[i]
            a_start = from_rfc3339(a.start)
            a_end = from_rfc3339(a.end)

            for j in range(i + 1, len(ev_list_sorted)):
                b: MappingEvent = ev_list_sorted[j]
                b_start = from_rfc3339(b.start)
                b_end = from_rfc3339(b.end)

                # If b starts after a ends, no further overlaps possible
                if b_start >= a_end:
                    break

                # Overlap condition
                if a_start < b_end and b_start < a_end:
                    cal_overlaps.append((a, b))

        if cal_overlaps:
            overlaps[cal_id] = cal_overlaps

    return overlaps


def conflicting_events() -> None:
    val = SETTINGS.get(EMAIL_TO_REPORTS)
    if isinstance(val, str):
        to_email = val
    else:
        raise ValueError("Email is not type str")
    mappings = MirrorCalendarManager.mapping_file()
    if not mappings:
        print("No Mappings locally")
        return

    calendars = CalendarMappingApi.read_calendar_sources()
    overlaps = find_overlaps(mappings)

    if not overlaps:
        print("No Overlaps")
        return
    lines: List[str] = []
    for cal_id, pairs in overlaps.items():
        cal_name = calendars[cal_id].name
        lines.append(f"Calendar:{cal_name}")
        for a, b in pairs:
            lines.append(f"Overlap end event {a.end} with start {b.start}")

    subject = f"Job Run Report - {datetime.now():%Y-%m-%d %H:%M:%S}"
    body_text = "\n".join(lines)

    sender = GmailTextSender()
    sender.send_text(
        to=to_email,
        subject=subject,
        body=body_text,
    )


if __name__ == "__main__":
    conflicting_events()
