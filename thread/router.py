from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from sql.database import get_db
from utils.token import get_access_token_payload

from . import dependencies, schemas

router = APIRouter(prefix="/threads")


# ============ 討論串操作 ============

@router.post("/{course_id}")
async def create_thread(
    course_id: str,
    title: Annotated[str, Form()],
    content: Annotated[str, Form()],
    is_anonymous: Annotated[bool, Form()] = False,
    image: Annotated[Optional[UploadFile], File()] = None,
    request: Request = None,
    db: Session = Depends(get_db),
):
    """建立新討論串，可選上傳單個圖片"""
    payload = get_access_token_payload(request)
    user_id = payload.get("id")
    
    image_data = None
    if image is not None:
        image_data = await image.read()
    
    thread_data = {
        "title": title,
        "content": content,
        "course_id": course_id,
        "is_anonymous": is_anonymous,
    }
    thread = dependencies.create_thread(db, thread_data, user_id, image_data)
    return {"status": "success", "thread_id": thread.id}


@router.get("/{course_id}")
def get_threads(
    course_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """取得課程的所有討論串"""
    threads = dependencies.get_threads(db, course_id, skip, limit)
    return threads


@router.get("/detail/{thread_id}")
def get_thread_detail(
    thread_id: str,
    db: Session = Depends(get_db),
):
    """取得單個討論串詳情"""
    thread = dependencies.get_thread(db, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="討論串不存在")
    return thread


@router.put("/{thread_id}")
def update_thread(
    thread_id: str,
    title: Annotated[Optional[str], Form()] = None,
    content: Annotated[Optional[str], Form()] = None,
    is_anonymous: Annotated[Optional[bool], Form()] = None,
    request: Request = None,
    db: Session = Depends(get_db),
):
    """更新討論串（僅擁有者或管理員可編輯）"""
    payload = get_access_token_payload(request)
    user_id = payload.get("id")
    
    # 驗證權限
    thread = db.query(dependencies.models.Thread).filter(
        dependencies.models.Thread.id == thread_id
    ).first()
    if thread is None:
        raise HTTPException(status_code=404, detail="討論串不存在")
    if thread.owner_id != user_id:
        raise HTTPException(status_code=403, detail="無權編輸此討論串")
    
    update_data = {}
    if title is not None:
        update_data["title"] = title
    if content is not None:
        update_data["content"] = content
    if is_anonymous is not None:
        update_data["is_anonymous"] = is_anonymous
    
    thread = dependencies.update_thread(db, thread_id, update_data)
    return {"status": "success", "thread_id": thread.id}


@router.delete("/{thread_id}")
def delete_thread(
    thread_id: str,
    request: Request = None,
    db: Session = Depends(get_db),
):
    """刪除討論串（僅擁有者或管理員可刪除）"""
    payload = get_access_token_payload(request)
    user_id = payload.get("id")
    
    # 驗證權限
    thread = db.query(dependencies.models.Thread).filter(
        dependencies.models.Thread.id == thread_id
    ).first()
    if thread is None:
        raise HTTPException(status_code=404, detail="討論串不存在")
    if thread.owner_id != user_id:
        raise HTTPException(status_code=403, detail="無權刪除此討論串")
    
    success = dependencies.delete_thread(db, thread_id)
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="討論串不存在")


@router.post("/{thread_id}/like")
def like_thread(
    thread_id: str,
    db: Session = Depends(get_db),
):
    """按讚討論串"""
    thread = dependencies.like_thread(db, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="討論串不存在")
    return {"status": "success", "like_count": thread.like_count}


# ============ 評論操作 ============

@router.post("/{thread_id}/comments")
def create_comment(
    thread_id: str,
    content: Annotated[str, Form()],
    is_anonymous: Annotated[bool, Form()] = False,
    parent_comment_id: Annotated[Optional[str], Form()] = None,
    request: Request = None,
    db: Session = Depends(get_db),
):
    """建立新評論或回覆"""
    payload = get_access_token_payload(request)
    user_id = payload.get("id")
    
    # 驗證討論串存在
    thread = db.query(dependencies.models.Thread).filter(
        dependencies.models.Thread.id == thread_id
    ).first()
    if thread is None:
        raise HTTPException(status_code=404, detail="討論串不存在")
    
    # 若有父評論，驗證父評論存在且屬於同一討論串
    if parent_comment_id:
        parent_comment = db.query(dependencies.models.ThreadComment).filter(
            dependencies.models.ThreadComment.id == parent_comment_id
        ).first()
        if parent_comment is None:
            raise HTTPException(status_code=404, detail="父評論不存在")
        if parent_comment.thread_id != thread_id:
            raise HTTPException(status_code=400, detail="父評論不屬於此討論串")
    
    comment_data = {
        "content": content,
        "is_anonymous": is_anonymous,
    }
    comment = dependencies.create_comment(db, thread_id, comment_data, user_id, parent_comment_id)
    return {"status": "success", "comment_id": comment.id}


@router.get("/{thread_id}/comments")
def get_comments(
    thread_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """取得討論串的所有一級評論"""
    comments = dependencies.get_comments(db, thread_id, skip, limit)
    return comments


@router.get("/comments/{comment_id}")
def get_comment_detail(
    comment_id: str,
    db: Session = Depends(get_db),
):
    """取得單個評論及其所有回覆"""
    comment = dependencies.get_comment_with_replies(db, comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="評論不存在")
    return comment


@router.put("/comments/{comment_id}")
def update_comment(
    comment_id: str,
    content: Annotated[Optional[str], Form()] = None,
    request: Request = None,
    db: Session = Depends(get_db),
):
    """更新評論"""
    payload = get_access_token_payload(request)
    user_id = payload.get("id")
    
    # 驗證權限
    comment = db.query(dependencies.models.ThreadComment).filter(
        dependencies.models.ThreadComment.id == comment_id
    ).first()
    if comment is None:
        raise HTTPException(status_code=404, detail="評論不存在")
    if comment.owner_id != user_id:
        raise HTTPException(status_code=403, detail="無權編輯此評論")
    
    if content is None:
        raise HTTPException(status_code=400, detail="缺少更新內容")
    
    update_data = {"content": content}
    comment = dependencies.update_comment(db, comment_id, update_data)
    return {"status": "success", "comment_id": comment.id}


@router.delete("/comments/{comment_id}")
def delete_comment(
    comment_id: str,
    request: Request = None,
    db: Session = Depends(get_db),
):
    """刪除評論及其所有回覆"""
    payload = get_access_token_payload(request)
    user_id = payload.get("id")
    
    # 驗證權限
    comment = db.query(dependencies.models.ThreadComment).filter(
        dependencies.models.ThreadComment.id == comment_id
    ).first()
    if comment is None:
        raise HTTPException(status_code=404, detail="評論不存在")
    if comment.owner_id != user_id:
        raise HTTPException(status_code=403, detail="無權刪除此評論")
    
    success = dependencies.delete_comment(db, comment_id)
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="評論不存在")


@router.post("/comments/{comment_id}/like")
def like_comment(
    comment_id: str,
    db: Session = Depends(get_db),
):
    """按讚評論"""
    comment = dependencies.like_comment(db, comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="評論不存在")
    return {"status": "success", "like_count": comment.like_count}
