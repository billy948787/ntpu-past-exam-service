from sqlalchemy import Boolean, Column, Integer, String, Text

from sql.database import Base, BaseColumn


class Thread(Base, BaseColumn):
    __tablename__ = "threads"
    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}

    title = Column(String(256))
    content = Column(Text)
    image_url = Column(String(1024), nullable=True)
    owner_id = Column(String(256), index=True)
    course_id = Column(String(256), index=True)
    is_anonymous = Column(Boolean, default=False)
    like_count = Column(Integer, default=0)


class ThreadComment(Base, BaseColumn):
    __tablename__ = "thread_comments"
    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}

    thread_id = Column(String(256), index=True)
    parent_comment_id = Column(String(256), index=True, nullable=True)
    content = Column(Text)
    owner_id = Column(String(256), index=True)
    is_anonymous = Column(Boolean, default=False)
    like_count = Column(Integer, default=0)
