from sqlalchemy import Boolean, Column, String, Text

from sql.database import Base, BaseColumn


class Post(Base, BaseColumn):
    __tablename__ = "posts"

    title = Column(String(256))
    content = Column(Text)
    owner_id = Column(String(256), index=True)
    course_id = Column(String(256), index=True)
    is_migrate = Column(Boolean, default=False)
    status = Column(String(256), index=True, default="PENDING")
    department_id = Column(String(256), index=True)


class PostFile(Base, BaseColumn):
    __tablename__ = "posts_files"

    url = Column(Text)
    post_id = Column(String(256), index=True)
