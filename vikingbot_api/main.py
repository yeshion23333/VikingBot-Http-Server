import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from prometheus_client import make_asgi_app
from slowapi.errors import RateLimitExceeded
from starlette.responses import JSONResponse

from vikingbot_api.core.auth import auth_middleware
from vikingbot_api.core.limiter import limiter, user_limiter, concurrency_limiter
from vikingbot_api.core.metrics import record_request_metrics
from vikingbot_api.core.config import get_config
from vikingbot_api.utils.response import error_response
from vikingbot_api.api.v1.bot import router as bot_router
from vikingbot_api.api.v1.ov import router as ov_router

logger = logging.getLogger(__name__)
REQUEST_ID_HEADERS = (
    "x-request-id",
    "x-faas-request-id",
    "x-bytefaas-request-id",
    "x-tt-logid",
    "x-bd-trace-id",
)


def _get_or_create_request_id(request: Request) -> str:
    for header_name in REQUEST_ID_HEADERS:
        value = request.headers.get(header_name, "").strip()
        if value:
            # Prevent untrusted headers from injecting extra log lines.
            safe_value = "".join(
                character
                for character in value
                if character.isalnum() or character in "-_.:"
            )
            if safe_value:
                return safe_value[:128]
    return str(uuid4())

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    log_level = get_config("server.log_level", "INFO").upper()
    log_level_enum = getattr(logging, log_level)

    logging.basicConfig(
        level=log_level_enum,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler()
        ],
        force=True  # Force override existing logging configuration
    )

    # Ensure all vikingbot_api modules have correct log level
    logging.getLogger("vikingbot_api").setLevel(log_level_enum)
    logging.getLogger("vikingbot_api.core").setLevel(log_level_enum)
    logging.getLogger("vikingbot_api.api").setLevel(log_level_enum)

    yield  # Application runs here

    # Shutdown code (if needed)
    logger.info("Application shutting down")

app = FastAPI(
    title="Vikingbot API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# Add rate limiter to app
app.state.limiter = limiter
app.state.user_limiter = user_limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded):
    request.state.error_type = "rate_limit_error"
    return JSONResponse(
        status_code=429,
        content=error_response(
            "limit_error",
            "Rate limit exceeded, please try again later",
            request_id=str(getattr(request.state, "request_id", "")),
            error_type="rate_limit_error",
        ).model_dump(),
    )

# Add validation error handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request.state.error_type = "validation_error"
    return JSONResponse(
        status_code=400,
        content=error_response(
            "invalid_params",
            "Invalid request parameters",
            request_id=str(getattr(request.state, "request_id", "")),
            error_type="validation_error",
        ).model_dump(),
    )

# Add middleware
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    start_time = time.time()

    try:
        response = await call_next(request)
        return response
    except Exception as e:
        process_time = (time.time() - start_time) * 1000
        logger.exception(
            "Request failed request_id=%s method=%s path=%s "
            "exception_type=%s error=%r duration_ms=%.2f",
            getattr(request.state, "request_id", "unknown"),
            request.method,
            request.url.path,
            type(e).__name__,
            str(e),
            process_time,
        )
        raise

@app.middleware("http")
async def auth_middleware_wrapper(request: Request, call_next):
    return await auth_middleware(request, call_next)

@app.middleware("http")
async def concurrency_middleware_wrapper(request: Request, call_next):
    return await concurrency_limiter(request, call_next)


@app.middleware("http")
async def prometheus_metrics_middleware(request: Request, call_next):
    return await record_request_metrics(request, call_next)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = _get_or_create_request_id(request)
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# Register routes
api_prefix = "/api/v1"
app.include_router(bot_router, prefix=api_prefix)
app.include_router(ov_router, prefix=api_prefix)
app.mount("/metrics", make_asgi_app())

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Vikingbot API is running"}

if __name__ == "__main__":
    import uvicorn
    host = get_config("server.host", "0.0.0.0")
    port = get_config("server.port", 8000)

    # SSL configuration
    ssl_enabled = get_config("server.ssl.enabled", False)
    ssl_certfile = get_config("server.ssl.cert_file", None) if ssl_enabled else None
    ssl_keyfile = get_config("server.ssl.key_file", None) if ssl_enabled else None

    # FaaS 环境不使用 reload，避免子进程导入问题
    uvicorn.run(
        "vikingbot_api.main:app",
        host=host,
        port=port,
        reload=False,
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile
    )
