from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from sql.database import get_db
from utils.token import get_access_token_payload

from . import dependencies, schemas

router = APIRouter(prefix="/users")


@router.get("", response_model=list[schemas.User])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = dependencies.get_users(db, skip=skip, limit=limit)
    return users


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
    return data
