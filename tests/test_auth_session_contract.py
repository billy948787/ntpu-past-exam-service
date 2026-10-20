from dataclasses import dataclass
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from jose import jwt
from redis.exceptions import ConnectionError as RedisConnectionError

from auth import router as auth_router
from auth.rate_limit import _client_ip
from auth.refresh_sessions import (
    DEFAULT_LEGACY_MIGRATION_DEADLINE,
    REFRESH_SESSION_VERSION,
    legacy_refresh_bearer_enabled,
)
from auth.security import (
    CSRF_HEADER_NAME,
    CSRF_HEADER_VALUE,
    REFRESH_COOKIE_NAME,
    REFRESH_COOKIE_PATH,
    allowed_auth_origins,
)
from sql.database import get_db
from utils.token import ALGORITHM, SECRET_KEY, create_access_token

ALLOWED_ORIGIN = "http://127.0.0.1:15173"


class FakeRedis:
    def __init__(self):
        self.counts = {}
        self.values = {}
        self.fail = False

    async def set(self, key, value, *, ex=None, nx=False):
        if self.fail:
            raise RedisConnectionError("redis unavailable")
        del ex
        if nx and key in self.values:
            return None
        self.values[key] = str(value)
        return True

    async def delete(self, key):
        if self.fail:
            raise RedisConnectionError("redis unavailable")
        return int(self.values.pop(key, None) is not None)

    async def eval(self, script, key_count, *args):
        if self.fail:
            raise RedisConnectionError("redis unavailable")

        if "refresh-session-rotate" in script:
            assert key_count == 1
            key, old_jti, new_jti, _ttl = args
            if self.values.get(key) != old_jti:
                return 0
            self.values[key] = new_jti
            return 1

        if "refresh-session-migrate-legacy" in script:
            assert key_count == 2
            used_key, session_key, _legacy_ttl, refresh_jti, _refresh_ttl = args
            if used_key in self.values:
                return 0
            self.values[used_key] = "1"
            self.values[session_key] = refresh_jti
            return 1

        assert key_count == 1
        key, window_seconds = args
        self.counts[key] = self.counts.get(key, 0) + 1
        return [self.counts[key], int(window_seconds)]


@dataclass
class AuthTestContext:
    app: FastAPI
    client: TestClient
    redis: FakeRedis
    user: SimpleNamespace


@pytest.fixture()
def auth_context(monkeypatch):
    monkeypatch.setenv(
        "AUTH_ALLOWED_ORIGINS",
        f"http://localhost:15173,{ALLOWED_ORIGIN}",
    )
    monkeypatch.setenv("ORIGIN", ALLOWED_ORIGIN)
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    monkeypatch.setenv("AUTH_ALLOW_LEGACY_REFRESH_BEARER", "false")
    monkeypatch.setenv("AUTH_RATE_LIMIT_REQUESTS", "10")
    monkeypatch.setenv("AUTH_RATE_LIMIT_GLOBAL_REQUESTS", "300")
    monkeypatch.setenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("AUTH_RATE_LIMIT_TRUST_PROXY_HEADERS", "false")

    user = SimpleNamespace(
        id="user-1",
        username="123456789",
        readable_name="Test User",
        school_department="CS",
        email="s123456789@gm.ntpu.edu.tw",
        hashed_password=None,
        is_super_user=False,
    )
    monkeypatch.setattr(
        auth_router.dependencies,
        "get_lms_user_info",
        lambda username, password: {
            "readable_name": user.readable_name,
            "department": user.school_department,
            "email": user.email,
        },
    )
    monkeypatch.setattr(
        auth_router.dependencies,
        "exchange_token_with_google",
        lambda code, redirect_uri: {"name": user.readable_name, "email": user.email},
    )
    monkeypatch.setattr(
        auth_router.users_dependencies,
        "get_user_by_username",
        lambda db, username: user,
    )
    monkeypatch.setattr(
        auth_router.users_dependencies, "get_user", lambda db, user_id: user
    )
    monkeypatch.setattr(
        auth_router.users_dependencies, "update_user", lambda db, data: None
    )
    monkeypatch.setattr(
        auth_router.users_dependencies,
        "get_user_department_admin_ids",
        lambda db, user_id: [],
    )

    app = FastAPI()
    redis = FakeRedis()
    app.state.redis = redis
    app.include_router(auth_router.router)

    def override_db():
        yield object()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield AuthTestContext(app=app, client=client, redis=redis, user=user)


def _login(client: TestClient, *, origin=ALLOWED_ORIGIN):
    headers = {} if origin is None else {"Origin": origin}
    return client.post(
        "/login",
        data={"username": "123456789", "password": "test-password"},
        headers=headers,
    )


def _csrf_headers(origin=ALLOWED_ORIGIN):
    return {
        "Origin": origin,
        CSRF_HEADER_NAME: CSRF_HEADER_VALUE,
    }


def _legacy_refresh_token(user_id: str) -> str:
    return create_access_token(
        {"sub": user_id, "id": user_id, "type": "refresh"},
        expires_delta=timedelta(days=365),
    )


def test_allowed_origins_support_comma_separated_local_hosts(auth_context):
    assert allowed_auth_origins() == {
        "http://localhost:15173",
        "http://127.0.0.1:15173",
    }


def test_allowed_origins_include_explicit_frontend_origin(auth_context, monkeypatch):
    monkeypatch.setenv("ORIGIN", "http://192.168.1.23:15173")

    assert allowed_auth_origins() == {
        "http://localhost:15173",
        "http://127.0.0.1:15173",
        "http://192.168.1.23:15173",
    }


def test_login_sets_host_only_httponly_refresh_cookie_and_returns_access_only(
    auth_context,
):
    response = _login(auth_context.client)

    assert response.status_code == 200
    assert set(response.json()) == {"access_token", "token_type"}
    assert "refresh_token" not in response.json()
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"

    set_cookie = response.headers["set-cookie"]
    lower_cookie = set_cookie.lower()
    assert f"{REFRESH_COOKIE_NAME}=" in set_cookie
    assert "httponly" in lower_cookie
    assert "samesite=lax" in lower_cookie
    assert f"path={REFRESH_COOKIE_PATH}" in lower_cookie
    assert "max-age=31536000" in lower_cookie
    assert "domain=" not in lower_cookie
    assert "secure" not in lower_cookie


def test_access_token_expires_in_fifteen_minutes(auth_context):
    response = _login(auth_context.client)
    claims = jwt.decode(
        response.json()["access_token"],
        SECRET_KEY,
        algorithms=[ALGORITHM],
    )

    lifetime = claims["exp"] - claims["iat"] if "iat" in claims else None
    if lifetime is None:
        from time import time

        lifetime = claims["exp"] - int(time())

    assert 895 <= lifetime <= 900


def test_cookie_refresh_requires_csrf_and_rotates_cookie(auth_context):
    assert _login(auth_context.client).status_code == 200
    original_cookie = auth_context.client.cookies.get(REFRESH_COOKIE_NAME)
    assert original_cookie

    response = auth_context.client.post("/refresh", headers=_csrf_headers())

    assert response.status_code == 200
    assert set(response.json()) == {"access_token", "token_type"}
    assert response.headers["cache-control"] == "no-store"
    assert auth_context.client.cookies.get(REFRESH_COOKIE_NAME) != original_cookie
    assert response.headers.get("set-cookie")


def test_rotated_refresh_cookie_cannot_be_replayed(auth_context):
    assert _login(auth_context.client).status_code == 200
    original_cookie = auth_context.client.cookies.get(REFRESH_COOKIE_NAME)
    assert original_cookie

    assert (
        auth_context.client.post("/refresh", headers=_csrf_headers()).status_code == 200
    )
    auth_context.client.cookies.set(
        REFRESH_COOKIE_NAME,
        original_cookie,
        path=REFRESH_COOKIE_PATH,
    )

    replay = auth_context.client.post("/refresh", headers=_csrf_headers())

    assert replay.status_code == 401


def test_unknown_managed_refresh_session_fails_closed(auth_context):
    unknown_token = create_access_token(
        {
            "sub": auth_context.user.id,
            "id": auth_context.user.id,
            "type": "refresh",
            "session_version": REFRESH_SESSION_VERSION,
            "sid": "unknown-session",
            "jti": "unknown-jti",
        },
        expires_delta=timedelta(days=365),
    )
    auth_context.client.cookies.set(
        REFRESH_COOKIE_NAME,
        unknown_token,
        path=REFRESH_COOKIE_PATH,
    )

    response = auth_context.client.post("/refresh", headers=_csrf_headers())

    assert response.status_code == 401


def test_untracked_pre_session_family_cookie_requires_relogin(auth_context):
    untracked_token = create_access_token(
        {
            "sub": auth_context.user.id,
            "id": auth_context.user.id,
            "type": "refresh",
            "jti": "pre-session-family-jti",
        },
        expires_delta=timedelta(days=365),
    )
    auth_context.client.cookies.set(
        REFRESH_COOKIE_NAME,
        untracked_token,
        path=REFRESH_COOKIE_PATH,
    )

    response = auth_context.client.post("/refresh", headers=_csrf_headers())

    assert response.status_code == 401


def test_refresh_fails_closed_when_session_store_is_unavailable(auth_context):
    assert _login(auth_context.client).status_code == 200
    auth_context.redis.fail = True

    response = auth_context.client.post("/refresh", headers=_csrf_headers())

    assert response.status_code == 503


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {CSRF_HEADER_NAME: CSRF_HEADER_VALUE},
        {"Origin": ALLOWED_ORIGIN},
        {"Origin": "https://evil.example", CSRF_HEADER_NAME: CSRF_HEADER_VALUE},
        {"Origin": "null", CSRF_HEADER_NAME: CSRF_HEADER_VALUE},
    ],
)
def test_cookie_refresh_rejects_missing_or_invalid_csrf_context(auth_context, headers):
    assert _login(auth_context.client).status_code == 200

    response = auth_context.client.post("/refresh", headers=headers)

    assert response.status_code == 403


def test_cookie_takes_precedence_over_valid_legacy_bearer(auth_context):
    assert _login(auth_context.client).status_code == 200
    legacy_token = _legacy_refresh_token(auth_context.user.id)

    response = auth_context.client.post(
        "/refresh",
        headers={"Authorization": f"Bearer {legacy_token}"},
    )

    assert response.status_code == 403


def test_legacy_refresh_bearer_is_disabled_by_default(auth_context):
    legacy_token = _legacy_refresh_token(auth_context.user.id)

    response = auth_context.client.post(
        "/refresh",
        headers={"Authorization": f"Bearer {legacy_token}"},
    )

    assert response.status_code == 401


def test_legacy_refresh_bearer_can_be_migrated_once(auth_context, monkeypatch):
    monkeypatch.setenv("AUTH_ALLOW_LEGACY_REFRESH_BEARER", "true")
    legacy_token = _legacy_refresh_token(auth_context.user.id)

    response = auth_context.client.post(
        "/refresh",
        headers={"Authorization": f"Bearer {legacy_token}"},
    )

    assert response.status_code == 200
    assert set(response.json()) == {"access_token", "token_type"}
    assert auth_context.client.cookies.get(REFRESH_COOKIE_NAME)
    assert "httponly" in response.headers["set-cookie"].lower()

    auth_context.client.cookies.delete(
        REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
    )
    replay = auth_context.client.post(
        "/refresh",
        headers={"Authorization": f"Bearer {legacy_token}"},
    )

    assert replay.status_code == 401


def test_legacy_refresh_migration_window_closes_automatically(monkeypatch):
    monkeypatch.delenv("AUTH_ALLOW_LEGACY_REFRESH_BEARER", raising=False)

    assert legacy_refresh_bearer_enabled(
        DEFAULT_LEGACY_MIGRATION_DEADLINE - timedelta(seconds=1)
    )
    assert not legacy_refresh_bearer_enabled(DEFAULT_LEGACY_MIGRATION_DEADLINE)


def test_explicit_legacy_refresh_setting_overrides_migration_window(monkeypatch):
    monkeypatch.setenv("AUTH_ALLOW_LEGACY_REFRESH_BEARER", "false")

    assert not legacy_refresh_bearer_enabled(
        DEFAULT_LEGACY_MIGRATION_DEADLINE - timedelta(days=1)
    )


def test_logout_deletes_refresh_cookie_with_exact_path(auth_context):
    assert _login(auth_context.client).status_code == 200

    response = auth_context.client.post("/logout", headers=_csrf_headers())

    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert f"{REFRESH_COOKIE_NAME}=" in cookie
    assert "max-age=0" in cookie
    assert f"path={REFRESH_COOKIE_PATH}" in cookie
    assert "httponly" in cookie
    assert response.headers["cache-control"] == "no-store"


def test_refresh_logout_revokes_the_server_side_session(auth_context):
    assert _login(auth_context.client).status_code == 200
    stale_cookie = auth_context.client.cookies.get(REFRESH_COOKIE_NAME)
    assert stale_cookie

    assert (
        auth_context.client.post("/refresh", headers=_csrf_headers()).status_code == 200
    )
    current_cookie = auth_context.client.cookies.get(REFRESH_COOKIE_NAME)
    assert current_cookie and current_cookie != stale_cookie

    # A logout request that was sent just before the rotation response arrived
    # still revokes the entire session family.
    auth_context.client.cookies.set(
        REFRESH_COOKIE_NAME,
        stale_cookie,
        path=REFRESH_COOKIE_PATH,
    )

    response = auth_context.client.post("/refresh/logout", headers=_csrf_headers())
    auth_context.client.cookies.set(
        REFRESH_COOKIE_NAME,
        current_cookie,
        path=REFRESH_COOKIE_PATH,
    )
    replay = auth_context.client.post("/refresh", headers=_csrf_headers())

    assert response.status_code == 200
    assert replay.status_code == 401


def test_refresh_logout_without_cookie_is_idempotent(auth_context):
    response = auth_context.client.post("/refresh/logout", headers=_csrf_headers())

    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert f"{REFRESH_COOKIE_NAME}=" in cookie
    assert "max-age=0" in cookie
    assert f"path={REFRESH_COOKIE_PATH}" in cookie


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Origin": ALLOWED_ORIGIN},
        {CSRF_HEADER_NAME: CSRF_HEADER_VALUE},
        {"Origin": ALLOWED_ORIGIN, CSRF_HEADER_NAME: "wrong"},
        {"Origin": "https://evil.example", CSRF_HEADER_NAME: CSRF_HEADER_VALUE},
    ],
)
@pytest.mark.parametrize("endpoint", ["/logout", "/refresh/logout"])
def test_logout_requires_allowed_origin_and_csrf_header(
    auth_context, headers, endpoint
):
    response = auth_context.client.post(endpoint, headers=headers)
    assert response.status_code == 403


@pytest.mark.parametrize("origin", ["https://evil.example", "null"])
def test_login_rejects_untrusted_and_null_origin(auth_context, origin):
    response = _login(auth_context.client, origin=origin)
    assert response.status_code == 403


def test_rejected_origins_do_not_consume_the_auth_rate_limit(auth_context):
    for _ in range(12):
        assert (
            _login(auth_context.client, origin="https://evil.example").status_code
            == 403
        )

    responses = [_login(auth_context.client, origin=None) for _ in range(11)]

    assert all(response.status_code == 200 for response in responses[:10])
    assert responses[10].status_code == 429


def test_login_without_origin_remains_available_to_nonbrowser_clients(auth_context):
    response = _login(auth_context.client, origin=None)
    assert response.status_code == 200


def test_exchange_uses_same_cookie_and_json_contract(auth_context):
    response = auth_context.client.post(
        "/exchange",
        data={"code": "test-code", "redirect_uri": f"{ALLOWED_ORIGIN}/login"},
        headers={"Origin": ALLOWED_ORIGIN},
    )

    assert response.status_code == 200
    assert set(response.json()) == {"access_token", "token_type"}
    assert "httponly" in response.headers["set-cookie"].lower()
    assert response.headers["cache-control"] == "no-store"


def test_create_user_does_not_replace_callers_session(auth_context, monkeypatch):
    created_user = SimpleNamespace(id="created-user")
    auth_context.app.dependency_overrides[auth_router.super_user_middleware] = (
        lambda: None
    )
    monkeypatch.setattr(
        auth_router.users_dependencies,
        "get_user_by_username",
        lambda db, username: None,
    )
    monkeypatch.setattr(
        auth_router.users_dependencies,
        "create_user",
        lambda db, data: created_user,
    )

    response = auth_context.client.post(
        "/create_user",
        data={"username": "created", "password": "password"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "success", "user_id": created_user.id}
    assert "access_token" not in response.json()
    assert "refresh_token" not in response.json()
    assert response.headers.get("set-cookie") is None
    assert response.headers["cache-control"] == "no-store"


def test_secure_cookie_is_enabled_when_configured(auth_context, monkeypatch):
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")

    response = _login(auth_context.client)

    assert response.status_code == 200
    assert "secure" in response.headers["set-cookie"].lower()


def test_auth_rate_limit_returns_retry_after(auth_context):
    responses = [_login(auth_context.client, origin=None) for _ in range(11)]

    assert all(response.status_code == 200 for response in responses[:10])
    assert responses[10].status_code == 429
    assert 1 <= int(responses[10].headers["retry-after"]) <= 60


def test_login_rate_limit_is_scoped_per_account(auth_context, monkeypatch):
    monkeypatch.setenv("AUTH_RATE_LIMIT_REQUESTS", "1")

    first_account = auth_context.client.post(
        "/login",
        data={"username": "111111111", "password": "test-password"},
    )
    second_account = auth_context.client.post(
        "/login",
        data={"username": "222222222", "password": "test-password"},
    )
    repeated_account = auth_context.client.post(
        "/login",
        data={"username": "111111111", "password": "test-password"},
    )

    assert first_account.status_code == 200
    assert second_account.status_code == 200
    assert repeated_account.status_code == 429


def test_rate_limit_does_not_trust_forwarded_header_by_default(
    monkeypatch,
):
    monkeypatch.setenv("AUTH_RATE_LIMIT_TRUST_PROXY_HEADERS", "false")
    request = Request(
        {
            "type": "http",
            "client": ("10.0.0.8", 1234),
            "headers": [(b"x-forwarded-for", b"198.51.100.10")],
        }
    )

    assert _client_ip(request) == "10.0.0.8"


def test_rate_limit_rejects_forwarded_header_from_untrusted_peer(
    monkeypatch,
):
    monkeypatch.setenv("AUTH_RATE_LIMIT_TRUST_PROXY_HEADERS", "true")
    monkeypatch.setenv("AUTH_RATE_LIMIT_TRUSTED_PROXY_CIDRS", "10.0.0.0/8")
    request = Request(
        {
            "type": "http",
            "client": ("203.0.113.9", 1234),
            "headers": [(b"x-forwarded-for", b"198.51.100.10")],
        }
    )

    assert _client_ip(request) == "203.0.113.9"


def test_rate_limit_uses_first_untrusted_hop_from_the_right(
    monkeypatch,
):
    monkeypatch.setenv("AUTH_RATE_LIMIT_TRUST_PROXY_HEADERS", "true")
    monkeypatch.setenv("AUTH_RATE_LIMIT_TRUSTED_PROXY_CIDRS", "10.0.0.0/8,192.0.2.0/24")
    request = Request(
        {
            "type": "http",
            "client": ("10.0.0.8", 1234),
            "headers": [(b"x-forwarded-for", b"6.6.6.6, 198.51.100.10, 192.0.2.20")],
        }
    )

    assert _client_ip(request) == "198.51.100.10"


def test_exchange_shares_the_global_auth_rate_limit(auth_context, monkeypatch):
    monkeypatch.setenv("AUTH_RATE_LIMIT_GLOBAL_REQUESTS", "10")
    for _ in range(10):
        assert _login(auth_context.client, origin=None).status_code == 200

    response = auth_context.client.post(
        "/exchange",
        data={"code": "test-code", "redirect_uri": f"{ALLOWED_ORIGIN}/login"},
        headers={"Origin": ALLOWED_ORIGIN},
    )

    assert response.status_code == 429
    assert response.headers.get("retry-after")


def test_session_issuance_fails_closed_when_redis_is_unavailable(auth_context):
    auth_context.redis.fail = True

    response = _login(auth_context.client, origin=None)

    # The limiter remains fail-open, but a new refresh session must not be
    # issued without its server-side allowlist entry.
    assert response.status_code == 503
