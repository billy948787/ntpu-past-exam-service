import asyncio
from unittest.mock import AsyncMock, Mock

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.requests import Request

from utils import exception_handlers


def test_validation_handler_never_logs_request_values(monkeypatch):
    password = "FAKE_PASSWORD_MUST_NOT_BE_LOGGED"
    oauth_code = "FAKE_OAUTH_CODE_MUST_NOT_BE_LOGGED"

    async def receive():
        raise AssertionError("the validation handler must not read the request body")

    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "https",
            "path": "/login",
            "raw_path": b"/login",
            "query_string": f"code={oauth_code}".encode(),
            "headers": [(b"content-type", b"application/json")],
            "client": ("testclient", 50000),
            "server": ("testserver", 443),
            "root_path": "",
        },
        receive=receive,
    )
    error = RequestValidationError(
        [
            {
                "type": "missing",
                "loc": ("body", "username"),
                "msg": f"Field required; rejected value was {password}",
                "input": {"password": password},
                "ctx": {"oauth_code": oauth_code},
            }
        ]
    )
    logger = Mock()
    default_handler = AsyncMock(return_value=JSONResponse({}, status_code=422))
    monkeypatch.setattr(exception_handlers, "logger", logger)
    monkeypatch.setattr(
        exception_handlers,
        "_request_validation_exception_handler",
        default_handler,
    )

    response = asyncio.run(
        exception_handlers.request_validation_exception_handler(request, error)
    )

    assert response.status_code == 422
    logged = repr(logger.info.call_args)
    assert password not in logged
    assert oauth_code not in logged
    assert "input" not in logged
    assert "ctx" not in logged
    assert "POST" in logged
    assert "/login" in logged
