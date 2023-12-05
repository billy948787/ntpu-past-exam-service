from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session

from sql.database import get_db
from utils.token import get_access_token_payload

from . import dependencies

router = APIRouter(prefix="/users")


@router.get("")
def read_users(
    is_active: bool, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    users = dependencies.get_users(db, skip=skip, limit=limit, is_active=is_active)
    data = []
    for user in users:
        u = user.__dict__
        u["is_admin"] = bool(u["is_admin"])
        u["is_active"] = bool(u["is_active"])
        del u["hashed_password"]
        data.append(u)
    return data


@router.get("/{user_id}")
def read_user(request: Request, user_id: str, db: Session = Depends(get_db)):
    if user_id == "me":
        payload = get_access_token_payload(request)
        user_id: str = payload.get("id")
    db_user = dependencies.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    data = db_user.__dict__
    del data["hashed_password"]
    data["is_admin"] = bool(data["is_admin"])
    data["is_active"] = bool(data["is_active"])
    return data


@router.put("/status/{user_id}")
def update_user_active_status(
    is_active: Annotated[bool, Form()], user_id: str, db: Session = Depends(get_db)
):
    dependencies.update_user_status(db, user_id=user_id, status=is_active)
    return {"status": "success"}


@router.put("/admin/{user_id}")
def update_user_admin_status(
    is_admin: Annotated[bool, Form()], user_id: str, db: Session = Depends(get_db)
):
    dependencies.update_user_admin(db, user_id=user_id, is_admin=is_admin)

    return {"status": "success"}
