"""Domain error hierarchy.

Every error raised by the application is a subclass of
:class:`AppError`. The API layer maps these to HTTP responses; nothing
outside the API layer should raise raw ``HTTPException``.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for all application errors.

    Attributes:
        message: Human-readable description, safe to show to the user.
        code: Stable machine-readable identifier (e.g. ``asset.not_found``).
        http_status: Default HTTP status code when surfaced via the API.
    """

    code: str = "app.error"
    http_status: int = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    """A referenced resource does not exist."""

    code = "resource.not_found"
    http_status = 404


class ValidationError(AppError):
    """The caller supplied data that fails domain validation."""

    code = "validation.failed"
    http_status = 422


class ExternalServiceError(AppError):
    """A downstream service (Anthropic, MinIO, FFmpeg) failed."""

    code = "external.failed"
    http_status = 502


class AssetNotFoundError(NotFoundError):
    """An EDL or operation references an asset that is missing."""

    code = "asset.not_found"
