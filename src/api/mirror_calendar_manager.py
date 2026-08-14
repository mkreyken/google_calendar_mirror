"""
On syncing, assume that anything with a source_id is set up by this system,
On a full sync, we need to sync forward, and then remove all that have not been
found in the mirror.


Data to share in the mirror should be  1 month back,
however repeat events in the past are repeat events in the future.
Audit should complete about excessively long repeat events (i.e. repeats should only be
1 year at most)

Weddings can be booked upto 2 years in advance

For this reason a full sync will be needed from time to time to ensure that nothing has been added or deleted.

To Avoid memory issues, syncing should be done on a page by page setup,
however we may need to delete in the mirror things in the date range to ensure that

"""
import logging
import os
import zoneinfo
from collections import Counter
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Dict, Tuple

from src.api.calendar_source_info import CalendarMappingApi
from src.api.types import EventType, MappingEvent, STATUS_OK, STATUS_CANCELLED, STATUS_DELETED, BadEvent, \
    GoogleEventData, CalendarPageData, CalendarSourceInfo
from src.clients.google_calendar_client import GoogleCalendarClient
from src.clients.settings_on_disk import SETTINGS, MY_TIMEZONE
from src.services.events_converter import EventConverter
from src.util.date_util import max_mirror_date,min_mirror_date
from src.util.exceptions import InvalidDataError
from src.util.filesystem import save_json_file, load_json_file, get_data_location_as_path, get_data_directory

logger = logging.getLogger(__name__)


# noinspection PyUnresolvedReferences
class MirrorCalendarManager:
    bad_events: Optional[list[BadEvent]]
    client: GoogleCalendarClient
    mirror_calendar: CalendarSourceInfo
    mappings: dict[str, MappingEvent]
    calendars: CalendarMappingApi

    def __init__(self, client: GoogleCalendarClient, mirror_calendar: CalendarSourceInfo,
                 calendars: CalendarMappingApi):
        self.bad_events = None
        self.client = client
        self.mirror_calendar = mirror_calendar
        self.mappings = {}
        self.calendars = calendars

    def read_mirror_and_report_errors(self, is_audit: bool) -> None:
        """
        Rebuild the sync mapping database by scanning the mirror calendar.
        Only events inside the rolling window are considered.
        """
        now = datetime.now(timezone.utc)

        # filtered does not allow for sync_token
        # Mirror is always window_synced, it has a local db instead of "incremental"
        # Rolling window: 2 months back, 18 months forward
        window_start = min_mirror_date()
        window_end = max_mirror_date()
        sync_token = None

        old_mapping: Dict[str, MappingEvent] = self.mappings
        self.mappings = {}
        self.bad_events = []

        page_token = None
        while True:
            results: CalendarPageData = self.client.list_events(
                calendar_id=self.mirror_calendar.id,
                single_events=True,  # recommended for windowed sync
                time_min=window_start,
                time_max=window_end,
                max_results=2500,
                page_token=page_token,
                sync_token=sync_token
            )

            page_token = results.next_page_token
            logger.info(
                f"Reading mirror cnt: {len(results.google_events)} sync: {results.next_sync_token or ''} page: {results.next_page_token or ''}")
            for google_event in results.google_events:
                event = EventConverter.to_event_data(google_event, self.mirror_calendar, True)
                if event.status == STATUS_CANCELLED or event.status == STATUS_DELETED:
                    continue
                if not event.mirror_event_id: raise InvalidDataError("not mirror id on mirror read")

                if not event.source_event_id or \
                        not event.source_calendar_id or \
                        not event.status or \
                        not event.start or \
                        not event.end:
                    bad_event = BadEvent(mirror_event_id=event.mirror_event_id)
                    self.bad_events.append(bad_event)
                elif not self.calendars.is_valid_calendar_id(event.source_calendar_id):
                    bad_event = BadEvent(
                        mirror_event_id=event.mirror_event_id
                    )
                    self.bad_events.append(bad_event)
                else:
                    new_map = EventConverter.from_event_to_mapping(event, event.mirror_event_id)
                    existing_map: Optional[MappingEvent] = self.__match_event(event, self.mappings)
                    if existing_map:
                        #  a duplicate copy
                        bad_event = BadEvent(
                            mirror_event_id=event.mirror_event_id
                        )
                        self.bad_events.append(bad_event)
                    else:
                        self.mappings[event.source_event_id] = new_map

            if not page_token:
                break
        logger.info(f"Finished reading mirror cnt :{len(self.mappings)} bad : {len(self.bad_events or [])}")
        if is_audit:
            audit_results = self.compare_maps(old_mapping, self.mappings)
            logger.info(f"Audit results: {dict(audit_results)}")
        return

    @classmethod
    def compare_maps(cls, old: dict[str, MappingEvent],
                     new: dict[str, MappingEvent]):
        counts = Counter[str]()

        old_keys = set(old)
        new_keys = set(new)

        counts["added"] += len(new_keys - old_keys)
        counts["deleted"] += len(old_keys - new_keys)

        # Must loop for updated vs unchanged
        for key in old_keys & new_keys:
            counts["updated" if old[key] != new[key] else "unchanged"] += 1

        return counts

    @classmethod
    def __match_event(cls, event: EventType, mappings: Dict[str, MappingEvent]) -> MappingEvent | None:
        """ for single_event=true, we only need to match the ids
        the return value is modifiable"""

        mapping = mappings.get(event.source_event_id)
        if not mapping:
            return None
        if mapping.source_calendar_id == event.source_calendar_id and event.status == STATUS_OK:
            return mapping
        logger.warning(f"--- Found an invalid match {event.source_event_id}")
        return None

    def audit(self, event: EventType, and_update: bool = True, always_update: bool = True) -> str:

        mapped_event = self.__match_event(event, self.mappings)

        if event.status == STATUS_CANCELLED:

            # DELETE
            if mapped_event:
                if not always_update:
                    return "No_action"

                if not and_update:
                    return "difference:del"

                self.client.delete_event(
                    calendar_id=self.mirror_calendar.id,
                    event_id=mapped_event.mirror_event_id
                )
            else:
                return "deleted:NF"
            self.__update_sync_data(event, mapped_event.mirror_event_id, deleted=True)
            return "deleted"

        if not mapped_event:
            logger.info(f"Missing  {event.source_event_id}")
        elif mapped_event.updated_at != event.updated_at:
            logger.info(f"Differences {mapped_event.source_event_id}")
        elif not always_update:
            return "No_action"

        if not and_update:
            return "difference"

        if mapped_event:
            # UPDATE
            self.client.update_event(
                calendar_id=self.mirror_calendar.id,
                event_id=mapped_event.mirror_event_id,
                event=event
            )
            self.__update_sync_data(event, mapped_event.mirror_event_id)
            return "updated"

        else:
            if not event.source_event_id or \
                    not event.source_calendar_id or \
                    not event.status or \
                    not event.start or \
                    not event.end:
                raise InvalidDataError("Create in mirror without support data")
            created = self.client.create_event(
                calendar_id=self.mirror_calendar.id,
                event=event
            )
            self.__update_sync_data(event, created["id"])
            return "added"

    def apply_change_to_mirror(self, event: EventType) -> str:
        mapped_event = self.__match_event(event, self.mappings)

        if event.status == STATUS_CANCELLED:
            # DELETE
            if mapped_event:
                self.client.delete_event(
                    calendar_id=self.mirror_calendar.id,
                    event_id=mapped_event.mirror_event_id
                )
            else:
                return "deleted:NF"
            self.__update_sync_data(event, mapped_event.mirror_event_id, deleted=True)
            return "deleted"

        if mapped_event:
            # UPDATE
            self.client.update_event(
                calendar_id=self.mirror_calendar.id,
                event_id=mapped_event.mirror_event_id,
                event=event
            )
            self.__update_sync_data(event, mapped_event.mirror_event_id)
            return "updated"

        else:
            if not event.source_event_id or \
                    not event.source_calendar_id or \
                    not event.status or \
                    not event.start or \
                    not event.end:
                raise InvalidDataError("Create in mirror without support data")
            created = self.client.create_event(
                calendar_id=self.mirror_calendar.id,
                event=event
            )
            self.__update_sync_data(event, created["id"])
            return "added"

    def __update_sync_data(self, event: EventType, mirror_event_id, deleted=False) -> None:
        source_event_id = event.source_event_id
        mapping = self.mappings.get(source_event_id)
        if deleted:
            if mapping:
                self.mappings.pop(source_event_id, None)
            return
        if mapping is None:
            mapping = EventConverter.from_event_to_mapping(event, mirror_event_id)
            self.mappings[source_event_id] = mapping
        else:
            self.mappings[source_event_id] = replace(mapping,
                                                     last_synced_at=event.last_synced_at,
                                                     updated_at=event.updated_at
                                                     )

    def delete_orphans_using_full_sync(self, source_calendar_id: str, full_source_events: List[GoogleEventData]) -> \
            dict[
                str, int]:
        """ Delete items that are in the mirror but in the primary calendar that have the sme calendar_id"""
        deleted = 0

        valid_source_ids = {
            ev.data.get("id")
            for ev in full_source_events
            if ev.data.get("id") is not None
        }

        for source_event_id_key, evt in list(self.mappings.items()):
            # Only consider events belonging to this source calendar
            if evt.source_calendar_id != source_calendar_id:
                continue

            source_event_id = evt.source_event_id
            mirror_event_id = evt.mirror_event_id

            # If the source event no longer exists → delete the mirror event
            if source_event_id not in valid_source_ids:
                self.client.delete_event(
                    calendar_id=self.mirror_calendar.id,
                    event_id=mirror_event_id
                )
                logger.info(f"Deleted event {mirror_event_id} for {source_calendar_id}")

                # Remove mapping evt
                self.mappings.pop(mirror_event_id, None)
                deleted += 1

        return {"deleted": deleted}

    def delete_bad_events(self) -> None:
        """ Delete items that are listed in the bad_events"""
        if self.bad_events:
            for evt in list(self.bad_events):
                bad_event_id = evt.mirror_event_id
                self.client.delete_event(
                    calendar_id=self.mirror_calendar.id,
                    event_id=bad_event_id
                )

                logger.info(f"Deleted Mirror event:{bad_event_id} in {self.mirror_calendar.id}")

    def save_mirror_mapping(self) -> None:
        filename = get_data_location_as_path(f"mirror_{self.mirror_calendar.id}_mapping.json")
        data = {
            key: asdict(evt)
            for key, evt in self.mappings.items()
        }

        save_json_file(filename, data)

    def load_mirror_mapping(self) -> bool:
        filename = get_data_location_as_path(f"mirror_{self.mirror_calendar.id}_mapping.json")
        self.bad_events = []

        if not os.path.exists(filename):
            self.mappings = {}
            return False

        self.mappings = self._load_mirror_mappings(filename)
        return True

    @classmethod
    def _load_mirror_mappings(cls, filename: Path) -> dict[str, MappingEvent]:

        raw = load_json_file(filename)
        return {
            key: MappingEvent(**value)
            for key, value in raw.items()
        }

    @classmethod
    def find_latest_mirror_filename(cls) -> Path | None:
        data_dir = get_data_directory()

        # Search mode: find any matching mapping file
        candidates = list(data_dir.glob("mirror_*_mapping.json"))

        if not candidates:
            return None
        if len(candidates) > 1:
            logger.warning("multiple mirror files")
            # If multiple exist, pick the newest
            candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates[0]

    @classmethod
    def summarize_mapping_events(cls) -> List[str]:
        my_timezone = SETTINGS.get(MY_TIMEZONE)
        if not isinstance(my_timezone, str):
            raise ValueError("timezone is not defined")

        status_counts = Counter[str]()
        updated_daily = Counter[str]()
        synced_daily = Counter[str]()
        updated_weekly = Counter[Tuple[str, str]]()
        synced_weekly = Counter[Tuple[str, str]]()

        filename = cls.find_latest_mirror_filename()
        if not filename:
            return ["No File"]

        events = cls._load_mirror_mappings(filename)

        tz = zoneinfo.ZoneInfo(my_timezone)
        now = datetime.now(tz=tz)
        one_week_ago = now - timedelta(days=7)

        def parse(ts: str) -> datetime:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(tz)

        def week_range(dt: datetime) -> Tuple[str, str]:
            the_date = dt.date()
            start_d = the_date - timedelta(days=the_date.weekday())  # Monday
            end_d = start_d + timedelta(days=6)  # Sunday
            return str(start_d), str(end_d)

        # Build the last 7 calendar days in local timezone
        last_7_days = []
        for i in range(7):
            d = (now - timedelta(days=i)).date()
            last_7_days.append(str(d))

        last_7_days.sort()  # oldest → newest

        for ev in events.values():
            status_counts[ev.status] += 1

            updated_dt = parse(ev.updated_at)
            synced_dt = parse(ev.last_synced_at)

            updated_day = str(updated_dt.date())
            synced_day = str(synced_dt.date())

            # Daily (last 7 days)
            if updated_dt >= one_week_ago:
                updated_daily[updated_day] += 1
            if synced_dt >= one_week_ago:
                synced_daily[synced_day] += 1

            # Weekly (use date ranges instead of ISO week numbers)
            updated_week = week_range(updated_dt)
            synced_week = week_range(synced_dt)

            updated_weekly[updated_week] += 1
            synced_weekly[synced_week] += 1

        # Build output
        lines = ["=== Status Totals ==="]
        for status, count in status_counts.items():
            lines.append(f"{status}: {count}")

        lines.append("")
        lines.append("=== Updated_at Daily (Last 7 Days) ===")
        for day in last_7_days:
            count = synced_daily.get(day, 0)
            lines.append(f"{day}: {count}")

        lines.append("")
        lines.append("=== Last_synced_at Daily (Last 7 Days) ===")
        for day, count in sorted(synced_daily.items()):
            lines.append(f"{day}: {count}")

        lines.append("")
        lines.append("=== Updated_at Weekly Totals ===")
        for (start, end), count in sorted(updated_weekly.items()):
            lines.append(f"{start} → {end}: {count}")

        lines.append("")
        lines.append("=== Last_synced_at Weekly Totals ===")
        for (start, end), count in sorted(synced_weekly.items()):
            lines.append(f"{start} → {end}: {count}")

        return lines
