from typing import Dict

from sqlalchemy.orm import Session

from posts.models import Post

from . import models


def get_courses(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Course).offset(skip).limit(limit).all()


def get_course(db: Session, course_id: str):
    course_data = db.query(models.Course).filter(models.Course.id == course_id).first()

    posts = db.query(Post).filter(Post.course_id == course_id).all()

    result = {"course": course_data, "posts": []}

    for post in posts:
        result["posts"].append(post)

    return result


def make_course(db: Session, course: Dict):
    db_course = models.Course(**course)
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return db_course
