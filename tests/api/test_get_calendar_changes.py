from src.api.calendar_change_reader import GoogleCalendarChangeReader
from src.api.calendar_source_info import CalendarMappingApi
from src.clients.google_calendar_client import GoogleCalendarClient

'''
Run's a basic test for faulty shares

'''
if __name__ == "__main__":
    client = GoogleCalendarClient()
    calendar_mapper = CalendarMappingApi(
        client,
        clear_database=True
    )
    mapped_calendars = calendar_mapper.fetch_calendars()
    print(mapped_calendars)
    mirror_calendar_id = calendar_mapper.get_mirror_calendar()
    for calendar in mapped_calendars.values():
        data_manager = GoogleCalendarChangeReader(client, calendar, calendar_mapper)
        changes = data_manager.full_read()
        print(f"{calendar}: {changes}")
"""
TODO: if the start up flag has "enforce" then it adds missing calendars, and changes all permissions

"""
