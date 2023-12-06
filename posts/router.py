from typing import Annotated

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from sql.database import get_db
from utils.token import get_access_token_payload

from . import dependencies

router = APIRouter(prefix="/posts")

load_dotenv()


@router.get("")
def read_all_post(
    status: str = "",
    user_id: str = "",
    course_id: str = "",
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    return dependencies.get_posts(
        db, status=status, user_id=user_id, course_id=course_id, skip=skip, limit=limit
    )


@router.get("/{post_id}")
def get_single_post(post_id: str, db: Session = Depends(get_db)):
    data = dependencies.get_post(db, post_id)
    if data is None:
        raise HTTPException(status_code=404)
    return data


@router.post("")
async def create_post(
    request: Request,
    title: Annotated[str, Form()],
    course_id: Annotated[str, Form()],
    file: Annotated[UploadFile, File()] = None,
    db: Session = Depends(get_db),
    content: Annotated[str, Form()] = "",
):
    payload = get_access_token_payload(request)
    user_id = payload.get("id")
    if file:
        file = await file.read()
    post = {
        "title": title,
        "content": content,
        "course_id": course_id,
    }
    post = dependencies.make_post(db, post, user_id, file)

    return {"status": "success", "post_id": post.id}


@router.put("/status/{post_id}")
def update_post_status(
    status: Annotated[str, Form()], post_id: str, db: Session = Depends(get_db)
):
    dependencies.update_post_status(db, post_id=post_id, status=status)
    return {"status": "success"}
