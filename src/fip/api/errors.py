from __future__ import annotations

from typing import Any


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


class NotFoundError(ApiError):
    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(404, "NOT_FOUND", f"{resource} '{identifier}' was not found")


class ForbiddenError(ApiError):
    def __init__(self, message: str = "The current user is not authorized") -> None:
        super().__init__(403, "FORBIDDEN", message)


class ConflictError(ApiError):
    def __init__(self, message: str, details: Any | None = None) -> None:
        super().__init__(409, "CONFLICT", message, details)


class InvalidQueryError(ApiError):
    def __init__(self, message: str) -> None:
        super().__init__(422, "VALIDATION_ERROR", message)
