import os

os.environ["ICAL_TEST_MODE"] = "1"

from src.services.launcher import main

if __name__ == "__main__":

    main()
