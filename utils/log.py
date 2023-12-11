# pylint: skip-file
import http
import logging
import os
import time

from dotenv import load_dotenv
from logtail import LogtailHandler

load_dotenv()

LOG_TAIL_SOURCE_KEY = os.getenv("LOG_TAIL_SOURCE_KEY")

handler = LogtailHandler(source_token=LOG_TAIL_SOURCE_KEY)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.handlers = []
logger.addHandler(handler)


async def log_request_middleware(request, call_next):
    url = (
        f"{request.url.path}?{request.query_params}"
        if request.query_params
        else request.url.path
    )
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    formatted_process_time = "{0:.2f}".format(process_time)
    try:
        status_phrase = http.HTTPStatus(response.status_code).phrase
    except ValueError:
        status_phrase = ""
    logger.info(
        f'"{request.method} {url}" {response.status_code} {status_phrase} {formatted_process_time}ms'
    )
    return response
