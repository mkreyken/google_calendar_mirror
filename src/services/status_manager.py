from typing import List

from src.api.mirror_calendar_manager import MirrorCalendarManager
from src.clients.mirror_key_store import SyncTokenStore
from src.services.env import CALENDAR_TOKEN_FILENAME


class StatusManager:

    @classmethod
    def read_calendar_syncs(cls) -> List[str]:
        calendars = SyncTokenStore(CALENDAR_TOKEN_FILENAME)
        return calendars.summarize()

    @classmethod
    def read_mirror_syncs(cls) -> List[str]:
        return MirrorCalendarManager.summarize_mapping_events()

    def get_status_text(self) -> str:
        lines = []
        lines.extend(self.read_calendar_syncs())
        lines.append("------------------------")
        lines.extend(self.read_mirror_syncs())
        return "\n".join(lines)
