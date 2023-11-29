import uuid

from sqlalchemy import Column, String, Text

from sql.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class Post(Base):
    __tablename__ = "posts"

    id = Column(String(256), primary_key=True, default=generate_uuid)
    title = Column(String(256), index=True)
    content = Column(Text)
    owner_id = Column(String(256))
    course_id = Column(String(256))


class PostFile(Base):
    __tablename__ = "posts_files"

    id = Column(String(256), primary_key=True, default=generate_uuid)
    url = Column(Text)
    post_id = Column(String(256), index=True)
