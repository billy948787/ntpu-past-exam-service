import os
from datetime import datetime, timedelta
from typing import Annotated

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session

from sql.database import get_db
from users import dependencies as users_dependencies

load_dotenv()

router = APIRouter()


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


SECRET_KEY = os.getenv("HASH_KEY")
ALGORITHM = "HS256"


def create_access_token(data: dict, expires_delta: int | None = 1):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=expires_delta)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid credentials",
)


async def auth_middleware(request: Request):
    try:
        token = request.headers.get("authorization") or " "
        payload = jwt.decode(token.split(" ")[1], SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password):
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


@router.post("/login")
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db),
):
    user = users_dependencies.get_user_by_username(db, form_data.username)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    access_token = create_access_token(data={"sub": user.username})
    refresh_token = create_access_token(
        data={"sub": user.username, "type": "refresh"}, expires_delta=365
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh")
def refresh(request: Request):
    token = request.headers.get("authorization") or " "
    try:
        payload = jwt.decode(token.split(" ")[1], SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        access_token = create_access_token(data={"sub": username})
        refresh_token = create_access_token(
            data={"sub": username, "type": "refresh"}, expires_delta=365
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }
    except JWTError:
        raise credentials_exception


@router.post("/register")
def register(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db),
):
    if not form_data.username or not form_data.password:
        raise HTTPException(status_code=400, detail="Invalid input")

    user = users_dependencies.get_user_by_username(db, form_data.username)
    if user:
        raise HTTPException(status_code=400, detail="Same username already exist.")

    hashed_password = get_password_hash(form_data.password)

    users_dependencies.create_user(
        db, {"username": form_data.username, "hashed_password": hashed_password}
    )

    access_token = create_access_token(data={"sub": user.username})

    refresh_token = create_access_token(
        data={"sub": user.username, "type": "refresh"}, expires_delta=365
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }
