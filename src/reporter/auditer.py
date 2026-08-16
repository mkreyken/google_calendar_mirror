from datetime import datetime

from src.clients.google_mail_client import GmailTextSender
from src.clients.settings_on_disk import EMAIL_TO_LOGS, SETTINGS
from src.reporter.reports_manager import ReportsManager
from src.services.controller import Controller
from src.services.env import AUDIT


def remote_audit() -> None:
    val = SETTINGS.get(EMAIL_TO_LOGS)
    if isinstance(val, str):
        to_email = val
    else:
        raise ValueError("Email is not type str")
    controller = Controller()
    reports_manager = ReportsManager()

    controller_text = controller.run_with_logger_output(AUDIT)

    status_text = reports_manager.get_notification_text()

    body_text = status_text + "\n" + controller_text

    subject = f"Job Run Report - {datetime.now():%Y-%m-%d %H:%M:%S}"

    sender = GmailTextSender()
    sender.send_text(
        to=to_email,
        subject=subject,
        body=body_text,
    )
