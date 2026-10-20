import hashlib
import os
from datetime import datetime, timezone

from fastapi import HTTPException, Request, status
from redis.exceptions import RedisError

from utils.log import logger

REFRESH_SESSION_VERSION = 1
REFRESH_SESSION_PREFIX = "auth:refresh-session:"
LEGACY_REFRESH_PREFIX = "auth:legacy-refresh-used:"
DEFAULT_LEGACY_MIGRATION_DEADLINE = datetime(2026, 11, 3, tzinfo=timezone.utc)

ROTATE_REFRESH_SESSION_SCRIPT = """
-- refresh-session-rotate
local current_jti = redis.call('GET', KEYS[1])
if not current_jti or current_jti ~= ARGV[1] then
  return 0
end
redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[3])
return 1
"""

MIGRATE_LEGACY_REFRESH_SCRIPT = """
-- refresh-session-migrate-legacy
if redis.call('EXISTS', KEYS[1]) == 1 then
  return 0
end
redis.call('SET', KEYS[1], '1', 'EX', ARGV[1])
redis.call('SET', KEYS[2], ARGV[2], 'EX', ARGV[3])
return 1
"""


def legacy_refresh_bearer_enabled(now: datetime | None = None) -> bool:
    configured = os.getenv("AUTH_ALLOW_LEGACY_REFRESH_BEARER")
    if configured is not None:
        return configured.strip().lower() in {"1", "true", "yes", "on"}

    # Existing production browsers hold the former bearer refresh token. Give
    # each token one opportunity to exchange itself for a managed HttpOnly
    # session, then close the compatibility path automatically.
    current_time = now or datetime.now(timezone.utc)
    return current_time < DEFAULT_LEGACY_MIGRATION_DEADLINE


def is_managed_refresh_payload(payload: dict) -> bool:
    return (
        payload.get("session_version") == REFRESH_SESSION_VERSION
        and isinstance(payload.get("sid"), str)
        and bool(payload["sid"])
        and isinstance(payload.get("jti"), str)
        and bool(payload["jti"])
    )


def is_legacy_refresh_payload(payload: dict) -> bool:
    return not payload.get("sid") and not payload.get("jti")


def token_ttl(payload: dict) -> int:
    expires_at = payload.get("exp")
    if not isinstance(expires_at, (int, float)):
        raise HTTPException(status_code=401, detail="Invalid refresh token expiry")

    ttl = int(expires_at - datetime.now(timezone.utc).timestamp())
    if ttl <= 0:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return ttl


def _session_key(session_id: str) -> str:
    digest = hashlib.sha256(session_id.encode()).hexdigest()
    return f"{REFRESH_SESSION_PREFIX}{digest}"


def _legacy_token_key(token: str) -> str:
    digest = hashlib.sha256(token.encode()).hexdigest()
    return f"{LEGACY_REFRESH_PREFIX}{digest}"


def _redis(request: Request):
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Refresh session store is unavailable",
        )
    return redis


def _session_store_unavailable(exc: RedisError) -> HTTPException:
    logger.error("Refresh session store unavailable: %s", type(exc).__name__)
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Refresh session store is unavailable",
    )


async def register_refresh_session(
    request: Request,
    *,
    session_id: str,
    refresh_jti: str,
    ttl: int,
) -> None:
    try:
        created = await _redis(request).set(
            _session_key(session_id),
            refresh_jti,
            ex=ttl,
            nx=True,
        )
    except RedisError as exc:
        raise _session_store_unavailable(exc) from exc

    if not created:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not create refresh session",
        )


async def rotate_refresh_session(
    request: Request,
    *,
    session_id: str,
    old_jti: str,
    new_jti: str,
    ttl: int,
) -> None:
    try:
        rotated = await _redis(request).eval(
            ROTATE_REFRESH_SESSION_SCRIPT,
            1,
            _session_key(session_id),
            old_jti,
            new_jti,
            ttl,
        )
    except RedisError as exc:
        raise _session_store_unavailable(exc) from exc

    if int(rotated) != 1:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh session is no longer active",
        )


async def migrate_legacy_refresh_session(
    request: Request,
    *,
    legacy_token: str,
    legacy_ttl: int,
    session_id: str,
    refresh_jti: str,
    refresh_ttl: int,
) -> None:
    try:
        migrated = await _redis(request).eval(
            MIGRATE_LEGACY_REFRESH_SCRIPT,
            2,
            _legacy_token_key(legacy_token),
            _session_key(session_id),
            legacy_ttl,
            refresh_jti,
            refresh_ttl,
        )
    except RedisError as exc:
        raise _session_store_unavailable(exc) from exc

    if int(migrated) != 1:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Legacy refresh token has already been used",
        )


async def revoke_refresh_session(request: Request, payload: dict, token: str) -> None:
    try:
        redis = _redis(request)
        if is_managed_refresh_payload(payload):
            # Revoking the family rather than only the presented jti also closes
            # a rotate-vs-logout race where the browser still sends the old token.
            await redis.delete(_session_key(payload["sid"]))
            return

        if is_legacy_refresh_payload(payload):
            await redis.set(
                _legacy_token_key(token),
                "1",
                ex=token_ttl(payload),
                nx=True,
            )
            return

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown refresh session",
        )
    except RedisError as exc:
        raise _session_store_unavailable(exc) from exc
