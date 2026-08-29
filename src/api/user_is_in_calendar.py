

import ctypes
import time


def get_active_window_title() -> str:
    user32 = ctypes.windll.user32

    # Get handle of the active (foreground) window
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""

    # Allocate buffer for the window title
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)

    # Read the window title
    user32.GetWindowTextW(hwnd, buffer, length + 1)

    return buffer.value


def is_calender_on_edge() -> bool:
    active_window = get_active_window_title()
    if not active_window.startswith("Immaculate Conception – Calendar"):
        return False
    return active_window.endswith(" Microsoft​ Edge")


if __name__ == "__main__":
    time.sleep(10)
    # is_edge_active_window()
    print(get_active_window_title())
    value = is_calender_on_edge()
    print(str(value))
