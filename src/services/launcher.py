import logging
import threading
from pathlib import Path
from typing import Any, List, Optional, Callable

import pystray  # type: ignore[import-untyped]
from PIL import Image
from pystray import Menu, MenuItem

from src.clients.settings_on_disk import IS_MASTER_SYNC_COMPUTER, SETTINGS, EMAIL_TO_LOGS
from src.reporter.reports_manager import ReportsManager
from src.services.controller import Controller
from src.services.env import APP_ID, FULL_SYNC, INCREMENTAL_SYNC, AUDIT_AND_FIX, APP_NAME
from src.util.filesystem import get_log_directory, get_data_location_as_path

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

    def __init__(self):
        val = SETTINGS.get(EMAIL_TO_LOGS)
        if isinstance(val, str):
            self.to_logs_email = val
        else:
            raise ValueError("Email is not type str")

    def run_sync(self, kind: str) -> bool:
        app_logger.info(f"Starting {kind} sync...")
        # noinspection PyBroadException
        try:
            controller = Controller()
            controller.run_with_email_report(kind, self.to_logs_email)
            success = True
            app_logger.info(f"{kind.capitalize()} sync completed successfully.")
        except Exception:
            app_logger.exception(f"{kind.capitalize()} sync failed.")
            success = False

        return success


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

        icon_image = create_icon()
        self.icon: IconType = pystray.Icon(
            self.app_name,
            icon_image,
            self.app_name,
            menu=self._create_menu(),
        )

    # --- Menu callbacks ---

    def _run_sync_background(self, kind: str,
                             follow_up: Optional[Callable[[bool], None]] = None):
        def worker() -> None:
            success = self.sync_manager.run_sync(kind)

            if follow_up:
                follow_up(success)

            title = "Sync completed" if success else "Sync failed"
            message = f"{kind.capitalize()} sync finished."
            self.notification_manager.send_toast(title, message)

        threading.Thread(target=worker, daemon=True).start()

    def on_sync_full(self) -> None:
        self._run_sync_background(FULL_SYNC)

    def on_sync_partial(self) -> None:
        self._run_sync_background(INCREMENTAL_SYNC, self.on_sync_partial_finished)

    def on_sync_refresh(self) -> None:
        self._run_sync_background(AUDIT_AND_FIX)

    @classmethod
    def on_sync_partial_finished(cls, was_success: bool) -> None:
        if was_success:
            to_val = SETTINGS.get(EMAIL_TO_LOGS)
            if isinstance(to_val, str):
                ReportsManager().full_report(to_val)

    def on_status(self) -> None:
        status_text = self.reports_manager.get_notification_text()
        app_logger.info("Status requested:\n%s", status_text)
        # if "do not disturb" is on, this goes into the notification window
        self.notification_manager.send_toast("Sync Status", status_text)

    # noinspection PyMethodMayBeStatic
    def on_exit(self, icon: IconType) -> None:
        icon.stop()

    def on_report_venues(self) -> None:
        pass

    def on_report_periodic(self) -> None:
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
            "Email venue Calendars",
            self.on_report_venues,
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
