from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import List, Optional, Dict
from vikingbot_api.utils.response import success_response, error_response, BaseResponse
from vikingbot_api.core.limiter import limiter, user_limiter
from vikingbot_api.core.openviking_client import openviking_client
import logging


router = APIRouter(prefix="/ov", tags=["openviking"])
logger = logging.getLogger(__name__)

class UserRequest(BaseModel):
    user_id: str

class MemoryItem(BaseModel):
    uri: str
    is_dir: bool
    children: Optional[List["MemoryItem"]] = None

class ListMemoryResult(BaseModel):
    data: List[MemoryItem]

class MemoryInfoRequest(BaseModel):
    user_id: str
    uri: str
    level: str  # read or abstract

class MemoryInfoResult(BaseModel):
    content: str

@router.post("/list/memory", response_model=BaseResponse[ListMemoryResult])
@limiter.limit("60/minute")
@user_limiter.limit("30/minute")
async def list_memory(request: Request, req: UserRequest):
    try:

        # Call OpenViking ls API to get user memory list
        memory_data = await openviking_client.list_user_memory(req.user_id)

        return success_response({
            "data": memory_data
        })
    except Exception as e:
        request.state.outcome = "business_error"
        logger.exception("Failed to list peer memory")
        return error_response("internal_error", str(e))

@router.post("/info/memory", response_model=BaseResponse[MemoryInfoResult])
@limiter.limit("60/minute")
@user_limiter.limit("30/minute")
async def get_memory_info(request: Request, req: MemoryInfoRequest):
    try:
        # user_id is treated as an OpenViking peer id.
        content = await openviking_client.get_memory_info(
            user_id=req.user_id,
            uri=req.uri,
            level=req.level
        )
        if content:
            content = content.replace("[Directory abstract is not ready]", "")

        return success_response({
            "content": content
        })
    except Exception as e:
        request.state.outcome = "business_error"
        logger.exception("Failed to get peer memory info")
        return error_response("internal_error", str(e))

@router.post("/delete/user", response_model=BaseResponse)
@limiter.limit("60/minute")
@user_limiter.limit("30/minute")
async def delete_user(request: Request, req: UserRequest):
    try:
        # Keep the public endpoint name for compatibility, but delete peer memory.
        await openviking_client.delete_user_memory(req.user_id)
        return success_response()
    except Exception as e:
        request.state.outcome = "business_error"
        logger.exception("Failed to delete peer memory")
        return error_response("internal_error", str(e))
