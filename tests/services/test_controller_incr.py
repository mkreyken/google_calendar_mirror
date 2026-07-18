from src.services.controller import Controller
from src.services.env import INCREMENTAL_SYNC

if __name__ == "__main__":
    controller = Controller()
    controller.run(INCREMENTAL_SYNC)