from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi_cache.decorator import cache
from sqlalchemy.orm import Session

from auth.router import admin_middleware
from sql.database import get_db
from utils.token import get_access_token_payload

from . import dependencies

router = APIRouter(prefix="/users")


@router.get("")
def read_users(
    is_active: bool = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    users = dependencies.get_users(db, skip=skip, limit=limit, is_active=is_active)
    data = []
    for user in users:
        u = user.__dict__
        del u["hashed_password"]
        data.append(u)
    return data


@router.get("/{user_id}")
@cache(expire=30)
def read_user(request: Request, user_id: str, db: Session = Depends(get_db)):
    if user_id == "me":
        payload = get_access_token_payload(request)
        user_id: str = payload.get("id")
    db_user = dependencies.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    data = db_user.__dict__
    del data["hashed_password"]
    return data


@router.get("/me/departments-admin")
@cache(expire=30)
def read_user_admin_scopes(request: Request, db: Session = Depends(get_db)):
    payload = get_access_token_payload(request)
    user_id: str = payload.get("id")
    scopes = dependencies.get_user_department_admin(db, user_id=user_id)

    return scopes


@router.put("/status/{user_id}", dependencies=[Depends(admin_middleware)])
def update_user_active_status(
    is_active: Annotated[bool, Form()], user_id: str, db: Session = Depends(get_db)
):
    dependencies.update_user_status(db, user_id=user_id, status=is_active)
    return {"status": "success"}


@router.put("/admin/{user_id}", dependencies=[Depends(admin_middleware)])
def update_user_admin_status(
    is_admin: Annotated[bool, Form()], user_id: str, db: Session = Depends(get_db)
):
    dependencies.update_user_admin(db, user_id=user_id, is_admin=is_admin)

    return {"status": "success"}
