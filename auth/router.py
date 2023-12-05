from typing import Annotated, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import ExpiredSignatureError, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session

from sql.database import get_db
from users import dependencies as users_dependencies
from utils.token import create_access_token, get_access_token_payload

from . import dependencies

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


async def auth_middleware(request: Request):
    try:
        payload = get_access_token_payload(request)
        username: str = payload.get("sub")
        token_type: str = payload.get("type")
        if username is None or not token_type == "access":
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
        hashed_password = get_password_hash(form_data.password)
        readable_name = dependencies.get_lms_readable_name(
            username=form_data.username, password=form_data.password
        )
        user = users_dependencies.create_user(
            db,
            {
                "username": form_data.username,
                "hashed_password": hashed_password,
                "readable_name": readable_name,
            },
        )
    elif not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    access_token = create_access_token(
        data={
            "sub": user.username,
            "type": "access",
            "id": user.id,
            "is_admin": user.is_admin,
            "is_active": user.is_active,
        }
    )
    refresh_token = create_access_token(
        data={
            "sub": user.username,
            "type": "refresh",
            "id": user.id,
            "is_admin": user.is_admin,
            "is_active": user.is_active,
        },
        expires_delta=365,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.get("/verify-token")
def verify(request: Request):
    try:
        payload = get_access_token_payload(request)
        is_admin = payload.get("is_admin")
        is_active = payload.get("is_active")

        permission_data = {
            "is_admin": is_admin,
            "is_active": is_active,
        }

        return permission_data
    except ExpiredSignatureError:
        payload = get_access_token_payload(request)
        is_admin = payload.get("is_admin")
        is_active = payload.get("is_active")

        permission_data = {
            "is_admin": is_admin,
            "is_active": is_active,
        }
        return permission_data
    except JWTError:
        raise credentials_exception


@router.post("/refresh")
def refresh(request: Request):
    try:
        payload = get_access_token_payload(request)
        username: str = payload.get("sub")
        user_id: str = payload.get("id")
        is_admin = payload.get("is_admin")
        is_active = payload.get("is_active")
        access_token = create_access_token(
            data={
                "sub": username,
                "type": "access",
                "id": user_id,
                "is_admin": is_admin,
                "is_active": is_active,
            }
        )
        refresh_token = create_access_token(
            data={
                "sub": username,
                "type": "refresh",
                "id": user_id,
                "is_admin": is_admin,
                "is_active": is_active,
            },
            expires_delta=365,
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }
    except JWTError:
        raise credentials_exception


@router.post("/create_user")
def create_user(
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
        },
    )

    access_token = create_access_token(data={"sub": user.username, "id": user.id})

    refresh_token = create_access_token(
        data={"sub": user.username, "type": "refresh"},
        expires_delta=365,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }
