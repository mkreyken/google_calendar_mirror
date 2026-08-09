from src.services.env import INCREMENTAL_SYNC
from src.services.launcher import SyncManager

if __name__ == "__main__":
    manager = SyncManager(None)
    manager.run_sync(INCREMENTAL_SYNC)
