"""全局异常处理器：把校验错误、HTTPException 与未捕获异常统一为 ErrorResponse 结构。

所有错误响应都遵循 ``{error_code, message, details}`` 三字段，
前端据此展示中文提示并按错误码做差异化处理（如 404 停止轮询）。
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from harness.logger import logger

# HTTP 状态码到业务错误码的兜底映射，仅用于未显式给出 error_code 的 HTTPException
_STATUS_CODE_MAP = {
    400: "INVALID_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "TOO_MANY_REQUESTS",
    502: "UPSTREAM_ERROR",
    503: "SERVICE_UNAVAILABLE",
}

_VALIDATION_MESSAGE = "请求参数校验失败"
_INTERNAL_MESSAGE = "服务器内部错误，请稍后重试"


def _status_to_code(status_code: int) -> str:
    """把 HTTP 状态码映射为业务错误码，5xx 统一视为内部错误。"""
    if status_code >= 500 and status_code not in _STATUS_CODE_MAP:
        return "INTERNAL_ERROR"
    return _STATUS_CODE_MAP.get(
        status_code, "INTERNAL_ERROR" if status_code >= 500 else "REQUEST_FAILED"
    )


def _error_response(
    status_code: int,
    error_code: str,
    message: str,
    details: str | None = None,
    headers: dict | None = None,
) -> JSONResponse:
    """构造统一错误响应体，供各处理器复用。"""
    return JSONResponse(
        status_code=status_code,
        content={"error_code": error_code, "message": message, "details": details},
        headers=headers,
    )


def _format_validation_errors(errors: list[dict]) -> str:
    """把 Pydantic 校验错误压缩成一行可读文本，避免前端展示整段 JSON。"""
    parts: list[str] = []
    for error in errors:
        location = ".".join(
            str(item) for item in error.get("loc", ()) if item not in ("body", "query", "path")
        )
        message = error.get("msg") or "字段无效"
        parts.append(f"{location}: {message}" if location else message)
    return "; ".join(parts)[:500]


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """把 FastAPI 默认的 422 结构改写为统一错误体。"""
    details = _format_validation_errors(exc.errors())
    logger.warning(f"[API] 请求参数校验失败: {request.method} {request.url.path}, {details}")
    return _error_response(422, "VALIDATION_ERROR", _VALIDATION_MESSAGE, details)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """兼容两种 detail：控制器已构造好的错误体直接透传，字符串则补充错误码。"""
    detail = exc.detail
    if isinstance(detail, dict) and "error_code" in detail:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": detail.get("error_code"),
                "message": detail.get("message") or _INTERNAL_MESSAGE,
                "details": detail.get("details"),
            },
            headers=exc.headers,
        )

    message = detail if isinstance(detail, str) and detail else "请求处理失败"
    logger.info(
        f"[API] HTTPException: {request.method} {request.url.path} -> {exc.status_code}, {message}"
    )
    return _error_response(
        exc.status_code, _status_to_code(exc.status_code), message, None, exc.headers
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底未捕获异常：记录完整堆栈，但不把内部错误细节回传给客户端。"""
    logger.exception(f"[API] 未捕获异常: {request.method} {request.url.path}, {exc}")
    return _error_response(500, "INTERNAL_ERROR", _INTERNAL_MESSAGE)


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器，需在应用创建后、启动前调用。"""
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
