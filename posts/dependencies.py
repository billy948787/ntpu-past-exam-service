from typing import Dict

from sqlalchemy.orm import Session

from . import models


def get_posts(db: Session, skip: int = 0, limit: int = 100):
    return (
        db.query(models.Post, models.PostFile)
        .join(models.PostFile, models.PostFile.post_id == models.Post.id)
        .offset(skip)
        .limit(limit)
        .all()
    )


def make_post(db: Session, post: Dict, user_id: str):
    db_post = models.Post(
        title=post["title"],
        content=post["content"],
        owner_id=user_id,
        course_id="12345",
    )
    db.add(db_post)

    db.commit()
    db.refresh(db_post)
    return db_post
