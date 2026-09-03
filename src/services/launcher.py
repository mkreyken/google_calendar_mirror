import datetime
import logging
import threading
import time
from pathlib import Path
from typing import Any, List, Optional, Callable

import pystray  # type: ignore[import-untyped]
from PIL import Image
from pystray import Menu, MenuItem

from src.api import user_is_in_calendar
from src.api.calendar_source_info import CalendarMappingApi
from src.clients.settings_on_disk import IS_MASTER_SYNC_COMPUTER, SETTINGS, EMAIL_TO_LOGS, CRON_RUN_INCR_SYNC_HOURS, \
    CRON_RUN_REPORTS_BEFORE_EOM_DAYS, LAST_REFRESH_DATE, EMAIL_TO_REPORTS
from src.reporter.reports_manager import ReportsManager
from src.services.controller import Controller
from src.services.env import APP_ID, FULL_SYNC, INCREMENTAL_SYNC, AUDIT_AND_FIX, APP_NAME
from src.util.date_util import parse_datestamp
from src.util.filesystem import get_log_directory, get_data_location_as_path
from src.util.semaphore import SyncSemaphore

# --- Optional: Windows toast notifications via winrt ---
# on laptop pad, 2 finger click is right click
USE_TOAST = True
# noinspection PyBroadException
try:
    # noinspection PyPackageRequirements
    import winrt.windows.ui.notifications as notifications
    # noinspection PyPackageRequirements
    import winrt.windows.data.xml.dom as dom
except Exception:
    USE_TOAST = False

# Icon is not exposed
IconType = Any

APP_LOG_FILE = get_log_directory() / "app.log"

app_handler = logging.FileHandler(APP_LOG_FILE, encoding="utf-8")

app_logger = logging.getLogger("app")
app_logger.setLevel(logging.INFO)
app_logger.addHandler(app_handler)

# Prevent double logging through root handlers
app_logger.propagate = False


# --- Sync logic ---

class SyncManager:
    to_logs_email: str
    sync_semaphore: SyncSemaphore
    shutdown: bool = False
    hours_between_incr_sync = 40
    days_before_eom_reports = 7

    def __init__(self): # type: ignore[no-untyped-def]
        self.sync_semaphore = SyncSemaphore()
        val = SETTINGS.get(EMAIL_TO_LOGS)
        if isinstance(val, str):
            self.to_logs_email = val
        else:
            raise ValueError(f"{EMAIL_TO_LOGS} is not type str")

        val = SETTINGS.get(CRON_RUN_INCR_SYNC_HOURS)
        if isinstance(val, int):
            self.hours_between_incr_sync = val
        else:
            raise ValueError(f"{CRON_RUN_INCR_SYNC_HOURS} is not type int")

        val = SETTINGS.get(CRON_RUN_REPORTS_BEFORE_EOM_DAYS)
        if isinstance(val, int):
            self.days_before_eom_reports = val
        else:
            raise ValueError(f"{CRON_RUN_REPORTS_BEFORE_EOM_DAYS} is not type int")

        threading.Thread(
            target=self._schedule_loop,
            daemon=True
        ).start()

    def is_running(self) -> bool:
        return self.sync_semaphore.sync_is_running()

    def exiting(self) -> None:
        self.shutdown = True

    def _run_sync(self, kind: str) -> bool:
        app_logger.info(f"Starting {kind} sync...")
        # noinspection PyBroadException
        try:
            controller = Controller()
            results = controller.run_with_email_report(kind, self.to_logs_email)
            success = results.success
        except Exception:
            success = False
        if success:
            app_logger.info(f"{kind.capitalize()} sync completed successfully.")
        else:
            app_logger.exception(f"{kind.capitalize()} sync failed.")

        return success

    def run_sync_background(self, kind: str,
                            follow_up: Optional[Callable[[str, bool], None]] = None) -> Optional[str]:

        if not self.sync_semaphore.try_start_sync():
            return "Busy"

        def worker() -> None:
            try:
                success = self._run_sync(kind)
                if follow_up:
                    follow_up(kind, success)

            finally:
                # ALWAYS release semaphore even if sync crashes
                self.sync_semaphore.end_sync()

        threading.Thread(target=worker, daemon=True).start()
        return None

    def _schedule_loop(self) -> None:

        last_run = CalendarMappingApi.get_latest_sync()
        if last_run:
            last_run_dt = last_run.date_stamp
        else:
            last_run_dt = datetime.datetime.now()

        interval = datetime.timedelta(hours=self.hours_between_incr_sync)
        short_wait = datetime.timedelta(minutes=10)
        next_run = last_run_dt + interval

        while not self.shutdown:
            now = datetime.datetime.now()

            if now >= next_run:
                if not user_is_in_calendar.is_calender_on_edge():
                    self.check_for_secondary()
                    # if already running, it doesn't matter and this will quit
                    self.run_sync_background(INCREMENTAL_SYNC)
                    next_run = now + interval
                else:
                    next_run = now + short_wait

            time.sleep(60)  # maximum delay to hold thread on quit

    def run_refresh_function(self) -> None:
        self.run_sync_background(AUDIT_AND_FIX)

    def check_for_secondary(self) -> None:
        today = datetime.date.today()

        last_refresh_str = SETTINGS.get_temp_value(LAST_REFRESH_DATE)

        # If nothing stored yet, treat as needing refresh
        if not last_refresh_str or not isinstance(last_refresh_str, str):
            self.run_refresh_function()
            SETTINGS.set_temp_value(LAST_REFRESH_DATE, today.strftime("%Y%m%d"))
            return

        last_refresh_date = parse_datestamp(last_refresh_str)

        # Detect month or year change
        month_changed = (
                today.year != last_refresh_date.year or
                today.month != last_refresh_date.month
        )

        if month_changed:
            self.run_refresh_function()
            SETTINGS.set_temp_value(LAST_REFRESH_DATE, today.strftime("%Y%m%d"))


# --- Notifications ---

class NotificationManager:
    def __init__(self, app_id: str, use_toast: bool = True):
        self.app_id = app_id
        self.use_toast = use_toast and USE_TOAST

    def send_toast(self, title: str, message: str) -> None:
        if not self.use_toast:
            return
        # noinspection PyBroadException
        try:
            toast_xml = f"""
            <toast duration="short">
              <visual>
                <binding template="ToastGeneric">
                  <text>{title}</text>
                  <text>{message}</text>
                </binding>
              </visual>
            </toast>
            """
            doc = dom.XmlDocument()
            doc.load_xml(toast_xml)
            toast = notifications.ToastNotification(doc)

            notifier = notifications.ToastNotificationManager.create_toast_notifier_with_id(self.app_id)
            notifier.show(toast)
        except Exception:
            app_logger.exception("Failed to send toast notification")


def create_icon() -> Image.Image:
    logo_path = get_data_location_as_path("logo.png")
    image: Image.Image = Image.open(logo_path)
    image = image.resize((64, 64), Image.Resampling.LANCZOS)
    return image


class TrayController:
    app_name: str
    sync_manager: SyncManager
    reports_manager: ReportsManager
    notification_manager: NotificationManager
    log_file: Path
    icon: IconType
    reports_email: str
    logs_email: str

    def __init__(
            self,
            app_name: str,
            sync_manager: SyncManager,
            reports_manager: ReportsManager,
            notification_manager: NotificationManager,
            log_file: Path,
    ):
        self.app_name = app_name
        self.sync_manager = sync_manager
        self.reports_manager = reports_manager
        self.notification_manager = notification_manager
        self.log_file = log_file

        val = SETTINGS.get(EMAIL_TO_REPORTS)
        if isinstance(val, str):
            self.reports_email = val
        else:
            raise ValueError(f"{EMAIL_TO_REPORTS} is not type str")

        val = SETTINGS.get(EMAIL_TO_LOGS)
        if isinstance(val, str):
            self.logs_email = val

        icon_image = create_icon()
        self.icon: IconType = pystray.Icon(
            self.app_name,
            icon_image,
            self.app_name,
            menu=self._create_menu(),
        )

    # --- Menu callbacks ---

    def _run_sync(self, kind: str,
                  follow_up: Optional[Callable[[str, bool], None]] = None):

        message = self.sync_manager.run_sync_background(kind, follow_up)
        if message:
            self.notification_manager.send_toast("Sync Busy", message)
            return

    def results_toast(self, kind: str, success: bool) -> None:
        title = "Sync completed" if success else "Sync failed"
        message = f"{kind.capitalize()} sync finished."
        self.notification_manager.send_toast(title, message)

    def on_sync_full(self) -> None:
        self._run_sync(FULL_SYNC)

    def on_sync_partial(self) -> None:
        self._run_sync(INCREMENTAL_SYNC, self.on_sync_partial_finished)

    def on_sync_refresh(self) -> None:
        self._run_sync(AUDIT_AND_FIX)

    def on_sync_partial_finished(self, kind: str, was_success: bool) -> None:
        if was_success:
            to_val = SETTINGS.get(EMAIL_TO_LOGS)
            if isinstance(to_val, str):
                ReportsManager().full_report(to_val)
        self.results_toast(kind, was_success)

    def on_status(self) -> None:
        if self.sync_manager.is_running():
            self.notification_manager.send_toast("Sync Status", "Running")
            return

        status_text = self.reports_manager.get_notification_text()
        app_logger.info("Status requested:\n%s", status_text)
        # if "do not disturb" is on, this goes into the notification window
        self.notification_manager.send_toast("Sync Status", status_text)

    # noinspection PyMethodMayBeStatic
    def on_exit(self, icon: IconType) -> None:
        if self.sync_manager.is_running():
            self.notification_manager.send_toast("Sync Status", "Running")
            return
        self.sync_manager.exiting()
        icon.stop()

    def on_report_venues_next_month(self) -> None:
        if self.sync_manager.is_running():
            self.notification_manager.send_toast("Sync Status", "Running")
            return
        ReportsManager.email_pdf_reports(self.logs_email, 1)

    def on_report_venues_this_month(self) -> None:
        if self.sync_manager.is_running():
            self.notification_manager.send_toast("Sync Status", "Running")
            return
        ReportsManager.email_pdf_reports(self.logs_email, 0)

    def on_report_periodic(self) -> None:
        if self.sync_manager.is_running():
            self.notification_manager.send_toast("Sync Status", "Running")
            return
        pass

    # --- Menu creation ---

    def _create_menu(self) -> Menu:
        menu_def: List[MenuItem] = [
            pystray.MenuItem(
                "Status",
                self.on_status,
                default=True,  # <-- left-click default
            )]

        if SETTINGS.get(IS_MASTER_SYNC_COMPUTER):
            # if there are tokens' use them, an audit and fix is all that is needed otherwise
            # the only reason for a full sync is a buggy program, or data changes in the private,
            # which should be done with the developer scripts
            # menu_def.append(pystray.MenuItem(
            #    "Sync now (full)",
            #    self.on_sync_full))
            menu_def.append(pystray.MenuItem(
                "Sync now and reports",
                self.on_sync_partial))
        menu_def.append(pystray.MenuItem(
            "Sync (Refresh)",
            self.on_sync_refresh))
        # Now add the rest — these MUST be appended
        menu_def.append(pystray.Menu.SEPARATOR)

        menu_def.append(pystray.MenuItem(
            "Email venue Calendars for next month",
            self.on_report_venues_next_month,
        ))

        menu_def.append(pystray.MenuItem(
            "Email venue Calendars for this month",
            self.on_report_venues_this_month,
        ))

        menu_def.append(pystray.MenuItem(
            "Email Regular Reports",
            self.on_report_periodic,
        ))

        menu_def.append(pystray.Menu.SEPARATOR)

        menu_def.append(pystray.MenuItem("Exit", self.on_exit))

        return pystray.Menu(*menu_def)

    # --- Run tray ---

    def run(self) -> None:
        app_logger.info("Starting SyncLauncher tray app...")
        self.icon.run()


# --- Main entry point ---

def main() -> None:
    APP_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    reports_manager = ReportsManager()
    sync_manager = SyncManager()
    notification_manager = NotificationManager(APP_ID, use_toast=True)

    tray = TrayController(
        app_name=APP_NAME,
        sync_manager=sync_manager,
        reports_manager=reports_manager,
        notification_manager=notification_manager,
        log_file=APP_LOG_FILE,
    )
    tray.run()


if __name__ == "__main__":
    main()
