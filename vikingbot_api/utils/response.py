from pydantic import BaseModel
from typing import Generic, TypeVar, Optional, Dict, List, Any

T = TypeVar('T')

class BaseResponse(BaseModel, Generic[T]):
    status: str = "ok"
    err_code: str = ""
    err_msg: str = ""
    result: Optional[T] = None

def success_response(data: Any = None) -> BaseResponse:
    return BaseResponse(
        status="ok",
        err_code="",
        err_msg="",
        result=data
    )

def error_response(err_code: str, err_msg: str) -> BaseResponse:
    return BaseResponse(
        status="error",
        err_code=err_code,
        err_msg=err_msg,
        result=None
    )
