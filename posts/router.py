from typing import Annotated

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from sql.database import get_db
from utils.token import get_access_token_payload

from . import dependencies

router = APIRouter(prefix="/posts")

load_dotenv()


@router.get("/")
def read_all_post(
    course_id: str = "", skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    return dependencies.get_posts(db, course_id, skip=skip, limit=limit)


@router.get("/{post_id}")
def get_single_post(post_id: str, db: Session = Depends(get_db)):
    data = dependencies.get_post(db, post_id)
    if data is None:
        raise HTTPException(status_code=404)
    return data


@router.post("/")
async def create_post(
    request: Request,
    title: Annotated[str, Form()],
    content: Annotated[str, Form()],
    course_id: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    db: Session = Depends(get_db),
):
    payload = get_access_token_payload(request)
    user_id = payload.get("id")
    file = await file.read()
    post = {
        "title": title,
        "content": content,
        "course_id": course_id,
    }
    post = dependencies.make_post(db, post, user_id, file)

    return {"status": "success", "post_id": post.id}
