import logging
from typing import Any

from googleapiclient.errors import HttpError  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


class CalendarError(Exception):
    pass

class InitializationError(CalendarError):
    pass

class InvalidDataError(CalendarError):
    pass

class GoogleApiError(CalendarError):
    """Base wrapper for Google API errors."""
    pass


class GoogleRateLimitError(GoogleApiError):
    pass


class GoogleAuthError(GoogleApiError):
    pass


class GoogleNotFoundError(GoogleApiError):
    pass


class GoogleInvalidSyncToken(GoogleApiError):
    pass


def google_call(func, *args, operation: str = "unset", **kwargs) -> Any:
    """
    Wraps Google API calls with consistent error handling.
    operation: "list", "get", "create", "update", "delete"
    """
    try:
        return func(*args, **kwargs).execute()

    except HttpError as e:

        status = e.resp.status
        reason = getattr(e, "error_details", None)
        # Not found
        if status == 404 and operation == "delete":
            logger.debug("Google API error %s: %s, %s", status, e, reason)
            # Already deleted → treat as success
            return None


        logger.error("Google API error %s: %s, %s", status, e, reason)

        if status == 403 and reason and reason[0].get("reason") == "rateLimitExceeded":
            raise GoogleRateLimitError("Rate limit exceeded") from e

        # Authentication / permission
        if status in (401, 403):
            raise GoogleAuthError("Authentication or permission error") from e

        # Not found
        if status == 404:
             raise GoogleNotFoundError("Resource not found") from e

        # Gone
        if status == 410:
            if operation == "delete":
                # Already deleted → treat as success
                return None
            # Only treat 410 as sync-token failure if operation is list/sync
            raise GoogleInvalidSyncToken("Invalid sync token") from e

        # Rate limits / server errors
        if status in (429, 500, 503):
            raise GoogleRateLimitError("Rate limit or server error") from e

        raise GoogleApiError(f"Unhandled Google API error: {status}") from e

    except Exception as e:
        logger.exception("Unexpected error during Google API call")
        raise GoogleApiError("Unexpected error") from e

