import os
os.environ["ICAL_TEST_MODE"] = "1"

from src.services.env import INCREMENTAL_SYNC
from src.services.launcher import SyncManager

if __name__ == "__main__":

    manager = SyncManager()
    manager._run_sync(INCREMENTAL_SYNC)
