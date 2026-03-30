import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel

from vikingbot_api.core.config import get_config
from vikingbot_api.core.limiter import limiter, user_limiter
from vikingbot_api.core.openviking_client import openviking_client
from vikingbot_api.utils.response import success_response, error_response, BaseResponse

router = APIRouter(prefix="/bot", tags=["bot"])

# Bot API configuration
def get_bot_api_url() -> str:
    base_url = get_config("openviking.base_url", "http://localhost:1933")
    return f"{base_url.rstrip('/')}/bot/v1/chat"

class ChatRequest(BaseModel):
    user_id: str
    query: str

class ChatResult(BaseModel):
    text: str

# Create a global httpx client
_bot_client = httpx.AsyncClient(timeout=60.0)

@router.post("/chat", response_model=BaseResponse[ChatResult])
@limiter.limit("60/minute")
@user_limiter.limit("30/minute")
async def chat(request: Request, chat_request: ChatRequest):
    try:
        # Ensure user exists in OpenViking, register if not
        await openviking_client.ensure_user_exists(chat_request.user_id)

        # Generate session_id if not provided, use user_id + uuid
        session_id = f"playground_default_{chat_request.user_id}"

        # Call bot API via HTTP
        bot_request = {
            "message": chat_request.query,
            "session_id": session_id,
            "user_id": chat_request.user_id,
            "stream": False
        }

        response = await _bot_client.post(
            get_bot_api_url(),
            json=bot_request,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        bot_response = response.json()

        # Extract the message from bot response
        response_text = bot_response.get("message", "抱歉，暂时无法处理您的问题，请稍后重试")

        return success_response({
            "text": response_text
        })
    except httpx.HTTPError as e:
        return error_response("internal_error", f"Bot API request failed: {str(e)}")
    except Exception as e:
        return error_response("internal_error", str(e))
