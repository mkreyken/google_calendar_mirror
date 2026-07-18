from src.services.controller import Controller
from src.services.env import FULL_SYNC

if __name__ == "__main__":
    controller = Controller()
    controller.run(FULL_SYNC)