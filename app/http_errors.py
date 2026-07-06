from __future__ import annotations

from typing import Any, Callable

import httpx
from fastapi import HTTPException

from app.avito_client import AvitoConfigError
from app.codex_app_server_client import CodexAppServerConfigError
from app.deepseek_client import DeepSeekConfigError


def error_detail(exc: Exception) -> object:
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            return exc.response.json()
        except ValueError:
            return exc.response.text
    return str(exc) or exc.__class__.__name__


def to_http_error(exc: Exception, *, record_log: Callable[[str, str, Any | None], None]) -> HTTPException:
    if isinstance(exc, (AvitoConfigError, DeepSeekConfigError, CodexAppServerConfigError)):
        record_log("error", "config_error", {"error": str(exc)})
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, httpx.HTTPStatusError):
        detail: object
        try:
            detail = exc.response.json()
        except ValueError:
            detail = exc.response.text
        record_log(
            "error",
            "avito_http_status_error",
            {"status_code": exc.response.status_code, "detail": detail},
        )
        return HTTPException(status_code=exc.response.status_code, detail=detail)
    if isinstance(exc, httpx.RequestError):
        record_log("error", "avito_request_failed", {"error_type": exc.__class__.__name__})
        return HTTPException(status_code=502, detail=f"Avito request failed: {exc.__class__.__name__}")
    return HTTPException(status_code=500, detail=exc.__class__.__name__)
