"""Telegram bot error types and user-facing messages."""

from __future__ import annotations

from dataclasses import dataclass


class UniAssistAPIError(Exception):
    """Base error for UniAssist API client failures."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        request_id: str | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.request_id = request_id
        self.error_code = error_code


class UniAssistAPIUnavailableError(UniAssistAPIError):
    """Raised when the API cannot be reached or is unavailable."""


class UniAssistAPIResponseError(UniAssistAPIError):
    """Raised when the API returns a malformed response."""


class RateLimitExceededError(Exception):
    """Raised when a Telegram user exceeds the configured rate limit."""


@dataclass(frozen=True)
class UserFacingError:
    """Student-safe error message."""

    text: str
    request_id: str | None = None


REFUSAL_MESSAGE = (
    "I couldn't find sufficient information in the university's "
    "verified documents to answer this reliably."
)

EMPTY_MESSAGE_TEXT = "Please send a text question about university rules or procedures."

UNSUPPORTED_MESSAGE_TEXT = (
    "I can only answer text questions about university rules and procedures "
    "in this version. Document uploads are handled through the admin portal."
)

UNKNOWN_COMMAND_TEXT = (
    "I don't recognize that command.\n\nUse /help to see available commands."
)

RATE_LIMIT_MESSAGE = (
    "You're sending questions too quickly.\nPlease wait a moment."
)

SERVICE_UNAVAILABLE_MESSAGE = (
    "UniAssist is temporarily unavailable. Please try again later."
)

INVALID_QUESTION_MESSAGE = (
    "That question could not be processed. Please try rephrasing it."
)


def map_api_error(error: UniAssistAPIError) -> UserFacingError:
    """Map API failures to concise student-facing messages."""
    status = error.status_code
    if status in {400, 422}:
        return UserFacingError(INVALID_QUESTION_MESSAGE, error.request_id)
    if status == 404:
        return UserFacingError(
            "The requested resource was not found.",
            error.request_id,
        )
    if status == 409:
        return UserFacingError(
            "UniAssist is temporarily busy updating documents. "
            "Please try again shortly.",
            error.request_id,
        )
    if status == 429:
        return UserFacingError(RATE_LIMIT_MESSAGE, error.request_id)
    if status == 503:
        return UserFacingError(SERVICE_UNAVAILABLE_MESSAGE, error.request_id)
    if isinstance(error, UniAssistAPIUnavailableError):
        return UserFacingError(SERVICE_UNAVAILABLE_MESSAGE, error.request_id)
    if isinstance(error, UniAssistAPIResponseError):
        return UserFacingError(SERVICE_UNAVAILABLE_MESSAGE, error.request_id)
    return UserFacingError(SERVICE_UNAVAILABLE_MESSAGE, error.request_id)
