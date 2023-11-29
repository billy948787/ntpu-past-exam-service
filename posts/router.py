import os
import uuid
from typing import Annotated

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from sql.database import get_db
from static_file.r2 import r2
from utils.token import get_access_token_payload

from . import dependencies, schemas

router = APIRouter(prefix="/posts")

load_dotenv()


@router.get("/", response_model=list[schemas.Post])
def read_all_post(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    items = dependencies.get_posts(db, skip=skip, limit=limit)
    return items


@router.post("/")
async def creat_post(
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
    post = dependencies.make_post(db, post, user_id)
    key = f"{post.id}/{user_id}/{str(uuid.uuid4())}"
    r2.put_object(Body=file, Bucket=os.getenv("R2_BUCKET_NAME"), Key=key)
    file_path = f'{os.getenv("R2_FILE_PATH")}/{key}'
    return file_path
