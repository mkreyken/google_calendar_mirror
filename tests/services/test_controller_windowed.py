from src.services.controller import Controller
from src.services.env import WINDOWED_SYNC

if __name__ == "__main__":
    controller = Controller()
    controller.run(WINDOWED_SYNC)