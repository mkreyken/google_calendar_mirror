import datetime
import os.path
from typing import cast

# noinspection PyPackageRequirements
from google.auth.exceptions import RefreshError
# noinspection PyPackageRequirements
from google.auth.transport.requests import Request
# noinspection PyPackageRequirements
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-untyped]
from googleapiclient.discovery import build  # type: ignore[import-untyped]
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]

from src.util.filesystem import get_tokens_filename, get_credentials_filename

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

def _build_flow(credentials_file) -> InstalledAppFlow:
    return cast(
        InstalledAppFlow,
        InstalledAppFlow.from_client_secrets_file(
            credentials_file,
            SCOPES,
        ))

def main() -> None:
    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user's calendar.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    secrets_token_filename = get_tokens_filename()
    secrets_cred_filename = get_credentials_filename()
    if os.path.exists(secrets_token_filename):
        creds = Credentials.from_authorized_user_file(secrets_token_filename, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as error:
                print(f"On refresh an error occurred: {error}")
                print(f"Delete the token.json file and restart")

        else:
            flow = _build_flow(
                os.path.abspath(secrets_cred_filename)
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(secrets_token_filename, "w") as token:
            token.write(creds.to_json())

    try:
        service = build("calendar", "v3", credentials=creds)

        # Call the Calendar API
        now = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        print("Getting the upcoming 10 events")
        events_result = (
            service.google_events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=10,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        if not events:
            print("No upcoming events found.")
            return

        # Prints the start and name of the next 10 events
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            print(start, event["summary"])

    except HttpError as error:
        print(f"An error occurred: {error}")


if __name__ == "__main__":
    main()
