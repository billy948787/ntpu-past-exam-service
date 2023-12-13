from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.orm import Session

from auth.router import admin_middleware
from sql.database import get_db

from . import dependencies

router = APIRouter(prefix="/bulletins")


@router.get("")
def read_courses(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    items = dependencies.get_bulletins(db, skip=skip, limit=limit)
    return items


@router.get("/{bulletin_id}")
def get_single_post(bulletin_id: str, db: Session = Depends(get_db)):
    data = dependencies.get_db_bulletin(db, bulletin_id)

    if data is None:
        raise HTTPException(status_code=404)

    return data.__dict__


@router.post("", dependencies=[Depends(admin_middleware)])
async def create_bulletin(
    title: Annotated[str, Form()],
    content: Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    bulletin = {"title": title, "content": content}
    bulletin = dependencies.make_db_bulletin(db, bulletin)

    return {"status": "success", "bulletin_id": bulletin.id}
