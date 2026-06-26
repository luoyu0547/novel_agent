"""统一 API 响应格式。

成功时所有端点返回 ``{"code": 0, "message": "ok", "data": ...}``。
失败时 ``code`` 非零，``data`` 为 None。
"""
from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.core.exceptions import AppException


class ApiResponse:
    @staticmethod
    def success(data: Any = None, message: str = "ok") -> JSONResponse:
        return JSONResponse(content={"code": 0, "message": message, "data": jsonable_encoder(data)})

    @staticmethod
    def error(code: int, message: str, status_code: int = 400) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content={"code": code, "message": message, "data": None},
        )
