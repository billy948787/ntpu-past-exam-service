from typing import Dict

from sqlalchemy.orm import Session

from posts.models import Post

from . import models


def get_courses(
    db: Session,
    visible_department_ids: list[str],
    skip: int = 0,
    limit: int = 100,
):
    if not visible_department_ids:
        return []

    normalized_skip = min(max(skip, 0), 10000)
    normalized_limit = max(1, min(limit, 100))
    return (
        db.query(models.Course)
        .filter(models.Course.department_id.in_(visible_department_ids))
        .offset(normalized_skip)
        .limit(normalized_limit)
        .all()
    )


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
