import logging
import re
import time
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.error_handlers import error_response, register_error_handlers
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import get_engine

logger = logging.getLogger("app.request")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(
        title="StockPilot API",
        version="1.0.0",
        description="Multi-workspace inventory and order management.",
    )

    register_error_handlers(app)

    @app.middleware("http")
    async def request_context(request: Request, call_next) -> Response:
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if _REQUEST_ID.match(incoming) else uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001 - last-resort handler; details go to the log, not the client
            logger.exception("unhandled error request_id=%s %s %s", request_id, request.method, request.url.path)
            response = error_response(request, 500, "INTERNAL_ERROR", "An unexpected error occurred")
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        logger.info(
            "request_id=%s %s %s -> %s (%.1f ms)",
            request_id,
            request.method,
            request.url.path,  # path only: query strings are not logged
            response.status_code,
            (time.perf_counter() - started) * 1000,
        )
        return response

    # Added last => outermost, so CORS headers are present on every response (including errors).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
        allow_credentials=False,  # bearer-token auth: no cookies are used cross-site
        max_age=600,
    )

    @app.get("/health", tags=["health"])
    def health() -> JSONResponse:
        """Liveness + database connectivity."""
        try:
            with get_engine().connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception:  # noqa: BLE001
            logger.exception("health check: database unreachable")
            return JSONResponse(status_code=503, content={"status": "unavailable", "database": "down"})
        return JSONResponse(content={"status": "ok", "database": "up"})

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
