from __future__ import annotations

import datetime as dt
import logging
from typing import Optional

from src.api.calendar_source_info import CalendarMappingApi
from src.api.types import CalendarSourceInfo, CalendarPageData, CalendarChangeData, GoogleEventData
from src.clients.google_calendar_client import GoogleCalendarClient
from src.clients.mirror_key_store import TokenStoreValue
from src.services.env import FULL_SYNC, INCREMENTAL_SYNC
from src.util.date_util import min_mirror_date, max_mirror_date, should_run_full_sync, current_sync_token_datestamp
from src.util.exceptions import GoogleInvalidSyncToken, InvalidDataError

logger = logging.getLogger(__name__)


class GoogleCalendarChangeReader:
    client: GoogleCalendarClient
    source_calendar: CalendarSourceInfo
    calendar_mapper: CalendarMappingApi

    def __init__(self, client: GoogleCalendarClient, source_calendar: CalendarSourceInfo,
                 calendar_mapper: CalendarMappingApi):
        self.client = client
        self.source_calendar = source_calendar
        self.calendar_mapper = calendar_mapper

    def _page_through(
            self,
            time_min: Optional[dt.datetime] = None,
            time_max: Optional[dt.datetime] = None,
            sync_token: Optional[str] = None,
            fetch_size: int = 2500
    ) -> CalendarPageData:
        # This method exists to hide Google Calendar pagination and return a complete set
        # of changes from either a full sync or an incremental sync.
        changed: list[GoogleEventData] = []
        page_token: Optional[str] = None
        next_sync_token: Optional[str] = None

        while True:

            results = self.client.list_events(
                single_events=True,
                calendar_id=self.source_calendar.id, time_min=time_min, time_max=time_max,
                sync_token=sync_token, page_token=page_token, max_results=fetch_size)
            logger.info(
                f"Reading Calendar cnt: {len(results.google_events)} sync: {results.next_sync_token or ''} page: {results.next_page_token or ''}")

            for change in results.google_events:
                changed.append(change)
            page_token = results.next_page_token

            if page_token:
                continue

            next_sync_token = results.next_sync_token
            break

        logger.info(f"Completed Reading Calendar cnt :{len(changed)} sync: {next_sync_token or ''}")

        return CalendarPageData(changed, next_sync_token=next_sync_token, next_page_token=None)

    def full_read(self) -> CalendarChangeData:
        # This method exists to perform the initial or recovery sync when we do not
        # have a valid sync token, or when Google has invalidated the old one.
        logger.info("Full sync")
        self.calendar_mapper.clear_sync_token(self.source_calendar.id)

        results = self._page_through(
            sync_token=None,
        )
        if results.next_sync_token:
            value = TokenStoreValue(results.next_sync_token, current_sync_token_datestamp(), self.source_calendar.name)
            self.calendar_mapper.update_sync_token(self.source_calendar.id, value)

        return CalendarChangeData(self.source_calendar, FULL_SYNC, results.google_events, results.next_sync_token)

    def windowed_read(
            self,
            time_min: Optional[dt.datetime] = min_mirror_date(),
            time_max: Optional[dt.datetime] = max_mirror_date(),
    ) -> CalendarChangeData:
        logger.info("Windowed sync")
        # This method exists to perform the initial or recovery sync when we do not
        # have a valid sync token, or when Google has invalidated the old one.

        results = self._page_through(
            time_min=time_min,
            time_max=time_max,
            sync_token=None,
        )

        return CalendarChangeData(self.source_calendar, FULL_SYNC, results.google_events, results.next_sync_token)

    def next_read(self, force_full_sync: bool, is_windowed_read: bool) -> CalendarChangeData:
        # This method exists to fetch only changes since the last successful sync,
        # which is much cheaper than reloading the entire calendar.
        sync_token: TokenStoreValue | None = self.calendar_mapper.get_sync_token(self.source_calendar.id)

        # check to ensure the window is correct
        if is_windowed_read:
            return self.windowed_read()

        if not sync_token or should_run_full_sync(sync_token.date_stamp) or force_full_sync:
            return self.full_read()

        logger.info("Incremental sync")
        # do sync from last sync up only
        try:
            results = self._page_through(
                sync_token=sync_token.token
            )
            if results.next_sync_token:
                value = TokenStoreValue(results.next_sync_token, current_sync_token_datestamp(),
                                        self.source_calendar.name)
                self.calendar_mapper.update_sync_token(self.source_calendar.id, value)

        except GoogleInvalidSyncToken as e:
            if sync_token:
                self.calendar_mapper.clear_sync_token(self.source_calendar.id)
                return self.full_read()
            else:
                raise InvalidDataError("Invalid sync token when no sync token given") from e

        return CalendarChangeData(self.source_calendar, INCREMENTAL_SYNC, results.google_events,
                                  results.next_sync_token)
