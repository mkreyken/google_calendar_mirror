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
        access = calendar_mapper.get_extra_acl(calendar.id, is_mirror=(mirror_calendar_id == calendar.id))
        if access:
            print(f" {calendar.name} : {access}")
            calendar_mapper.delete_acl_violations(calendar.id, access)
        else:
            print(f" {calendar.name} nothing flagged")
"""
TODO: if the start up flag has "enforce" then it adds missing calendars, and changes all permissions

"""
