from fastapi import APIRouter, Request
from pydantic import BaseModel
from vikingbot_api.utils.response import success_response, error_response, BaseResponse
from vikingbot_api.core.limiter import limiter, user_limiter
from vikingbot_api.core.openviking_client import openviking_client

router = APIRouter(prefix="/bot", tags=["bot"])

class ChatRequest(BaseModel):
    user_id: str
    query: str

class ChatResult(BaseModel):
    text: str

@router.post("/chat", response_model=BaseResponse[ChatResult])
@limiter.limit("60/minute")
@user_limiter.limit("30/minute")
async def chat(request: Request, chat_request: ChatRequest):
    try:
        # Ensure user exists in OpenViking, register if not
        await openviking_client.ensure_user_exists(chat_request.user_id)

        # TODO: Integrate with actual vikingbot chat implementation
        # For now, return mock response
        response_text = f"收到您的消息：{chat_request.query}。这是来自Vikingbot的回复。"

        return success_response({
            "text": response_text
        })
    except Exception as e:
        return error_response("internal_error", str(e))
