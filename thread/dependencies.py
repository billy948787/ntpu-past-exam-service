import os
import uuid
from typing import Dict, List, Optional

from dotenv import load_dotenv
from sqlalchemy.orm import Session

from static_file.r2 import r2
from users.models import User

from . import models

load_dotenv()


def get_threads(db: Session, course_id: str, skip: int = 0, limit: int = 100):
    """取得課程的所有討論串"""
    query_result = (
        db.query(models.Thread, User)
        .filter(models.Thread.course_id == course_id)
        .join(User, models.Thread.owner_id == User.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    threads = []
    for thread, user in query_result:
        data = {
            **thread.__dict__,
            "owner_name": "匿名用戶" if thread.is_anonymous else (user.readable_name if user.readable_name else user.username),
            "owner_id": "anonymous" if thread.is_anonymous else thread.owner_id,
        }
        threads.append(data)
    return threads


def get_thread(db: Session, thread_id: str):
    """取得單個討論串詳情"""
    query_result = (
        db.query(models.Thread, User)
        .filter(models.Thread.id == thread_id)
        .join(User, models.Thread.owner_id == User.id)
        .first()
    )
    
    if query_result is None:
        return None
    
    thread, user = query_result
    data = {
        **thread.__dict__,
        "owner_name": "匿名用戶" if thread.is_anonymous else (user.readable_name if user.readable_name else user.username),
        "owner_id": "anonymous" if thread.is_anonymous else thread.owner_id,
    }
    return data


def create_thread(db: Session, thread_data: Dict, user_id: str, image_data: Optional[bytes] = None):
    """建立新討論串，可選上傳圖片"""
    # 上傳圖片到 R2
    image_url = None
    if image_data is not None:
        key = f"{user_id}/threads/{str(uuid.uuid4())}"
        r2.put_object(Body=image_data, Bucket=os.getenv("R2_BUCKET_NAME"), Key=key)
        image_url = f'{os.getenv("R2_FILE_PATH")}/{key}'
    
    db_thread = models.Thread(
        **thread_data,
        owner_id=user_id,
        image_url=image_url,
    )
    db.add(db_thread)
    db.commit()
    db.refresh(db_thread)
    return db_thread


def update_thread(db: Session, thread_id: str, update_data: Dict):
    """更新討論串"""
    db_thread = db.query(models.Thread).filter(models.Thread.id == thread_id).first()
    if db_thread is None:
        return None
    
    # 只允許更新特定欄位
    for key, value in update_data.items():
        if key in ["title", "content", "is_anonymous"]:
            setattr(db_thread, key, value)
    
    db.commit()
    db.refresh(db_thread)
    return db_thread


def delete_thread(db: Session, thread_id: str):
    """刪除討論串及其所有評論"""
    # 先刪除該討論串的所有評論
    db.query(models.ThreadComment).filter(
        models.ThreadComment.thread_id == thread_id
    ).delete()
    
    # 再刪除討論串
    db_thread = db.query(models.Thread).filter(models.Thread.id == thread_id).first()
    if db_thread is None:
        return False
    
    db.delete(db_thread)
    db.commit()
    return True


def get_comments(
    db: Session, thread_id: str, skip: int = 0, limit: int = 100
):
    """取得討論串的所有一級評論（不包括回覆）"""
    query_result = (
        db.query(models.ThreadComment, User)
        .filter(
            models.ThreadComment.thread_id == thread_id,
            models.ThreadComment.parent_comment_id == None,
        )
        .join(User, models.ThreadComment.owner_id == User.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    comments = []
    for comment, user in query_result:
        data = {
            **comment.__dict__,
            "owner_name": "匿名用戶" if comment.is_anonymous else (user.readable_name if user.readable_name else user.username),
            "owner_id": "anonymous" if comment.is_anonymous else comment.owner_id,
        }
        comments.append(data)
    return comments


def get_comment_with_replies(db: Session, comment_id: str):
    """取得單個評論及其所有回覆（遞迴構建樹狀結構）"""
    query_result = (
        db.query(models.ThreadComment, User)
        .filter(models.ThreadComment.id == comment_id)
        .join(User, models.ThreadComment.owner_id == User.id)
        .first()
    )
    
    if query_result is None:
        return None
    
    comment, user = query_result
    data = {
        **comment.__dict__,
        "owner_name": "匿名用戶" if comment.is_anonymous else (user.readable_name if user.readable_name else user.username),
        "owner_id": "anonymous" if comment.is_anonymous else comment.owner_id,
        "replies": [],
    }
    
    # 遞迴取得所有回覆
    _build_reply_tree(db, comment_id, data["replies"])
    
    return data


def _build_reply_tree(db: Session, parent_id: str, replies_list: List):
    """遞迴構建評論樹狀結構"""
    reply_results = (
        db.query(models.ThreadComment, User)
        .filter(models.ThreadComment.parent_comment_id == parent_id)
        .join(User, models.ThreadComment.owner_id == User.id)
        .all()
    )
    
    for reply, user in reply_results:
        data = {
            **reply.__dict__,
            "owner_name": "匿名用戶" if reply.is_anonymous else (user.readable_name if user.readable_name else user.username),
            "owner_id": "anonymous" if reply.is_anonymous else reply.owner_id,
            "replies": [],
        }
        replies_list.append(data)
        # 遞迴取得下一層回覆
        _build_reply_tree(db, reply.id, data["replies"])


def create_comment(
    db: Session, thread_id: str, comment_data: Dict, user_id: str, parent_comment_id: Optional[str] = None
):
    """建立新評論或回覆"""
    db_comment = models.ThreadComment(
        thread_id=thread_id,
        parent_comment_id=parent_comment_id,
        owner_id=user_id,
        **comment_data,
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return db_comment


def update_comment(db: Session, comment_id: str, update_data: Dict):
    """更新評論"""
    db_comment = (
        db.query(models.ThreadComment).filter(models.ThreadComment.id == comment_id).first()
    )
    if db_comment is None:
        return None
    
    # 只允許更新內容
    if "content" in update_data:
        db_comment.content = update_data["content"]
    
    db.commit()
    db.refresh(db_comment)
    return db_comment


def delete_comment(db: Session, comment_id: str):
    """刪除評論及其所有回覆"""
    # 先遞迴刪除所有回覆
    _delete_comment_tree(db, comment_id)
    db.commit()
    return True


def _delete_comment_tree(db: Session, comment_id: str):
    """遞迴刪除評論樹"""
    # 先取得所有子回覆
    child_comments = (
        db.query(models.ThreadComment)
        .filter(models.ThreadComment.parent_comment_id == comment_id)
        .all()
    )
    
    # 遞迴刪除子回覆
    for child in child_comments:
        _delete_comment_tree(db, child.id)
    
    # 刪除當前評論
    db_comment = (
        db.query(models.ThreadComment).filter(models.ThreadComment.id == comment_id).first()
    )
    if db_comment:
        db.delete(db_comment)


def like_thread(db: Session, thread_id: str):
    """按讚討論串"""
    db_thread = db.query(models.Thread).filter(models.Thread.id == thread_id).first()
    if db_thread is None:
        return None
    
    db_thread.like_count += 1
    db.commit()
    db.refresh(db_thread)
    return db_thread


def like_comment(db: Session, comment_id: str):
    """按讚評論"""
    db_comment = (
        db.query(models.ThreadComment).filter(models.ThreadComment.id == comment_id).first()
    )
    if db_comment is None:
        return None
    
    db_comment.like_count += 1
    db.commit()
    db.refresh(db_comment)
    return db_comment
