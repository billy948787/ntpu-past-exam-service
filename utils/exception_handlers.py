# pylint: skip-file
import sys
from typing import Union

from fastapi import Request
from fastapi.exception_handlers import http_exception_handler as _http_exception_handler
from fastapi.exception_handlers import (
    request_validation_exception_handler as _request_validation_exception_handler,
)
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from utils.log import logger


async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    This is a wrapper to the default RequestValidationException handler of FastAPI.
    This function will be called when client input is not valid.
    """
    logger.debug("Our custom request_validation_exception_handler was called")
    body = await request.body()
    query_params = request.query_params._dict  # pylint: disable=protected-access
    detail = {
        "errors": exc.errors(),
        "body": body.decode(),
        "query_params": query_params,
    }
    logger.info(detail)
    return await _request_validation_exception_handler(request, exc)


async def http_exception_handler(
    request: Request, exc: HTTPException
) -> Union[JSONResponse, Response]:
    """
    This is a wrapper to the default HTTPException handler of FastAPI.
    This function will be called when a HTTPException is explicitly raised.
    """
    return await _http_exception_handler(request, exc)


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> PlainTextResponse:
    """
    This middleware will log all unhandled exceptions.
    Unhandled exceptions are all exceptions that are not HTTPExceptions or RequestValidationErrors.
    """

    logger.exception(
        exc,
    )
    return PlainTextResponse(str("Internal Server Error"), status_code=500)
