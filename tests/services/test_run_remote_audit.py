import os

from src.reporter.auditer import remote_audit

os.environ["ICAL_TEST_MODE"] = "1"
remote_audit()
