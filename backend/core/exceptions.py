"""
Centralized exception hierarchy.

Domains raise these instead of bare `HTTPException`/`ValueError`, so
main.py's single exception handler can return one consistent JSON shape
everywhere and never leak raw internals (a stack trace, a GCS error string,
a provider's exception message) into a client response.
"""

from fastapi import status


class AppException(Exception):
    """
    Base for all application-raised errors. Carries an HTTP status and a
    stable, machine-readable `error_code` so clients can branch on it
    without parsing message text.
    """

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
        status_code: int | None = None,
    ):
        super().__init__(message)
        self.message = message
        if error_code is not None:
            self.error_code = error_code
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "not_found"


class ValidationError(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "validation_error"


class AuthError(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "auth_error"


class RateLimitedError(AppException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "rate_limited"


class ExternalServiceError(AppException):
    """
    A downstream dependency (GCS, Whisper, an LLM provider, Razorpay...)
    failed. The original exception should be logged server-side by the
    caller; only `message` — a caller-supplied, client-safe summary — ever
    reaches the response body.
    """

    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "external_service_error"
