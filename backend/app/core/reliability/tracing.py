"""
TourSafe Distributed Tracing & Correlation Context.
Maintains trace_id and correlation_id across async contexts, HTTP requests,
WebSocket events, and background worker jobs.
"""

import contextvars
import time
import uuid
from typing import Optional, Dict, Any
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from .metrics import metrics_collector

# Context Variables for Distributed Tracing
_trace_id_ctx = contextvars.ContextVar[str]("trace_id", default="")
_correlation_id_ctx = contextvars.ContextVar[str]("correlation_id", default="")
_span_name_ctx = contextvars.ContextVar[str]("span_name", default="root")


def get_current_trace_id() -> str:
    """Return the active distributed trace ID or generate a default one."""
    tid = _trace_id_ctx.get()
    if not tid:
        tid = f"trc-{uuid.uuid4().hex[:16]}"
        _trace_id_ctx.set(tid)
    return tid


def get_current_correlation_id() -> str:
    """Return the active correlation ID or generate a default one."""
    cid = _correlation_id_ctx.get()
    if not cid:
        cid = f"cor-{uuid.uuid4().hex[:16]}"
        _correlation_id_ctx.set(cid)
    return cid


def set_trace_context(trace_id: Optional[str] = None, correlation_id: Optional[str] = None) -> Dict[str, str]:
    """Set trace and correlation IDs for the current async task context."""
    tid = trace_id or f"trc-{uuid.uuid4().hex[:16]}"
    cid = correlation_id or f"cor-{uuid.uuid4().hex[:16]}"
    _trace_id_ctx.set(tid)
    _correlation_id_ctx.set(cid)
    return {"trace_id": tid, "correlation_id": cid}


class trace_context:
    """Context manager for tracing discrete sub-operations (spans)."""

    def __init__(self, operation_name: str, span_type: str = "internal"):
        self.operation_name = operation_name
        self.span_type = span_type
        self.start_time = 0.0
        self.token = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        self.token = _span_name_ctx.set(self.operation_name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        if self.token:
            _span_name_ctx.reset(self.token)
        if exc_type is not None:
            metrics_collector.golden.record_dependency_error()


class TracingMiddleware(BaseHTTPMiddleware):
    """
    FastAPI Middleware:
    1. Extracts or injects X-Trace-ID and X-Correlation-ID.
    2. Times the HTTP request execution.
    3. Records latency and status codes to GoldenSignals metrics.
    4. Attaches correlation headers to the response.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = request.headers.get("X-Trace-ID") or request.headers.get("traceparent")
        correlation_id = request.headers.get("X-Correlation-ID") or request.headers.get("X-Request-ID")
        
        set_trace_context(trace_id=trace_id, correlation_id=correlation_id)
        
        start_time = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            metrics_collector.golden.record_dependency_error()
            raise e
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            # Don't skew metrics with raw Prometheus polling or basic live probes
            if not request.url.path.endswith(("/metrics", "/health/live")):
                metrics_collector.golden.record_request(status_code, duration_ms)

        response.headers["X-Trace-ID"] = get_current_trace_id()
        response.headers["X-Correlation-ID"] = get_current_correlation_id()
        response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"
        return response
