from fastapi import APIRouter, Request
from pip._internal import req
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
        # Check if user exists
        user_exists = await openviking_client.check_user_exists(req.user_id)
        logger.info(f"Checking user {req.user_id} exists: {user_exists}")

        if not user_exists:
            # Return empty structure if user doesn't exist
            empty_data = [
                {
                    "uri": "/entities",
                    "is_dir": True,
                    "children": []
                },
                {
                    "uri": "/events",
                    "is_dir": True,
                    "children": []
                },
                {
                    "uri": "/preferences",
                    "is_dir": True,
                    "children": []
                }
            ]
            return success_response({
                "data": empty_data
            })

        # Call OpenViking ls API to get user memory list
        memory_data = await openviking_client.list_user_memory(req.user_id)

        return success_response({
            "data": memory_data
        })
    except Exception as e:
        return error_response("internal_error", str(e))

@router.post("/info/memory", response_model=BaseResponse[MemoryInfoResult])
@limiter.limit("60/minute")
@user_limiter.limit("30/minute")
async def get_memory_info(request: Request, req: MemoryInfoRequest):
    try:
        # Check if user exists
        user_exists = await openviking_client.check_user_exists(req.user_id)
        if not user_exists:
            # Return empty content if user doesn't exist
            return success_response({
                "content": ""
            })

        # Call OpenViking read API to get memory content
        content = await openviking_client.get_memory_info(
            user_id=req.user_id,
            uri=req.uri,
            level=req.level
        )

        return success_response({
            "content": content
        })
    except Exception as e:
        return error_response("internal_error", str(e))

@router.post("/delete/user", response_model=BaseResponse)
@limiter.limit("60/minute")
@user_limiter.limit("30/minute")
async def delete_user(request: Request, req: UserRequest):
    try:
        # Check if user exists
        user_exists = await openviking_client.check_user_exists(req.user_id)
        if not user_exists:
            # Return success directly if user doesn't exist
            return success_response()

        # Call OpenViking rm API to delete user memory
        await openviking_client.delete_user_memory(req.user_id)
        return success_response()
    except Exception as e:
        return error_response("internal_error", str(e))
