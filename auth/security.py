import os
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, Response, status


REFRESH_COOKIE_NAME = "ntpu-past-exam-refresh-token-v2"
REFRESH_COOKIE_PATH = "/refresh"
REFRESH_TOKEN_EXPIRE_DAYS = 365
CSRF_HEADER_NAME = "X-CSRF-Protection"
CSRF_HEADER_VALUE = "1"


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def refresh_cookie_secure() -> bool:
    # Production is secure by default. Local Compose explicitly opts out for
    # plain-http development.
    return _env_flag("AUTH_COOKIE_SECURE", True)


def allowed_auth_origins() -> set[str]:
    configured = ",".join(
        value
        for value in (
            os.getenv("AUTH_ALLOWED_ORIGINS", ""),
            os.getenv("ORIGIN", ""),
        )
        if value
    )
    return {
        origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()
    }


def validate_request_origin(request: Request, *, required: bool) -> None:
    origin = request.headers.get("origin")
    if origin is None:
        if required:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Origin header is required",
            )
        return

    if origin == "null" or origin not in allowed_auth_origins():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origin is not allowed",
        )


def validate_browser_mutation_request(request: Request) -> None:
    validate_request_origin(request, required=True)
    if request.headers.get(CSRF_HEADER_NAME) != CSRF_HEADER_VALUE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{CSRF_HEADER_NAME} header is required",
        )


def validate_cookie_refresh_request(request: Request) -> None:
    validate_browser_mutation_request(request)


def set_refresh_cookie(response: Response, token: str) -> None:
    max_age = int(timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS).total_seconds())
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=max_age,
        expires=datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        path=REFRESH_COOKIE_PATH,
        secure=refresh_cookie_secure(),
        httponly=True,
        samesite="lax",
    )


def delete_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        secure=refresh_cookie_secure(),
        httponly=True,
        samesite="lax",
    )


def mark_auth_response_no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
