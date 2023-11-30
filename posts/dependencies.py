from typing import Dict

from sqlalchemy.orm import Session

from . import models


def get_posts(db: Session, skip: int = 0, limit: int = 100):
    query_result = (
        db.query(models.Post, models.PostFile)
        .join(models.PostFile, models.PostFile.post_id == models.Post.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    data = []
    print(query_result)
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


def make_post(db: Session, post: Dict, user_id: str):
    db_post = models.Post(
        **post,
        owner_id=user_id,
    )
    db.add(db_post)

    db.commit()
    db.refresh(db_post)
    return db_post


def make_post_file(db: Session, file: Dict):
    db_file = models.PostFile(**file)
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    return db_file
