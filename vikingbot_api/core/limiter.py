from slowapi import Limiter
from slowapi.util import get_remote_address
from asyncio import Semaphore
from fastapi import Request
from starlette.responses import JSONResponse

from vikingbot_api.utils.response import error_response


PUBLIC_PATHS = {"/health", "/metrics"}

# Rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
)

# Concurrency limiters
chat_semaphore = Semaphore(5)
ov_semaphore = Semaphore(10)


async def concurrency_limiter(request: Request, call_next):
    path = request.url.path

    if path.rstrip("/") in PUBLIC_PATHS:
        return await call_next(request)

    if path == "/api/v1/bot/chat":
        if chat_semaphore.locked():
            return JSONResponse(
                status_code=429,
                content=error_response(
                    "limit_error",
                    "Chat service is busy, please try again later",
                ).model_dump(),
            )
        async with chat_semaphore:
            response = await call_next(request)
    else:
        if ov_semaphore.locked():
            return JSONResponse(
                status_code=429,
                content=error_response(
                    "limit_error",
                    "Service is busy, please try again later",
                ).model_dump(),
            )
        async with ov_semaphore:
            response = await call_next(request)

    return response

# Per user rate limit
def get_user_id(request: Request):
    try:
        body = request.json()
        return body.get("user_id", get_remote_address(request))
    except:
        return get_remote_address(request)


user_limiter = Limiter(
    key_func=get_user_id,
    storage_uri="memory://",
)
