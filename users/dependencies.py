from fastapi import HTTPException
from sqlalchemy.orm import Session

from departments.models import Department
from . import models, schemas


def get_user_department_admin_ids(db: Session, user_id: str):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    is_admin_departments = []
    if user.is_super_user:
        for department in db.query(Department).all():
            is_admin_departments.append(department.id)

    else:
        for record in (
            db.query(models.UserDepartment)
            .filter(
                (models.UserDepartment.is_department_admin.is_(True))
                & (models.UserDepartment.status == "APPROVED")
                & (models.UserDepartment.user_id == user_id)
            )
            .all()
        ):
            is_admin_departments.append(record.department_id)

    return is_admin_departments


def get_user_department_admin(db: Session, user_id: str):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.is_super_user:
        return db.query(Department).all()
    sub_query = db.query(models.UserDepartment.department_id).filter(
        (models.UserDepartment.is_department_admin.is_(True))
        & (models.UserDepartment.status == "APPROVED")
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


def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()


def can_view_user_details(db: Session, viewer_id: str, target_user_id: str) -> bool:
    """Allow self, superusers, or an admin sharing a department with target.

    Pending department memberships are intentionally included for the target so
    an administrator can review the note attached to a join request.
    """
    if viewer_id == target_user_id:
        return True

    viewer = get_user(db, viewer_id)
    if viewer is None:
        return False
    if viewer.is_super_user:
        return True

    admin_department_ids = [
        row[0]
        for row in (
            db.query(models.UserDepartment.department_id)
            .filter(
                (models.UserDepartment.user_id == viewer_id)
                & (models.UserDepartment.status == "APPROVED")
                & (models.UserDepartment.is_department_admin.is_(True))
            )
            .all()
        )
    ]
    if not admin_department_ids:
        return False

    return (
        db.query(models.UserDepartment)
        .filter(
            (models.UserDepartment.user_id == target_user_id)
            & (models.UserDepartment.department_id.in_(admin_department_ids))
        )
        .first()
        is not None
    )


def get_user_preference(db: Session, user_id: str):
    return (
        db.query(models.UserPreference)
        .filter(models.UserPreference.user_id == user_id)
        .first()
    )


def update_user_preference(
    db: Session, user_id: str, show_empty_courses: bool, default_is_anonymous: bool
):
    pref = (
        db.query(models.UserPreference)
        .filter(models.UserPreference.user_id == user_id)
        .first()
    )
    if pref:
        pref.show_empty_courses = show_empty_courses
        pref.default_is_anonymous = default_is_anonymous
    else:
        pref = models.UserPreference(
            user_id=user_id,
            show_empty_courses=show_empty_courses,
            default_is_anonymous=default_is_anonymous,
        )
        db.add(pref)
    db.commit()
    db.refresh(pref)
    return pref


def create_user(db: Session, user: schemas.UserCreate):
    user_kwargs = {
        "username": user["username"],
        "readable_name": user["readable_name"],
        # Local accounts created by a superuser do not have school profile data
        # until the owner fills it in.
        "school_department": user.get("school_department"),
        "email": user.get("email"),
    }
    if user.get("hashed_password"):
        user_kwargs["hashed_password"] = user["hashed_password"]
    db_user = models.User(**user_kwargs)
    db.add(db_user)
    db.flush()
    db_pref = models.UserPreference(
        user_id=db_user.id, show_empty_courses=True, default_is_anonymous=False
    )
    db.add(db_pref)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, user: schemas.UserCreate):
    update_data = {
        "username": user.get("username"),
        "readable_name": user.get("readable_name"),
        "school_department": user.get("school_department"),
        "email": user.get("email"),
        "note": user.get("note"),
    }
    if user.get("hashed_password"):
        update_data["hashed_password"] = user["hashed_password"]
    db.query(models.User).filter(models.User.username == user["username"]).update(
        update_data
    )
    db.commit()
