import io
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from src.clients.google_mail_client import GmailTextSender
from src.util.filesystem import get_log_directory

JobFunc = Callable[[], None]

LOG_FILE = get_log_directory() / "sync.log"

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
FORMATTER = logging.Formatter(LOG_FORMAT)


def close_handlers(logger: logging.Logger) -> None:
    """Remove and close every handler attached directly to a logger."""
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.flush()
        handler.close()


def close_existing_logging() -> None:
    """
    Close handlers that may have been created by an earlier run or by
    logging.basicConfig().
    """
    root_logger = logging.getLogger()
    close_handlers(root_logger)

    job_logger = logging.getLogger("job")
    if job_logger is not root_logger:
        close_handlers(job_logger)


def rotate_logs_on_start() -> None:
    """Rotate sync.log to sync.log.1, sync.log.2, ..., sync.log.10."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Rotate older files first.
    for index in range(9, 0, -1):
        source = LOG_FILE.with_suffix(f".log.{index}")
        destination = LOG_FILE.with_suffix(f".log.{index + 1}")

        if source.exists():
            # os.replace() also replaces an existing destination on Windows.
            os.replace(source, destination)

    # Rotate the current file.
    rotated_file = LOG_FILE.with_suffix(".log.1")
    if LOG_FILE.exists():
        os.replace(LOG_FILE, rotated_file)


@dataclass
class LoggerData:
    logger: logging.Logger
    file_handler: logging.FileHandler
    console_handler: logging.StreamHandler
    capture_handler: logging.Handler
    output_buffer: io.StringIO


def configure_logging() -> LoggerData:
    """
    Configure logging for one job run.

    The root logger is configured so that logs from modules such as
    src.clients.google_mail_client also reach the file, console, and capture
    handlers through normal logger propagation.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    output_buffer = io.StringIO()

    file_handler = logging.FileHandler(
        LOG_FILE,
        mode="w",
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(FORMATTER)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(FORMATTER)

    capture_handler = logging.StreamHandler(output_buffer)
    capture_handler.setLevel(logging.INFO)
    capture_handler.setFormatter(FORMATTER)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(capture_handler)

    # Code may use logging.getLogger("job"), logging.getLogger(__name__),
    # or logging.info(). All of those can propagate to the root logger.
    job_logger = logging.getLogger("job")
    job_logger.setLevel(logging.INFO)
    job_logger.propagate = True

    return LoggerData(
        job_logger,
        file_handler,
        console_handler,
        capture_handler,
        output_buffer,
    )


def run_job_with_email_report(function: JobFunc, to_email: str) -> None:
    # Close handlers from a previous configuration before renaming the file.
    close_existing_logging()

    # Rotate before creating the new FileHandler.
    rotate_logs_on_start()

    logger_data: LoggerData = configure_logging()
    logger = logger_data.logger

    logger.info("Job started")

    # noinspection broad-exception
    try:
        function()
    except Exception as ex:
        logger.exception("Job failed with an unhandled exception", exc_info=ex)

    finally:
        logger_data.file_handler.flush()
        logger_data.console_handler.flush()
        logger_data.capture_handler.flush()

        log_text = logger_data.output_buffer.getvalue()

        # This closes sync.log and releases the file handle.
        close_existing_logging()
        logger_data.output_buffer.close()

    subject = f"Job Run Report - {datetime.now():%Y-%m-%d %H:%M:%S}"

    if to_email:
        sender = GmailTextSender()
        sender.send_text(
            to=to_email,
            subject=subject,
            body=log_text,
        )
