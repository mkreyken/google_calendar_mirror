import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, Optional

import src.services.env
from src.api.calendar_change_reader import GoogleCalendarChangeReader
from src.api.calendar_source_info import CalendarMappingApi, CalendarSourceInfo
from src.api.mirror_calendar_manager import MirrorCalendarManager
from src.clients.google_calendar_client import GoogleCalendarClient
from src.clients.google_mail_client import GmailTextSender
from src.services.env import FULL_SYNC
from src.services.events_converter import EventConverter
from src.services.run_with_logger import run_job_and_capture_log
from src.util.date_util import min_mirror_date, max_mirror_date, from_rfc3339

logger = logging.getLogger(__name__)


class Controller:
    client: GoogleCalendarClient
    calendar_mapper: CalendarMappingApi
    mirror: Optional[MirrorCalendarManager]
    kind: Optional[str]

    def __init__(self) -> None:  # type: ignore[misc]

        self.client = GoogleCalendarClient()
        self.calendar_mapper = CalendarMappingApi(self.client)
        self.mirror = None
        self.kind = None

    @property
    def is_full_sync(self) -> bool:
        return self.kind == src.services.env.FULL_SYNC

    @property
    def is_audit_any(self) -> bool:
        return self.kind == src.services.env.AUDIT or self.is_audit_fix

    @property
    def is_audit_fix(self) -> bool:
        return self.kind == src.services.env.AUDIT_AND_FIX or self.is_audit_fix_and_overwrite

    @property
    def is_audit_fix_and_overwrite(self) -> bool:
        return self.kind == src.services.env.AUDIT_AND_UPDATE

    def update_mirror_from_source_calendar(self, calendar: CalendarSourceInfo) -> Dict[str, int]:

        if not self.mirror: raise RuntimeError("Mirror not initialized")
        calendar_sync = GoogleCalendarChangeReader(self.client, calendar, self.calendar_mapper)
        sync_time = datetime.now(timezone.utc)
        changes = calendar_sync.next_read(self.is_full_sync, self.is_audit_any)
        time_min = min_mirror_date()
        time_max = max_mirror_date()

        results = Counter[str]()

        for evt in changes.changed_events:
            # canceled events may not have start and end times, especially recurring markers
            if EventConverter.is_google_event_cancel(evt) :
                pass
            else:
                if not evt.data.get("start",None):
                    raise ValueError("No Start date in event stream")
                start_str = evt.data["start"]
                end_str = evt.data["end"]
                if start_str.get("dateTime"):
                    start = from_rfc3339(start_str["dateTime"])
                    end = from_rfc3339(end_str["dateTime"])
                elif start_str.get("date"):
                    start = from_rfc3339(start_str["date"])
                    end = from_rfc3339(end_str["date"])
                else:
                    raise RuntimeError("can't figure out date")

                if not start or not end or start < time_min or end > time_max:
                    results["Ignored"] += 1
                    continue

            normalize_event = EventConverter.to_event_data(evt, calendar)
            sanitize_event = EventConverter.sanitize_event(normalize_event)
            adjusted_event = EventConverter.mirror_ish(sanitize_event, calendar, sync_time)
            if self.is_audit_any:
                result = self.mirror.audit(adjusted_event, self.is_audit_fix, self.is_audit_fix_and_overwrite)
            else:
                result = self.mirror.apply_change_to_mirror(adjusted_event)

            results[result] += 1

        if changes.mode == FULL_SYNC:
            orphans = self.mirror.delete_orphans_using_full_sync(calendar.id, changes.changed_events)
            results.update(orphans)
        return results

    def delete_bad_mirror_events(self) -> None:
        if not self.mirror: raise RuntimeError("Mirror not initialized")
        self.mirror.delete_bad_events()


    def __run(self) -> None:
        self.calendar_mapper.fetch_calendars()
        mirror_calendar = self.calendar_mapper.get_mirror_calendar()

        self.mirror = MirrorCalendarManager(self.client, mirror_calendar, self.calendar_mapper)
        assert self.mirror is not None
        this_needs_fresh_mirror = self.is_full_sync
        if not this_needs_fresh_mirror:
            if not self.mirror.load_mirror_mapping():
                this_needs_fresh_mirror = True
        if this_needs_fresh_mirror or self.is_audit_any:
            self.mirror.read_mirror_and_report_errors(self.is_audit_any)
            self.delete_bad_mirror_events()

        self.sync_all_calendars()

        logger.info("Saving mirrored events")
        self.mirror.save_mirror_mapping()
        logger.info("End of loop")

    def sync_all_calendars(self) -> Dict[str, Dict[str, int]]:
        summary = {}

        for cal in self.calendar_mapper.get_calendar_sources().values():
            logger.info(f"Doing Calendar: {cal.name} {cal.id}")
            result = self.update_mirror_from_source_calendar(cal)
            summary[cal.id] = result
            logger.info(f"Finished Calendar: {cal.name} with {dict(result)}")

        return summary

    def run_with_logger_output(self,kind) ->str:
        self.kind = kind
        return run_job_and_capture_log(self.__run)

    def run_with_email_report(self, kind: str, to_email: str) -> None:
        self.kind = kind
        log_text = run_job_and_capture_log(self.__run)
        subject = f"Job Run Report - {datetime.now():%Y-%m-%d %H:%M:%S}"

        if to_email:
            sender = GmailTextSender()
            sender.send_text(
                to=to_email,
                subject=subject,
                body=log_text,
    )
