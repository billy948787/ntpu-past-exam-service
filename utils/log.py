# pylint: skip-file
import http
import logging
import os
import time

from dotenv import load_dotenv
from logtail import LogtailHandler

load_dotenv()

LOG_TAIL_SOURCE_KEY = os.getenv("LOG_TAIL_SOURCE_KEY")
SERVICE_NAME = os.getenv("SERVICE_NAME") or "local"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.handlers = []
if LOG_TAIL_SOURCE_KEY:
    logger.addHandler(LogtailHandler(source_token=LOG_TAIL_SOURCE_KEY))
else:
    logger.addHandler(logging.StreamHandler())


async def log_request_middleware(request, call_next):
    # Query strings commonly carry OAuth codes and other credentials. Keep
    # request logs useful without persisting their values.
    path = request.url.path
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = (time.perf_counter() - start_time) * 1000
    try:
        status_phrase = http.HTTPStatus(response.status_code).phrase
    except ValueError:
        status_phrase = ""
    logger.info(
        '"%s %s" %s %s %.2fms',
        request.method,
        path,
        response.status_code,
        status_phrase,
        process_time,
        extra={
            "env": SERVICE_NAME,
        },
    )
    return response
