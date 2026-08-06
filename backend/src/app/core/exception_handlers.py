from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.exceptions import AppException
from app.core.logging import get_logger

logger = get_logger(__name__)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """业务异常处理器 — 记录 WARNING 日志。"""
    logger.warning(
        "%s %s → %d %s",
        request.method,
        request.url.path,
        exc.status_code,
        exc.detail,
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": exc.status_code,
            "exc_type": type(exc).__name__,
        },
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """未预期的异常处理器 — 记录 ERROR 日志并带回溯。"""
    logger.error(
        "Unexpected error in %s %s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": 500,
            "exc_type": type(exc).__name__,
        },
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误"},
    )
