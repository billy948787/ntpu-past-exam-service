import os
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from fastapi import Request
from jose import jwt

load_dotenv()


SECRET_KEY = os.getenv("HASH_KEY")
ALGORITHM = "HS256"


def get_access_token_payload(request: Request):
    token = request.headers.get("authorization") or " "
    payload = jwt.decode(token.split(" ")[1], SECRET_KEY, algorithms=[ALGORITHM])
    return payload


def create_access_token(data: dict, expires_delta: Optional[int] = 1):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=expires_delta)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
