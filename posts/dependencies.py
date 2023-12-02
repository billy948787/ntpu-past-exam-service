import os
import uuid
from typing import Dict

from dotenv import load_dotenv
from sqlalchemy.orm import Session

from static_file.r2 import r2

from . import models

load_dotenv()


def get_posts(db: Session, course_id: str, skip: int = 0, limit: int = 100):
    query_filter = []

    if course_id:
        query_filter.append(models.Post.course_id == course_id)

    query_result = (
        db.query(models.Post, models.PostFile)
        .filter(*query_filter)
        .join(models.PostFile, models.PostFile.post_id == models.Post.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    data = []
    for post, file in query_result:
        data.append({**post.__dict__, "file": file.url})
    return data


def get_post(db: Session, post_id: str):
    query_result = (
        db.query(models.Post, models.PostFile)
        .filter(models.Post.id == post_id)
        .join(models.PostFile, models.PostFile.post_id == models.Post.id)
        .first()
    )
    if query_result is None:
        return None
    (post, file) = query_result
    data = {**post.__dict__, "file": file.url}

    return data


def make_post(db: Session, post: Dict, user_id: str, file: bytes):
    db_post = models.Post(
        **post,
        owner_id=user_id,
    )
    db.add(db_post)

    db.flush()

    key = f"{user_id}/{db_post.id}/{str(uuid.uuid4())}"
    r2.put_object(Body=file, Bucket=os.getenv("R2_BUCKET_NAME"), Key=key)
    file_path = f'{os.getenv("R2_FILE_PATH")}/{key}'
    file = {"url": file_path, "post_id": db_post.id}
    db_file = models.PostFile(**file)
    db.add(db_file)

    db.commit()
    db.refresh(db_post)
    return db_post
