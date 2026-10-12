"""Application errors. Every error is rendered as {"error": {"code", "message", "details"}}."""

from typing import Any


class AppError(Exception):
    status_code = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str, *, code: str | None = None, details: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.details = details or []


class UnauthorizedError(AppError):
    status_code = 401
    code = "UNAUTHORIZED"


class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(AppError):
    """The request is valid but conflicts with the current state of the resource."""

    status_code = 409
    code = "CONFLICT"


class ValidationFailedError(AppError):
    """The request is well-formed but violates a business/input rule."""

    status_code = 422
    code = "VALIDATION_ERROR"
