from fastapi import Request, HTTPException
from starlette.responses import JSONResponse

from vikingbot_api.core.security import (
    decrypt_auth_token,
    get_auth_encryption_key,
)
from vikingbot_api.utils.response import error_response

PUBLIC_PATHS = {"/health", "/metrics"}


def _unauthorized_response(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content=error_response("unauthorized", message).model_dump(),
    )


def decrypt_token(encrypted_data: str) -> str:
    encryption_key = get_auth_encryption_key()
    try:
        return decrypt_auth_token(encrypted_data, encryption_key)
    except Exception as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token",
        ) from exc


async def auth_middleware(request: Request, call_next):
    # Health checks and Prometheus scrapes must work without an API token.
    if (
        request.method == "OPTIONS"
        or request.url.path.rstrip("/") in PUBLIC_PATHS
    ):
        return await call_next(request)

    auth_key = request.headers.get("X-OpenViking-Bot-Key")
    if not auth_key:
        return _unauthorized_response("X-OpenViking-Bot-Key header is required")

    try:
        decrypted = decrypt_token(auth_key)
    except HTTPException as exc:
        return _unauthorized_response(str(exc.detail))

    if decrypted != "ov-chat":
        return _unauthorized_response("Invalid authentication token")

    response = await call_next(request)
    return response
