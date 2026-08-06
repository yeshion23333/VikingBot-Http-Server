import time

from fastapi import Request
from prometheus_client import Counter, Gauge, Histogram


HTTP_REQUESTS = Counter(
    "vikingbot_http_requests_total",
    "Total number of HTTP requests",
    [
        "method",
        "route",
        "status_code",
        "outcome",
        "error_type",
        "upstream_status_code",
    ],
)

HTTP_REQUEST_DURATION = Histogram(
    "vikingbot_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "route"],
    buckets=(0.01, 0.05, 0.1, 0.3, 0.5, 1, 3, 5, 10, 30, 60),
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "vikingbot_http_requests_in_progress",
    "Number of HTTP requests currently being processed",
    ["method"],
)

KNOWN_ROUTE_TEMPLATES = {
    "/health",
    "/api/v1/bot/chat",
    "/api/v1/ov/list/memory",
    "/api/v1/ov/info/memory",
    "/api/v1/ov/delete/user",
}


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    if route is not None:
        return getattr(route, "path", "unmatched")

    # Authentication and concurrency middleware may return before routing.
    # Only use known static paths here to avoid high-cardinality labels.
    path = request.url.path.rstrip("/")
    if path in KNOWN_ROUTE_TEMPLATES:
        return path
    return "unmatched"


async def record_request_metrics(request: Request, call_next):
    # Avoid recording Prometheus scrapes as application traffic.
    if request.url.path.rstrip("/") == "/metrics":
        return await call_next(request)

    method = request.method
    started_at = time.perf_counter()
    status_code = 500
    HTTP_REQUESTS_IN_PROGRESS.labels(method=method).inc()

    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        outcome = getattr(request.state, "outcome", None)
        if outcome is None:
            if status_code >= 500:
                outcome = "server_error"
            elif status_code >= 400:
                outcome = "client_error"
            else:
                outcome = "success"

        error_type = getattr(request.state, "error_type", None)
        if not error_type:
            error_type = "none" if outcome == "success" else outcome
        upstream_status_code = str(
            getattr(request.state, "upstream_status_code", "none") or "none"
        )

        route = _route_template(request)
        HTTP_REQUESTS.labels(
            method=method,
            route=route,
            status_code=str(status_code),
            outcome=outcome,
            error_type=error_type,
            upstream_status_code=upstream_status_code,
        ).inc()
        HTTP_REQUEST_DURATION.labels(
            method=method,
            route=route,
        ).observe(time.perf_counter() - started_at)
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method).dec()
