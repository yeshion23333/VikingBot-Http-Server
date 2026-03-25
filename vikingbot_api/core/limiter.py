from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter
from asyncio import Semaphore
from fastapi import Request

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

    if path == "/api/v1/bot/chat":
        if chat_semaphore.locked():
            raise RateLimitExceeded("Chat service is busy, please try again later")
        async with chat_semaphore:
            response = await call_next(request)
    else:
        if ov_semaphore.locked():
            raise RateLimitExceeded("Service is busy, please try again later")
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
