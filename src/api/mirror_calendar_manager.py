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
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from src.api.calendar_source_info import CalendarMappingApi
from src.api.types import EventType, MappingEvent, STATUS_OK, STATUS_CANCELLED, STATUS_BAD, STATUS_DELETED, BadEvent, \
    GoogleEventData, CalendarPageData, CalendarSourceInfo
from src.clients.google_calendar_client import GoogleCalendarClient
from src.services.events_converter import EventConverter
from src.util.exceptions import InvalidDataError
from src.util.filesystem import save_json_file, load_json_file, get_data_location_as_path

logger = logging.getLogger(__name__)


# noinspection PyUnresolvedReferences
class MirrorCalendarManager:

    def __init__(self, client: GoogleCalendarClient, mirror_calendar: CalendarSourceInfo,
                 calendars: CalendarMappingApi):
        self.bad_events: Optional[list[BadEvent]] = None
        self.client: GoogleCalendarClient = client
        self.mirror_calendar: CalendarSourceInfo = mirror_calendar
        self.mappings: dict[str, MappingEvent] = {}
        self.calendars = calendars

    def read_mirror_and_report_errors(self) -> None:
        """
        Rebuild the sync mapping database by scanning the mirror calendar.
        Only events inside the rolling window are considered.
        """
        now = datetime.now(timezone.utc)

        # filtered does not allow for sync_token
        # Mirror is always window_synced, it has a local db instead of "incremental"
        # Rolling window: 2 months back, 18 months forward
        window_start = now - timedelta(days=60)
        window_end = now + timedelta(days=540)
        sync_token = None

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
                elif ((not self.calendars.is_valid_calendar_id(event.source_calendar_id))
                      or self.mappings.get(event.source_event_id)):
                    # it is in a deleted calendar, or is a duplicate copy
                    bad_event = BadEvent(
                        mirror_event_id=event.mirror_event_id
                    )
                    self.bad_events.append(bad_event)
                else:
                    self.mappings[event.source_event_id] = \
                        EventConverter.from_event_to_mapping(event, event.mirror_event_id)

            if not page_token:
                break
        logger.info(f"Finished reading mirror cnt :{len(self.mappings)} bad : {len(self.bad_events or [])}")

        return

    def __match_event(self, event: EventType) -> MappingEvent | None:
        """ for single_event=true, we only need to match the ids
        the return value is modifiable"""

        mapping = self.mappings.get(event.source_event_id)
        if not mapping:
            return None
        if mapping.source_calendar_id == event.source_calendar_id and event.status == STATUS_OK:
            return mapping
        mapping.status = STATUS_BAD
        return None

    def apply_change_to_mirror(self, event: EventType) -> str:
        mapped_event = self.__match_event(event)

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
            mapped_event.status = "Updated"
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
                                                     last_synced_at=event.last_synced_at
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

    def delete_bad_events(self) -> None :
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

        raw = load_json_file(filename)
        self.mappings = {
            key: MappingEvent(**value)
            for key, value in raw.items()
        }
        return True
