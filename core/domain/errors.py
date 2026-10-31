"""Domain errors with stable API error codes."""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """A rejected command or query, modeled as a stable API error.

    `code` is part of the FE/AI contract; do not rename it casually.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 409,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }
