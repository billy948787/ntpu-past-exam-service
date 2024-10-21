from sqlalchemy.orm import Session

from departments.models import Department
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


def get_user_department_admin_ids(db: Session, user_id: str):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    is_admin_departments = []
    if user.is_super_user:
        for department in db.query(Department).all():
            is_admin_departments.append(department.id)

    else:
        for record in (
            db.query(models.UserDepartment)
            .filter(
                (models.UserDepartment.is_department_admin == True)
                & (models.UserDepartment.user_id == user_id)
            )
            .all()
        ):
            is_admin_departments.append(record.department_id)

    return is_admin_departments


def get_user_department_admin(db: Session, user_id: str):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user.is_super_user:
        return db.query(Department).all()
    sub_query = db.query(models.UserDepartment.department_id).filter(
        (models.UserDepartment.is_department_admin == True)
        & (models.UserDepartment.user_id == user_id)
        & (models.UserDepartment.department_id == Department.id)
    )

    items = db.query(Department).filter(sub_query.exists()).all()
    return items


def get_user(db: Session, user_id: str):
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()


def get_users(db: Session, is_active: bool, skip: int = 0, limit: int = 100):
    query_filter = []

    if is_active is not None:
        if is_active:
            query_filter.append(models.User.is_active == True)
        else:
            query_filter.append(
                (models.User.is_active == False) | (models.User.is_active == None)
            )

    return db.query(models.User).filter(*query_filter).offset(skip).limit(limit).all()


def create_user(db: Session, user: schemas.UserCreate):
    try:
        db_user = models.User(
            username=user["username"],
            hashed_password=user["hashed_password"],
            readable_name=user["readable_name"],
            school_department=user["school_department"],
            email=user["email"],
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except KeyError:
        db_user = models.User(
            username=user["username"],
            readable_name=user["readable_name"],
            school_department=user["school_department"],
            email=user["email"],
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user


def update_user(db: Session, user: schemas.UserCreate):
    db.query(models.User).filter(models.User.username == user["username"]).update(
        {
            "username": user.get('username'),
            "hashed_password": user.get('hashed_password'),
            "readable_name": user.get('readable_name'),
            "school_department": user.get('school_department'),
            "email": user.get('email'),
            "note": user.get('note'),
        }
    )
    db.commit()
