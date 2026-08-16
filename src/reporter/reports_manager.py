from datetime import datetime
from typing import List

from src.api.mirror_calendar_manager import MirrorCalendarManager
from src.clients.google_calendar_client import GoogleCalendarClient
from src.clients.google_mail_client import GmailTextSender
from src.clients.mirror_key_store import SyncTokenStore
from src.clients.settings_on_disk import SETTINGS, EMAIL_TO_LOGS
from src.reporter.conflicting import conflicting_events
from src.reporter.deleted import deleted_events
from src.services.env import CALENDAR_TOKEN_FILENAME

SEPERATOR = "=================================================================="


class ReportsManager:

    @classmethod
    def calendar_syncs_summary(cls) -> List[str]:
        calendars = SyncTokenStore(CALENDAR_TOKEN_FILENAME)
        return calendars.summarize()

    @classmethod
    def mirror_syncs_summary(cls) -> List[str]:
        return MirrorCalendarManager.summarize_mapping_events()

    def get_notification_text(self) -> str:
        lines = []
        lines.extend(self.calendar_syncs_summary())
        lines.append(SEPERATOR)
        lines.extend(self.mirror_syncs_summary())
        return "\n".join(lines)

    @classmethod
    def email_report(cls, body_text: str, to_email: str):
        subject = f"Calendar Report- {datetime.now():%Y-%m-%d %H:%M:%S}"
        sender = GmailTextSender()
        sender.send_text(
            to=to_email,
            subject=subject,
            body=body_text
        )

    # noinspection list-creation
    def full_report(self, to_email: str) -> None:
        """ this should only be run after a incremental sync is run"""
        gclient = GoogleCalendarClient()
        lines = []
        lines.append(SEPERATOR)
        lines.append("== Check for Overlapping Events ==")
        lines.append(conflicting_events())
        lines.append(SEPERATOR)
        lines.append("== Recently Deleted Events ==")
        lines.append(deleted_events(gclient))
        lines.append(SEPERATOR)
        lines.append("== Sync History ==")
        result = self.mirror_syncs_summary()
        lines.append("\n".join(result))
        self.email_report("\n".join(lines), to_email)


if __name__ == "__main__":
    to_val = SETTINGS.get(EMAIL_TO_LOGS)
    if isinstance(to_val, str):
        ReportsManager().full_report(to_val)
    else:
        raise ValueError("Email is not type str")

