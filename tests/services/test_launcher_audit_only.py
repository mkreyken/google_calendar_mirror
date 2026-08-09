from src.services.env import AUDIT
from src.services.launcher import SyncManager

if __name__ == "__main__":
    manager = SyncManager(None)
    manager.run_sync(AUDIT)
