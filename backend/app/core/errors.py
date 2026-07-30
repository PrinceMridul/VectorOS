"""Domain errors.

Note :class:`PedagogicalViolation` — it is not an HTTP concern, it is the
system refusing to break its own teaching contract (e.g. an attempt submitted
without a committed confidence, or a scaffold level that tried to skip a rung).
Surfacing these as a distinct class keeps guardrail failures loud.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

log = get_logger(__name__)


class VectorOSError(Exception):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "vectoros_error"

    def __init__(self, message: str, **context: object) -> None:
        super().__init__(message)
        self.message = message
        self.context = context


class NotFound(VectorOSError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class Unauthorized(VectorOSError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"


class PedagogicalViolation(VectorOSError):
    """The request would have broken a learning invariant. Refuse it."""

    status_code = status.HTTP_409_CONFLICT
    code = "pedagogical_violation"


class ProviderError(VectorOSError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "provider_error"


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(VectorOSError)
    async def _handle(_: Request, exc: VectorOSError) -> JSONResponse:
        if isinstance(exc, PedagogicalViolation):
            log.warning("pedagogical_violation", message=exc.message, **exc.context)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, **exc.context}},
        )
