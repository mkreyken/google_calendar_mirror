from __future__ import annotations

import datetime as dt
import logging
from typing import List

from src.api.types import CalendarPageData, GoogleEventData, EventType
from src.clients.google_calendar_client import GoogleCalendarClient
from src.services.events_converter import EventConverter

logger = logging.getLogger(__name__)


class EventsReader:
    client: GoogleCalendarClient
    calendar_id: str

    def __init__(self, client: GoogleCalendarClient, calendar_id: str):
        self.client = client
        self.calendar_id = calendar_id

    def _page_through(
            self,
            time_min: dt.datetime,
            time_max: dt.datetime,
            fetch_size: int = 2500
    ) -> CalendarPageData:
        final_list: list[GoogleEventData] = []

        while True:

            results = self.client.list_events(
                single_events=True,
                calendar_id=self.calendar_id, time_min=time_min, time_max=time_max,
                max_results=fetch_size)
            logger.debug(
                f"Reading Calendar cnt: {len(results.google_events)} sync: {results.next_sync_token or ''} page: {results.next_page_token or ''}")

            for change in results.google_events:
                final_list.append(change)
            page_token = results.next_page_token

            if page_token:
                continue
            break

        logger.debug(f"Completed Reading Calendar cnt :{len(final_list)}")

        return CalendarPageData(final_list, next_sync_token=None, next_page_token=None)

    def get_events(self,
                   time_min: dt.datetime,
                   time_max: dt.datetime) -> List[EventType]:
        results = self._page_through(time_min, time_max)
        final_list: List[EventType] = []
        for evt in results.google_events:
            normalize_event = EventConverter.to_event_data(evt, self.calendar_id)
            sanitize_event = EventConverter.sanitize_event(normalize_event)
            final_list.append(sanitize_event)
        return final_list
