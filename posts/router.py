from typing import Annotated, List

from dotenv import load_dotenv
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi_cache.decorator import cache
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from auth.router import admin_middleware
from sql.database import get_db
from users.models import User, UserDepartment
from utils.cache import clear_namespace
from utils.token import get_access_token_payload

from . import dependencies, models

router = APIRouter(prefix="/posts")

load_dotenv()

MAX_POST_FILES = 10
MAX_POST_FILE_SIZE_BYTES = 20 * 1024 * 1024
MAX_POST_TOTAL_SIZE_BYTES = 50 * 1024 * 1024
ALLOWED_POST_FILE_TYPES = {"application/pdf", "application/x-pdf"}


async def _read_pdf_uploads(files: List[UploadFile] | None) -> List[bytes]:
    if not files:
        return []
    if len(files) > MAX_POST_FILES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Too many files; maximum is {MAX_POST_FILES}",
        )

    file_array = []
    total_size = 0
    try:
        for upload in files:
            if upload.content_type not in ALLOWED_POST_FILE_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only PDF files are allowed",
                )

            remaining_total = MAX_POST_TOTAL_SIZE_BYTES - total_size
            read_limit = min(MAX_POST_FILE_SIZE_BYTES, remaining_total) + 1
            data = await upload.read(read_limit)

            if len(data) > MAX_POST_FILE_SIZE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="A PDF exceeds the per-file size limit",
                )
            if len(data) > remaining_total:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="PDF uploads exceed the total size limit",
                )
            if not data.startswith(b"%PDF-"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid PDF content",
                )

            file_array.append(data)
            total_size += len(data)
    finally:
        for upload in files:
            await upload.close()

    return file_array


@router.get("")
def read_all_post(
    request: Request,
    status: str = "",
    user_id: str = "",
    course_id: str = "",
    department_id: str = "",
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    payload = get_access_token_payload(request)
    return dependencies.get_posts(
        db,
        current_user_id=payload.get("id"),
        status=status,
        user_id=user_id,
        course_id=course_id,
        department_id=department_id,
        skip=skip,
        limit=limit,
    )


@router.get("/{post_id}")
@cache(expire=60, namespace="posts")
def get_single_post(request: Request, post_id: str, db: Session = Depends(get_db)):
    payload = get_access_token_payload(request)
    data = dependencies.get_post(db, post_id, payload.get("id"))
    if data is None:
        raise HTTPException(status_code=404)
    return data


@router.post("")
async def create_post(
    request: Request,
    title: Annotated[str, Form(min_length=1, max_length=256)],
    course_id: Annotated[str, Form(min_length=1, max_length=256)],
    department_id: Annotated[str, Form(max_length=256)] = "",
    files: List[Annotated[UploadFile, File()]] = None,
    db: Session = Depends(get_db),
    content: Annotated[str, Form(max_length=10000)] = "",
    is_migrate: Annotated[bool, Form()] = False,
    is_anonymous: Annotated[bool, Form()] = False,
):
    payload = get_access_token_payload(request)
    user_id = payload.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token: missing user id")

    dependencies.validate_post_target(db, user_id, course_id, department_id)
    file_array = await _read_pdf_uploads(files)
    post = {
        "title": title,
        "content": content,
        "course_id": course_id,
        "is_migrate": is_migrate,
        "is_anonymous": is_anonymous,
        "department_id": department_id,
    }
    post = await run_in_threadpool(
        dependencies.make_post, db, post, user_id, file_array
    )
    await clear_namespace("course-detail")
    await clear_namespace("posts")
    await clear_namespace("dept-courses")
    return {"status": "success", "post_id": post.id}


@router.put(
    "/status/{department_id}/{post_id}", dependencies=[Depends(admin_middleware)]
)
async def update_post_status(
    request: Request,
    status: Annotated[str, Form()],
    department_id: str,
    post_id: str,
    db: Session = Depends(get_db),
):
    await run_in_threadpool(
        dependencies.update_post_status,
        db,
        department_id=department_id,
        post_id=post_id,
        status=status,
    )
    await clear_namespace("posts")
    await clear_namespace("course-detail")
    await clear_namespace("dept-courses")
    payload = get_access_token_payload(request)
    updated_post = await run_in_threadpool(
        dependencies.get_post, db, post_id, payload.get("id")
    )
    return updated_post


@router.delete("/{post_id}")
async def delete_post(
    request: Request,
    post_id: str,
    db: Session = Depends(get_db),
):
    payload = get_access_token_payload(request)
    user_id = payload.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token: missing user id")

    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    if not user.is_super_user:
        is_department_admin = (
            db.query(UserDepartment)
            .filter(
                UserDepartment.user_id == user.id,
                UserDepartment.department_id == post.department_id,
                UserDepartment.status == "APPROVED",
                UserDepartment.is_department_admin,
            )
            .first()
            is not None
        )
        if not is_department_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    await run_in_threadpool(dependencies.delete_post, db, post_id)
    await clear_namespace("posts")
    await clear_namespace("course-detail")
    await clear_namespace("dept-courses")
    return {"status": "success"}
