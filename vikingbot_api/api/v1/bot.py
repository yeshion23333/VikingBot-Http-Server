import httpx
import logging
from fastapi import APIRouter, Request
from pydantic import BaseModel

from vikingbot_api.core.config import get_config
from vikingbot_api.core.limiter import limiter, user_limiter
from vikingbot_api.utils.response import success_response, error_response, BaseResponse

router = APIRouter(prefix="/bot", tags=["bot"])
logger = logging.getLogger(__name__)
MAX_UPSTREAM_ERROR_BODY_CHARS = 2048

# Bot API configuration
def get_bot_api_url() -> str:
    base_url = get_config("openviking.base_url", "http://localhost:1933")
    return f"{base_url.rstrip('/')}/bot/v1/chat"

class ChatRequest(BaseModel):
    user_id: str
    query: str

class ChatResult(BaseModel):
    text: str

# Chat responses may include model inference and memory retrieval, so they need a
# much longer read timeout than ordinary API calls. Keep connection/write/pool
# timeouts short so unreachable or overloaded upstreams still fail promptly.
_bot_client = httpx.AsyncClient(
    timeout=httpx.Timeout(
        connect=10.0,
        read=float(get_config("openviking.chat_timeout_seconds", 600.0)),
        write=30.0,
        pool=30.0,
    )
)


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "") or "unknown")


def _truncate_response_body(response: httpx.Response | None) -> str:
    if response is None:
        return ""
    try:
        body = response.text
    except Exception:
        return "<unavailable>"

    # Keep log entries single-line and bounded. The complete upstream body must
    # never become a Prometheus label.
    return (
        body[:MAX_UPSTREAM_ERROR_BODY_CHARS]
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )[:MAX_UPSTREAM_ERROR_BODY_CHARS]


def _classify_http_error(exc: httpx.HTTPError) -> tuple[str, str, str]:
    upstream_status_code = "none"
    upstream_body = ""

    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        upstream_status_code = str(status_code)
        upstream_body = _truncate_response_body(exc.response)
        if 400 <= status_code < 500:
            error_type = "upstream_http_4xx"
        elif status_code >= 500:
            error_type = "upstream_http_5xx"
        else:
            error_type = "upstream_http_status_error"
    elif isinstance(exc, httpx.ReadTimeout):
        error_type = "upstream_read_timeout"
    elif isinstance(exc, httpx.ConnectTimeout):
        error_type = "upstream_connect_timeout"
    elif isinstance(exc, httpx.WriteTimeout):
        error_type = "upstream_write_timeout"
    elif isinstance(exc, httpx.PoolTimeout):
        error_type = "upstream_pool_timeout"
    elif isinstance(exc, httpx.TimeoutException):
        error_type = "upstream_timeout"
    elif isinstance(exc, httpx.ConnectError):
        error_type = "upstream_connect_error"
    elif isinstance(exc, httpx.RemoteProtocolError):
        error_type = "upstream_protocol_error"
    else:
        error_type = "upstream_http_error"

    return error_type, upstream_status_code, upstream_body


def _set_error_metrics_context(
    request: Request,
    error_type: str,
    upstream_status_code: str = "none",
) -> None:
    request.state.outcome = "business_error"
    request.state.error_type = error_type
    request.state.upstream_status_code = upstream_status_code

@router.post("/chat", response_model=BaseResponse[ChatResult])
@limiter.limit("60/minute")
@user_limiter.limit("30/minute")
async def chat(request: Request, chat_request: ChatRequest):
    request_id = _request_id(request)
    try:
        # Current OpenViking treats the external user_id as a peer id.
        # A peer does not need to be pre-created as an OpenViking user.
        session_id = f"playground_default_{chat_request.user_id}"

        # Call bot API via HTTP
        bot_request = {
            "message": chat_request.query,
            "session_id": session_id,
            "user_id": chat_request.user_id,
            "stream": False,
        }

        response = await _bot_client.post(
            get_bot_api_url(),
            json=bot_request,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": get_config("openviking.api_key", ""),
                "X-OpenViking-Actor-Peer": chat_request.user_id,
            }
        )
        response.raise_for_status()
        try:
            bot_response = response.json()
        except ValueError as exc:
            error_type = "upstream_invalid_json"
            _set_error_metrics_context(
                request,
                error_type,
                str(response.status_code),
            )
            logger.exception(
                "Invalid Bot API response request_id=%s exception_type=%s "
                "error_type=%s upstream_status_code=%s upstream_body=%r",
                request_id,
                type(exc).__name__,
                error_type,
                response.status_code,
                _truncate_response_body(response),
            )
            return error_response(
                "internal_error",
                "Bot API returned an invalid JSON response",
                request_id=request_id,
                error_type=error_type,
            )

        if not isinstance(bot_response, dict):
            error_type = "upstream_invalid_response"
            _set_error_metrics_context(
                request,
                error_type,
                str(response.status_code),
            )
            logger.error(
                "Invalid Bot API response shape request_id=%s "
                "exception_type=InvalidResponseShape error_type=%s "
                "upstream_status_code=%s upstream_body=%r",
                request_id,
                error_type,
                response.status_code,
                _truncate_response_body(response),
            )
            return error_response(
                "internal_error",
                "Bot API returned an invalid response",
                request_id=request_id,
                error_type=error_type,
            )

        # Extract the message from bot response
        response_text = bot_response.get("message", "抱歉，暂时无法处理您的问题，请稍后重试")

        return success_response(
            {"text": response_text},
            request_id=request_id,
        )
    except httpx.HTTPError as e:
        error_type, upstream_status_code, upstream_body = _classify_http_error(e)
        _set_error_metrics_context(request, error_type, upstream_status_code)
        logger.exception(
            "Bot API request failed request_id=%s exception_type=%s "
            "error_type=%s upstream_status_code=%s upstream_body=%r",
            request_id,
            type(e).__name__,
            error_type,
            upstream_status_code,
            upstream_body,
        )
        return error_response(
            "internal_error",
            "Bot API request failed",
            request_id=request_id,
            error_type=error_type,
        )
    except Exception as e:
        error_type = "unexpected_chat_error"
        _set_error_metrics_context(request, error_type)
        logger.exception(
            "Unexpected chat error request_id=%s exception_type=%s "
            "error_type=%s upstream_status_code=none upstream_body=''",
            request_id,
            type(e).__name__,
            error_type,
        )
        return error_response(
            "internal_error",
            "Unexpected chat error",
            request_id=request_id,
            error_type=error_type,
        )
