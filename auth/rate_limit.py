import hashlib
import ipaddress
import os
import time

from fastapi import HTTPException, Request, status
from redis.exceptions import RedisError

from utils.log import logger

AUTH_RATE_LIMIT_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {current, ttl}
"""

_LAST_FAILURE_LOG = 0.0


def _positive_int_from_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def _trust_proxy_headers() -> bool:
    return os.getenv("AUTH_RATE_LIMIT_TRUST_PROXY_HEADERS", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _trusted_proxy_networks() -> (
    tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]
):
    networks = []
    for value in os.getenv("AUTH_RATE_LIMIT_TRUSTED_PROXY_CIDRS", "").split(","):
        value = value.strip()
        if not value:
            continue
        try:
            networks.append(ipaddress.ip_network(value, strict=False))
        except ValueError:
            logger.warning("Ignoring invalid trusted proxy CIDR")
    return tuple(networks)


def _is_trusted_proxy(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
    networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...],
) -> bool:
    return any(
        address.version == network.version and address in network
        for network in networks
    )


def _client_ip(request: Request) -> str:
    direct_ip = request.client.host if request.client else "unknown"
    if not _trust_proxy_headers():
        return direct_ip

    try:
        direct_address = ipaddress.ip_address(direct_ip)
    except ValueError:
        return direct_ip

    trusted_networks = _trusted_proxy_networks()
    if not trusted_networks or not _is_trusted_proxy(direct_address, trusted_networks):
        return direct_ip

    forwarded_for = request.headers.get("x-forwarded-for", "")
    try:
        forwarded_addresses = [
            ipaddress.ip_address(value.strip())
            for value in forwarded_for.split(",")
            if value.strip()
        ]
    except ValueError:
        return direct_ip

    # Proxies append addresses to the right. Walk backwards over explicitly
    # trusted hops and use the first untrusted address. A client-supplied value
    # farther left therefore cannot override the address seen by the edge.
    for address in reversed(forwarded_addresses):
        if not _is_trusted_proxy(address, trusted_networks):
            return str(address)

    return direct_ip


def _rate_limit_window(identifier: str, window_seconds: int) -> tuple[str, int]:
    identifier_digest = hashlib.sha256(identifier.encode()).hexdigest()[:32]
    now = int(time.time())
    window = now // window_seconds
    retry_after = window_seconds - (now % window_seconds)
    return f"rate-limit:auth:{window}:{identifier_digest}", retry_after


def _log_fail_open_once() -> None:
    global _LAST_FAILURE_LOG  # pylint: disable=global-statement
    now = time.monotonic()
    if now - _LAST_FAILURE_LOG >= 60:
        logger.warning("Auth rate limiter unavailable; allowing request")
        _LAST_FAILURE_LOG = now


async def _enforce_window(redis, key: str, limit: int, window_ttl: int) -> None:
    current, ttl = await redis.eval(
        AUTH_RATE_LIMIT_SCRIPT,
        1,
        key,
        window_ttl,
    )

    if int(current) > limit:
        retry_after = max(int(ttl), 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts",
            headers={"Retry-After": str(retry_after)},
        )


async def enforce_auth_rate_limit(request: Request, subject: str | None = None) -> None:
    """Apply global and per-account Redis-backed auth rate limits.

    Authentication remains available when Redis is unavailable because Redis is
    also a cache rather than the source of authentication truth. The failure is
    logged at most once per minute to avoid amplifying an outage.
    """
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        _log_fail_open_once()
        return

    window_seconds = _positive_int_from_env("AUTH_RATE_LIMIT_WINDOW_SECONDS", 60)
    client_ip = _client_ip(request)
    global_key, window_ttl = _rate_limit_window(f"global:{client_ip}", window_seconds)

    try:
        await _enforce_window(
            redis,
            global_key,
            _positive_int_from_env("AUTH_RATE_LIMIT_GLOBAL_REQUESTS", 300),
            window_ttl,
        )
        if subject:
            subject_key, _ = _rate_limit_window(
                f"subject:{client_ip}:{subject.casefold()}", window_seconds
            )
            await _enforce_window(
                redis,
                subject_key,
                _positive_int_from_env("AUTH_RATE_LIMIT_REQUESTS", 10),
                window_ttl,
            )
    except RedisError:
        _log_fail_open_once()
