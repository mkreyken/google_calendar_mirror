from datetime import datetime, timezone
from typing import Dict, Optional

from src.api.calendar_change_reader import GoogleCalendarChangeReader
from src.api.calendar_source_info import CalendarMappingApi, CalendarSourceInfo
from src.api.mirror_calendar_manager import MirrorCalendarManager
from src.clients.google_calendar_client import GoogleCalendarClient
from src.services.env import FULL_SYNC, WINDOWED_SYNC
from src.services.events_converter import EventConverter
from src.services.run_with_logger import run_job_with_email_report
from src.util.date_util import min_mirror_date, max_mirror_date, from_rfc3339

import logging

logger = logging.getLogger(__name__)

class Controller:
    def __init__(self)  -> None:  # type: ignore[misc]

        self.client: GoogleCalendarClient = GoogleCalendarClient()
        self.calendar_mapper: CalendarMappingApi = CalendarMappingApi(
            self.client
        )
        self.mirror: Optional[MirrorCalendarManager]= None
        self.is_full_sync: bool = False
        self.is_windowed_sync: bool = False

    def update_mirror_from_source_calendar(self, calendar: CalendarSourceInfo) -> Dict[str, int]:

        if not self.mirror: raise RuntimeError("Mirror not initialized")
        calendar_sync = GoogleCalendarChangeReader(self.client, calendar, self.calendar_mapper)
        # Read changes (incremental or full)
        sync_time = datetime.now(timezone.utc)
        changes = calendar_sync.next_read(self.is_full_sync, self.is_windowed_sync)
        time_min = min_mirror_date()
        time_max = max_mirror_date()

        results = {
            "added": 0,
            "updated": 0,
            "deleted": 0,
        }
        for evt in changes.changed_events:
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
            adjusted_event = EventConverter.mirror_ish(sanitize_event, calendar,sync_time)
            result = self.mirror.apply_change_to_mirror(adjusted_event)

            results[result] += 1

        if changes.mode == FULL_SYNC:
            orphans = self.mirror.delete_orphans_using_full_sync(calendar.id, changes.changed_events)
            results.update(orphans)
        logger.info(f"results: {results}")
        return results

    def delete_bad_mirror_events(self) -> None :
        if not self.mirror: raise RuntimeError("Mirror not initialized")
        self.mirror.delete_bad_events()

    def __run(self) -> None:
        self.calendar_mapper.fetch_calendars()
        mirror_calendar = self.calendar_mapper.get_mirror_calendar()

        self.mirror = MirrorCalendarManager(self.client, mirror_calendar, self.calendar_mapper)
        assert self.mirror is not None
        if not self.is_full_sync:
            if not self.mirror.load_mirror_mapping():
                self.is_full_sync = True
        if self.is_full_sync:
            self.mirror.read_mirror_and_report_errors()
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
            logger.info(f"Finished Calendar: {cal.name} with {result}")

        return summary

    def run_with_email_report(self, kind: str) -> None:
        if kind == FULL_SYNC:
            self.is_full_sync = True
        run_job_with_email_report(self.__run, "michael@krey.ca")

    def run(self, kind: str) -> None:
        if kind == FULL_SYNC:
            self.is_full_sync = True
        if kind == WINDOWED_SYNC:
            self.is_windowed_sync = True
        self.__run()


if __name__ == "__main__":
    controller = Controller()
    controller.run_with_email_report(FULL_SYNC)
