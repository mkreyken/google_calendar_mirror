from __future__ import annotations

import datetime as dt
import os
from datetime import datetime
from typing import Any, Optional, Dict, cast

# noinspection PyPackageRequirements
from google.auth.exceptions import RefreshError
# noinspection PyPackageRequirements
from google.auth.transport.requests import Request
# noinspection PyPackageRequirements
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-untyped]
from googleapiclient.discovery import build  # type: ignore[import-untyped]

from src.api.types import CalendarPageData, GoogleEventData, CalendarSourceInfo
from src.api.types import EventType
from src.services.env import ALL_GOOGLE_AUTH_SCOPES
from src.services.events_converter import EventConverter
from src.util.date_util import to_rfc3339
from src.util.exceptions import google_call, GoogleApiError
from src.util.filesystem import get_tokens_filename, get_credentials_filename

GoogleCalendarClientType = Any
GoogleClientJsonType = Dict[str, Any]


class GoogleCalendarClient:

    def __init__(self,
                 credentials_file: str = get_credentials_filename(),
                 token_file: str = get_tokens_filename()):
        self.credentials_file = credentials_file
        self._token_file = token_file
        self._creds: Optional[Credentials] = None
        self._google_client_With_auth: Optional[GoogleCalendarClientType] = None

    def _build_flow(self) -> InstalledAppFlow:
        return cast(
            InstalledAppFlow,
            InstalledAppFlow.from_client_secrets_file(
                self.credentials_file,
                ALL_GOOGLE_AUTH_SCOPES,
            ))

    def _authenticate(self) -> Credentials:
        creds: Optional[Credentials] = None

        if os.path.exists(self._token_file):
            creds = Credentials.from_authorized_user_file(self._token_file, ALL_GOOGLE_AUTH_SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except RefreshError:
                    creds = None
                    if os.path.exists(self._token_file):
                        os.remove(self._token_file)

            if not creds:
                flow = self._build_flow()
                creds = flow.run_local_server(port=0, prompt="consent")

            if not creds:
                raise GoogleApiError("no Credentials")

            with open(self._token_file, "w", encoding="utf-8") as token:
                token.write(creds.to_json())

        return creds

    @property
    def _google_client(self) -> GoogleCalendarClientType:
        if self._google_client_With_auth is None:
            self._creds = self._authenticate()
            self._google_client_With_auth = build("calendar", "v3", credentials=self._creds)
        return self._google_client_With_auth

    def list_events(
            self,
            calendar_id: str = "primary",
            max_results: int = 2500,
            time_min: Optional[dt.datetime] = None,
            time_max: Optional[dt.datetime] = None,
            page_token: Optional[str] = None,
            sync_token: Optional[str] = None,
            single_events: bool = True
    ) -> CalendarPageData:

        params: GoogleClientJsonType = {
            "calendarId": calendar_id,
            "maxResults": max_results,
            "singleEvents": single_events,
        }

        if page_token:
            params["pageToken"] = page_token

        if time_min is not None:
            params["timeMin"] = to_rfc3339(time_min)
            params["orderBy"] = "startTime"
        if time_max is not None:
            params["timeMax"] = to_rfc3339(time_max)
            params["orderBy"] = "startTime"
        # Initial request can still be a sync, but without a sync_token
        if sync_token:
            params["syncToken"] = sync_token
            params.pop("timeMin", None)
            params.pop("timeMax", None)
            params.pop("orderBy", None)

        results = google_call(
            self._google_client.events().list,
            operation="list",
            **params)
        changed = []
        for change in results.get("items", []):
            changed.append(GoogleEventData(data=change))
        return CalendarPageData(
            changed,
            next_page_token=results.get("nextPageToken"),
            next_sync_token=results.get("nextSyncToken"))

    def create_event(self, calendar_id: str, event: EventType):
        # iCalUID is unique across all calendars, so it must be removed
        event_body = EventConverter.to_google_mirror_event(event).data
        return google_call(
            self._google_client.events().insert,
            operation="create",
            calendarId=calendar_id,
            body=event_body
        )

    def get_event(self, event_id: str, calendar: CalendarSourceInfo) -> EventType:
        result = google_call(
            self._google_client.events().get,
            operation="get",
            calendarId=calendar.id,
            eventId=event_id
        )
        return EventConverter.to_event_data(result, calendar, is_from_mirror=False)

    def update_event(self, event_id: str, calendar_id: str, event: EventType) -> None:

        event_body = EventConverter.to_google_mirror_event(event).data
        google_call(
            self._google_client.events().update,
            operation="update",
            calendarId=calendar_id,
            eventId=event_id,
            body=event_body
        )

    def delete_event(self, event_id: str, calendar_id: str) -> None:
        google_call(
            self._google_client.events().delete,
            operation="delete",
            calendarId=calendar_id,
            eventId=event_id
        )

    def list_calendars(self) -> list[GoogleClientJsonType]:
        resp = google_call(
            self._google_client.calendarList().list,
            operation="list"
        )
        return resp.get("items", [])

    def get_acl(self, calendar_id: str) -> GoogleClientJsonType:
        return google_call(
            self._google_client.acl().list,
            operation=";ist",
            calendarId=calendar_id
        )

    def acl_delete(self, cal_id: str, rule_id: str) -> None:
        google_call(
            self._google_client.acl().delete,
            operation="delete",
            calendarId=cal_id,
            ruleId=rule_id
        )

    def search_calendar_events(
            self,
            calendar_id: str = "primary",
            query: Optional[str] = None,
            time_min: Optional[datetime] = None,
            time_max: Optional[datetime] = None,
            max_results: int = 2500,
            single_events: bool = True,
            order_by: str = "startTime",
            i_cal_uid: Optional[str] = None,
            sync_token: Optional[str] = None,
            updated_min: Optional[datetime] = None,
    ) -> list[GoogleClientJsonType]:

        time_min_str = to_rfc3339(time_min)
        time_max_str = to_rfc3339(time_max)
        updated_min_str = to_rfc3339(updated_min)

        events: list[GoogleClientJsonType] = []
        page_token: Optional[str] = None

        while True:
            result = google_call(
                self._google_client.events().list,
                operation="list",
                calendarId=calendar_id,
                q=query,
                timeMin=time_min_str,
                timeMax=time_max_str,
                maxResults=max_results,
                singleEvents=single_events,
                orderBy=order_by,
                iCalUID=i_cal_uid,
                syncToken=sync_token,
                updatedMin=updated_min_str,
                pageToken=page_token
            )

            items = result.get("items", [])
            events.extend(items)

            page_token = result.get("nextPageToken")
            if not page_token:
                break

        return events
