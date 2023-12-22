import uuid

from sqlalchemy import Boolean, Column, String

from sql.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class Department(Base):
    __tablename__ = "departments"

    id = Column(String(256), primary_key=True, default=generate_uuid)
    key = Column(String(256))
    name = Column(String(256))
    is_public = Column(Boolean, default=True, index=True)
