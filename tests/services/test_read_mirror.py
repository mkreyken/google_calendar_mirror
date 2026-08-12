from src.api.calendar_source_info import CalendarMappingApi
from src.api.mirror_calendar_manager import MirrorCalendarManager
from src.clients.google_calendar_client import GoogleCalendarClient

client = GoogleCalendarClient()

calendar_mapper = CalendarMappingApi(
    client
)

mapped_calendars = calendar_mapper.fetch_calendars()
mirror_calendar_id = calendar_mapper.get_mirror_calendar()
mirror = MirrorCalendarManager(client, mirror_calendar_id, calendar_mapper)
mirror.read_mirror_and_report_errors(True)
print(f"Bad events = {mirror.bad_events or ''}")
print(f"Mirror Events = {mirror.mappings}")
