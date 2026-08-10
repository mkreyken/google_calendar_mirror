import os
from typing import Dict, Optional

from src.services.env import SETTINGS_ON_DISK_FILENAME
from src.util.filesystem import get_data_location_as_path, load_json_file, save_json_file

GOOGLE_COLOR_AS_HEX = "google_color_as_hex"
IS_MASTER_SYNC_COMPUTER = "is_master_sync_computer"
EMAIL_TO_REPORT = "email_report_to"

SettingsOnDisk = str | bool


class Settings:
    _instance = None

    def __new__(cls) -> Settings:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):  # type: ignore[no-untyped-def]
        # Only run initialization once
        if not hasattr(self, "settings"):
            self.settings = self.load_mirror_mapping()

    def get(self, key: str) -> Optional[str | bool]:
        results = self.settings.get(key)
        if results is None:
            return self.default_values().get(key)
        return results

    @classmethod
    def default_values(cls) -> Dict[str, SettingsOnDisk]:
        values: Dict[str, SettingsOnDisk] = {
            GOOGLE_COLOR_AS_HEX: False,
            IS_MASTER_SYNC_COMPUTER: True,
            EMAIL_TO_REPORT: "me"
        }
        return values

    def load_mirror_mapping(self) -> Dict[str, SettingsOnDisk]:
        filename = get_data_location_as_path(SETTINGS_ON_DISK_FILENAME)
        if not os.path.exists(filename):
            mappings = self.default_values()
            save_json_file(filename, mappings)
            return mappings
        raw = load_json_file(filename)

        mappings = {}
        for key, entry in raw.items():
            v = entry
            if not isinstance(v, (str, bool)):
                raise ValueError(f"Invalid type for {key}: {type(v)}")
            mappings[key] = v

        return mappings


# start singletons.
SETTINGS = Settings()
