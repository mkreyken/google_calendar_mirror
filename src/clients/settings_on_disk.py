import os
from typing import Dict, Optional

from src.services.env import SETTINGS_ON_DISK_FILENAME
from src.util.filesystem import get_data_location_as_path, load_json_file, save_json_file

GOOGLE_COLOR_AS_HEX = "google_color_as_hex"
IS_MASTER_SYNC_COMPUTER = "is_master_sync_computer"
EMAIL_TO_LOGS = "email_logs_to"
EMAIL_TO_REPORTS = "email_reports_to"
MY_TIMEZONE = "timezone"
MAXIMUM_MULTI_DAY_EVENT = "maximum_multi_day_event"
CRON_RUN_INCR_SYNC_HOURS = "cron_run_incr_sync_hours"
CRON_RUN_REPORTS_BEFORE_EOM_DAYS = "cron_run_repotrs_before_eom_days"

SettingsOnDisk = str | bool | int

LAST_REFRESH_DATE = "last_refresh_date"
LAST_REPORTS_DATE = "last_reports_data"


class Settings:
    _instance = None
    settings: Dict[str, SettingsOnDisk]

    def __new__(cls) -> Settings:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):  # type: ignore[no-untyped-def]
        # Only run initialization once
        if not hasattr(self, "settings"):
            self.settings = self.load_settings_values()

    def get(self, key: str) -> Optional[SettingsOnDisk]:
        results = self.settings.get(key)
        if results is None:
            return self.default_values().get(key)
        return results

    @classmethod
    def get_temp_value(cls,key:str) -> Optional[SettingsOnDisk]:
        filename = get_data_location_as_path(SETTINGS_ON_DISK_FILENAME+"_"+key)
        if not os.path.exists(filename):
            return None
        raw = load_json_file(filename)
        return raw.get(key)

    @classmethod
    def set_temp_value(cls,key:str, value:SettingsOnDisk) -> None:
        filename = get_data_location_as_path(SETTINGS_ON_DISK_FILENAME+"_"+key)
        mappings : Dict[str,SettingsOnDisk] = {key: value}
        save_json_file(filename, mappings)

    @classmethod
    def default_values(cls) -> Dict[str, SettingsOnDisk]:
        values: Dict[str, SettingsOnDisk] = {
            GOOGLE_COLOR_AS_HEX: False,
            IS_MASTER_SYNC_COMPUTER: True,
            EMAIL_TO_LOGS: "me",
            MAXIMUM_MULTI_DAY_EVENT: 2,
            CRON_RUN_INCR_SYNC_HOURS: 40,
            CRON_RUN_REPORTS_BEFORE_EOM_DAYS : 7
        }
        return values

    def load_settings_values(self) -> Dict[str, SettingsOnDisk]:
        filename = get_data_location_as_path(SETTINGS_ON_DISK_FILENAME)
        if not os.path.exists(filename):
            mappings = self.default_values()
            save_json_file(filename, mappings)
            return mappings
        raw = load_json_file(filename)

        mappings = {}
        for key, entry in raw.items():
            v = entry
            if not isinstance(v, SettingsOnDisk):
                raise ValueError(f"Invalid type for {key}: {type(v)}")
            mappings[key] = v

        return mappings


# start singletons.
SETTINGS = Settings()
