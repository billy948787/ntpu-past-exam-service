import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from jose import jwt
from starlette.requests import Request

from auth import router as auth_router
from users import router as users_router
from utils.token import ALGORITHM, SECRET_KEY, create_access_token


def _request(token: str, path: str = "/", path_params=None) -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [(b"authorization", f"Bearer {token}".encode())],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "root_path": "",
            "path_params": path_params or {},
        }
    )


def _token(user_id: str, **claims) -> str:
    return create_access_token(
        {
            "sub": user_id,
            "id": user_id,
            "type": "access",
            **claims,
        }
    )


def test_verify_rejects_expired_access_token():
    token = jwt.encode(
        {
            "sub": "user-1",
            "id": "user-1",
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    with pytest.raises(HTTPException) as exc_info:
        auth_router.verify(_request(token), response=Response(), db=object())

    assert exc_info.value.status_code == 401


def test_access_token_requires_explicit_type_claim():
    token = jwt.encode(
        {
            "sub": "user-1",
            "id": "user-1",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    with pytest.raises(HTTPException) as exc_info:
        auth_router._get_authenticated_user(_request(token), db=object())

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token type"


def test_token_requires_expiration_claim():
    token = jwt.encode(
        {"sub": "user-1", "id": "user-1", "type": "access"},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    with pytest.raises(HTTPException) as exc_info:
        auth_router._get_authenticated_user(_request(token), db=object())

    assert exc_info.value.status_code == 401


def test_admin_middleware_ignores_forged_token_privileges(monkeypatch):
    user = SimpleNamespace(id="user-1", is_super_user=False)
    monkeypatch.setattr(
        auth_router.users_dependencies, "get_user", lambda db, uid: user
    )
    monkeypatch.setattr(
        auth_router.users_dependencies,
        "get_user_department_admin_ids",
        lambda db, uid: [],
    )
    request = _request(
        _token("user-1", isu=True, adm='["department-1"]'),
        path="/departments/department-1/join-request",
        path_params={"department_id": "department-1"},
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(auth_router.admin_middleware(request, db=object()))

    assert exc_info.value.status_code == 403


def test_superuser_middleware_uses_live_database_state(monkeypatch):
    user = SimpleNamespace(id="user-1", is_super_user=True)
    monkeypatch.setattr(
        auth_router.users_dependencies, "get_user", lambda db, uid: user
    )
    request = _request(_token("user-1", isu=False, adm="[]"))

    assert asyncio.run(auth_router.super_user_middleware(request, db=object())) is None


def test_deleted_user_token_is_rejected(monkeypatch):
    monkeypatch.setattr(
        auth_router.users_dependencies, "get_user", lambda db, uid: None
    )
    monkeypatch.setattr(
        auth_router.users_dependencies, "get_user_by_username", lambda db, name: None
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            auth_router.auth_middleware(_request(_token("deleted")), db=object())
        )

    assert exc_info.value.status_code == 401


def test_other_user_profile_requires_authorization(monkeypatch):
    monkeypatch.setattr(
        users_router.dependencies,
        "can_view_user_details",
        lambda db, viewer_id, target_id: False,
    )

    with pytest.raises(HTTPException) as exc_info:
        users_router.read_user(
            _request(_token("viewer")), user_id="target", db=object()
        )

    assert exc_info.value.status_code == 403


def test_authorized_nonself_profile_redacts_private_fields(monkeypatch):
    monkeypatch.setattr(
        users_router.dependencies,
        "can_view_user_details",
        lambda db, viewer_id, target_id: True,
    )
    monkeypatch.setattr(
        users_router.dependencies,
        "get_user",
        lambda db, user_id: SimpleNamespace(
            id=user_id,
            username="student",
            readable_name="Student",
            school_department="CS",
            note="join reason",
            email="private@example.com",
            hashed_password="secret-hash",
            is_super_user=False,
        ),
    )

    response = users_router.read_user(
        _request(_token("viewer")), user_id="target", db=object()
    )

    assert response["note"] == "join reason"
    assert "email" not in response
    assert "hashed_password" not in response
    assert "is_super_user" not in response


def test_removed_is_active_filter_returns_gone():
    with pytest.raises(HTTPException) as exc_info:
        users_router.read_users(is_active=True, db=object())

    assert exc_info.value.status_code == 410
