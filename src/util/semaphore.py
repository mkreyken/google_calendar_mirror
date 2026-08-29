import threading


class Semaphore:
    def __init__(self):
        self._lock = threading.Lock()

    def try_lock(self) -> bool:
        return self._lock.acquire(blocking=False)

    def try_unlock(self) -> None:
        try:
            self._lock.release()
        except RuntimeError:
            pass  # unlock attempted when not locked


class SyncSemaphore:
    def __init__(self):
        self._lock = threading.Lock()
        self._sync_running = False

    def try_start_sync(self) -> bool:
        """Attempt to start a sync. Returns True if allowed."""
        with self._lock:
            if self._sync_running:
                return False
            self._sync_running = True
            return True

    def end_sync(self) -> None:
        """Mark sync as finished."""
        with self._lock:
            self._sync_running = False

    def sync_is_running(self) -> bool:
        """Optional helper."""
        with self._lock:
            return self._sync_running
