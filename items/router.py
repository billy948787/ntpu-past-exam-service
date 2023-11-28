from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from sql.database import get_db

from . import dependencies, schemas

router = APIRouter(prefix="/items")


@router.get("/", response_model=list[schemas.Item])
def read_items(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    items = dependencies.get_items(db, skip=skip, limit=limit)
    return items
