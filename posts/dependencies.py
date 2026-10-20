import logging
import os
import uuid
from typing import Dict, List

logger = logging.getLogger(__name__)

from dotenv import load_dotenv
from fastapi import HTTPException
from sqlalchemy.orm import Session

from courses.models import Course
from departments.dependencies import (
    get_department_admins,
    get_department_information,
    get_viewable_departments_ids,
    require_viewable_department,
)
from static_file.r2 import r2
from users.models import User, UserDepartment
from utils.send_mail import send_notification_mail

from . import models

load_dotenv()

domain = os.getenv("ORIGIN")

ALLOWED_POST_STATUSES = {"PENDING", "APPROVED", "REJECTED"}


def validate_post_target(db: Session, user_id: str, course_id: str, department_id: str):
    course = db.query(Course).filter(Course.id == course_id).first()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    if course.department_id != department_id:
        raise HTTPException(
            status_code=400,
            detail="Course does not belong to the selected department",
        )

    return require_viewable_department(db, user_id=user_id, department_id=department_id)


def _get_live_user(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def _get_admin_department_ids(db: Session, user_id: str) -> set[str]:
    return {
        department_id
        for (department_id,) in db.query(UserDepartment.department_id)
        .filter(
            UserDepartment.user_id == user_id,
            UserDepartment.status == "APPROVED",
            UserDepartment.is_department_admin,
        )
        .all()
    }


def _can_view_unapproved_post(
    post: models.Post,
    user: User,
    admin_department_ids: set[str],
) -> bool:
    return (
        user.is_super_user
        or post.owner_id == user.id
        or post.department_id in admin_department_ids
    )


def get_posts(
    db: Session,
    current_user_id: str,
    status: str,
    user_id: str,
    department_id: str,
    course_id: str,
    skip: int = 0,
    limit: int = 100,
):
    query_filter = []
    current_user = _get_live_user(db, current_user_id)
    visible_department_ids = get_viewable_departments_ids(db, current_user_id)

    if not visible_department_ids:
        return []

    query_filter.append(models.Post.department_id.in_(visible_department_ids))

    admin_department_ids = _get_admin_department_ids(db, current_user_id)
    if not current_user.is_super_user:
        unapproved_access = models.Post.owner_id == current_user_id
        if admin_department_ids:
            unapproved_access = unapproved_access | models.Post.department_id.in_(
                admin_department_ids
            )
        query_filter.append((models.Post.status == "APPROVED") | unapproved_access)

    if status == "PENDING":
        query_filter.append(
            (models.Post.status != "APPROVED") | (models.Post.status == None)
        )
    elif status == "APPROVED":
        query_filter.append(models.Post.status == "APPROVED")
    elif status == "REJECTED":
        query_filter.append(models.Post.status == "REJECTED")
    elif status:
        raise HTTPException(status_code=400, detail="Invalid post status")

    if course_id:
        query_filter.append(models.Post.course_id == course_id)

    if user_id:
        query_filter.append(models.Post.owner_id == user_id)

    if department_id:
        query_filter.append(models.Post.department_id == department_id)

    normalized_skip = min(max(skip, 0), 10000)
    normalized_limit = max(1, min(limit, 100))
    query_result = (
        db.query(models.Post, Course)
        .filter(*query_filter)
        .join(Course, models.Post.course_id == Course.id)
        .order_by(models.Post.create_time.desc())
        .offset(normalized_skip)
        .limit(normalized_limit)
        .all()
    )
    posts = []
    for post, course in query_result:
        data = {
            **post.__dict__,
            "course_name": course.name,
            "owner_id": "anonymous" if post.is_anonymous else post.owner_id,
        }
        posts.append(data)
    return posts


def get_post(db: Session, post_id: str, current_user_id: str):
    query_result = (
        db.query(models.Post, User)
        .filter(models.Post.id == post_id)
        .join(User, models.Post.owner_id == User.id)
        .first()
    )
    if query_result is None:
        return None

    (post, user) = query_result
    current_user = _get_live_user(db, current_user_id)
    visible_department_ids = get_viewable_departments_ids(db, current_user_id)
    if post.department_id not in visible_department_ids:
        raise HTTPException(status_code=404)

    if post.status != "APPROVED":
        admin_department_ids = _get_admin_department_ids(db, current_user_id)
        if not _can_view_unapproved_post(post, current_user, admin_department_ids):
            raise HTTPException(status_code=404)

    query_file_result = (
        db.query(models.PostFile).filter(models.PostFile.post_id == post_id).all()
    )
    data = {
        **post.__dict__,
        "files": [],
        "owner_name": (
            "匿名用戶"
            if post.is_anonymous
            else user.readable_name if user.readable_name else user.username
        ),
        "owner_id": "anonymous" if post.is_anonymous else post.owner_id,
    }

    for file in query_file_result:
        data["files"].append(file.__dict__["url"])

    return data


def make_post(db: Session, post: Dict, user_id: str, file_array: List[bytes]):
    department = validate_post_target(
        db,
        user_id=user_id,
        course_id=post["course_id"],
        department_id=post["department_id"],
    )
    db_post = models.Post(
        **post,
        status="APPROVED" if department.is_public else "PENDING",
        owner_id=user_id,
    )
    uploaded_keys = []
    committed = False
    try:
        db.add(db_post)
        db.flush()

        for file_data in file_array:
            key = f"{user_id}/{db_post.id}/{str(uuid.uuid4())}"
            # Record the key before upload so cleanup also handles providers
            # that persist an object but surface a late transport error.
            uploaded_keys.append(key)
            r2.put_object(
                Body=file_data,
                Bucket=os.getenv("R2_BUCKET_NAME"),
                Key=key,
            )
            file_path = f'{os.getenv("R2_FILE_PATH")}/{key}'
            db.add(models.PostFile(url=file_path, post_id=db_post.id))

        db.commit()
        committed = True
        db.refresh(db_post)
    except Exception:
        db.rollback()
        if not committed:
            for key in uploaded_keys:
                try:
                    r2.delete_object(Bucket=os.getenv("R2_BUCKET_NAME"), Key=key)
                except Exception:
                    logger.warning(
                        "Failed to clean up R2 object after post creation failure (key=%s)",
                        key,
                        exc_info=True,
                    )
        raise

    if not department.is_public:
        admins = get_department_admins(db=db, department_id=post["department_id"])
        recipients = []
        for admin in admins:
            recipients.append(
                admin.email
                if admin.email is not None
                else f"s{admin.username}@gm.ntpu.edu.tw"
            )
        if len(recipients) > 0:
            try:
                send_notification_mail(
                    title="考古題審核",
                    content=f"有人在您所管理的 {department.name} 社群發布考古題，請儘速審核。",
                    recipients=recipients,
                    cta={
                        "text": "前往審核",
                        "link": f"{domain}/admin/{department.id}?open_edit_post_dialog=true&edit_post_detail_id={db_post.id}",
                    },
                )
            except Exception:
                logger.warning(
                    "Failed to notify department admins for post %s",
                    db_post.id,
                    exc_info=True,
                )
    return db_post


def delete_post(db: Session, post_id: str):
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    files = db.query(models.PostFile).filter(models.PostFile.post_id == post_id).all()
    bucket = os.getenv("R2_BUCKET_NAME")
    file_path_prefix = os.getenv("R2_FILE_PATH")

    file_keys = []
    for file in files:
        url = file.__dict__["url"]
        key = url.replace(f"{file_path_prefix}/", "", 1)
        file_keys.append(key)
        db.delete(file)

    db.delete(post)
    db.commit()

    for key in file_keys:
        try:
            r2.delete_object(Bucket=bucket, Key=key)
        except Exception:
            logger.warning(
                "Failed to delete R2 object for post %s (key=%s)",
                post_id,
                key,
                exc_info=True,
            )


def update_post_status(db: Session, department_id: str, post_id: str, status: str):
    if status not in ALLOWED_POST_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid post status")

    post = (
        db.query(models.Post)
        .filter(
            models.Post.id == post_id,
            models.Post.department_id == department_id,
        )
        .first()
    )
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")

    post.status = status
    db.commit()

    user = db.query(User).filter(User.id == post.owner_id).first()
    department = get_department_information(db=db, department_id=post.department_id)

    if status == "APPROVED" and user is not None:
        try:
            send_notification_mail(
                title="考古題審核通過",
                content=f"您在『{department.name}』發布標題為『{post.title}』的考古題已通過管理員的審核。",
                recipients=[
                    (
                        user.email
                        if user.email is not None
                        else f"s{user.username}@gm.ntpu.edu.tw"
                    )
                ],
                cta={
                    "text": "查看考古題",
                    "link": f"{domain}/{department.id}/{post.course_id}/{post.id}",
                },
            )
        except Exception:
            logger.warning(
                "Failed to notify owner about approved post %s",
                post.id,
                exc_info=True,
            )

    return post
