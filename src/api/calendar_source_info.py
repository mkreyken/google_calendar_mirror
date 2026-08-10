from src.api.types import CalendarSourceInfo, AclInfo
from src.clients.google_calendar_client import GoogleCalendarClient
from src.clients.mirror_key_store import SyncTokenStore, TokenStoreValue
from src.services.env import KNOWN_LOCATION_CODES, MIRROR_CALENDAR, CALENDAR_TOKEN_FILENAME
from src.util.exceptions import InitializationError, InvalidDataError


def generate_location_short_code(name: str) -> str:
    key = name.lower().strip()

    if key in KNOWN_LOCATION_CODES:
        return KNOWN_LOCATION_CODES[key]
    else:
        return f"Z{key}"


class CalendarMappingApi:
    def __init__(
            self,
            client: GoogleCalendarClient,
            clear_database=False
    ):
        self.client = client
        self.calendars: dict[str, CalendarSourceInfo] = {}
        self.mirror_calendar: CalendarSourceInfo | None = None
        self.keystore: SyncTokenStore = SyncTokenStore(CALENDAR_TOKEN_FILENAME, clear_database)
        self.my_email = None

    def check_id_and_throw(self, calender_id: str) -> None:
        if not self.is_valid_calendar_id(calender_id):
            raise ValueError("Invalid Calendar ID")

    def get_calendar_sources(self) -> dict[str, CalendarSourceInfo]:
        return self.calendars

    def is_valid_calendar_id(self, calendar_id: str) -> bool:
        return (self.get_calendar_sources().get(calendar_id)) is not None

    def update_sync_token(self, calender_id: str, token: TokenStoreValue):
        self.check_id_and_throw(calender_id)
        if not token.token or not token.date_stamp:
            raise ValueError("Invalid  token")
        self.keystore.set(calender_id, token)

    def clear_sync_token(self, calender_id: str):
        self.check_id_and_throw(calender_id)
        self.keystore.delete(calender_id)

    def get_sync_token(self, calender_id: str) -> TokenStoreValue | None:
        self.check_id_and_throw(calender_id)
        return self.keystore.get(calender_id)

    def get_mirror_calendar(self) -> CalendarSourceInfo:
        if not self.mirror_calendar: raise InitializationError("Not initialized properly")
        return self.mirror_calendar

    def fetch_calendars(self) -> dict[str, CalendarSourceInfo]:
        calendars = self.client.list_calendars()
        self.my_email = next(c["id"] for c in calendars if c.get("primary"))

        kept = [
            c for c in calendars
            if not c.get("primary", False)
               and c.get("accessRole") == "owner"
        ]

        sources_by_id: dict[str, CalendarSourceInfo] = {}
        sources_by_name: dict[str, CalendarSourceInfo] = {}
        ''' calendar id's are bad right now for google to use on events'''
        color_id = 1
        for cal in kept:
            name = cal.get("summary", "").strip()
            if not name:
                continue

            info = CalendarSourceInfo(
                name=name,
                id=cal["id"],
                color_id=str(cal.get("colorId", "")),
                color_id_for_event=str(color_id),
                short_id=generate_location_short_code(name),
                foreground_color=str(cal.get("foregroundColor", "")),
                background_color=str(cal.get("backgroundColor", "")),
            )
            color_id += 1
            if color_id > 11: color_id = 1

            if sources_by_name.get(info.name):
                raise InvalidDataError(f"Duplicate Calendar Name {info.name}")

            sources_by_id[info.id] = info
            sources_by_name[info.name] = info
        self.mirror_calendar = sources_by_name.pop(MIRROR_CALENDAR, None)
        if not self.mirror_calendar: raise InitializationError("Not initialized properly : no mirror")
        sources_by_id.pop(self.mirror_calendar.id, None)
        self.calendars = sources_by_id
        return sources_by_id

    def get_extra_acl(self, cal_id, is_mirror=False) -> list[AclInfo]:
        if not self.my_email: raise InitializationError("Not initialized properly : no email")
        acl = self.client.get_acl(cal_id)
        outsiders = []

        for rule in acl.get("items", []):
            rule_id = rule["id"]
            role = rule.get("role")  # <-- FIX: extract role

            if rule_id.startswith("user:"):
                email = rule_id.split(":", 1)[1]

                # Skip internal calendar identity
                if email.endswith("@group.calendar.google.com"):
                    continue

                # Skip your own account
                if email.lower() == self.my_email.lower():
                    continue

                # Mirror calendar rule:
                # Readers are allowed → do NOT treat as violation
                if is_mirror and role == "reader":
                    continue

                outsiders.append(AclInfo(email, role))

        return outsiders

    def delete_acl_violations(self, cal_id: str, violations: list[AclInfo]):
        for v in violations:
            rule_id = f"user:{v.email}"
            self.client.acl_delete(cal_id, rule_id)
