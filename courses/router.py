from typing import Annotated

from fastapi import APIRouter, Depends, Form
from sqlalchemy.orm import Session

from sql.database import get_db

from . import dependencies, schemas

router = APIRouter(prefix="/courses")


@router.get("/", response_model=list[schemas.Course])
def read_courses(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    items = dependencies.get_courses(db, skip=skip, limit=limit)
    return items


@router.post("/")
async def create_course(
    name: Annotated[str, Form()],
    category: Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    course = {"name": name, "category": category}
    course = dependencies.make_course(db, course)

    return {"status": "success", "course_id": course.id}
