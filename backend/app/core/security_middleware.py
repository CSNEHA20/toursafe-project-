"""
TourSafe Defense-in-Depth Security Middleware.
Provides:
1. HTTP Security Headers (HSTS, CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy)
2. Request Correlation ID Generation and Tracking (X-Correlation-ID)
3. Request Body Size Protection
4. Safe Error Handling and Information Leakage Prevention
"""

import logging
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger("toursafe.security.middleware")

MAX_BODY_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit


class SecurityHeadersAndCorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 1. Correlation ID
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        # 2. Content Length limit check
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_SIZE_BYTES:
            return JSONResponse(
                status_code=413,
                content={
                    "detail": "Request payload exceeds maximum allowed size limit of 10MB.",
                    "correlation_id": correlation_id,
                },
                headers={"X-Correlation-ID": correlation_id},
            )

        # 3. Process request
        try:
            response = await call_next(request)
        except Exception as exc:
            # Internal server error without leaking stack traces
            logger.error(
                "Unhandled server exception [correlation_id=%s]: %s",
                correlation_id,
                str(exc),
                exc_info=True,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "An internal server error occurred. Please contact support with the correlation ID.",
                    "correlation_id": correlation_id,
                },
                headers={"X-Correlation-ID": correlation_id},
            )

        # 4. Attach Security Headers
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self';"
        )
        response.headers["Permissions-Policy"] = "geolocation=(self), camera=(), microphone=()"

        return response
