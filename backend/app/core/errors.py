"""业务码与统一错误响应。码表唯一来源是仓库根目录的 shared/error-codes.json。"""

import json
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import REPO_ROOT


@dataclass(frozen=True, slots=True)
class ErrorCode:
    name: str
    code: int
    http: int
    message: str


def _load_codes() -> dict[str, ErrorCode]:
    raw = json.loads((REPO_ROOT / "shared" / "error-codes.json").read_text(encoding="utf-8"))
    return {name: ErrorCode(name=name, **item) for name, item in raw["codes"].items()}


CODES = _load_codes()
_BY_HTTP = {c.http: c for c in reversed(CODES.values()) if c.code != 0}


def code(name: str) -> ErrorCode:
    return CODES[name]


class AppError(Exception):
    """业务异常：抛出后由全局处理器转换为 {code, message, data}。"""

    def __init__(self, name: str, message: str | None = None, data: Any = None) -> None:
        self.error = code(name)
        self.message = message or self.error.message
        self.data = data
        super().__init__(self.message)


def envelope(error: ErrorCode, message: str | None = None, data: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=error.http,
        content={"code": error.code, "message": message or error.message, "data": data},
    )


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.opt(exception=exc).error("未处理异常 {} {}", request.method, request.url.path)
    return envelope(code("INTERNAL_ERROR"))


# Starlette 的处理器签名统一收 Exception，这里按类型分派，类型不符时按未处理异常兜底
async def _app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):
        return await _unhandled_error_handler(request, exc)
    return envelope(exc.error, exc.message, exc.data)


async def _http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        return await _unhandled_error_handler(request, exc)
    return envelope(_BY_HTTP.get(exc.status_code, code("INTERNAL_ERROR")))


async def _validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        return await _unhandled_error_handler(request, exc)
    details = [{"loc": list(err.get("loc", ())), "msg": err.get("msg", "")} for err in exc.errors()]
    return envelope(code("VALIDATION_ERROR"), data=details)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
