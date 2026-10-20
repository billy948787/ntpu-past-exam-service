import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Union

from dotenv import load_dotenv
from fastapi import HTTPException, Request
from jose import JWTError, jwt

load_dotenv()


SECRET_KEY = os.getenv("HASH_KEY")
if not SECRET_KEY:
    raise RuntimeError("HASH_KEY environment variable is not set or empty")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15


def get_token_payload(token: str, token_type: str):
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require_exp": True, "require_sub": True},
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if token_type is not None:
        payload_type = payload.get("type")
        if payload_type != token_type:
            raise HTTPException(status_code=401, detail="Invalid token type")
    return payload


def get_access_token_payload(request: Request, token_type: str = "access"):
    auth_header = request.headers.get("authorization") or ""
    parts = auth_header.split(" ")
    if len(parts) != 2 or parts[0] != "Bearer":
        raise HTTPException(
            status_code=401, detail="Invalid or missing authorization header"
        )
    return get_token_payload(parts[1], token_type)


def create_access_token(
    data: dict,
    expires_delta: Optional[Union[timedelta, int]] = None,
):
    """Create a short-lived access token.

    Integer ``expires_delta`` values remain interpreted as days for compatibility
    with older internal callers. New code should pass a ``timedelta`` explicitly.
    """
    to_encode = data.copy()
    if expires_delta is None:
        lifetime = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    elif isinstance(expires_delta, int):
        lifetime = timedelta(days=expires_delta)
    else:
        lifetime = expires_delta
    expire = datetime.now(timezone.utc) + lifetime

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
