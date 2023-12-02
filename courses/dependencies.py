from typing import Dict

from sqlalchemy.orm import Session

from . import models


def get_courses(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Course).offset(skip).limit(limit).all()


def make_course(db: Session, course: Dict):
    db_course = models.Course(**course)
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return db_course
