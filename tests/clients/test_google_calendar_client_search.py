from datetime import datetime, timezone

from src.clients.google_calendar_client import GoogleCalendarClient
from src.util.date_util import to_rfc3339

# Define date range
time_min = datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)
time_max = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)

client = GoogleCalendarClient()

events = client.search_calendar_events(
    calendar_id="primary",
    query="House Visit",          # free-text search
    time_min=time_min,
    time_max=time_max,
    single_events=True,
    order_by="startTime",
    max_results=2500,
)

for ev in events:

    print(f" {to_rfc3339(ev.start)}  {ev.summary}")