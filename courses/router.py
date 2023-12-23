from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi_cache.decorator import cache
from sqlalchemy.orm import Session

from auth.router import admin_middleware
from sql.database import get_db

from . import dependencies, schemas

router = APIRouter(prefix="/courses")


@router.get("", response_model=list[schemas.Course])
@cache(expire=60)
def read_courses(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    items = dependencies.get_courses(db, skip=skip, limit=limit)
    return items


@router.get("/{course_id}")
@cache(expire=30)
def get_single_post(course_id: str, db: Session = Depends(get_db)):
    data = dependencies.get_course(db, course_id)

    if data["course"] is None:
        raise HTTPException(status_code=404)

    formatted_data = {"course": data["course"].__dict__, "posts": []}
    for post in data["posts"]:
        try:
            post = post.__dict__
            if post["status"] == "APPROVED":
                del post["status"]
                formatted_data["posts"].append(post)
        except KeyError:
            pass
    return formatted_data


@router.post("", dependencies=[Depends(admin_middleware)])
async def create_course(
    name: Annotated[str, Form()],
    category: Annotated[str, Form()],
    department_id: Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    course = {"name": name, "category": category, "department_id": department_id}
    course = dependencies.make_course(db, course)

    return {"status": "success", "course_id": course.id}
