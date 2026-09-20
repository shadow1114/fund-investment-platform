from __future__ import annotations

from typing import Any

ERROR_CODES: dict[str, tuple[int, bool]] = {
    "VALIDATION_ERROR": (422, False),
    "UNAUTHENTICATED": (401, False),
    "FORBIDDEN": (403, False),
    "NOT_FOUND": (404, False),
    "RESOURCE_NOT_FOUND": (404, False),
    "CONFLICT": (409, False),
    "BUSINESS_RULE_VIOLATION": (422, False),
    "SERVICE_UNAVAILABLE": (503, True),
    "RATE_LIMITED": (429, True),
}


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


class ServiceUnavailableError(ApiError):
    def __init__(self, message: str = "Service is temporarily unavailable") -> None:
        super().__init__(503, "SERVICE_UNAVAILABLE", message)


class RateLimitedError(ApiError):
    def __init__(self, retry_after: int) -> None:
        super().__init__(
            429,
            "RATE_LIMITED",
            "Request rate limit exceeded",
            {"retry_after": retry_after},
        )


class NotFoundError(ApiError):
    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(404, "NOT_FOUND", f"{resource} '{identifier}' was not found")


class ForbiddenError(ApiError):
    def __init__(self, message: str = "The current user is not authorized") -> None:
        super().__init__(403, "FORBIDDEN", message)


class AuthenticationError(ApiError):
    def __init__(self, message: str = "Authentication is required") -> None:
        super().__init__(401, "UNAUTHENTICATED", message)


class ConflictError(ApiError):
    def __init__(self, message: str, details: Any | None = None) -> None:
        super().__init__(409, "CONFLICT", message, details)


class InvalidQueryError(ApiError):
    def __init__(self, message: str) -> None:
        super().__init__(422, "VALIDATION_ERROR", message)
