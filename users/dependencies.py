from sqlalchemy.orm import Session

from posts import models

from . import models, schemas


def update_user_status(db: Session, user_id: str, status: bool):
    (
        db.query(models.User)
        .filter(models.User.id == user_id)
        .update({"is_active": status})
    )
    db.commit()


def update_user_admin(db: Session, user_id: str, is_admin: bool):
    (
        db.query(models.User)
        .filter(models.User.id == user_id)
        .update({"is_admin": is_admin})
    )
    db.commit()


def get_user(db: Session, user_id: str):
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()


def get_users(db: Session, is_active: bool, skip: int = 0, limit: int = 100):
    query_filter = []

    if is_active is not None:
        query_filter.append(models.User.is_active == is_active)

    return db.query(models.User).filter(*query_filter).offset(skip).limit(limit).all()


def create_user(db: Session, user: schemas.UserCreate):
    db_user = models.User(
        username=user["username"],
        hashed_password=user["hashed_password"],
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user
