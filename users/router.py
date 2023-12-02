from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from sql.database import get_db

from . import dependencies, schemas

router = APIRouter(prefix="/users")


@router.get("", response_model=list[schemas.User])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = dependencies.get_users(db, skip=skip, limit=limit)
    return users


@router.get("/{user_id}")
def read_user(user_id: str, db: Session = Depends(get_db)):
    db_user = dependencies.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user
