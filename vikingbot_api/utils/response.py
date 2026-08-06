from pydantic import BaseModel
from typing import Generic, TypeVar, Optional, Dict, List, Any

T = TypeVar('T')

class BaseResponse(BaseModel, Generic[T]):
    status: str = "ok"
    err_code: str = ""
    err_msg: str = ""
    request_id: str = ""
    error_type: str = ""
    result: Optional[T] = None

def success_response(data: Any = None, request_id: str = "") -> BaseResponse:
    return BaseResponse(
        status="ok",
        err_code="",
        err_msg="",
        request_id=request_id,
        error_type="",
        result=data
    )

def error_response(
    err_code: str,
    err_msg: str,
    request_id: str = "",
    error_type: str = "",
) -> BaseResponse:
    return BaseResponse(
        status="error",
        err_code=err_code,
        err_msg=err_msg,
        request_id=request_id,
        error_type=error_type,
        result=None
    )
