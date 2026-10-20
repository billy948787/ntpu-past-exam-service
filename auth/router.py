import json
import uuid
from datetime import timedelta
from typing import Annotated, Optional

import bcrypt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from departments import dependencies as departments_dependencies
from sql.database import get_db
from users import dependencies as users_dependencies
from utils.token import (
    create_access_token,
    get_access_token_payload,
    get_token_payload,
)

from . import dependencies
from .rate_limit import enforce_auth_rate_limit
from .refresh_sessions import (
    REFRESH_SESSION_VERSION,
    is_legacy_refresh_payload,
    is_managed_refresh_payload,
    legacy_refresh_bearer_enabled,
    migrate_legacy_refresh_session,
    register_refresh_session,
    revoke_refresh_session,
    rotate_refresh_session,
    token_ttl,
)
from .security import (
    REFRESH_COOKIE_NAME,
    REFRESH_TOKEN_EXPIRE_DAYS,
    delete_refresh_cookie,
    mark_auth_response_no_store,
    set_refresh_cookie,
    validate_browser_mutation_request,
    validate_cookie_refresh_request,
    validate_request_origin,
)

load_dotenv()

router = APIRouter()


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid credentials",
)


def _get_authenticated_user_from_payload(payload: dict, db: Session):
    """Resolve a token subject against the live database."""
    user_id = payload.get("id")
    user = users_dependencies.get_user(db, user_id) if user_id else None

    # Keep compatibility with early tokens that only carried ``sub``. Depending
    # on the issuer version, it contained either the database id or username.
    if user is None and payload.get("sub"):
        subject = payload["sub"]
        user = users_dependencies.get_user(db, subject)
        if user is None:
            user = users_dependencies.get_user_by_username(db, subject)

    if user is None:
        raise credentials_exception

    return user


def _get_authenticated_user(request: Request, db: Session, token_type: str = "access"):
    """Resolve the current user from a verified bearer token and live database.

    Authorization claims such as ``isu`` and ``adm`` are intentionally not used
    here: their values can be stale for as long as the token remains valid.
    """
    payload = get_access_token_payload(request, token_type=token_type)
    user = _get_authenticated_user_from_payload(payload, db)
    return payload, user


def _token_claims(user, token_type: str, department_admin_ids: list[str]) -> dict:
    return {
        "sub": user.id,
        "type": token_type,
        "isu": user.is_super_user,
        "id": user.id,
        "adm": json.dumps(department_admin_ids),
    }


def _build_session_tokens(db: Session, user, session_id: str | None = None):
    department_admin_ids = users_dependencies.get_user_department_admin_ids(db, user.id)
    access_token = create_access_token(
        _token_claims(user, "access", department_admin_ids)
    )
    session_id = session_id or str(uuid.uuid4())
    refresh_jti = str(uuid.uuid4())
    refresh_claims = _token_claims(user, "refresh", department_admin_ids)
    refresh_claims.update(
        {
            "session_version": REFRESH_SESSION_VERSION,
            "sid": session_id,
            "jti": refresh_jti,
        }
    )
    refresh_token = create_access_token(
        refresh_claims,
        expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    return access_token, refresh_token, session_id, refresh_jti


def _apply_session_response(
    response: Response, access_token: str, refresh_token: str
) -> dict:
    set_refresh_cookie(response, refresh_token)
    mark_auth_response_no_store(response)
    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


async def _issue_session(
    request: Request, response: Response, db: Session, user
) -> dict:
    access_token, refresh_token, session_id, refresh_jti = await run_in_threadpool(
        _build_session_tokens, db, user
    )
    await register_refresh_session(
        request,
        session_id=session_id,
        refresh_jti=refresh_jti,
        ttl=int(timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS).total_seconds()),
    )
    return _apply_session_response(response, access_token, refresh_token)


async def enforce_auth_entrypoint_security(request: Request) -> None:
    # Validate a browser's Origin before incrementing any counter. This
    # prevents a cross-site form POST from exhausting the victim's login quota.
    validate_request_origin(request, required=False)
    subject = None
    if request.url.path.rstrip("/").endswith("/login"):
        form = await request.form()
        username = form.get("username")
        if username:
            subject = f"login:{str(username).strip()}"
    await enforce_auth_rate_limit(request, subject=subject)


async def auth_middleware(request: Request, db: Session = Depends(get_db)):
    _get_authenticated_user(request, db)


async def admin_middleware(request: Request, db: Session = Depends(get_db)):
    department_id = request.path_params.get("department_id")
    _, user = _get_authenticated_user(request, db)

    if user.is_super_user:
        return

    admin_ids = users_dependencies.get_user_department_admin_ids(db, user.id)
    if department_id is None or department_id not in admin_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)


async def super_user_middleware(request: Request, db: Session = Depends(get_db)):
    _, user = _get_authenticated_user(request, db)
    if not user.is_super_user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)


def get_password_hash(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def _login_with_google_user(code: str, redirect_uri: str, db: Session):
    user_data_from_google = dependencies.exchange_token_with_google(
        code=code, redirect_uri=redirect_uri
    )
    school_id = str(user_data_from_google["email"])[1:10]
    user = users_dependencies.get_user_by_username(db, school_id)

    if not user:
        user = users_dependencies.create_user(
            db,
            {
                "username": school_id,
                "readable_name": user_data_from_google["name"],
                "school_department": " ",
                "email": user_data_from_google["email"],
            },
        )
    else:
        users_dependencies.update_user(
            db,
            {
                "username": school_id,
                "readable_name": user_data_from_google["name"],
                "school_department": user.school_department,
                "email": user_data_from_google["email"],
            },
        )

    return user


def _login_user(form_data: OAuth2PasswordRequestForm, db: Session):
    user = users_dependencies.get_user_by_username(db, form_data.username)
    try:
        lms_user_info = dependencies.get_lms_user_info(
            username=str(int(form_data.username)), password=form_data.password
        )

        user_dict = {
            "username": form_data.username,
            "readable_name": lms_user_info["readable_name"],
            "school_department": lms_user_info["department"],
            "email": lms_user_info["email"],
        }
        if not user:
            user = users_dependencies.create_user(
                db,
                user_dict,
            )
        else:
            users_dependencies.update_user(
                db,
                user_dict,
            )
    except ValueError:
        if not user or not user.hashed_password:
            raise HTTPException(
                status_code=400, detail="incorrect username or password"
            )
        if not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=400, detail="incorrect username or password"
            )

    return user


@router.post("/exchange", dependencies=[Depends(enforce_auth_entrypoint_security)])
async def login_with_google(
    request: Request,
    response: Response,
    code: Annotated[str, Form()],
    redirect_uri: Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    user = await run_in_threadpool(_login_with_google_user, code, redirect_uri, db)
    return await _issue_session(request, response, db, user)


@router.post("/login", dependencies=[Depends(enforce_auth_entrypoint_security)])
async def login(
    request: Request,
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db),
):
    user = await run_in_threadpool(_login_user, form_data, db)
    return await _issue_session(request, response, db, user)


@router.get("/verify-token")
def verify(request: Request, response: Response, db: Session = Depends(get_db)):
    _, user = _get_authenticated_user(request, db)

    admin_scope = users_dependencies.get_user_department_admin_ids(db, user.id)
    visible_departments = departments_dependencies.get_viewable_departments_ids(
        db, user.id
    )

    mark_auth_response_no_store(response)
    return {
        "admin": admin_scope,
        "visible_departments": visible_departments,
    }


def _bearer_token(request: Request) -> str:
    authorization = request.headers.get("authorization") or ""
    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0] != "Bearer" or not parts[1]:
        raise credentials_exception
    return parts[1]


@router.post("/refresh")
async def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    refresh_cookie = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh_cookie:
        validate_cookie_refresh_request(request)
        refresh_token = refresh_cookie
    else:
        refresh_token = _bearer_token(request)

    payload = get_token_payload(refresh_token, token_type="refresh")
    managed_session = is_managed_refresh_payload(payload)
    legacy_session = is_legacy_refresh_payload(payload)

    if not managed_session:
        if not legacy_session:
            raise HTTPException(status_code=401, detail="Unknown refresh session")
        if refresh_cookie or not legacy_refresh_bearer_enabled():
            raise HTTPException(
                status_code=401,
                detail="Legacy refresh bearer migration is disabled",
            )

    user = await run_in_threadpool(_get_authenticated_user_from_payload, payload, db)
    existing_session_id = payload.get("sid") if managed_session else None
    access_token, new_refresh_token, session_id, refresh_jti = await run_in_threadpool(
        _build_session_tokens, db, user, existing_session_id
    )

    refresh_ttl = int(timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS).total_seconds())
    if managed_session:
        await rotate_refresh_session(
            request,
            session_id=session_id,
            old_jti=payload["jti"],
            new_jti=refresh_jti,
            ttl=refresh_ttl,
        )
    else:
        await migrate_legacy_refresh_session(
            request,
            legacy_token=refresh_token,
            legacy_ttl=token_ttl(payload),
            session_id=session_id,
            refresh_jti=refresh_jti,
            refresh_ttl=refresh_ttl,
        )

    return _apply_session_response(response, access_token, new_refresh_token)


@router.post("/refresh/logout")
async def refresh_logout(request: Request, response: Response):
    validate_browser_mutation_request(request)
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh_token:
        try:
            payload = get_token_payload(refresh_token, token_type="refresh")
        except HTTPException:
            # A malformed or expired cookie has no active session to revoke.
            payload = None
        if payload is not None:
            await revoke_refresh_session(request, payload, refresh_token)

    delete_refresh_cookie(response)
    mark_auth_response_no_store(response)
    return {"status": "success"}


@router.post("/logout")
def logout(request: Request, response: Response):
    # Compatibility endpoint for old clients. The refresh cookie deliberately
    # has Path=/refresh, so only /refresh/logout can receive and revoke it.
    validate_browser_mutation_request(request)
    delete_refresh_cookie(response)
    mark_auth_response_no_store(response)
    return {"status": "success"}


@router.post("/create_user", dependencies=[Depends(super_user_middleware)])
def create_user(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db),
):
    if not form_data.username or not form_data.password:
        raise HTTPException(status_code=400, detail="Invalid input")

    user = users_dependencies.get_user_by_username(db, form_data.username)
    if user:
        raise HTTPException(status_code=400, detail="Same username already exist.")

    hashed_password = get_password_hash(form_data.password)

    user = users_dependencies.create_user(
        db,
        {
            "username": form_data.username,
            "hashed_password": hashed_password,
            "readable_name": form_data.username,
        },
    )

    mark_auth_response_no_store(response)
    return {"status": "success", "user_id": user.id}
