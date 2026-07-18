import io
import logging
from contextlib import contextmanager
from logging import Logger
from typing import Any, Callable, Generator


@contextmanager
def capture_logs_to_string(level=logging.INFO) -> Generator[tuple[Logger, Callable[[], str]], Any, None]:
    """
    Context manager that:
      - creates a temporary in-memory log handler
      - yields (logger, get_logs_callable)
      - on exit, returns full log contents as a string
    """
    logger = logging.getLogger("job_logger")
    logger.setLevel(level)
    logger.handlers.clear()  # optional: ensure clean state

    log_buffer = io.StringIO()
    handler = logging.StreamHandler(log_buffer)
    handler.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)

    def get_logs() -> str:
        # Flush to make sure everything is in the buffer
        handler.flush()
        return log_buffer.getvalue()

    try:
        yield logger, get_logs
    finally:
        logger.removeHandler(handler)
        handler.close()
        log_buffer.close()
