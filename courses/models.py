import uuid

from sqlalchemy import Column, String

from sql.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class Course(Base):
    __tablename__ = "courses"

    id = Column(String(256), primary_key=True, default=generate_uuid)
    name = Column(String(256), index=True)
    category = Column(String(256), index=True)
