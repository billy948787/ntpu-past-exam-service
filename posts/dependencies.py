import os
import uuid
from typing import Dict

from dotenv import load_dotenv
from sqlalchemy.orm import Session

from courses.models import Course
from static_file.r2 import r2
from users.models import User

from . import models

load_dotenv()


def get_posts(
    db: Session,
    status: str,
    user_id: str,
    course_id: str,
    skip: int = 0,
    limit: int = 100,
):
    query_filter = []

    if status == "PENDING":
        query_filter.append(
            (models.Post.status != "APPROVED")
            # pylint: disable-next=singleton-comparison
            | (models.Post.status == None)
        )
    elif status == "APPROVED":
        query_filter.append(models.Post.status == "APPROVED")

    if course_id:
        query_filter.append(models.Post.course_id == course_id)

    if user_id:
        query_filter.append(models.Post.owner_id == user_id)

    query_result = (
        db.query(models.Post, models.PostFile, Course)
        .filter(*query_filter)
        .join(models.PostFile, models.PostFile.post_id == models.Post.id, isouter=True)
        .join(Course, models.Post.course_id == Course.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    data = []
    for post, file, course in query_result:
        data.append(
            {
                **post.__dict__,
                "file": file.url if file else "",
                "course_name": course.name,
            }
        )
    return data


def get_post(db: Session, post_id: str):
    query_result = (
        db.query(models.Post, models.PostFile, User)
        .filter(models.Post.id == post_id)
        .join(models.PostFile, models.PostFile.post_id == models.Post.id, isouter=True)
        .join(User, models.Post.owner_id == User.id)
        .first()
    )
    if query_result is None:
        return None
    (post, file, user) = query_result
    data = {
        **post.__dict__,
        "file": file.url if file else "",
        "owner_name": user.readable_name if user.readable_name else user.username,
    }

    return data


def make_post(db: Session, post: Dict, user_id: str, file: bytes):
    db_post = models.Post(
        **post,
        owner_id=user_id,
    )
    db.add(db_post)

    db.flush()

    if file:
        key = f"{user_id}/{db_post.id}/{str(uuid.uuid4())}"
        r2.put_object(Body=file, Bucket=os.getenv("R2_BUCKET_NAME"), Key=key)
        file_path = f'{os.getenv("R2_FILE_PATH")}/{key}'
        file = {"url": file_path, "post_id": db_post.id}
        db_file = models.PostFile(**file)
        db.add(db_file)

    db.commit()
    db.refresh(db_post)
    return db_post


def update_post_status(db: Session, post_id: str, status: str):
    (db.query(models.Post).filter(models.Post.id == post_id).update({"status": status}))
    db.commit()
