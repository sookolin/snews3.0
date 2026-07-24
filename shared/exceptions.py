"""Domain exceptions with structured HTTP mapping."""

from __future__ import annotations


class AppError(Exception):
    """Base application error.

    Attributes:
        message: Human readable message.
        status_code: HTTP status the API layer should return.
        code: Stable machine readable error code.
    """

    status_code: int = 400
    code: str = "app_error"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class AuthenticationError(AppError):
    status_code = 401
    code = "authentication_error"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "permission_denied"


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limited"


class ExternalServiceError(AppError):
    status_code = 502
    code = "external_service_error"


class ParserError(ExternalServiceError):
    code = "parser_error"


class AIProviderError(ExternalServiceError):
    code = "ai_provider_error"


class PublishError(ExternalServiceError):
    code = "publish_error"
