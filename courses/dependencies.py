from typing import Dict

from sqlalchemy import func
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Session

from posts.models import Post

from . import models


def get_courses(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Course).offset(skip).limit(limit).all()


def get_course(db: Session, course_id: str):
    sq = (
        db.query(
            func.json_object(
                "name",
                models.Course.name,
                "id",
                models.Course.id,
                "category",
                models.Course.category,
            ).label("course"),
            func.json_arrayagg(
                func.json_object(
                    "title", Post.title, "id", Post.id, "status", Post.status
                )
            ).label("posts"),
        )
        .filter(models.Course.id == course_id)
        .filter(Post.course_id == course_id)
        .group_by(models.Course.id)
        .subquery()
    )

    result = db.query(
        func.json_object("course", sq.c.course, "posts", sq.c.posts, type_=JSON)
    ).scalar()

    return result


def make_course(db: Session, course: Dict):
    db_course = models.Course(**course)
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return db_course
