import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from slowapi.errors import RateLimitExceeded
from starlette.responses import JSONResponse

from vikingbot_api.core.auth import auth_middleware
from vikingbot_api.core.limiter import limiter, user_limiter, concurrency_limiter
from vikingbot_api.core.config import get_config
from vikingbot_api.utils.response import error_response
from vikingbot_api.api.v1.bot import router as bot_router
from vikingbot_api.api.v1.ov import router as ov_router

logger = logging.getLogger(__name__)

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
)

# Add rate limiter to app
app.state.limiter = limiter
app.state.user_limiter = user_limiter
app.add_exception_handler(RateLimitExceeded, lambda request, exc: JSONResponse(
    status_code=429,
    content=error_response("limit_error", "Rate limit exceeded, please try again later").dict()
))

# Add validation error handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content=error_response("invalid_params", "Invalid request parameters").dict()
    )

# Add middleware
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")


    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        return response
    except Exception as e:
        process_time = (time.time() - start_time) * 1000
        logger.error(f"Request failed: {request.method} {request.url.path} - Error: {str(e)} - Duration: {process_time:.2f}ms")
        raise

@app.middleware("http")
async def auth_middleware_wrapper(request: Request, call_next):
    return await auth_middleware(request, call_next)

@app.middleware("http")
async def concurrency_middleware_wrapper(request: Request, call_next):
    return await concurrency_limiter(request, call_next)

# Register routes
api_prefix = "/api/v1"
app.include_router(bot_router, prefix=api_prefix)
app.include_router(ov_router, prefix=api_prefix)

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Vikingbot API is running"}

if __name__ == "__main__":
    import uvicorn
    host = get_config("server.host", "0.0.0.0")
    port = get_config("server.port", 1995)
    uvicorn.run("vikingbot_api.main:app", host=host, port=port, reload=True)
