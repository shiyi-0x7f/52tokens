"""统一成功响应：{code: 0, message, data}。"""

from pydantic import BaseModel


class ApiResponse[T](BaseModel):
    code: int = 0
    message: str = "成功"
    data: T | None = None


def ok[T](data: T) -> ApiResponse[T]:
    return ApiResponse[T](data=data)
