OATH_CLIENT_ID = "156693914634-44dp6foqsn981ei05rbd5j4c9svkh3au.apps.googleusercontent.com"
SECRETS_FILE = "client_secret_2_" + OATH_CLIENT_ID + ".json"
TOKEN_FILE = "token.json"

MIRROR_CALENDAR = "z_ic_all_events"
CALENDAR_TOKEN_FILENAME = "calendar_source_info.json"
SETTINGS_ON_DISK_FILENAME = "settings.json"

APP_NAME = "CalendarSyncApp"

KNOWN_LOCATION_CODES = {
    "church": "C",
    "gathering area": "GA",
    "library": "L",
    "meeting rooms": "MR",
    "prep building": "PB",
    "school classrooms": "SC",
    "school gym": "G",
    "school hall": "H",
}

SENSITIVE_KEYWORDS = [
    "wedding",
    "funeral",
    "memorial",
    "baptism"
    "burial",
    "wake",
    "celebration of life",
    "ceremony",
    "private"
]

# Use the registered AppID for the system Python
APP_ID = r"C:\Python314\python.exe"

# Rolling window: 2 months back, 18 months forward
# work in full months for easier reference
MIRROR_MONTHS_MIN = -2
MIRROR_MONTHS_MAX = 18

FULL_SYNC = "full"
AUDIT_AND_FIX = "audit and fix time window"
AUDIT_AND_UPDATE = "audit and update time window"
AUDIT = "audit time window"
INCREMENTAL_SYNC = "incremental"

ALL_GOOGLE_AUTH_SCOPES = ["https://www.googleapis.com/auth/calendar",
                          "https://www.googleapis.com/auth/gmail.send"]
